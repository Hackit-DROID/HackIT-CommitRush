import logging
import time
import uuid
import redis
from django.conf import settings
from core.models import EventConfig

logger = logging.getLogger(__name__)

# Lua script to atomically clean expired locks and acquire a semaphore slot
LUA_ACQUIRE_SCRIPT = """
local key = KEYS[1]
local client_id = ARGV[1]
local now = tonumber(ARGV[2])
local ttl = tonumber(ARGV[3])
local max_concurrency = tonumber(ARGV[4])

-- 1. Remove expired entries
local cutoff = now - ttl
redis.call('ZREMRANGEBYSCORE', key, '-inf', cutoff)

-- 2. Check if client_id already holds a slot
local rank = redis.call('ZRANK', key, client_id)
if rank ~= nil then
    redis.call('ZADD', key, now, client_id)
    redis.call('EXPIRE', key, ttl * 2)
    return 1
end

-- 3. Check capacity against max_concurrency
local current_count = redis.call('ZCARD', key)
if current_count < max_concurrency then
    redis.call('ZADD', key, now, client_id)
    redis.call('EXPIRE', key, ttl * 2)
    return 1
else
    return 0
end
"""

# Lua script to release a specific client's semaphore slot
LUA_RELEASE_SCRIPT = """
local key = KEYS[1]
local client_id = ARGV[1]
return redis.call('ZREM', key, client_id)
"""

# Lua script to extend a specific client's semaphore TTL
LUA_EXTEND_SCRIPT = """
local key = KEYS[1]
local client_id = ARGV[1]
local now = tonumber(ARGV[2])
local ttl = tonumber(ARGV[3])

local rank = redis.call('ZRANK', key, client_id)
if rank ~= nil then
    redis.call('ZADD', key, now, client_id)
    redis.call('EXPIRE', key, ttl * 2)
    return 1
else
    return 0
end
"""

# Lua script to get active slot count after pruning stale entries
LUA_USAGE_SCRIPT = """
local key = KEYS[1]
local now = tonumber(ARGV[1])
local ttl = tonumber(ARGV[2])

local cutoff = now - ttl
redis.call('ZREMRANGEBYSCORE', key, '-inf', cutoff)
return redis.call('ZCARD', key)
"""


class RedisMergeSemaphore:
    """
    Distributed Redis semaphore for merge queue worker concurrency enforcement (PRD §10.1, §12.3, Plan M6-T1).
    Enforces bounded concurrency across all worker processes using atomic Redis Lua scripts with ZSET and epoch scoring.
    Automatically purges expired/crashed worker slots via TTL window.
    """

    def __init__(
        self,
        key: str | None = None,
        ttl: int | None = None,
        max_concurrency: int | None = None,
        client_id: str | None = None,
        redis_client: redis.Redis | None = None,
    ):
        self.key = key or getattr(settings, 'MERGE_SEMAPHORE_KEY', 'commitrush:semaphore:merge')
        self.ttl = ttl or getattr(settings, 'MERGE_SEMAPHORE_TTL', 120)
        self.max_concurrency = max_concurrency
        self.client_id = client_id or str(uuid.uuid4())
        self._redis = redis_client
        self._acquired = False

    def get_redis_client(self) -> redis.Redis:
        if self._redis is not None:
            return self._redis
        redis_url = getattr(settings, 'REDIS_URL', getattr(settings, 'CELERY_BROKER_URL', 'redis://localhost:6379/0'))
        self._redis = redis.Redis.from_url(redis_url, decode_responses=True)
        return self._redis

    def get_max_concurrency(self) -> int:
        if self.max_concurrency is not None:
            return max(1, self.max_concurrency)
        try:
            config = EventConfig.get_solo()
            return max(1, config.merge_concurrency)
        except Exception as e:
            logger.warning("Failed to fetch EventConfig merge_concurrency (%s); defaulting to 5", e)
            return 5

    def acquire(self, client_id: str | None = None, max_concurrency: int | None = None) -> bool:
        """
        Attempt to acquire a merge semaphore slot.
        Returns True if acquired, False if at capacity or on Redis connection error.
        """
        cid = client_id or self.client_id
        limit = max_concurrency if max_concurrency is not None else self.get_max_concurrency()
        now = time.time()

        try:
            r = self.get_redis_client()
            result = r.eval(LUA_ACQUIRE_SCRIPT, 1, self.key, cid, now, self.ttl, limit)
            acquired = bool(result == 1 or result == b'1')
            if acquired:
                self._acquired = True
                self.client_id = cid
                logger.debug("Acquired merge semaphore slot for client %s (key=%s, limit=%s)", cid, self.key, limit)
            else:
                logger.debug("Merge semaphore at capacity (%s slots occupied) for client %s", limit, cid)
            return acquired
        except (redis.exceptions.ConnectionError, redis.exceptions.TimeoutError, redis.exceptions.RedisError) as e:
            logger.warning("Redis error acquiring merge semaphore: %s", str(e))
            return False
        except Exception as e:
            logger.exception("Unexpected error acquiring merge semaphore: %s", str(e))
            return False

    def release(self, client_id: str | None = None) -> bool:
        """
        Release the acquired semaphore slot.
        Returns True if released, False otherwise.
        """
        cid = client_id or self.client_id
        try:
            r = self.get_redis_client()
            result = r.eval(LUA_RELEASE_SCRIPT, 1, self.key, cid)
            released = bool(result == 1 or result == b'1')
            self._acquired = False
            logger.debug("Released merge semaphore slot for client %s (result=%s)", cid, released)
            return released
        except (redis.exceptions.ConnectionError, redis.exceptions.TimeoutError, redis.exceptions.RedisError) as e:
            logger.warning("Redis error releasing merge semaphore: %s", str(e))
            self._acquired = False
            return False
        except Exception as e:
            logger.exception("Unexpected error releasing merge semaphore: %s", str(e))
            self._acquired = False
            return False

    def extend(self, client_id: str | None = None, ttl: int | None = None) -> bool:
        """
        Extend the TTL for an active semaphore slot (heartbeat).
        """
        cid = client_id or self.client_id
        t = ttl or self.ttl
        now = time.time()
        try:
            r = self.get_redis_client()
            result = r.eval(LUA_EXTEND_SCRIPT, 1, self.key, cid, now, t)
            return bool(result == 1 or result == b'1')
        except Exception as e:
            logger.warning("Redis error extending merge semaphore TTL: %s", str(e))
            return False

    def get_current_usage(self) -> int:
        """
        Return the number of currently active (non-expired) semaphore slots.
        """
        now = time.time()
        try:
            r = self.get_redis_client()
            result = r.eval(LUA_USAGE_SCRIPT, 1, self.key, now, self.ttl)
            return int(result)
        except Exception as e:
            logger.warning("Redis error querying merge semaphore usage: %s", str(e))
            return 0

    def is_acquired(self) -> bool:
        return self._acquired

    def __enter__(self):
        self.acquire()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._acquired:
            self.release()


LUA_RELEASE_LOCK_SCRIPT = """
local key = KEYS[1]
local token = ARGV[1]
if redis.call('GET', key) == token then
    return redis.call('DEL', key)
else
    return 0
end
"""


class RedisContributionLock:
    """
    Exclusive per-contribution distributed lock (PRD §12.4, Plan M6-T4).
    Prevents duplicate Celery tasks from concurrently calling GitHub merge API for the same contribution.
    """

    def __init__(
        self,
        contribution_id: int,
        ttl: int = 60,
        redis_client: redis.Redis | None = None,
    ):
        self.contribution_id = contribution_id
        self.key = f"commitrush:lock:contribution:{contribution_id}"
        self.ttl = ttl
        self.token = str(uuid.uuid4())
        self._redis = redis_client
        self._acquired = False

    def get_redis_client(self) -> redis.Redis:
        if self._redis is not None:
            return self._redis
        redis_url = getattr(settings, 'REDIS_URL', getattr(settings, 'CELERY_BROKER_URL', 'redis://localhost:6379/0'))
        self._redis = redis.Redis.from_url(redis_url, decode_responses=True)
        return self._redis

    def acquire(self) -> bool:
        """
        Attempt to acquire exclusive per-contribution lock using SET NX EX.
        Returns True if acquired, False if already held by another worker.
        """
        try:
            r = self.get_redis_client()
            acquired = bool(r.set(self.key, self.token, nx=True, ex=self.ttl))
            self._acquired = acquired
            if acquired:
                logger.debug("Acquired exclusive lock for contribution %s (key=%s, token=%s)", self.contribution_id, self.key, self.token)
            else:
                logger.info("Contribution %s is already locked by another task execution", self.contribution_id)
            return acquired
        except (redis.exceptions.ConnectionError, redis.exceptions.TimeoutError, redis.exceptions.RedisError) as e:
            logger.warning("Redis error acquiring lock for contribution %s (%s); proceeding with DB-level lock fallback", self.contribution_id, str(e))
            self._acquired = True
            return True
        except Exception as e:
            logger.exception("Unexpected error acquiring contribution lock for %s: %s", self.contribution_id, str(e))
            return False

    def release(self) -> bool:
        """
        Atomically release lock only if the token matches.
        """
        if not self._acquired:
            return False
        try:
            r = self.get_redis_client()
            result = r.eval(LUA_RELEASE_LOCK_SCRIPT, 1, self.key, self.token)
            released = bool(result == 1 or result == b'1')
            self._acquired = False
            logger.debug("Released lock for contribution %s (result=%s)", self.contribution_id, released)
            return released
        except Exception as e:
            logger.warning("Redis error releasing lock for contribution %s: %s", self.contribution_id, str(e))
            self._acquired = False
            return False

    def is_acquired(self) -> bool:
        return self._acquired

    def __enter__(self):
        self.acquire()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._acquired:
            self.release()
