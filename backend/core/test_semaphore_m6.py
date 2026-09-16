import time
import unittest
from unittest.mock import MagicMock, patch
from django.test import TestCase, override_settings

from core.models import EventConfig
from core.semaphore import (
    RedisMergeSemaphore,
    LUA_ACQUIRE_SCRIPT,
    LUA_RELEASE_SCRIPT,
    LUA_EXTEND_SCRIPT,
    LUA_USAGE_SCRIPT,
)


class MockRedisClient:
    """
    In-memory simulation of Redis eval and key-value commands for testing Lua semaphore and lock logic.
    """
    def __init__(self):
        # zsets: key -> dict(member: score)
        self.zsets = {}
        self.strings = {}
        self.expiries = {}

    def set(self, key, value, nx=False, ex=None):
        if nx and key in self.strings:
            return None
        self.strings[key] = value
        return True

    def get(self, key):
        return self.strings.get(key)

    def delete(self, key):
        if key in self.strings:
            del self.strings[key]
            return 1
        return 0

    def eval(self, script, numkeys, key, *args):
        if script == LUA_ACQUIRE_SCRIPT:
            client_id = args[0]
            now = float(args[1])
            ttl = float(args[2])
            max_concurrency = int(args[3])

            zset = self.zsets.setdefault(key, {})
            # 1. Prune expired
            cutoff = now - ttl
            to_del = [m for m, score in zset.items() if score <= cutoff]
            for m in to_del:
                del zset[m]

            # 2. Check if client_id already in set
            if client_id in zset:
                zset[client_id] = now
                return 1

            # 3. Check capacity
            if len(zset) < max_concurrency:
                zset[client_id] = now
                return 1
            else:
                return 0

        elif script == LUA_RELEASE_SCRIPT:
            client_id = args[0]
            zset = self.zsets.setdefault(key, {})
            if client_id in zset:
                del zset[client_id]
                return 1
            return 0

        elif script == LUA_EXTEND_SCRIPT:
            client_id = args[0]
            now = float(args[1])
            ttl = float(args[2])
            zset = self.zsets.setdefault(key, {})
            if client_id in zset:
                zset[client_id] = now
                return 1
            return 0

        elif script == LUA_USAGE_SCRIPT:
            now = float(args[0])
            ttl = float(args[1])
            zset = self.zsets.setdefault(key, {})
            cutoff = now - ttl
            to_del = [m for m, score in zset.items() if score <= cutoff]
            for m in to_del:
                del zset[m]
            return len(zset)

        from core.semaphore import LUA_RELEASE_LOCK_SCRIPT
        if script == LUA_RELEASE_LOCK_SCRIPT:
            token = args[0]
            if self.strings.get(key) == token:
                del self.strings[key]
                return 1
            return 0

        raise NotImplementedError("Unknown Lua script")


class RedisMergeSemaphoreTests(TestCase):
    """
    Unit tests for RedisMergeSemaphore distributed concurrency control (PRD §10.1, §12.3, Plan M6-T1).
    """

    def setUp(self):
        self.mock_redis = MockRedisClient()
        self.config = EventConfig.get_solo()
        self.config.merge_concurrency = 3
        self.config.save()

    def test_acquire_and_release_within_limit(self):
        sem1 = RedisMergeSemaphore(redis_client=self.mock_redis, client_id='worker-1', ttl=60)
        sem2 = RedisMergeSemaphore(redis_client=self.mock_redis, client_id='worker-2', ttl=60)
        sem3 = RedisMergeSemaphore(redis_client=self.mock_redis, client_id='worker-3', ttl=60)

        self.assertTrue(sem1.acquire())
        self.assertTrue(sem2.acquire())
        self.assertTrue(sem3.acquire())
        self.assertEqual(sem1.get_current_usage(), 3)

        # 4th should be rejected because max_concurrency is 3
        sem4 = RedisMergeSemaphore(redis_client=self.mock_redis, client_id='worker-4', ttl=60)
        self.assertFalse(sem4.acquire())

        # Release worker-1, then worker-4 can acquire
        self.assertTrue(sem1.release())
        self.assertEqual(sem1.get_current_usage(), 2)
        self.assertTrue(sem4.acquire())
        self.assertEqual(sem1.get_current_usage(), 3)

    def test_reentrant_acquire_refreshes_timestamp(self):
        sem = RedisMergeSemaphore(redis_client=self.mock_redis, client_id='worker-1', ttl=60)
        self.assertTrue(sem.acquire())
        self.assertEqual(sem.get_current_usage(), 1)

        # Re-acquiring with same client_id returns True without consuming additional slots
        self.assertTrue(sem.acquire())
        self.assertEqual(sem.get_current_usage(), 1)

    def test_stale_worker_ttl_auto_eviction(self):
        sem1 = RedisMergeSemaphore(redis_client=self.mock_redis, client_id='crashed-worker', ttl=10)
        self.assertTrue(sem1.acquire())
        self.assertEqual(sem1.get_current_usage(), 1)

        # Simulate time passing beyond TTL (manually set score to past)
        self.mock_redis.zsets[sem1.key]['crashed-worker'] = time.time() - 20

        # Next check / acquisition should auto-evict crashed-worker
        self.assertEqual(sem1.get_current_usage(), 0)

        sem2 = RedisMergeSemaphore(redis_client=self.mock_redis, client_id='new-worker', ttl=10)
        self.assertTrue(sem2.acquire())
        self.assertEqual(sem2.get_current_usage(), 1)

    def test_extend_heartbeat(self):
        sem = RedisMergeSemaphore(redis_client=self.mock_redis, client_id='worker-live', ttl=30)
        self.assertTrue(sem.acquire())
        self.assertTrue(sem.extend())

        sem_other = RedisMergeSemaphore(redis_client=self.mock_redis, client_id='worker-unacquired', ttl=30)
        self.assertFalse(sem_other.extend())

    def test_context_manager(self):
        sem = RedisMergeSemaphore(redis_client=self.mock_redis, client_id='ctx-worker', ttl=60)
        with sem as s:
            self.assertTrue(s.is_acquired())
            self.assertEqual(s.get_current_usage(), 1)
        self.assertFalse(sem.is_acquired())
        self.assertEqual(sem.get_current_usage(), 0)

    def test_redis_connection_error_graceful_handling(self):
        error_redis = MagicMock()
        import redis
        error_redis.eval.side_effect = redis.exceptions.ConnectionError("Redis connection refused")

        sem = RedisMergeSemaphore(redis_client=error_redis, client_id='worker-err')
        self.assertFalse(sem.acquire())
        self.assertFalse(sem.release())
        self.assertEqual(sem.get_current_usage(), 0)


class RedisContributionLockTests(TestCase):
    """
    Unit tests for RedisContributionLock exclusive per-contribution locking (PRD §12.4, Plan M6-T4).
    """

    def setUp(self):
        self.mock_redis = MockRedisClient()

    def test_acquire_and_release_exclusive_lock(self):
        from core.semaphore import RedisContributionLock
        lock1 = RedisContributionLock(contribution_id=42, ttl=60, redis_client=self.mock_redis)
        lock2 = RedisContributionLock(contribution_id=42, ttl=60, redis_client=self.mock_redis)

        # First worker acquires lock
        self.assertTrue(lock1.acquire())
        self.assertTrue(lock1.is_acquired())

        # Second worker is blocked from acquiring same contribution lock
        self.assertFalse(lock2.acquire())
        self.assertFalse(lock2.is_acquired())

        # First worker releases lock
        self.assertTrue(lock1.release())
        self.assertFalse(lock1.is_acquired())

        # Now second worker can acquire
        self.assertTrue(lock2.acquire())
        self.assertTrue(lock2.release())

    def test_context_manager(self):
        from core.semaphore import RedisContributionLock
        lock = RedisContributionLock(contribution_id=99, ttl=60, redis_client=self.mock_redis)
        with lock as acquired:
            self.assertTrue(acquired)
            self.assertTrue(lock.is_acquired())
        self.assertFalse(lock.is_acquired())

