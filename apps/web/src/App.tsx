import { useEffect, useState, type FormEvent } from 'react'

type Source = {id:string; provider:string; account_alias:string; sync_mode:string; coverage:string; last_sync_at:string|null}
type Conversation = {id:string; title:string; provider:string; account_alias:string; message_count:number; external_id:string; project_id:string|null}
type Project = {id:string; name:string}
type Hit = {message_id:string; provider:string; account_alias:string; title:string; content:string; occurred_at:string|null}
type Receipt = {counts:{messages_inserted:number; messages_duplicates:number}}
type Page = 'overview'|'search'|'conversations'|'projects'|'connections'

async function api<T>(path:string, init?:RequestInit):Promise<T> {
  const res = await fetch('/api/v1' + path, init)
  if (!res.ok) {
    const raw = await res.json().catch(() => null) as {detail?:string}|null
    throw new Error(raw?.detail || 'Request failed (' + res.status + ')')
  }
  return await res.json() as T
}

const tabs: {id:Page; label:string}[] = [
  {id:'overview',label:'Overview'}, {id:'search',label:'Universal Search'},
  {id:'conversations',label:'Conversations'}, {id:'projects',label:'Projects'},
  {id:'connections',label:'Connections'}
]

export default function App() {
  const [page,setPage] = useState<Page>('overview')
  const [sources,setSources] = useState<Source[]>([])
  const [convos,setConvos] = useState<Conversation[]>([])
  const [projects,setProjects] = useState<Project[]>([])
  const [hits,setHits] = useState<Hit[]>([])
  const [query,setQuery] = useState('')
  const [provider,setProvider] = useState('chatgpt')
  const [alias,setAlias] = useState('personal')
  const [file,setFile] = useState<File|null>(null)
  const [projectName,setProjectName] = useState('')
  const [notice,setNotice] = useState('')
  const [receipt,setReceipt] = useState<Receipt|null>(null)
  const [busy,setBusy] = useState(false)

  async function reload() {
    try {
      const [a,b,c] = await Promise.all([
        api<{items:Source[]}>('/sources'),
        api<{items:Conversation[]}>('/conversations'),
        api<{items:Project[]}>('/projects')
      ])
      setSources(a.items); setConvos(b.items); setProjects(c.items)
    } catch (err) { setNotice(String(err)) }
  }
  useEffect(() => { void reload() }, [])

  async function importFile(event:FormEvent) {
    event.preventDefault()
    if (!file) return
    setBusy(true); setNotice('')
    try {
      const form = new FormData()
      form.set('provider',provider)
      form.set('account_alias',alias)
      form.set('file',file)
      setReceipt(await api<Receipt>('/imports',{method:'POST',body:form}))
      await reload()
    } catch (err) { setNotice(String(err)) }
    finally { setBusy(false) }
  }

  async function search(event:FormEvent) {
    event.preventDefault()
    setBusy(true)
    try {
      const param = new URLSearchParams({q:query})
      setHits((await api<{items:Hit[]}>('/search?' + param.toString())).items)
      setNotice('')
    } catch (err) { setNotice(String(err)) }
    finally { setBusy(false) }
  }

  async function addProject(event:FormEvent) {
    event.preventDefault()
    try {
      await api('/projects', {method:'POST',headers:{'Content-Type':'application/json'},
        body:JSON.stringify({name:projectName})})
      setProjectName('')
      await reload()
    } catch (err) { setNotice(String(err)) }
  }

  async function mapProject(id:string,projectId:string) {
    try {
      await api('/conversations/' + encodeURIComponent(id), {
        method:'PATCH',headers:{'Content-Type':'application/json'},
        body:JSON.stringify({project_id:projectId || null})
      })
      await reload()
    } catch (err) { setNotice(String(err)) }
  }

  return <div className="layout">
    <aside className="sidebar">
      <div className="brand"><div className="symbol">N</div><div><b>ARK NEXUS</b><small>MULTI-AI WORKSPACE</small></div></div>
      <div className="navtitle">WORKSPACE</div>
      {tabs.map(t => <button type="button" className={page===t.id?'tab active':'tab'} key={t.id} onClick={()=>setPage(t.id)}>{t.label}</button>)}
      <div className="sidebottom"><span className="dot"/> LOCAL-FIRST<br/><small>V1 / SYNTHETIC ONLY</small></div>
    </aside>
    <main>
      <header className="topbar"><span>WORKSPACE / {page.toUpperCase()}</span><span className="pill">OFFLINE BASELINE</span></header>
      <div className="body">
        {notice && <div className="error" role="alert">{notice} <button onClick={()=>setNotice('')}>×</button></div>}
        <p className="eyebrow">ARK NEXUS · V1</p>
        <h1>{page==='overview'?'Intelligence, connected.':page==='search'?'Universal Search':page==='conversations'?'Conversation Library':page==='projects'?'Project Registry':'Source Connections'}</h1>
        <p className="intro">複数AIの履歴と作業を、出典を保ったままローカルで統合するための開発用ワークスペース。</p>
        <div className="warning"><b>制限事項:</b> 合成テスト用フィクスチャだけに対応しています。実際のChatGPT・Claude履歴、自動同期、Work/Codex/Claude Code実行、AIへの指示送信はまだ未対応です。</div>

        {page==='overview' && <>
          <section className="stats">
            <div><small>SOURCES</small><strong>{sources.length}</strong><span>registered</span></div>
            <div><small>CONVERSATIONS</small><strong>{convos.length}</strong><span>normalized</span></div>
            <div><small>MESSAGES</small><strong>{convos.reduce((n,c)=>n+c.message_count,0)}</strong><span>indexed</span></div>
            <div><small>PROJECTS</small><strong>{projects.length}</strong><span>manual mapping</span></div>
          </section>
          <section className="panels">
            <article className="panel">
              <h2>Import History <span className="chip">MANUAL</span></h2>
              <p>合成JSONまたはZIPのみ。個人の実データは使用しないでください。</p>
              <form onSubmit={importFile}>
                <label>Source<select value={provider} onChange={e=>setProvider(e.target.value)}><option value="chatgpt">ChatGPT synthetic</option><option value="claude">Claude synthetic</option></select></label>
                <label>Account alias<input value={alias} onChange={e=>setAlias(e.target.value)} required /></label>
                <label>Fixture<input type="file" accept=".json,.zip" onChange={e=>setFile(e.target.files?.[0]||null)} required /></label>
                <button className="primary" disabled={busy||!file}>Import and verify →</button>
              </form>
              {receipt && <p className="success">Inserted {receipt.counts.messages_inserted} messages; skipped {receipt.counts.messages_duplicates} duplicates.</p>}
            </article>
            <article className="panel"><h2>Sources <span className="chip">{sources.length} REGISTERED</span></h2>
              {sources.length===0?<p className="muted">No sources yet. Import a synthetic fixture.</p>:
                sources.map(s=><div key={s.id} className="line"><b>{s.provider}</b> {s.account_alias} <small>Manual · partial</small></div>)}
              <p className="muted">No OAuth or paid provider API is required for this version.</p>
            </article>
          </section>
        </>}

        {page==='search' && <>
          <article className="panel">
            <form className="searchform" onSubmit={search}>
              <input value={query} onChange={e=>setQuery(e.target.value)} placeholder="Search imported messages…" />
              <button className="primary" disabled={busy}>Search</button>
            </form>
            <h2>{hits.length} results</h2>
            {hits.map(h=><div className="searchresult" key={h.message_id}><small>{h.provider.toUpperCase()} · {h.account_alias} · {h.occurred_at || 'Unknown date'}</small><h3>{h.title}</h3><p>{h.content}</p></div>)}
          </article>
        </>}

        {page==='conversations' && <article className="panel">
          <h2>{convos.length} conversations</h2>
          {convos.map(c=><div className="conversation" key={c.id}>
            <div><b>{c.title}</b><small>{c.provider} · {c.account_alias} · {c.message_count} messages · Source {c.external_id}</small></div>
            <select aria-label={'Project for '+c.title} value={c.project_id || ''} onChange={e=>void mapProject(c.id,e.target.value)}>
              <option value="">Unassigned</option>{projects.map(p=><option key={p.id} value={p.id}>{p.name}</option>)}
            </select>
          </div>)}
        </article>}

        {page==='projects' && <>
          <article className="panel"><h2>Create a project</h2>
            <form className="searchform" onSubmit={addProject}><input value={projectName} onChange={e=>setProjectName(e.target.value)} placeholder="Project name" required /><button className="primary">Add</button></form>
          </article>
          <section className="panels">{projects.map(p=><article className="panel" key={p.id}><h2>{p.name}</h2><p>{convos.filter(c=>c.project_id===p.id).length} mapped conversations</p></article>)}</section>
        </>}

        {page==='connections' && <article className="panel"><h2>Connection capabilities</h2>
          <div className="line"><b>ChatGPT consumer</b><span>Synthetic import only</span><small>No live sync</small></div>
          <div className="line"><b>Claude consumer</b><span>Synthetic import only</span><small>No live sync</small></div>
          <div className="line"><b>ChatGPT Work</b><span>Pending technical validation</span><small>Not connected</small></div>
          <div className="line"><b>Codex / Claude Code</b><span>V2–V4 candidate</span><small>Not connected</small></div>
        </article>}
        <footer>ARK NEXUS / V1 · NO LIVE SYNC · NO EXTERNAL COMMANDS · LOCAL DATA ONLY</footer>
      </div>
    </main>
  </div>
}
