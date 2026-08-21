import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { AppShell } from '../components/layout/AppShell'
import { HomePage } from '../pages/HomePage'
import { RunDetailPage } from '../pages/RunDetailPage'
import { RunHistoryPage } from '../pages/RunHistoryPage'
import { SettingsPage } from '../pages/SettingsPage'
import { WorkbookDetailPage } from '../pages/WorkbookDetailPage'
import { WorkbooksPage } from '../pages/WorkbooksPage'

const queryClient = new QueryClient({ defaultOptions: { queries: { staleTime: 10_000, retry: 1 } } })

export function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          <Route element={<AppShell />}>
            <Route index element={<HomePage />} />
            <Route path="workbooks" element={<WorkbooksPage />} />
            <Route path="workbooks/:workbookId" element={<WorkbookDetailPage />} />
            <Route path="runs" element={<RunHistoryPage />} />
            <Route path="runs/:runId" element={<RunDetailPage />} />
            <Route path="settings" element={<SettingsPage />} />
            <Route path="feedback" element={<Navigate to="/runs" replace />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  )
}

