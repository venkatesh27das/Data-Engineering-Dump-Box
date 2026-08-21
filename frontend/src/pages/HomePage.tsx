import { useMutation, useQuery } from '@tanstack/react-query'
import { ArrowRight, FileSpreadsheet, RefreshCw, Sparkles, Upload, X } from 'lucide-react'
import { DragEvent, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../api/client'
import { BrandMark } from '../components/common/BrandMark'
import { ErrorState, LoadingState } from '../components/common/States'
import { WorkbookTable } from '../components/common/WorkbookTable'

const allowed = ['xlsx', 'xlsm', 'xlsb']

export function HomePage() {
  const navigate = useNavigate()
  const inputRef = useRef<HTMLInputElement>(null)
  const [file, setFile] = useState<File | null>(null)
  const [purpose, setPurpose] = useState('Knowledge extraction / Entity & relationship')
  const [description, setDescription] = useState('')
  const [fileError, setFileError] = useState('')
  const workbooks = useQuery({ queryKey: ['workbooks'], queryFn: () => api.listWorkbooks() })
  const upload = useMutation({ mutationFn: () => api.uploadWorkbook(file!, purpose, description), onSuccess: ({ run }) => navigate(`/runs/${run.id}`) })

  const chooseFile = (candidate?: File) => {
    if (!candidate) return
    const extension = candidate.name.split('.').pop()?.toLowerCase() || ''
    if (!allowed.includes(extension)) { setFileError('Choose an .xlsx, .xlsm, or .xlsb workbook.'); return }
    if (candidate.size > 200 * 1024 * 1024) { setFileError('The workbook must be 200 MB or smaller.'); return }
    setFileError(''); setFile(candidate)
  }
  const drop = (event: DragEvent<HTMLDivElement>) => { event.preventDefault(); chooseFile(event.dataTransfer.files[0]) }

  return <div className="home-page">
    <section className="card upload-card">
      <div className="section-heading"><h1>Process your Excel workbook</h1><p>Upload your Excel file and let the agent understand and convert it<br className="desktop-only" /> into structured knowledge assets.</p></div>
      <div className="upload-grid">
        <div className={`drop-zone ${file ? 'drop-zone--selected' : ''}`} onDragOver={(event) => event.preventDefault()} onDrop={drop}>
          <input ref={inputRef} type="file" accept=".xlsx,.xlsm,.xlsb" onChange={(event) => chooseFile(event.target.files?.[0])} hidden />
          {file ? <><div className="file-preview"><BrandMark /><div><strong>{file.name}</strong><span>{formatBytes(file.size)}</span></div><button className="icon-button" aria-label="Remove file" onClick={() => setFile(null)}><X /></button></div><button className="secondary-button" onClick={() => inputRef.current?.click()}>Choose another file</button></> : <><div className="document-icon"><BrandMark /></div><strong>Drag and drop your Excel file here</strong><span>.xlsx, .xlsm, .xlsb supported</span><button className="primary-button" onClick={() => inputRef.current?.click()}>Browse Files</button></>}
        </div>
        <div className="upload-form">
          <label>What do you want to use this workbook for?<select value={purpose} onChange={(event) => setPurpose(event.target.value)}><option>Knowledge extraction / Entity & relationship</option><option>Multimodal extraction</option><option>Formula and lineage extraction</option><option>Document and table extraction</option></select></label>
          <label>Optional description <span>(helps the agent understand better)</span><textarea value={description} onChange={(event) => setDescription(event.target.value)} placeholder="E.g. Monthly sales forecast, financial planning model, inspection reports, etc." /></label>
          {(fileError || upload.error) && <div className="inline-error">{fileError || upload.error?.message}</div>}
          <button className="primary-button analyze-button" disabled={!file || upload.isPending} onClick={() => upload.mutate()}>{upload.isPending ? 'Uploading…' : 'Analyze Workbook'}<Sparkles size={17} /></button>
        </div>
      </div>
    </section>
    <section className="card recent-card"><h2>Recent Workbooks</h2>{workbooks.isLoading ? <LoadingState /> : workbooks.error ? <ErrorState error={workbooks.error} /> : <WorkbookTable workbooks={(workbooks.data || []).slice(0, 2)} compact />}<button className="text-button" onClick={() => navigate('/workbooks')}>View all workbooks <ArrowRight size={17} /></button></section>
    <section className="card how-card"><h2>How it works</h2><div className="steps"><Step icon={Upload} number="1" title="Upload" text="Upload your Excel workbook" /><ArrowRight className="step-arrow" /><Step icon={Sparkles} number="2" title="Process" text="Agent analyzes and understands the workbook" /><ArrowRight className="step-arrow" /><Step icon={FileSpreadsheet} number="3" title="Review" text="Review extracted assets and provide feedback" /><ArrowRight className="step-arrow" /><Step icon={RefreshCw} number="4" title="Improve" text="Re-run with feedback for better results" /></div></section>
  </div>
}

function Step({ icon: Icon, number, title, text }: { icon: typeof Upload; number: string; title: string; text: string }) { return <div className="step"><div className="step-icon"><Icon /></div><div><strong>{number}. {title}</strong><span>{text}</span></div></div> }
function formatBytes(size: number) { return size < 1024 * 1024 ? `${Math.ceil(size / 1024)} KB` : `${(size / 1024 / 1024).toFixed(1)} MB` }

