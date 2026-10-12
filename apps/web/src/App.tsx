import { useEffect, useRef, useState, type FormEvent } from 'react'
import { AppShell, MetricCard, OrbitPanel, SingularityHub, StarNav, StatusConstellation,
  type WorkspacePage } from './components/CosmicShell'

type PageData<T> = {items:T[]; total:number; offset:number; next_offset:number|null}
type Source = {id:string; provider:string; account_alias:string; connection_state:string; data_kind:string; last_sync_at:string|null; freshness?:string; not_connected_reason?:string}
type Conversation = {id:string; title:string; provider:string; account_alias:string; message_count:number; external_id:string; project_id:string|null}
type Project = {id:string; name:string; conversation_count:number}
type Hit = {message_id:string; external_message_id:string; provider:string; account_alias:string; title:string; content:string; occurred_at:string|null}
type Message = {id:string; external_id:string; role:string; content:string; occurred_at:string|null}
type Counts = {sources:number; conversations:number; messages:number; projects:number; imports:number}
type ImportCounts = {messages_inserted:number; messages_duplicates:number}
type Receipt = {id:string; provider:string; account_alias:string; started_at:string; counts:ImportCounts; parser_version:string; data_kind:string; status:string; import_hash?:string; coverage?:string; missing_records_possible?:boolean}
type ImportResult = {status:string; counts?:ImportCounts; conversations?:number; messages?:number; persisted?:boolean}
type Connection = {id:string; label:string; connection_state:string; implemented:boolean; execution_enabled:boolean; official:Record<string,string>; obtainable:string; latency:string; permissions:string; provider?:string; product?:string; capabilities?:Record<string,string>; not_connected_reason?:string}
type Page = WorkspacePage
type Operation = {kind:string; session:number; controller:AbortController}
const emptyPage = <T,>():PageData<T> => ({items:[],total:0,offset:0,next_offset:null})
function checkedPage<T>(value:PageData<T>,requestedOffset=0):PageData<T> {
  if(!value || !Array.isArray(value.items) || !Number.isSafeInteger(value.total) || value.total<value.items.length ||
    !Number.isSafeInteger(value.offset) || value.offset<0 ||
    (value.next_offset!==null && (!Number.isSafeInteger(value.next_offset) || value.next_offset<=Math.max(value.offset,requestedOffset))))
    throw new Error('ページ情報が不正です。Refreshで再取得してください。')
  return value
}
function appendPage<T>(previous:PageData<T>,response:PageData<T>,offset:number,key:(item:T)=>string):PageData<T> {
  checkedPage(response,offset)
  const items=[...new Map([...previous.items,...response.items].map(item=>[key(item),item])).values()]
  if(response.next_offset!==null && items.length<=previous.items.length)
    throw new Error('ページ取得が進みません。Refreshで再取得してください。')
  return {...response,items}
}

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
const headings:Record<Page,string> = {overview:'Your intelligence. In orbit.',search:'Universal Search',
  conversations:'Conversation Library',projects:'Project Registry',connections:'Sources / Connections',imports:'Import History'}
const time = (value:string|null) => value ? new Date(value).toLocaleString('ja-JP') : '日時未提供'
const errorText = (err:unknown) => err instanceof Error ? err.message : 'Request failed'
const locationPage = ():Page|null => {
  const value=window.location.hash.slice(1)
  if(!value) return 'overview'
  return tabs.some(tab=>tab.id===value)?value as Page:null
}
const conversationParams = (source:string,project:string,offset?:number) => {
  const params=new URLSearchParams()
  if(source) params.set('source_id',source)
  if(project) params.set('project_id',project)
  if(offset!==undefined) params.set('offset',String(offset))
  return params.size?'?'+params.toString():''
}

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
  const [conversationSource,setConversationSource] = useState('')
  const [conversationProject,setConversationProject] = useState('')
  const [conversationStatus,setConversationStatus] = useState<'idle'|'loading'|'success'|'error'>('idle')
  const [searchParams,setSearchParams] = useState<URLSearchParams|null>(null)
  const [searchStatus,setSearchStatus] = useState<'idle'|'loading'|'success'|'error'>('idle')
  const [provider,setProvider] = useState('chatgpt')
  const [alias,setAlias] = useState('personal')
  const [file,setFile] = useState<File|null>(null)
  const [dryRun,setDryRun] = useState(false)
  const [projectName,setProjectName] = useState('')
  const [notice,setNotice] = useState('')
  const [feedback,setFeedback] = useState('')
  const [result,setResult] = useState<ImportResult|null>(null)
  const [rejected,setRejected] = useState<{provider:string; at:string; status:number|null}|null>(null)
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
  const sessionRun = useRef(0)
  const fileInput = useRef<HTMLInputElement>(null)
  const activeOperation = useRef<Operation|null>(null)
  const loadPending = useRef(false)
  const controllers = useRef(new Set<AbortController>())

  function beginOperation(kind:string):Operation|null {
    // React may batch two submits before disabled controls reach the DOM.
    // This synchronous guard also rejects programmatic submits while locked.
    if(activeOperation.current || loadPending.current || apiState!=='ready') return null
    const operation={kind,session:sessionRun.current,controller:new AbortController()}
    activeOperation.current=operation; controllers.current.add(operation.controller)
    setBusy(true); setNotice(''); setFeedback('')
    return operation
  }
  const current = (operation:Operation) => activeOperation.current===operation && operation.session===sessionRun.current
  function finishOperation(operation:Operation) {
    controllers.current.delete(operation.controller)
    if(current(operation)) {activeOperation.current=null; setBusy(false)}
  }
  function cancelOperation(kind:string) {
    const operation=activeOperation.current
    if(operation?.kind!==kind) return
    operation.controller.abort(); controllers.current.delete(operation.controller)
    activeOperation.current=null; setBusy(false)
  }
  function resetSearch() {
    searchRun.current++; cancelOperation('search')
    setSearchParams(null); setHits(emptyPage()); setSearchStatus('idle')
  }
  function navigate(next:Page) {
    if(next!==page) window.history.pushState(null,'','#'+next)
    setPage(next)
  }

  function lockWorkspace() {
    loadRun.current++; searchRun.current++
    sessionRun.current++
    for(const controller of controllers.current) controller.abort()
    controllers.current.clear(); activeOperation.current=null; loadPending.current=false
    sessionStorage.removeItem('nexus-local-key')
    setApiState('locked'); setLoading(false); setBusy(false)
    setCounts(null); setSources([]); setConvos(emptyPage()); setProjects([])
    setConnections([]); setImports(emptyPage()); setHits(emptyPage()); setSearchParams(null)
    setSearchStatus('idle'); setSelected(null); setMessages(null); setResult(null)
    setIntegrity(null); setUpdatedAt(null); setRejected(null); setNotice('')
    setFeedback(''); setConversationSource(''); setConversationProject(''); setConversationStatus('idle')
    setQuery(''); setSourceFilter(''); setProjectFilter(''); setProjectName('')
    setAlias('personal'); setFile(null); setDryRun(false); setAccessInput('')
    if(fileInput.current) fileInput.current.value=''
  }

  async function unlock(event:FormEvent) {
    event.preventDefault()
    if(loadPending.current || activeOperation.current) return
    const key=accessInput.trim()
    if(key.length<32 || key.length>256) return
    setNotice('')
    sessionRun.current++
    sessionStorage.setItem('nexus-local-key',key)
    setAccessInput('')
    await reload()
  }

  function reportError(err:unknown) {
    if (err instanceof ApiError && err.status===401) {
      lockWorkspace(); setNotice('ローカルアクセスキーを確認してください。')
    } else setNotice(errorText(err))
  }

  async function reload() {
    if(loadPending.current || !sessionStorage.getItem('nexus-local-key')) return false
    loadPending.current=true
    const run = ++loadRun.current
    const session=sessionRun.current
    const controller=new AbortController()
    controllers.current.add(controller)
    const init={signal:controller.signal}
    const read=<T,>(path:string):Promise<T> => api<T>(path,init).catch(err=>{
      // Promise.all may already have rejected on an unrelated transport error.
      // A later authentication failure still invalidates this entire session.
      if(session===sessionRun.current && err instanceof ApiError && err.status===401) {
        lockWorkspace(); setNotice('ローカルアクセスキーを確認してください。')
      }
      throw err
    })
    setLoading(true); setFeedback(''); resetSearch(); setSelected(null); setMessages(null)
    try {
      const [a,b,c,d,e,f] = await Promise.all([
        read<{items:Source[]}>('/sources'), read<PageData<Conversation>>('/conversations'+conversationParams(conversationSource,conversationProject)),
        read<{items:Project[]}>('/projects'), read<{counts:Counts}>('/overview'),
        read<PageData<Receipt>>('/imports'), read<{items:Connection[]}>('/connections')
      ])
      if (run!==loadRun.current) return false
      const conversations=checkedPage(b), receipts=checkedPage(e)
      if(!Array.isArray(a.items) || !Array.isArray(c.items) || !Array.isArray(f.items)) throw new Error('取得データが不正です。Refreshで再取得してください。')
      setSources(a.items); setConvos(conversations); setProjects(c.items); setCounts(d.counts)
      setImports(receipts); setConnections(f.items); setApiState('ready')
      setConversationStatus('success')
      setUpdatedAt(new Date().toISOString())
      setIntegrity(null)
      return true
    } catch (err) {
      if (run!==loadRun.current) return false
      if (err instanceof ApiError && err.status===401) {
        lockWorkspace(); setNotice('ローカルアクセスキーを確認してください。'); return false
      }
      setApiState('unavailable'); setNotice(errorText(err))
      return false
    } finally {
      controllers.current.delete(controller)
      if (run===loadRun.current) {loadPending.current=false; setLoading(false)}
    }
  }
  useEffect(() => {
    if (sessionStorage.getItem('nexus-local-key')) void reload()
    else { setApiState('locked'); setLoading(false) }
    const restorePage=()=>{const next=locationPage(); if(next) setPage(next)}
    window.addEventListener('popstate',restorePage)
    window.addEventListener('hashchange',restorePage)
    return ()=>{
      window.removeEventListener('popstate',restorePage)
      window.removeEventListener('hashchange',restorePage)
      loadRun.current++; searchRun.current++; sessionRun.current++
      for(const controller of controllers.current) controller.abort()
      controllers.current.clear(); activeOperation.current=null; loadPending.current=false
    }
  }, [])

  async function importFile(event:FormEvent) {
    event.preventDefault()
    if (!file) return
    const operation=beginOperation('import')
    if(!operation) return
    setResult(null); setRejected(null)
    try {
      if (file.size > 8*1024*1024) throw new Error('ファイル上限は8 MiBです。')
      if (!file.size) throw new Error('空のファイルは取り込めません。')
      if (!alias.trim() || alias.trim().length>100) throw new Error('Account aliasは1〜100文字で入力してください。')
      const form = new FormData()
      form.set('provider',provider); form.set('account_alias',alias.trim())
      form.set('file',file); form.set('dry_run',String(dryRun))
      const response = await api<ImportResult>('/imports',{method:'POST',body:form,signal:operation.controller.signal})
      if(!current(operation)) return
      setResult(response)
      if (response.status!=='dry_run') await reload()
    } catch (err) {
      if(current(operation)) {
        if(!(err instanceof ApiError && err.status===401))
          setRejected({provider,at:new Date().toISOString(),status:err instanceof ApiError?err.status:null})
        reportError(err)
      }
    }
    finally { finishOperation(operation) }
  }

  async function runSearch(params:URLSearchParams, append=false) {
    const operation=beginOperation('search')
    if(!operation) return
    const run = ++searchRun.current
    setSearchStatus('loading')
    try {
      const response = await api<PageData<Hit>>('/search?' + params.toString(),{signal:operation.controller.signal})
      if (run===searchRun.current && current(operation)) {
        setHits(append?appendPage(hits,response,Number(params.get('offset') || 0),hit=>hit.message_id):checkedPage(response))
        setSearchStatus('success')
      }
    } catch (err) { if (run===searchRun.current && current(operation)) {
      reportError(err); if(run===searchRun.current) setSearchStatus('error')
    } }
    finally { finishOperation(operation) }
  }
  async function search(event:FormEvent) {
    event.preventDefault()
    if(activeOperation.current || loadPending.current || apiState!=='ready' || !query.trim()) return
    const params = new URLSearchParams({q:query.trim()})
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
    event.preventDefault()
    if(!projectName.trim()) return
    const operation=beginOperation('project')
    if(!operation) return
    try {
      await api('/projects', {method:'POST',headers:{'Content-Type':'application/json'},
        body:JSON.stringify({name:projectName.trim()}),signal:operation.controller.signal})
      if(!current(operation)) return
      setProjectName(''); await reload()
      if(current(operation)) setFeedback('プロジェクトを作成しました。')
    } catch (err) { if(current(operation)) reportError(err) }
    finally { finishOperation(operation) }
  }
  async function mapProject(id:string,projectId:string) {
    const operation=beginOperation('project-map')
    if(!operation) return
    try {
      await api('/conversations/' + encodeURIComponent(id), {
        method:'PATCH',headers:{'Content-Type':'application/json'},
        body:JSON.stringify({project_id:projectId || null}),signal:operation.controller.signal
      })
      if(!current(operation)) return
      await reload()
      if(current(operation)) setFeedback(projectId?'プロジェクト割当を保存しました。':'プロジェクト割当を解除しました。')
    } catch (err) { if(current(operation)) reportError(err) }
    finally { finishOperation(operation) }
  }

  async function filterConversations(source:string,project:string) {
    cancelOperation('conversation-filter')
    const operation=beginOperation('conversation-filter')
    if(!operation) return
    setConversationSource(source); setConversationProject(project)
    setConvos(emptyPage()); setSelected(null); setMessages(null); setConversationStatus('loading')
    try {
      const response=await api<PageData<Conversation>>('/conversations'+conversationParams(source,project),{signal:operation.controller.signal})
      if(!current(operation)) return
      setConvos(checkedPage(response)); setConversationStatus('success')
    } catch(err) {
      if(current(operation)) {reportError(err); if(current(operation)) setConversationStatus('error')}
    } finally {finishOperation(operation)}
  }

  async function moreConversations() {
    if (convos.next_offset===null) return
    const operation=beginOperation('conversation-page')
    if(!operation) return
    try {
      const response = await api<PageData<Conversation>>('/conversations'+conversationParams(conversationSource,conversationProject,convos.next_offset),{signal:operation.controller.signal})
      if(!current(operation)) return
      setConvos(appendPage(convos,response,convos.next_offset,conversation=>conversation.id))
    } catch (err) { if(current(operation)) reportError(err) }
    finally { finishOperation(operation) }
  }
  async function openConversation(conversation:Conversation, offset=0) {
    const operation=beginOperation('messages')
    if(!operation) return
    setSelected(conversation)
    if (!offset) setMessages(null)
    try {
      const response = await api<PageData<Message>>('/conversations/'+encodeURIComponent(conversation.id)+'/messages?offset='+offset,{signal:operation.controller.signal})
      if(!current(operation)) return
      setMessages(offset && messages?appendPage(messages,response,offset,message=>message.id):checkedPage(response,offset))
    } catch (err) { if(current(operation)) reportError(err) }
    finally { finishOperation(operation) }
  }
  async function moreImports() {
    if (imports.next_offset===null) return
    const operation=beginOperation('import-page')
    if(!operation) return
    try {
      const response = await api<PageData<Receipt>>('/imports?offset='+imports.next_offset,{signal:operation.controller.signal})
      if(!current(operation)) return
      setImports(appendPage(imports,response,imports.next_offset,receipt=>receipt.id))
    } catch (err) { if(current(operation)) reportError(err) }
    finally { finishOperation(operation) }
  }
  async function checkIntegrity() {
    const operation=beginOperation('integrity')
    if(!operation) return
    setIntegrity(null)
    try {
      const response = await api<{ok:boolean; checks:Record<string,number>}>('/integrity',{signal:operation.controller.signal})
      if(current(operation)) setIntegrity(response)
    }
    catch (err) { if(current(operation)) reportError(err) }
    finally { finishOperation(operation) }
  }

  const controlsDisabled=busy || loading || apiState!=='ready'
  const clearImportAttempt=()=>{setResult(null); setRejected(null)}

  const importer = <article className="panel">
    <h2>手動取り込み <span className="chip">SYNTHETIC</span></h2>
    <p>合成テスト用JSON・ZIPのみ。実エクスポートは未検証のため受け付けません。</p>
    <form onSubmit={importFile} aria-busy={activeOperation.current?.kind==='import'}>
      <label>Provider<select disabled={controlsDisabled} value={provider} onChange={e=>{setProvider(e.target.value); clearImportAttempt()}}>
        <option value="chatgpt">ChatGPT synthetic</option><option value="claude">Claude synthetic</option>
      </select></label>
      <label>Account alias<input disabled={controlsDisabled} value={alias} onChange={e=>{setAlias(e.target.value); clearImportAttempt()}} maxLength={100} required /></label>
      <label>Fixture · 上限8 MiB<input disabled={controlsDisabled} ref={fileInput} type="file" accept=".json,.zip" onChange={e=>{setFile(e.target.files?.[0]||null); clearImportAttempt()}} required /></label>
      <label className="checkbox"><input disabled={controlsDisabled} type="checkbox" checked={dryRun} onChange={e=>{setDryRun(e.target.checked); clearImportAttempt()}} />保存せず形式を検証</label>
      <button className="primary" disabled={controlsDisabled||!file}>{dryRun?'Validate fixture':'Import fixture'}</button>
    </form>
    {result && <p className="success" role="status" aria-label="Import result">{result.status==='dry_run'
      ? '検証完了: '+result.conversations+'会話 / '+result.messages+'メッセージ。保存0件。'
      : '保存 '+result.counts?.messages_inserted+'件 / 重複追加0件（既存 '+result.counts?.messages_duplicates+'件）。'}</p>}
  </article>

  return <AppShell page={page} apiState={apiState}>
        {notice && <div className="error" role="alert">{notice} <button type="button" aria-label="Dismiss error" onClick={()=>setNotice('')}>×</button></div>}
        <div className={'page-heading '+(page==='overview'?'home-heading':'')}>
          <div><p className="eyebrow">ARK NEXUS <span> / </span> V1 UNIFIED HISTORY</p>
            <h1>{headings[page]}</h1><p className="intro">対話と知性が、ひとつの軌道に。<br/>出典を保った履歴を、このPCのワークスペースへ。</p></div>
          {page==='overview'?<div className="universe-note" aria-hidden="true"><span>WHITE SPACE / 01</span>
            <p>A quiet space<br/>for connected thinking.</p><span className="note-line" /></div>:null}
        </div>
        <section className={'workspace-map '+(page==='overview'?'orbit-map':'compact-map')}>
          <StarNav routes={tabs} page={page} onNavigate={navigate} />{page==='overview'?<SingularityHub />:null}
        </section>
        {page==='overview'?<>
          <section className="stats" aria-label="Stored history metrics">
            {(['sources','conversations','messages','projects'] as const).map((key,index)=>
              <MetricCard key={key} label={key.toUpperCase()} value={counts?counts[key]:null}
                detail={key==='projects'?'manual mapping':'synthetic records'} index={index} />)}
          </section><StatusConstellation />
        </>:null}
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
            {apiState!=='locked' && <button type="button" className="secondary" onClick={lockWorkspace}>Lock workspace</button>}</div>
        </div>
        {feedback && <p className="success" aria-live="polite" aria-atomic="true">{feedback}</p>}

        {page==='overview' && <>
          <section className="panels">{importer}
            <OrbitPanel><h2>保存済みSources <span className="chip">MANUAL</span></h2>
              {sources.length===0?<p className="muted">{counts?'保存済みSourceはありません。':'データ未取得。'}</p>:
                sources.map(s=><div key={s.id} className="line"><b>{s.provider}</b><span>{s.account_alias}</span><small>手動取り込み · 合成のみ</small></div>)}
              <p>外部プロバイダとの接続: 0件</p>
              <button type="button" className="secondary" disabled={busy||apiState!=='ready'} onClick={()=>void checkIntegrity()}>Check stored data integrity</button>
              {integrity && <p className={integrity.ok?'success':'error'} role="status" aria-label="Stored data integrity">{integrity.ok?'保存済みデータの整合性: PASS':'保存済みデータの整合性: FAIL'}
                {' · 問題 '+Object.values(integrity.checks).reduce((a,b)=>a+b,0)+'件'}</p>}
              <p className="muted">整合性検査は保存済みレコードが対象です。プロバイダ側の履歴全件取得は未検証です。</p>
            </OrbitPanel>
          </section>
        </>}

        {page==='search' && <article className="panel" aria-busy={searchStatus==='loading'}>
          <form onSubmit={search}>
            <div className="searchform"><input aria-label="Search imported messages" value={query} maxLength={300} onChange={e=>{setQuery(e.target.value); resetSearch()}} placeholder="日本語・キーワードで検索" />
              <button className="primary" disabled={controlsDisabled||!query.trim()}>Search</button></div>
            <div className="filters">
              <label>Source<select aria-label="Source" value={sourceFilter} onChange={e=>{setSourceFilter(e.target.value); resetSearch()}}><option value="">All sources</option>
                {sources.map(s=><option value={s.id} key={s.id}>{s.provider} · {s.account_alias}</option>)}</select></label>
              <label>Project<select aria-label="Project" value={projectFilter} onChange={e=>{setProjectFilter(e.target.value); resetSearch()}}><option value="">All projects</option>
                {projects.map(p=><option value={p.id} key={p.id}>{p.name}</option>)}</select></label>
            </div>
          </form>
          <h2 aria-live="polite" aria-atomic="true">{searchStatus==='success'?hits.total+' results · '+hits.items.length+' shown':searchStatus==='loading'?'検索中…':searchStatus==='error'?'検索失敗（最新結果は未取得）':'保存済み履歴を検索'}</h2>
          {searchStatus==='idle' && <p className="muted">キーワードと条件を指定し、Searchを押してください。条件変更とRefreshで前回結果をクリアします。</p>}
          {searchStatus==='success' && hits.total===0 && <p className="muted">条件に一致する保存済みメッセージはありません。キーワードやフィルターを変更してください。</p>}
          {searchStatus==='error' && hits.items.length>0 && <p className="muted">追加取得に失敗しました。表示中の結果は直前の取得分です。Load more resultsで再試行できます。</p>}
          {hits.items.map(h=><div className="searchresult" key={h.message_id}><small>{h.provider.toUpperCase()} · {h.account_alias} · {time(h.occurred_at)} · Source message {h.external_message_id}</small><h3>{h.title}</h3><p>{h.content}</p></div>)}
          {hits.next_offset!==null && <button type="button" className="secondary" disabled={controlsDisabled} onClick={()=>void moreSearch()}>Load more results</button>}
        </article>}

        {page==='conversations' && <>
          <article className="panel" aria-busy={activeOperation.current?.kind==='conversation-filter' || activeOperation.current?.kind==='conversation-page'}>
            <h2 aria-live="polite" aria-atomic="true">{conversationStatus==='loading'?'会話取得中…':conversationStatus==='error'?'会話取得失敗（最新結果は未取得）':counts?convos.total+' conversations · '+convos.items.length+' shown':'データ未取得'}</h2>
            <div className="filters">
              <label>Conversation source<select aria-label="Conversation source" disabled={controlsDisabled} value={conversationSource} onChange={e=>void filterConversations(e.target.value,conversationProject)}><option value="">All sources</option>
                {sources.map(s=><option value={s.id} key={s.id}>{s.provider} · {s.account_alias}</option>)}</select></label>
              <label>Conversation project<select aria-label="Conversation project" disabled={controlsDisabled} value={conversationProject} onChange={e=>void filterConversations(conversationSource,e.target.value)}><option value="">All projects</option>
                {projects.map(p=><option value={p.id} key={p.id}>{p.name}</option>)}</select></label>
            </div>
            {conversationStatus==='success' && convos.total===0 && <p className="muted">この条件の会話はありません。合成fixtureを取り込むか、フィルターを変更してください。</p>}
            {conversationStatus==='error' && <button type="button" className="secondary" disabled={controlsDisabled} onClick={()=>void filterConversations(conversationSource,conversationProject)}>Retry conversations</button>}
            {convos.items.map(c=><div className="conversation" key={c.id}>
              <div><button type="button" className="textbutton" disabled={controlsDisabled} onClick={()=>void openConversation(c)}>{c.title}</button>
                <small>{c.provider} · {c.account_alias} · {c.message_count} messages · Source {c.external_id}</small></div>
              <select aria-label={'Project for '+c.title} disabled={controlsDisabled} value={c.project_id || ''} onChange={e=>void mapProject(c.id,e.target.value)}>
                <option value="">Unassigned</option>{projects.map(p=><option key={p.id} value={p.id}>{p.name}</option>)}
              </select>
            </div>)}
            {convos.next_offset!==null && <button type="button" className="secondary" disabled={controlsDisabled} onClick={()=>void moreConversations()}>Load more conversations</button>}
          </article>
          {selected && <article className="panel" aria-busy={activeOperation.current?.kind==='messages'}><h2>{selected.title}</h2><p>{selected.provider} · {selected.account_alias} · Source {selected.external_id}</p>
            {!messages?<><p aria-live="polite">{busy?'メッセージ取得中…':'メッセージ未取得。Retry messagesで再試行してください。'}</p>
              {!busy && <button type="button" className="secondary" disabled={controlsDisabled} onClick={()=>void openConversation(selected)}>Retry messages</button>}</>:<>
              <p aria-live="polite" aria-atomic="true">{messages.total} messages · {messages.items.length} shown</p>
              {messages.items.map(m=><div className="searchresult" key={m.id}><small>{m.role} · {time(m.occurred_at)} · Source message {m.external_id}</small><p>{m.content}</p></div>)}
              {messages.next_offset!==null && <button type="button" className="secondary" disabled={controlsDisabled} onClick={()=>void openConversation(selected,messages.next_offset!)}>Load more messages</button>}
            </>}
          </article>}
        </>}

        {page==='projects' && <>
          <article className="panel"><h2>Create a project</h2>
            <form className="searchform" onSubmit={addProject} aria-busy={activeOperation.current?.kind==='project'}><input aria-label="Project name" disabled={controlsDisabled} value={projectName} maxLength={120} onChange={e=>setProjectName(e.target.value)} placeholder="Project name" required />
              <button className="primary" disabled={controlsDisabled||!projectName.trim()}>Add</button></form>
          </article>
          {counts && projects.length===0 && <p className="muted">保存済みプロジェクトはありません。名前を指定して作成してください。</p>}
          <section className="panels">{projects.map(p=><article className="panel" key={p.id}><h2>{p.name}</h2><p>{p.conversation_count} mapped conversations</p></article>)}</section>
        </>}

        {page==='connections' && <>
          <article className="panel"><h2>登録済みSource</h2>
            {sources.length===0?<p>{counts?'未登録':'データ未取得'}</p>:sources.map(s=><div className="line" key={s.id}><b>{s.provider} · {s.account_alias}</b><span>手動取り込み / 合成</span><small>最終取り込み: {time(s.last_sync_at)}</small></div>)}
            <p>取得範囲: 合成データの手動スナップショット。リアルタイム同期なし。</p>
            {sources.map(s=><p className="muted" key={s.id}>{s.account_alias}: {s.not_connected_reason || '実形式Adapterと自動同期は未接続'}</p>)}
          </article>
          <section className="panels">{connections.map(c=><article className="panel" key={c.id}><h2>{c.label}<span className="chip">未接続</span></h2>
            <p>{c.id==='chatgpt'||c.id==='claude'?'Nexus: 合成取り込みのみ実装。実形式検証はBLOCKED。':'Nexus: Connector未実装 / AI実行無効。'}</p>
            <p>公式手段の調査: {c.id==='codex_cloud'?'タスクのメタデータ取得あり（会話本文は未確認）':c.official.history==='documented'?'履歴取得あり':c.official.history==='manual_export'?'手動エクスポート':'未確認'}</p>
            <p>Provider / Product: {c.provider || '未提供'} / {c.product || c.id}</p>
            <p>未接続理由: {c.not_connected_reason || 'Nexusでの接続は未実装'}</p>
            {c.capabilities && <p>手動export: {c.capabilities.manual_export} · イベント監視: {c.capabilities.event_monitor} · 新規タスク: {c.capabilities.dispatch_new} · 再開: {c.capabilities.resume_existing}</p>}
            <p className="muted">{c.obtainable}</p><p className="muted">同期遅延: {c.latency}</p>
            <details><summary>必要権限・条件</summary><p>{c.permissions}</p></details>
          </article>)}</section>
        </>}

        {page==='imports' && <>
          {importer}
          <article className="panel"><h2>{counts?imports.total+' successful imports':'データ未取得'}</h2>
            <p>保存完了した取り込みの記録です。拒否した入力はロールバックし、内容を履歴に保存しません。</p>
            {counts && imports.total===0 && <p className="muted">保存済みの取り込み記録はありません。形式検証のみでは記録を追加しません。</p>}
            {rejected && <p className="error">直近の取り込み: {rejected.status===422||rejected.status===409?'拒否':'失敗'} · {rejected.provider} · {time(rejected.at)} · {rejected.status?'HTTP '+rejected.status:'接続または入力エラー'}。このタブ内のみの記録です。</p>}
            {imports.items.map(r=><div className="importreceipt" key={r.id}><div><b>{r.provider} · {r.account_alias}</b><span className="chip">合成 / 手動 / 保存済み</span></div>
              <p>{time(r.started_at)} · 保存 {r.counts.messages_inserted}件 / 既存 {r.counts.messages_duplicates}件</p>
              <small>Receipt {r.id} · {r.parser_version}</small>
              <p className="hash">SHA-256: {r.import_hash || '未提供'}</p>
              <p className="muted">取得範囲: {r.coverage || '未提供'} · 欠損可能性: {r.missing_records_possible===false?'なし（検証済み範囲のみ）':'未検証'} · プロバイダ全件取得は未確認</p>
            </div>)}
            {imports.next_offset!==null && <button type="button" className="secondary" disabled={controlsDisabled} onClick={()=>void moreImports()}>Load more imports</button>}
          </article>
        </>}
        <footer>ARK NEXUS / V1 · NO LIVE SYNC · AI EXECUTION DISABLED · SYNTHETIC DATA ONLY</footer>
  </AppShell>
}
