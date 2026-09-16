import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { Layout } from './components/Layout';
import { IssuesExplorerPage } from './pages/IssuesExplorerPage';
import { IssueDetailPage } from './pages/IssueDetailPage';
import { ProjectsExplorerPage } from './pages/ProjectsExplorerPage';
import { ProjectDetailPage } from './pages/ProjectDetailPage';
import { MyContributionsPage } from './pages/MyContributionsPage';
import { ContributionDetailPage } from './pages/ContributionDetailPage';
import { LeaderboardPage } from './pages/LeaderboardPage';
import { DashboardPage } from './pages/DashboardPage';
import { PublicProfilePage } from './pages/PublicProfilePage';
import { StatsPage } from './pages/StatsPage';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      retry: 1,
    },
  },
});

export function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Layout>
          <Routes>
            <Route path="/" element={<Navigate to="/issues" replace />} />
            <Route path="/issues" element={<IssuesExplorerPage />} />
            <Route path="/issues/:id" element={<IssueDetailPage />} />
            <Route path="/projects" element={<ProjectsExplorerPage />} />
            <Route path="/projects/:slug" element={<ProjectDetailPage />} />
            <Route path="/projects/*" element={<ProjectDetailPage />} />
            <Route path="/contributions" element={<MyContributionsPage />} />
            <Route path="/contributions/:id" element={<ContributionDetailPage />} />
            {/* M7 Routes (PRD §9, §16, §17, Plan M7-T6) */}
            <Route path="/leaderboard" element={<LeaderboardPage />} />
            <Route path="/dashboard" element={<DashboardPage />} />
            <Route path="/profile/:username" element={<PublicProfilePage />} />
            <Route path="/stats" element={<StatsPage />} />
            <Route path="*" element={<Navigate to="/issues" replace />} />
          </Routes>
        </Layout>
      </BrowserRouter>
    </QueryClientProvider>
  );
}

export default App;

