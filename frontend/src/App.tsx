import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { Layout } from './components/Layout';
import { RootGate } from './components/RootGate';
import { ProtectedRoute } from './components/ProtectedRoute';
import { IssuesExplorerPage } from './pages/IssuesExplorerPage';
import { IssueDetailPage } from './pages/IssueDetailPage';
import { ProjectsExplorerPage } from './pages/ProjectsExplorerPage';
import { ProjectDetailPage } from './pages/ProjectDetailPage';
import { MyProfilePage } from './pages/MyProfilePage';
import { ContributionDetailPage } from './pages/ContributionDetailPage';
import { LeaderboardPage } from './pages/LeaderboardPage';
import { PublicProfilePage } from './pages/PublicProfilePage';
import { NotFoundPage } from './pages/NotFoundPage';

export const queryClient = new QueryClient({
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
            {/* Public Root Route with Auth Gate */}
            <Route path="/" element={<RootGate />} />

            {/* Public Exploration Routes */}
            <Route path="/issues" element={<IssuesExplorerPage />} />
            <Route path="/issues/:id" element={<IssueDetailPage />} />
            <Route path="/projects" element={<ProjectsExplorerPage />} />
            <Route path="/projects/:slug" element={<ProjectDetailPage />} />
            <Route path="/projects/*" element={<ProjectDetailPage />} />
            <Route path="/leaderboard" element={<LeaderboardPage />} />
            <Route path="/profile/:username" element={<PublicProfilePage />} />

            {/* Authenticated Participant Primary Area: My Profile */}
            <Route
              path="/profile"
              element={
                <ProtectedRoute>
                  <MyProfilePage />
                </ProtectedRoute>
              }
            />

            {/* Contribution Detail Deep Dive */}
            <Route
              path="/contributions/:id"
              element={
                <ProtectedRoute>
                  <ContributionDetailPage />
                </ProtectedRoute>
              }
            />

            {/* Deprecated Participant Routes - Graceful Redirects to Unified My Profile */}
            <Route path="/dashboard" element={<Navigate to="/profile" replace />} />
            <Route path="/contributions" element={<Navigate to="/profile?tab=contributions" replace />} />
            <Route path="/stats" element={<Navigate to="/profile" replace />} />

            {/* 404 Custom Not Found Route */}
            <Route path="*" element={<NotFoundPage />} />
          </Routes>
        </Layout>
      </BrowserRouter>
    </QueryClientProvider>
  );
}

export default App;

