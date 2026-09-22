import { useQuery } from '@tanstack/react-query';

const REPO_OWNER = 'Hackit-DROID';
const REPO_NAME = 'Open-Source-Contribution-Drive';
const GITHUB_API = 'https://api.github.com';
const REPO_URL = `https://github.com/${REPO_OWNER}/${REPO_NAME}`;

/**
 * A single directory entry from the GitHub Contents API.
 */
export interface GitHubContentEntry {
  name: string;
  path: string;
  sha: string;
  size: number;
  url: string;
  html_url: string;
  git_url: string;
  type: 'file' | 'dir';
}

/**
 * A monorepo project derived from grouping directory entries.
 */
export interface MonorepoProject {
  /** Display-friendly name: underscores replaced with spaces */
  name: string;
  /** Raw directory name (the base, without _N suffix) */
  baseName: string;
  /** Number of variant directories for this project */
  variantCount: number;
  /** All directory names belonging to this project group */
  variants: string[];
  /** Direct GitHub link to the first variant */
  githubUrl: string;
  /** Inferred category from the project name */
  category: string;
}

/**
 * Detail view for a specific project directory in the monorepo.
 */
export interface MonorepoProjectDetail {
  /** Raw directory name */
  dirName: string;
  /** Display name */
  name: string;
  /** GitHub URL */
  githubUrl: string;
  /** Files in the directory */
  files: GitHubContentEntry[];
  /** README content (if available) */
  readmeContent: string | null;
  /** Inferred category */
  category: string;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Strip trailing _N suffix to get the base project name. */
function getBaseName(dirName: string): string {
  return dirName.replace(/_\d+$/, '');
}

/** Convert underscored dir name to a display-friendly title. */
function toDisplayName(baseName: string): string {
  return baseName.replace(/_/g, ' ');
}

/** Categorize project by keywords in the name. */
function inferCategory(name: string): string {
  const lower = name.toLowerCase();
  if (lower.includes('ai') || lower.includes('langchain') || lower.includes('openai') || lower.includes('agent')) {
    return 'AI & Automation';
  }
  if (lower.includes('deep') || lower.includes('invoice') || lower.includes('extractor')) {
    return 'Deep Learning & CV';
  }
  if (lower.includes('student') || lower.includes('college') || lower.includes('university') || lower.includes('academic') || lower.includes('hostel') || lower.includes('library') || lower.includes('attendance') || lower.includes('grade') || lower.includes('enrollment') || lower.includes('catalog') || lower.includes('records')) {
    return 'Campus & Academic MIS';
  }
  if (lower.includes('streamlit') || lower.includes('dashboard')) {
    return 'Data Visualization';
  }
  if (lower.includes('hotel') || lower.includes('reservation') || lower.includes('blood') || lower.includes('donation') || lower.includes('book') || lower.includes('issuance')) {
    return 'Enterprise Applications';
  }
  return 'General';
}

// ---------------------------------------------------------------------------
// Fetchers
// ---------------------------------------------------------------------------

async function fetchRepoContents(): Promise<GitHubContentEntry[]> {
  const res = await fetch(`${GITHUB_API}/repos/${REPO_OWNER}/${REPO_NAME}/contents/`, {
    headers: { Accept: 'application/vnd.github.v3+json' },
  });
  if (!res.ok) {
    throw new Error(`GitHub API error: ${res.status} ${res.statusText}`);
  }
  return res.json();
}

async function fetchDirectoryContents(dirPath: string): Promise<GitHubContentEntry[]> {
  const res = await fetch(
    `${GITHUB_API}/repos/${REPO_OWNER}/${REPO_NAME}/contents/${encodeURIComponent(dirPath)}`,
    { headers: { Accept: 'application/vnd.github.v3+json' } }
  );
  if (!res.ok) {
    throw new Error(`GitHub API error: ${res.status} ${res.statusText}`);
  }
  return res.json();
}

async function fetchFileContent(filePath: string): Promise<string> {
  const res = await fetch(
    `https://raw.githubusercontent.com/${REPO_OWNER}/${REPO_NAME}/main/${filePath}`
  );
  if (!res.ok) return '';
  return res.text();
}

// ---------------------------------------------------------------------------
// Derived data
// ---------------------------------------------------------------------------

export async function fetchMonorepoProjects(): Promise<MonorepoProject[]> {
  const entries = await fetchRepoContents();
  const dirs = entries.filter((e) => e.type === 'dir');

  // Group by base name
  const groups = new Map<string, string[]>();
  for (const d of dirs) {
    const base = getBaseName(d.name);
    if (!groups.has(base)) {
      groups.set(base, []);
    }
    groups.get(base)!.push(d.name);
  }

  const projects: MonorepoProject[] = [];
  for (const [baseName, variants] of groups) {
    // Sort variants naturally (base first, then _2, _3, …)
    variants.sort((a, b) => {
      const numA = a === baseName ? 0 : parseInt(a.replace(`${baseName}_`, ''), 10) || 0;
      const numB = b === baseName ? 0 : parseInt(b.replace(`${baseName}_`, ''), 10) || 0;
      return numA - numB;
    });

    projects.push({
      name: toDisplayName(baseName),
      baseName,
      variantCount: variants.length,
      variants,
      githubUrl: `${REPO_URL}/tree/main/${variants[0]}`,
      category: inferCategory(baseName),
    });
  }

  // Sort alphabetically by display name
  projects.sort((a, b) => a.name.localeCompare(b.name));
  return projects;
}

export async function fetchMonorepoProjectDetail(dirName: string): Promise<MonorepoProjectDetail> {
  const [files, readmeContent] = await Promise.all([
    fetchDirectoryContents(dirName),
    // Try common README filenames
    fetchFileContent(`${dirName}/README.md`)
      .then((c) => c || null)
      .catch(() =>
        fetchFileContent(`${dirName}/readme.md`)
          .then((c) => c || null)
          .catch(() => null)
      ),
  ]);

  const baseName = getBaseName(dirName);

  return {
    dirName,
    name: toDisplayName(baseName),
    githubUrl: `${REPO_URL}/tree/main/${dirName}`,
    files,
    readmeContent,
    category: inferCategory(baseName),
  };
}

// ---------------------------------------------------------------------------
// React Query hooks
// ---------------------------------------------------------------------------

export function useMonorepoProjects() {
  return useQuery({
    queryKey: ['monorepo-projects'],
    queryFn: fetchMonorepoProjects,
    staleTime: 5 * 60 * 1000, // 5 minutes
  });
}

export function useMonorepoProjectDetail(dirName: string) {
  return useQuery({
    queryKey: ['monorepo-project-detail', dirName],
    queryFn: () => fetchMonorepoProjectDetail(dirName),
    enabled: Boolean(dirName),
    staleTime: 5 * 60 * 1000,
  });
}
