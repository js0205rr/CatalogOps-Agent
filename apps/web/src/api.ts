export type ProductInput = {
  sku_id: string
  title: string
  description: string
  seller_category: string
  merchant_category: string
  attributes: Record<string, string>
}

const configuredApiBase = import.meta.env.VITE_API_BASE
const API_BASE =
  typeof configuredApiBase === 'string'
    ? configuredApiBase.replace(/\/$/, '')
    : 'http://localhost:8000'

function apiUrl(path: string) {
  return `${API_BASE}${path}`
}

export async function reviewSingle(product: ProductInput) {
  const res = await fetch(apiUrl('/api/reviews/single'), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(product),
  })
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

export async function reviewBatch(file: File) {
  const form = new FormData()
  form.append('file', file)
  const upload = await fetch(apiUrl('/api/batch/upload'), { method: 'POST', body: form })
  if (!upload.ok) throw new Error(await upload.text())
  const { batch_id } = await upload.json()
  const run = await fetch(apiUrl(`/api/batch/${batch_id}/run`), { method: 'POST' })
  if (!run.ok) throw new Error(await run.text())
  const payload = await run.json()
  return payload.report
}

export async function policyQa(question: string) {
  const res = await fetch(apiUrl('/api/chat/policy'), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ question, top_k: 5 }),
  })
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

export function traceSocketUrl(runId: string) {
  const base =
    API_BASE ||
    `${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//${window.location.host}`
  return `${base.replace(/^http/, 'ws')}/api/runs/${runId}/events`
}
