import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'

const queryClient = new QueryClient()

function HomePage() {
  return (
    <div className="min-h-screen bg-slate-900 text-slate-100 flex items-center justify-center p-4">
      <div className="max-w-md w-full bg-slate-800 rounded-lg p-6 shadow-lg border border-slate-700 text-center">
        <h1 className="text-2xl font-bold mb-2 text-white">HackIT CommitRush</h1>
        <p className="text-sm text-slate-400 mb-4">
          Frontend scaffolding initialized. Ready for module implementation.
        </p>
        <div className="inline-block px-3 py-1 bg-emerald-900/60 text-emerald-300 rounded-full text-xs font-mono">
          Status: Scaffold Ready (M1-T1)
        </div>
      </div>
    </div>
  )
}

export function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<HomePage />} />
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  )
}

export default App
