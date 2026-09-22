import { Link, useParams } from 'react-router-dom';
import { useMonorepoProjectDetail } from '../api/github';
import { ErrorState } from '../components/ErrorState';
import { ProjectDetailSkeleton } from '../components/Skeletons';
import { useDocumentTitle } from '../hooks/useDocumentTitle';

const FILE_ICONS: Record<string, string> = {
  py: '🐍',
  js: '🟨',
  ts: '🔷',
  html: '🌐',
  css: '🎨',
  json: '📋',
  md: '📝',
  txt: '📄',
  yml: '⚙️',
  yaml: '⚙️',
  toml: '⚙️',
  cfg: '⚙️',
  ini: '⚙️',
  env: '🔐',
  gitignore: '🙈',
  sql: '🗃️',
  csv: '📊',
  png: '🖼️',
  jpg: '🖼️',
  svg: '🖼️',
};

function getFileIcon(filename: string): string {
  const ext = filename.split('.').pop()?.toLowerCase() || '';
  if (filename.toLowerCase() === '.env' || filename.toLowerCase() === '.env.example') return '🔐';
  if (filename.toLowerCase() === '.gitignore') return '🙈';
  return FILE_ICONS[ext] || '📄';
}

function formatFileSize(bytes: number): string {
  if (bytes === 0) return '—';
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export function ProjectDetailPage() {
  const params = useParams();
  const rawSlug = params.slug || params['*'] || '';
  const dirName = decodeURIComponent(rawSlug);

  const { data: project, isLoading, isError, error, refetch } = useMonorepoProjectDetail(dirName);

  useDocumentTitle(
    project ? `CommitRush 2026 — ${project.name}` : 'CommitRush 2026 — Project Details',
    project
      ? `Explore the ${project.name} project from the Open Source Contribution Drive monorepo.`
      : 'View project details from the monorepo.'
  );

  if (isLoading) {
    return <ProjectDetailSkeleton />;
  }

  if (isError || !project) {
    return (
      <div className="space-y-6">
        <Link
          to="/projects"
          className="inline-flex items-center text-xs text-[#777777] hover:text-[#111111] transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-[#ff5a1f] rounded-sm"
        >
          ← Back to Projects
        </Link>
        <ErrorState error={error} onRetry={() => refetch()} />
      </div>
    );
  }

  const directories = project.files.filter((f) => f.type === 'dir');
  const files = project.files.filter((f) => f.type === 'file');

  return (
    <div className="space-y-8" data-testid="project-detail-view">
      {/* Top Breadcrumb / Back Link */}
      <div className="flex items-center justify-between">
        <Link
          to="/projects"
          className="inline-flex items-center gap-1.5 text-xs font-medium text-[#555555] hover:text-[#111111] transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-[#ff5a1f] rounded-sm"
        >
          <span>←</span> Back to Projects
        </Link>
        <span className="text-xs font-mono font-medium px-3 py-1 rounded-full bg-[#eef5f3] border border-[#c0d8d0] text-[#22443d]">
          {project.category}
        </span>
      </div>

      {/* Main Project Header Card */}
      <div className="bg-white border border-[#d8d8d3] rounded-md p-6 sm:p-8 space-y-4 shadow-sm">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div className="min-w-0">
            <div className="text-xs font-mono text-[#ff5a1f] uppercase tracking-wider mb-1">
              Hackit-DROID
            </div>
            <h1 className="text-2xl sm:text-3xl font-display font-bold text-[#111111] tracking-tight break-words">
              {project.name}
            </h1>
          </div>

          <div className="flex items-center gap-3 shrink-0">
            <a
              href={project.githubUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-2 px-6 py-2.5 rounded-[4px] bg-[#050505] hover:bg-[#1a1a1a] text-white text-sm font-semibold shadow-sm transition-all focus:outline-none focus-visible:ring-2 focus-visible:ring-[#ff5a1f]"
            >
              <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 24 24">
                <path d="M12 0c-6.626 0-12 5.373-12 12 0 5.302 3.438 9.8 8.207 11.387.599.111.793-.261.793-.577v-2.234c-3.338.726-4.033-1.416-4.033-1.416-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.083-.729.083-.729 1.205.084 1.839 1.237 1.839 1.237 1.07 1.834 2.807 1.304 3.492.997.107-.775.418-1.305.762-1.604-2.665-.305-5.467-1.334-5.467-5.931 0-1.311.469-2.381 1.236-3.221-.124-.303-.535-1.524.117-3.176 0 0 1.008-.322 3.301 1.23A11.509 11.509 0 0112 5.803c1.02.005 2.047.138 3.006.404 2.291-1.552 3.297-1.23 3.297-1.23.653 1.653.242 2.874.118 3.176.77.84 1.235 1.911 1.235 3.221 0 4.609-2.807 5.624-5.479 5.921.43.372.823 1.102.823 2.222v3.293c0 .319.192.694.801.576C20.566 21.797 24 17.3 24 12c0-6.627-5.373-12-12-12z" />
              </svg>
              <span>View on GitHub</span>
              <span>→</span>
            </a>
          </div>
        </div>

        <div className="pt-4 flex flex-wrap items-center gap-4 border-t border-[#d8d8d3] text-xs text-[#777777] font-mono">
          <div className="flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full bg-[#ff5a1f]" />
            <span className="text-[#111111] font-medium">Directory:</span> {project.dirName}
          </div>
          <div className="text-[#d8d8d3]">•</div>
          <div>
            <span className="text-[#111111] font-medium">Files:</span> {files.length}
          </div>
          {directories.length > 0 && (
            <>
              <div className="text-[#d8d8d3]">•</div>
              <div>
                <span className="text-[#111111] font-medium">Subdirectories:</span> {directories.length}
              </div>
            </>
          )}
        </div>
      </div>

      {/* README Content */}
      {project.readmeContent && (
        <div className="bg-white border border-[#d8d8d3] rounded-md shadow-sm overflow-hidden">
          <div className="px-6 py-3 border-b border-[#d8d8d3] bg-[#fafaf8]">
            <h2 className="text-sm font-semibold text-[#111111] font-mono">📝 README.md</h2>
          </div>
          <div className="p-6 prose prose-sm max-w-none text-[#333333] overflow-x-auto">
            <pre className="whitespace-pre-wrap text-sm font-mono text-[#333333] leading-relaxed bg-transparent p-0 m-0 border-0">
              {project.readmeContent}
            </pre>
          </div>
        </div>
      )}

      {/* File Listing */}
      <div className="bg-white border border-[#d8d8d3] rounded-md shadow-sm overflow-hidden">
        <div className="px-6 py-3 border-b border-[#d8d8d3] bg-[#fafaf8]">
          <h2 className="text-sm font-semibold text-[#111111] font-mono">
            📁 Files & Directories
          </h2>
        </div>
        <div className="divide-y divide-[#ebebeb]">
          {/* Directories first */}
          {directories.map((entry) => (
            <a
              key={entry.sha}
              href={entry.html_url}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center justify-between px-6 py-3 hover:bg-[#fafaf8] transition-colors group"
            >
              <div className="flex items-center gap-3 min-w-0">
                <span className="text-base shrink-0">📂</span>
                <span className="text-sm text-[#111111] font-medium truncate group-hover:text-[#ff5a1f] transition-colors">
                  {entry.name}
                </span>
              </div>
              <span className="text-xs text-[#777777] font-mono shrink-0 ml-4">directory</span>
            </a>
          ))}
          {/* Files */}
          {files.map((entry) => (
            <a
              key={entry.sha}
              href={entry.html_url}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center justify-between px-6 py-3 hover:bg-[#fafaf8] transition-colors group"
            >
              <div className="flex items-center gap-3 min-w-0">
                <span className="text-base shrink-0">{getFileIcon(entry.name)}</span>
                <span className="text-sm text-[#111111] truncate group-hover:text-[#ff5a1f] transition-colors">
                  {entry.name}
                </span>
              </div>
              <span className="text-xs text-[#777777] font-mono shrink-0 ml-4">
                {formatFileSize(entry.size)}
              </span>
            </a>
          ))}
        </div>
      </div>
    </div>
  );
}
