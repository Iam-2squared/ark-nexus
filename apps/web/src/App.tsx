import { useEffect, useRef, useState, type FormEvent } from 'react'

type PageData<T> = {items:T[]; total:number; offset:number; next_offset:number|null}
type Source = {id:string; provider:string; account_alias:string; connection_state:string; data_kind:string; last_sync_at:string|null}
type Conversation = {id:string; title:string; provider:string; account_alias:string; message_count:number; external_id:string; project_id:string|null}
type Project = {id:string; name:string; conversation_count:number}
type Hit = {message_id:string; external_message_id:string; provider:string; account_alias:string; title:string; content:string; occurred_at:string|null}
type Message = {id:string; external_id:string; role:string; content:string; occurred_at:string|null}
type Counts = {sources:number; conversations:number; messages:number; projects:number; imports:number}
type ImportCounts = {messages_inserted:number; messages_duplicates:number}
type Receipt = {id:string; provider:string; account_alias:string; started_at:string; counts:ImportCounts; parser_version:string; data_kind:string; status:string}
type ImportResult = {status:string; counts?:ImportCounts; conversations?:number; messages?:number; persisted?:boolean}
type Connection = {id:string; label:string; connection_state:string; implemented:boolean; execution_enabled:boolean; official:Record<string,string>; obtainable:string; latency:string; permissions:string}
type Page = 'overview'|'search'|'conversations'|'projects'|'connections'|'imports'
const emptyPage = <T,>():PageData<T> => ({items:[],total:0,offset:0,next_offset:null})

class ApiError extends Error {
  constructor(message:string, public status:number) { super(message) }
}

async function api<T>(path:string, init?:RequestInit):Promise<T> {
  const headers = new Headers(init?.headers)
  const key = sessionStorage.getItem('nexus-local-key')
  if (key) headers.set('Authorization','Bearer '+key)
  if (init?.method && ['POST','PATCH','PUT','DELETE'].includes(init.method)) headers.set('X-Nexus-Request','1')
  const res = await fetch('/api/v1' + path, {...init,headers,cache:'no-store'})
  if (!res.ok) {
    const raw = await res.json().catch(() => null) as {detail?:unknown}|null
    throw new ApiError(typeof raw?.detail==='string' ? raw.detail : 'Request failed (' + res.status + ')',res.status)
  }
  return await res.json() as T
}

const tabs: {id:Page; label:string}[] = [
  {id:'overview',label:'Overview'}, {id:'conversations',label:'Conversations'},
  {id:'search',label:'Universal Search'}, {id:'projects',label:'Projects'},
  {id:'connections',label:'Sources / Connections'}, {id:'imports',label:'Import History'}
]
const headings:Record<Page,string> = {overview:'Intelligence, connected.',search:'Universal Search',
  conversations:'Conversation Library',projects:'Project Registry',connections:'Sources / Connections',imports:'Import History'}
const time = (value:string|null) => value ? new Date(value).toLocaleString('ja-JP') : '日時未提供'
const errorText = (err:unknown) => err instanceof Error ? err.message : 'Request failed'

export default function App() {
  const [page,setPage] = useState<Page>('overview')
  const [sources,setSources] = useState<Source[]>([])
  const [convos,setConvos] = useState<PageData<Conversation>>(emptyPage)
  const [projects,setProjects] = useState<Project[]>([])
  const [connections,setConnections] = useState<Connection[]>([])
  const [imports,setImports] = useState<PageData<Receipt>>(emptyPage)
  const [counts,setCounts] = useState<Counts|null>(null)
  const [hits,setHits] = useState<PageData<Hit>>(emptyPage)
  const [query,setQuery] = useState('')
  const [sourceFilter,setSourceFilter] = useState('')
  const [projectFilter,setProjectFilter] = useState('')
  const [searchParams,setSearchParams] = useState<URLSearchParams|null>(null)
  const [searchStatus,setSearchStatus] = useState<'idle'|'loading'|'success'|'error'>('idle')
  const [provider,setProvider] = useState('chatgpt')
  const [alias,setAlias] = useState('personal')
  const [file,setFile] = useState<File|null>(null)
  const [dryRun,setDryRun] = useState(false)
  const [projectName,setProjectName] = useState('')
  const [notice,setNotice] = useState('')
  const [result,setResult] = useState<ImportResult|null>(null)
  const [busy,setBusy] = useState(false)
  const [loading,setLoading] = useState(true)
  const [apiState,setApiState] = useState<'loading'|'ready'|'unavailable'|'locked'>('loading')
  const [accessInput,setAccessInput] = useState('')
  const [updatedAt,setUpdatedAt] = useState<string|null>(null)
  const [selected,setSelected] = useState<Conversation|null>(null)
  const [messages,setMessages] = useState<PageData<Message>|null>(null)
  const [integrity,setIntegrity] = useState<{ok:boolean; checks:Record<string,number>}|null>(null)
  const searchRun = useRef(0)
  const loadRun = useRef(0)

  function lockWorkspace() {
    loadRun.current++; searchRun.current++
    sessionStorage.removeItem('nexus-local-key')
    setApiState('locked'); setLoading(false); setBusy(false)
    setCounts(null); setSources([]); setConvos(emptyPage()); setProjects([])
    setConnections([]); setImports(emptyPage()); setHits(emptyPage()); setSearchParams(null)
    setSearchStatus('idle'); setSelected(null); setMessages(null); setResult(null)
    setIntegrity(null); setUpdatedAt(null)
  }

  async function unlock(event:FormEvent) {
    event.preventDefault(); setNotice('')
    sessionStorage.setItem('nexus-local-key',accessInput.trim())
    setAccessInput('')
    await reload()
  }

  function reportError(err:unknown) {
    if (err instanceof ApiError && err.status===401) {
      lockWorkspace(); setNotice('ローカルアクセスキーを確認してください。')
    } else setNotice(errorText(err))
  }

  async function reload() {
    const run = ++loadRun.current
    setLoading(true)
    try {
      const [a,b,c,d,e,f] = await Promise.all([
        api<{items:Source[]}>('/sources'), api<PageData<Conversation>>('/conversations'),
        api<{items:Project[]}>('/projects'), api<{counts:Counts}>('/overview'),
        api<PageData<Receipt>>('/imports'), api<{items:Connection[]}>('/connections')
      ])
      if (run!==loadRun.current) return
      setSources(a.items); setConvos(b); setProjects(c.items); setCounts(d.counts)
      setImports(e); setConnections(f.items); setApiState('ready')
      setUpdatedAt(new Date().toISOString())
      setIntegrity(null)
    } catch (err) {
      if (run!==loadRun.current) return
      if (err instanceof ApiError && err.status===401) {
        lockWorkspace(); setNotice('ローカルアクセスキーを確認してください。'); return
      }
      setApiState('unavailable'); setNotice(errorText(err))
    } finally { if (run===loadRun.current) setLoading(false) }
  }
  useEffect(() => {
    if (sessionStorage.getItem('nexus-local-key')) void reload()
    else { setApiState('locked'); setLoading(false) }
  }, [])

  async function importFile(event:FormEvent) {
    event.preventDefault()
    if (!file) return
    setBusy(true); setNotice(''); setResult(null)
    try {
      if (file.size > 8*1024*1024) throw new Error('ファイル上限は8 MiBです。')
      const form = new FormData()
      form.set('provider',provider); form.set('account_alias',alias)
      form.set('file',file); form.set('dry_run',String(dryRun))
      const response = await api<ImportResult>('/imports',{method:'POST',body:form})
      setResult(response)
      if (response.status!=='dry_run') { setSelected(null); setMessages(null); await reload() }
    } catch (err) { reportError(err) }
    finally { setBusy(false) }
  }

  async function runSearch(params:URLSearchParams, append=false) {
    const run = ++searchRun.current
    setBusy(true); setNotice(''); setSearchStatus('loading')
    try {
      const response = await api<PageData<Hit>>('/search?' + params.toString())
      if (run===searchRun.current) {
        setHits(previous => append ? {...response,items:[...previous.items,...response.items]} : response)
        setSearchStatus('success')
      }
    } catch (err) { if (run===searchRun.current) {reportError(err); setSearchStatus('error')} }
    finally { if (run===searchRun.current) setBusy(false) }
  }
  async function search(event:FormEvent) {
    event.preventDefault()
    const params = new URLSearchParams({q:query})
    if (sourceFilter) params.set('source_id',sourceFilter)
    if (projectFilter) params.set('project_id',projectFilter)
    setSearchParams(params); setHits(emptyPage())
    await runSearch(params)
  }
  async function moreSearch() {
    if (!searchParams || hits.next_offset===null) return
    const params = new URLSearchParams(searchParams)
    params.set('offset',String(hits.next_offset))
    await runSearch(params,true)
  }

  async function addProject(event:FormEvent) {
    event.preventDefault(); setBusy(true); setNotice('')
    try {
      await api('/projects', {method:'POST',headers:{'Content-Type':'application/json'},
        body:JSON.stringify({name:projectName.trim()})})
      setProjectName(''); await reload()
    } catch (err) { reportError(err) }
    finally { setBusy(false) }
  }
  async function mapProject(id:string,projectId:string) {
    setBusy(true); setNotice('')
    try {
      await api('/conversations/' + encodeURIComponent(id), {
        method:'PATCH',headers:{'Content-Type':'application/json'},
        body:JSON.stringify({project_id:projectId || null})
      })
      await reload()
    } catch (err) { reportError(err) }
    finally { setBusy(false) }
  }

  async function moreConversations() {
    if (convos.next_offset===null) return
    setBusy(true)
    try {
      const response = await api<PageData<Conversation>>('/conversations?offset='+convos.next_offset)
      setConvos(previous => ({...response,items:[...previous.items,...response.items]}))
    } catch (err) { reportError(err) }
    finally { setBusy(false) }
  }
  async function openConversation(conversation:Conversation, offset=0) {
    setBusy(true); setNotice(''); setSelected(conversation)
    if (!offset) setMessages(null)
    try {
      const response = await api<PageData<Message>>('/conversations/'+encodeURIComponent(conversation.id)+'/messages?offset='+offset)
      setMessages(previous => offset && previous ? {...response,items:[...previous.items,...response.items]} : response)
    } catch (err) { reportError(err) }
    finally { setBusy(false) }
  }
  async function moreImports() {
    if (imports.next_offset===null) return
    setBusy(true)
    try {
      const response = await api<PageData<Receipt>>('/imports?offset='+imports.next_offset)
      setImports(previous => ({...response,items:[...previous.items,...response.items]}))
    } catch (err) { reportError(err) }
    finally { setBusy(false) }
  }
  async function checkIntegrity() {
    setBusy(true); setNotice('')
    try { setIntegrity(await api('/integrity')) }
    catch (err) { setNotice(errorText(err)) }
    finally { setBusy(false) }
  }

  const importer = <article className="panel">
    <h2>手動取り込み <span className="chip">SYNTHETIC</span></h2>
    <p>合成テスト用JSON・ZIPのみ。実エクスポートは未検証のため受け付けません。</p>
    <form onSubmit={importFile}>
      <label>Provider<select value={provider} onChange={e=>setProvider(e.target.value)}>
        <option value="chatgpt">ChatGPT synthetic</option><option value="claude">Claude synthetic</option>
      </select></label>
      <label>Account alias<input value={alias} onChange={e=>setAlias(e.target.value)} maxLength={100} required /></label>
      <label>Fixture · 上限8 MiB<input type="file" accept=".json,.zip" onChange={e=>setFile(e.target.files?.[0]||null)} required /></label>
      <label className="checkbox"><input type="checkbox" checked={dryRun} onChange={e=>setDryRun(e.target.checked)} />保存せず形式を検証</label>
      <button className="primary" disabled={busy||!file||apiState!=='ready'}>{dryRun?'Validate fixture':'Import fixture'}</button>
    </form>
    {result && <p className="success" role="status">{result.status==='dry_run'
      ? '検証完了: '+result.conversations+'会話 / '+result.messages+'メッセージ。保存0件。'
      : '保存 '+result.counts?.messages_inserted+'件 / 重複追加0件（既存 '+result.counts?.messages_duplicates+'件）。'}</p>}
  </article>

  return <div className="layout">
    <aside className="sidebar">
      <div className="brand"><div className="symbol">N</div><div><b>ARK NEXUS</b><small>MULTI-AI WORKSPACE</small></div></div>
      <div className="navtitle">WORKSPACE</div>
      {tabs.map(t => <button type="button" className={page===t.id?'tab active':'tab'} key={t.id} onClick={()=>setPage(t.id)}>{t.label}</button>)}
      <div className="sidebottom">LOCAL-FIRST<br/><small>V1 / SYNTHETIC ONLY</small></div>
    </aside>
    <main>
      <header className="topbar"><span>WORKSPACE / {page.toUpperCase()}</span>
        <span className={'pill '+(apiState==='unavailable'?'offline':'')}>{apiState==='ready'?'LOCAL API READY':apiState==='loading'?'CHECKING LOCAL API':apiState==='locked'?'LOCAL WORKSPACE LOCKED':'LOCAL API UNAVAILABLE'}</span>
      </header>
      <div className="body">
        {notice && <div className="error" role="alert">{notice} <button type="button" aria-label="Dismiss error" onClick={()=>setNotice('')}>×</button></div>}
        <p className="eyebrow">ARK NEXUS · V1 UNIFIED HISTORY</p>
        <h1>{headings[page]}</h1>
        <p className="intro">出典を保った会話履歴と、プロジェクトの作業状況をひとつのローカルワークスペースへ。</p>
        <div className="warning"><b>開発中:</b> 合成取り込みのみ実装済み。ChatGPT・Claude実形式の検証はBLOCKEDです。外部AIは未接続で、実行・自動同期は無効です。</div>
        {apiState==='locked' && <article className="panel"><h2>ローカルワークスペースを開く</h2>
          <p>このPCのNexusで発行したアクセスキーを入力してください。キーはこのタブのセッション内だけに保持します。</p>
          <form className="searchform" onSubmit={unlock}>
            <label className="accesslabel">Local access key<input type="password" value={accessInput} onChange={e=>setAccessInput(e.target.value)} autoComplete="off" minLength={32} maxLength={256} required /></label>
            <button className="primary" disabled={loading||accessInput.trim().length<32}>Unlock local workspace</button>
          </form>
        </article>}
        <div className="snapshot"><span>{loading?'取得中…':updatedAt?'取得時刻: '+time(updatedAt):'データ未取得'}
          {apiState==='unavailable' && updatedAt?' · 前回取得時の表示':''}</span>
          <div className="snapshotactions"><button type="button" className="secondary" disabled={loading||busy||apiState==='locked'} onClick={()=>void reload()}>Refresh</button>
            {apiState!=='locked' && <button type="button" className="secondary" disabled={loading||busy} onClick={lockWorkspace}>Lock workspace</button>}</div>
        </div>

        {page==='overview' && <>
          <section className="stats">
            {(['sources','conversations','messages','projects'] as const).map(key=>
              <div key={key}><small>{key.toUpperCase()}</small><strong>{counts?counts[key].toLocaleString():'—'}</strong><span>{key==='projects'?'manual mapping':'synthetic records'}</span></div>)}
          </section>
          <section className="panels">{importer}
            <article className="panel"><h2>保存済みSources <span className="chip">MANUAL</span></h2>
              {sources.length===0?<p className="muted">{counts?'保存済みSourceはありません。':'データ未取得。'}</p>:
                sources.map(s=><div key={s.id} className="line"><b>{s.provider}</b><span>{s.account_alias}</span><small>手動取り込み · 合成のみ</small></div>)}
              <p>外部プロバイダとの接続: 0件</p>
              <button type="button" className="secondary" disabled={busy||apiState!=='ready'} onClick={()=>void checkIntegrity()}>Check stored data integrity</button>
              {integrity && <p className={integrity.ok?'success':'error'} role="status">{integrity.ok?'保存済みデータの整合性: PASS':'保存済みデータの整合性: FAIL'}
                {' · 問題 '+Object.values(integrity.checks).reduce((a,b)=>a+b,0)+'件'}</p>}
              <p className="muted">整合性検査は保存済みレコードが対象です。プロバイダ側の履歴全件取得は未検証です。</p>
            </article>
          </section>
        </>}

        {page==='search' && <article className="panel">
          <form onSubmit={search}>
            <div className="searchform"><input aria-label="Search imported messages" value={query} maxLength={300} onChange={e=>setQuery(e.target.value)} placeholder="日本語・キーワードで検索" />
              <button className="primary" disabled={busy||apiState!=='ready'}>Search</button></div>
            <div className="filters">
              <label>Source<select value={sourceFilter} onChange={e=>setSourceFilter(e.target.value)}><option value="">All sources</option>
                {sources.map(s=><option value={s.id} key={s.id}>{s.provider} · {s.account_alias}</option>)}</select></label>
              <label>Project<select value={projectFilter} onChange={e=>setProjectFilter(e.target.value)}><option value="">All projects</option>
                {projects.map(p=><option value={p.id} key={p.id}>{p.name}</option>)}</select></label>
            </div>
          </form>
          <h2>{searchStatus==='success'?hits.total+' results · '+hits.items.length+' shown':searchStatus==='loading'?'検索中…':searchStatus==='error'?'検索失敗（最新結果は未取得）':'保存済み履歴を検索'}</h2>
          {hits.items.map(h=><div className="searchresult" key={h.message_id}><small>{h.provider.toUpperCase()} · {h.account_alias} · {time(h.occurred_at)} · Source message {h.external_message_id}</small><h3>{h.title}</h3><p>{h.content}</p></div>)}
          {hits.next_offset!==null && <button type="button" className="secondary" disabled={busy} onClick={()=>void moreSearch()}>Load more results</button>}
        </article>}

        {page==='conversations' && <>
          <article className="panel"><h2>{counts?convos.total+' conversations · '+convos.items.length+' shown':'データ未取得'}</h2>
            {convos.items.map(c=><div className="conversation" key={c.id}>
              <div><button type="button" className="textbutton" disabled={busy} onClick={()=>void openConversation(c)}>{c.title}</button>
                <small>{c.provider} · {c.account_alias} · {c.message_count} messages · Source {c.external_id}</small></div>
              <select aria-label={'Project for '+c.title} disabled={busy} value={c.project_id || ''} onChange={e=>void mapProject(c.id,e.target.value)}>
                <option value="">Unassigned</option>{projects.map(p=><option key={p.id} value={p.id}>{p.name}</option>)}
              </select>
            </div>)}
            {convos.next_offset!==null && <button type="button" className="secondary" disabled={busy} onClick={()=>void moreConversations()}>Load more conversations</button>}
          </article>
          {selected && <article className="panel"><h2>{selected.title}</h2><p>{selected.provider} · {selected.account_alias} · Source {selected.external_id}</p>
            {!messages?<p>{busy?'メッセージ取得中…':'メッセージ未取得。会話を選び直して再試行してください。'}</p>:<>
              <p>{messages.total} messages · {messages.items.length} shown</p>
              {messages.items.map(m=><div className="searchresult" key={m.id}><small>{m.role} · {time(m.occurred_at)} · Source message {m.external_id}</small><p>{m.content}</p></div>)}
              {messages.next_offset!==null && <button type="button" className="secondary" disabled={busy} onClick={()=>void openConversation(selected,messages.next_offset!)}>Load more messages</button>}
            </>}
          </article>}
        </>}

        {page==='projects' && <>
          <article className="panel"><h2>Create a project</h2>
            <form className="searchform" onSubmit={addProject}><input aria-label="Project name" value={projectName} maxLength={120} onChange={e=>setProjectName(e.target.value)} placeholder="Project name" required />
              <button className="primary" disabled={busy||!projectName.trim()||apiState!=='ready'}>Add</button></form>
          </article>
          <section className="panels">{projects.map(p=><article className="panel" key={p.id}><h2>{p.name}</h2><p>{p.conversation_count} mapped conversations</p></article>)}</section>
        </>}

        {page==='connections' && <>
          <article className="panel"><h2>登録済みSource</h2>
            {sources.length===0?<p>{counts?'未登録':'データ未取得'}</p>:sources.map(s=><div className="line" key={s.id}><b>{s.provider} · {s.account_alias}</b><span>手動取り込み / 合成</span><small>最終取り込み: {time(s.last_sync_at)}</small></div>)}
          </article>
          <section className="panels">{connections.map(c=><article className="panel" key={c.id}><h2>{c.label}<span className="chip">未接続</span></h2>
            <p>{c.id==='chatgpt'||c.id==='claude'?'Nexus: 合成取り込みのみ実装。実形式検証はBLOCKED。':'Nexus: Connector未実装 / AI実行無効。'}</p>
            <p>公式手段の調査: {c.official.history==='documented'?'履歴取得あり':c.official.history==='manual_export'?'手動エクスポート':'未確認'}</p>
            <p className="muted">{c.obtainable}</p><p className="muted">同期遅延: {c.latency}</p>
            <details><summary>必要権限・条件</summary><p>{c.permissions}</p></details>
          </article>)}</section>
        </>}

        {page==='imports' && <>
          {importer}
          <article className="panel"><h2>{counts?imports.total+' successful imports':'データ未取得'}</h2>
            <p>保存完了した取り込みの記録です。拒否した入力はロールバックし、内容を履歴に保存しません。</p>
            {imports.items.map(r=><div className="importreceipt" key={r.id}><div><b>{r.provider} · {r.account_alias}</b><span className="chip">合成 / 手動 / 保存済み</span></div>
              <p>{time(r.started_at)} · 保存 {r.counts.messages_inserted}件 / 既存 {r.counts.messages_duplicates}件</p>
              <small>Receipt {r.id} · {r.parser_version}</small>
            </div>)}
            {imports.next_offset!==null && <button type="button" className="secondary" disabled={busy} onClick={()=>void moreImports()}>Load more imports</button>}
          </article>
        </>}
        <footer>ARK NEXUS / V1 · NO LIVE SYNC · AI EXECUTION DISABLED · SYNTHETIC DATA ONLY</footer>
      </div>
    </main>
  </div>
}
