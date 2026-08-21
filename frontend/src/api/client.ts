import type { Asset, ModelStatus, ProcessingRun, ReviewItem, Workbook } from '../types'

const API = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1'

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${API}${path}`, options)
  if (!response.ok) {
    const payload = await response.json().catch(() => ({ detail: 'Something went wrong.' }))
    throw new Error(payload.detail?.message || payload.detail || 'Something went wrong.')
  }
  return response.json()
}

export const api = {
  listWorkbooks: (query = '') => request<Workbook[]>(`/workbooks?search=${encodeURIComponent(query)}`),
  getWorkbook: (id: string) => request<Workbook>(`/workbooks/${id}`),
  uploadWorkbook: (file: File, purpose: string, description: string) => {
    const form = new FormData()
    form.append('file', file)
    form.append('purpose', purpose)
    form.append('description', description)
    return request<{ workbook: Workbook; run: ProcessingRun }>('/workbooks', { method: 'POST', body: form })
  },
  archiveWorkbook: (id: string) => request<Workbook>(`/workbooks/${id}`, { method: 'DELETE' }),
  listRuns: (query = '') => request<ProcessingRun[]>(`/runs?search=${encodeURIComponent(query)}`),
  getRun: (id: string) => request<ProcessingRun>(`/runs/${id}`),
  listWorkbookRuns: (id: string) => request<ProcessingRun[]>(`/runs?workbook_id=${id}`),
  listAssets: (id: string) => request<Asset[]>(`/runs/${id}/assets`),
  listReviewItems: (id: string) => request<ReviewItem[]>(`/runs/${id}/review-items`),
  resolveReview: (id: string, action: string) => request<ReviewItem>(`/review-items/${id}/${action}`, { method: 'POST' }),
  reprocess: (id: string, raw_text: string) => request<ProcessingRun>(`/runs/${id}/reprocess`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ raw_text, scope: 'impacted_assets', preserve_approved_assets: true }) }),
  cancelRun: (id: string) => request<ProcessingRun>(`/runs/${id}/cancel`, { method: 'POST' }),
  acceptRun: (id: string) => request<ProcessingRun>(`/runs/${id}/accept`, { method: 'POST' }),
  modelStatus: () => request<ModelStatus>('/models/status'),
  probeModels: () => request<ModelStatus>('/models/probe', { method: 'POST' }),
  packageUrl: (id: string) => `${API}/runs/${id}/package/download`,
  eventUrl: (id: string) => `${API}/runs/${id}/events`,
}
