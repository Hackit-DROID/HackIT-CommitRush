import { Link, useParams } from 'react-router-dom';
import { useProject } from '../api/projects';
import { ErrorState } from '../components/ErrorState';
import { ProjectDetailSkeleton } from '../components/Skeletons';
import { useDocumentTitle } from '../hooks/useDocumentTitle';

export function ProjectDetailPage() {
  const params = useParams();
  // Support both /projects/:slug and /projects/*
  const rawSlug = params.slug || params['*'] || '';
  const slug = decodeURIComponent(rawSlug);

  const { data: project, isLoading, isError, error, refetch } = useProject(slug);

  useDocumentTitle(
    project ? `CommitRush — Project: ${project.name}` : 'CommitRush — Project Details',
    project
      ? `Tracked repository details, issue counts, and contribution activity for ${project.full_name}.`
      : 'View tracked repository details on CommitRush.'
  );

  if (isLoading) {
    return <ProjectDetailSkeleton />;
  }

  if (isError || !project) {
    return (
      <div className="space-y-6">
        <Link
          to="/projects"
          className="inline-flex items-center text-xs text-slate-400 hover:text-white transition-colors"
        >
          ← Back to Projects
        </Link>
        <ErrorState error={error} onRetry={() => refetch()} />
      </div>
    );
  }

  return (
    <div className="space-y-8" data-testid="project-detail-view">
      {/* Top Breadcrumb / Back Link */}
      <div className="flex items-center justify-between">
        <Link
          to="/projects"
          className="inline-flex items-center gap-1.5 text-xs font-medium text-slate-400 hover:text-cyan-400 transition-colors"
        >
          <span>←</span> Back to Projects
        </Link>
        <span
          className={`text-xs font-medium px-2.5 py-1 rounded-full ${
            project.is_enabled
              ? 'bg-emerald-950/70 border border-emerald-800/60 text-emerald-400'
              : 'bg-slate-800 text-slate-400 border border-slate-700'
          }`}
        >
          {project.is_enabled ? 'Active Tracked Repository' : 'Disabled Repository'}
        </span>
      </div>

      {/* Main Project Header Card */}
      <div className="bg-slate-900/60 border border-slate-800 rounded-2xl p-6 sm:p-8 space-y-4 shadow-sm">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div>
            <div className="text-xs font-mono text-cyan-400 uppercase tracking-wider mb-1">
              {project.owner}
            </div>
            <h1 className="text-2xl sm:text-3xl font-extrabold text-white tracking-tight">
              {project.name}
            </h1>
          </div>

          <div className="flex items-center gap-3">
            <Link
              to={`/issues?project=${encodeURIComponent(project.full_name)}`}
              className="inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-cyan-600 hover:bg-cyan-500 text-white text-sm font-semibold shadow-lg shadow-cyan-600/20 transition-all"
            >
              <span>Explore Issues ({project.issue_count})</span>
              <span>→</span>
            </Link>
          </div>
        </div>

        <p className="text-sm sm:text-base text-slate-300 leading-relaxed max-w-3xl">
          {project.description || 'No description provided for this repository.'}
        </p>

        <div className="pt-4 flex flex-wrap items-center gap-4 border-t border-slate-800/80 text-xs text-slate-400">
          <div className="flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full bg-cyan-400" />
            <span className="text-slate-300 font-medium">Language:</span> {project.language || 'Not specified'}
          </div>
          <div className="text-slate-600">•</div>
          <div>
            <span className="text-slate-300 font-medium">Full Name:</span> {project.full_name}
          </div>
          <div className="text-slate-600">•</div>
          <div>
            <span className="text-slate-300 font-medium">GitHub Repo ID:</span> {project.github_repo_id}
          </div>
        </div>
      </div>

      {/* Metrics & Activity Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-5">
        {/* Issue Count Metric */}
        <div className="bg-slate-900/40 border border-slate-800 rounded-xl p-5 space-y-1.5">
          <div className="text-xs font-medium text-slate-400">Total Tracked Issues</div>
          <div className="text-3xl font-extrabold text-white">{project.issue_count}</div>
          <div className="text-xs text-emerald-400 font-medium">
            {project.open_issue_count} open for contributions
          </div>
        </div>

        {/* Contribution Activity: Merged */}
        <div className="bg-slate-900/40 border border-slate-800 rounded-xl p-5 space-y-1.5">
          <div className="text-xs font-medium text-slate-400">Merged PRs / Contributions</div>
          <div className="text-3xl font-extrabold text-emerald-400">
            {project.contribution_activity?.merged_contributions ?? 0}
          </div>
          <div className="text-xs text-slate-500">
            Confirmed completed sprint contributions
          </div>
        </div>

        {/* Contribution Activity: In Progress */}
        <div className="bg-slate-900/40 border border-slate-800 rounded-xl p-5 space-y-1.5">
          <div className="text-xs font-medium text-slate-400">Active In-Progress</div>
          <div className="text-3xl font-extrabold text-amber-400">
            {project.contribution_activity?.in_progress_contributions ?? 0}
          </div>
          <div className="text-xs text-slate-500">
            PRs currently in review or validation queue
          </div>
        </div>
      </div>
    </div>
  );
}
