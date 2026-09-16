import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { Layout } from './components/Layout';
import { IssuesExplorerPage } from './pages/IssuesExplorerPage';
import { IssueDetailPage } from './pages/IssueDetailPage';
import { ProjectsExplorerPage } from './pages/ProjectsExplorerPage';
import { ProjectDetailPage } from './pages/ProjectDetailPage';

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
            <Route path="*" element={<Navigate to="/issues" replace />} />
          </Routes>
        </Layout>
      </BrowserRouter>
    </QueryClientProvider>
  );
}

export default App;
