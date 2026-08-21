import { render, screen } from '@testing-library/react'
import { vi } from 'vitest'
import { App } from './App'

vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify([]), { status: 200, headers: { 'Content-Type': 'application/json' } })))

test('renders the workbook upload experience', async () => {
  render(<App />)
  expect(screen.getByRole('heading', { name: 'Process your Excel workbook' })).toBeInTheDocument()
  expect(screen.getByRole('button', { name: 'Browse Files' })).toBeInTheDocument()
  expect(await screen.findByText('No workbooks found')).toBeInTheDocument()
})

