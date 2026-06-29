import { useState } from 'react'
import { policyQa, reviewBatch, reviewSingle, traceSocketUrl, type ProductInput } from './api'

type Tab = 'single' | 'batch' | 'policy' | 'trace'

const TEXT = {
  single: '\u5355\u5546\u54c1\u5ba1\u6838',
  batch: '\u6279\u91cf\u5ba1\u6838',
  policy: '\u89c4\u5219\u77e5\u8bc6\u5e93',
  trace: 'Agent Trace',
  decision: '\u53d1\u5e03\u51b3\u7b56',
  confidence: '\u8d28\u91cf\u8bc4\u5206',
  issueCount: '\u95ee\u9898\u6570',
  evidenceCount: '\u8bc1\u636e\u6570',
  issueList: '\u95ee\u9898\u5217\u8868',
  suggestion: '\u4fee\u8ba2\u5efa\u8bae',
  waiting: '\u7b49\u5f85\u5ba1\u6838\u7ed3\u679c',
  runReview: '\u8fd0\u884c\u5ba1\u6838',
  reviewing: '\u5ba1\u6838\u4e2d',
  uploadCsv: '\u4e0a\u4f20 CSV',
  processing: '\u5904\u7406\u4e2d',
  rows: '\u884c\u6570',
  reviewedRows: '\u5b8c\u6574\u5ba1\u6838',
  issueTypes: '\u95ee\u9898\u7c7b\u578b',
  uploadHint: 'Upload data/sample_products/sample_products.csv to inspect the batch report',
  queryRule: '\u68c0\u7d22\u89c4\u5219',
  evidenceSnippets: '\u8bc1\u636e\u7247\u6bb5',
  runTrace: '\u8fd0\u884c Trace',
  traceRunning: '\u8fd0\u884c\u4e2d',
  governanceDesk: '\u5546\u54c1\u53d1\u5e03\u524d\u7c7b\u76ee\u3001\u5c5e\u6027\u4e0e\u6807\u9898\u5408\u89c4\u6cbb\u7406',
  none: '\u65e0',
} as const

const sampleProduct: ProductInput = {
  sku_id: 'P1002',
  title: '\u5168\u7f51\u6700\u4f4e \u7eaf\u68c9\u5973\u88c5\u77ed\u8896T\u6064 \u767d\u8272',
  description: '\u57fa\u7840\u6b3e\u4e0a\u8863 \u5c3a\u7801: M',
  seller_category: '\u670d\u9970\u978b\u5305/\u5973\u88c5/T\u6064',
  merchant_category: '\u670d\u9970\u978b\u5305/\u5973\u88c5/T\u6064',
  attributes: {
    '\u6750\u8d28': '\u7eaf\u68c9',
    '\u5c3a\u7801': 'M',
    '\u989c\u8272': '\u767d\u8272',
  },
}

const tabs: Array<{ id: Tab; label: string }> = [
  { id: 'single', label: TEXT.single },
  { id: 'batch', label: TEXT.batch },
  { id: 'policy', label: TEXT.policy },
  { id: 'trace', label: TEXT.trace },
]

function pretty(value: unknown) {
  return JSON.stringify(value, null, 2)
}

function StatusPill({ value }: { value: string }) {
  return <span className={`pill pill-${value}`}>{value}</span>
}

function ResultPanel({ result }: { result: any }) {
  if (!result) {
    return <aside className="resultPane empty">{TEXT.waiting}</aside>
  }
  return (
    <aside className="resultPane">
      <div className="resultHeader">
        <h2>{TEXT.decision}</h2>
        <StatusPill value={result.publish_decision || result.decision} />
      </div>
      <div className="metricGrid">
        <div>
          <b>{Math.round(result.quality_score?.overall ?? result.confidence ?? 0)}%</b>
          <span>{TEXT.confidence}</span>
        </div>
        <div>
          <b>{(result.compliance_issues || result.issues || []).length}</b>
          <span>{TEXT.issueCount}</span>
        </div>
        <div>
          <b>{(result.evidence || []).length}</b>
          <span>{TEXT.evidenceCount}</span>
        </div>
      </div>
      <h3>{TEXT.issueList}</h3>
      <ul className="issueList">
        {(result.compliance_issues || result.issues || []).map((issue: any) => (
          <li key={issue.issue_id}>
            <span>{issue.severity}</span>
            <p>{issue.message}</p>
          </li>
        ))}
      </ul>
      <h3>{TEXT.suggestion}</h3>
      <pre>{result.rewrite_suggestions?.title || result.suggestion?.revised_title || TEXT.none}</pre>
      <h3>{TEXT.trace}</h3>
      <ol className="traceList">
        {result.trace.map((item: any, idx: number) => (
          <li key={idx}>
            {item.node}: {item.detail}
          </li>
        ))}
      </ol>
    </aside>
  )
}

function SingleReview() {
  const [payload, setPayload] = useState(pretty(sampleProduct))
  const [result, setResult] = useState<any>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  async function run() {
    setLoading(true)
    setError('')
    try {
      setResult(await reviewSingle(JSON.parse(payload)))
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setLoading(false)
    }
  }

  return (
    <section className="workspace">
      <div className="editorPane">
        <div className="paneHeader">
          <h2>{TEXT.single}</h2>
          <button onClick={run} disabled={loading}>
            {loading ? TEXT.reviewing : TEXT.runReview}
          </button>
        </div>
        <textarea
          value={payload}
          onChange={(event) => setPayload(event.target.value)}
          spellCheck={false}
        />
        {error ? <div className="error">{error}</div> : null}
      </div>
      <ResultPanel result={result} />
    </section>
  )
}

function BatchReview() {
  const [result, setResult] = useState<any>(null)
  const [loading, setLoading] = useState(false)

  async function onFile(file?: File) {
    if (!file) return
    setLoading(true)
    try {
      setResult(await reviewBatch(file))
    } finally {
      setLoading(false)
    }
  }

  return (
    <section className="workspace oneColumn">
      <div className="paneHeader">
        <h2>{TEXT.batch}</h2>
        <label className="upload">
          {loading ? TEXT.processing : TEXT.uploadCsv}
          <input type="file" accept=".csv" onChange={(event) => onFile(event.target.files?.[0])} />
        </label>
      </div>
      {result ? (
        <div className="report">
          <div className="metricGrid">
            <div>
              <b>{result.profile.row_count ?? result.profile.rows}</b>
              <span>{TEXT.rows}</span>
            </div>
            <div>
              <b>{result.rows.length}</b>
              <span>{TEXT.reviewedRows}</span>
            </div>
            <div>
              <b>{result.issue_summary.length}</b>
              <span>{TEXT.issueTypes}</span>
            </div>
          </div>
          <pre>{result.report_markdown}</pre>
        </div>
      ) : (
        <div className="empty">{TEXT.uploadHint}</div>
      )}
    </section>
  )
}

function PolicyKnowledge() {
  const [question, setQuestion] = useState('\u6807\u9898\u53ef\u4ee5\u5199\u5168\u7f51\u6700\u4f4e\u5417\uff1f')
  const [result, setResult] = useState<any>(null)

  async function ask() {
    setResult(await policyQa(question))
  }

  return (
    <section className="workspace oneColumn">
      <div className="paneHeader">
        <h2>{TEXT.policy}</h2>
        <button onClick={ask}>{TEXT.queryRule}</button>
      </div>
      <input
        className="question"
        value={question}
        onChange={(event) => setQuestion(event.target.value)}
      />
      {result ? (
        <div className="report">
          <p>{result.answer}</p>
          <h3>{TEXT.evidenceSnippets}</h3>
          {result.hits.map((hit: any) => (
            <pre key={hit.chunk_id}>
              {hit.title} #{hit.rank}
              {'\n'}
              {hit.text}
            </pre>
          ))}
        </div>
      ) : null}
    </section>
  )
}

function TracePage() {
  const [events, setEvents] = useState<any[]>([])
  const [running, setRunning] = useState(false)

  async function runTrace() {
    setEvents([])
    setRunning(true)
    try {
      const result = await reviewSingle(sampleProduct)
      const socket = new WebSocket(traceSocketUrl(result.trace_id))
      socket.onmessage = (event) => {
        const message = JSON.parse(event.data)
        setEvents((items) => [...items, message])
        if (message.event === 'final_result' || message.event === 'error') {
          setRunning(false)
          socket.close()
        }
      }
      socket.onerror = () => {
        setRunning(false)
      }
    } catch (err) {
      setEvents([{ event: 'error', payload: { message: err instanceof Error ? err.message : String(err) } }])
      setRunning(false)
    }
  }

  return (
    <section className="workspace oneColumn">
      <div className="paneHeader">
        <h2>{TEXT.trace}</h2>
        <button onClick={runTrace} disabled={running}>
          {running ? TEXT.traceRunning : TEXT.runTrace}
        </button>
      </div>
      <ol className="eventStream">
        {events.map((event, idx) => (
          <li key={idx}>
            <span>{event.event}</span>
            <pre>{pretty(event.payload || event.result || event.message || {})}</pre>
          </li>
        ))}
      </ol>
    </section>
  )
}

export default function App() {
  const [tab, setTab] = useState<Tab>('single')

  return (
    <main>
      <header className="topbar">
        <div>
          <h1>CatalogOps-Agent</h1>
          <p>{TEXT.governanceDesk}</p>
        </div>
        <nav>
          {tabs.map((item) => (
            <button
              key={item.id}
              className={tab === item.id ? 'active' : ''}
              onClick={() => setTab(item.id)}
            >
              {item.label}
            </button>
          ))}
        </nav>
      </header>
      {tab === 'single' ? <SingleReview /> : null}
      {tab === 'batch' ? <BatchReview /> : null}
      {tab === 'policy' ? <PolicyKnowledge /> : null}
      {tab === 'trace' ? <TracePage /> : null}
    </main>
  )
}
