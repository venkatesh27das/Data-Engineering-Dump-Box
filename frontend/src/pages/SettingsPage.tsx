import { useMutation, useQuery } from '@tanstack/react-query'
import { Bot, CircleCheck, CircleX, Database, RefreshCw } from 'lucide-react'
import { api } from '../api/client'
import { ErrorState, LoadingState } from '../components/common/States'
import type { ModelStatus } from '../types'

const roleLabels: Record<string, string> = {
  reasoning: 'Reasoning & agents',
  vision: 'Workbook images',
  embedding: 'Semantic embeddings',
}

export function SettingsPage() {
  const status = useQuery({ queryKey: ['model-status'], queryFn: api.modelStatus })
  const probe = useMutation({ mutationFn: api.probeModels })
  const data = probe.data || status.data

  return <div>
    <div className="page-heading">
      <div><h1>Settings</h1><p>Review local intelligence and storage capabilities.</p></div>
      <button className="secondary-button" disabled={!data?.reachable || probe.isPending} onClick={() => probe.mutate()}>
        <RefreshCw className={probe.isPending ? 'spin' : ''} />{probe.isPending ? 'Testing…' : 'Test capabilities'}
      </button>
    </div>
    {status.isLoading ? <LoadingState /> : status.error ? <ErrorState error={status.error} /> : data && <SettingsContent data={data} />}
  </div>
}

function SettingsContent({ data }: { data: ModelStatus }) {
  return <div className="settings-grid">
    <section className="card settings-card">
      <Bot />
      <div><h2>LM Studio</h2><p>{data.reachable ? 'Connected. Local agents can process workbook context.' : 'Offline. Deterministic extraction remains available.'}</p></div>
      {data.reachable ? <CircleCheck className="green" /> : <CircleX className="red" />}
    </section>
    <section className="card settings-card">
      <Database />
      <div><h2>Local storage</h2><p>Workbook originals, vectors, and packages stay on this device.</p></div>
      <CircleCheck className="green" />
    </section>
    <section className="card model-list">
      <div className="model-list-heading"><div><h2>Local intelligence roles</h2><p>{data.framework ? `Runtime: ${data.framework.replaceAll('_', ' ')}` : 'Models are selected automatically from LM Studio.'}</p></div><span className={`capability-badge capability-badge--${data.capability_check === 'ready' ? 'ready' : 'warning'}`}>{data.capability_check.replaceAll('_', ' ')}</span></div>
      <div className="role-grid">{Object.entries(data.roles || {}).map(([name, role]) => {
        const check = data.checks?.[name]
        const ready = (check?.status || role.status).startsWith('ready')
        return <article key={name} className="role-card">
          <div><span className={`role-dot role-dot--${ready ? 'ready' : 'warning'}`} /><strong>{roleLabels[name] || name}</strong></div>
          <p>{role.model || 'No matching model found'}</p>
          <small>{check ? check.status.replaceAll('_', ' ') : `${role.status} · ${role.selection} selection`}{check?.dimensions ? ` · ${check.dimensions} dimensions` : ''}</small>
        </article>
      })}</div>
    </section>
  </div>
}
