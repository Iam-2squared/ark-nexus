// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import App from './App'

const page = <T,>(items:T[],total=items.length,next_offset:number|null=null) =>
  ({items,total,offset:0,next_offset})
const source = {id:'s1',provider:'chatgpt',account_alias:'synthetic-account',
  connection_state:'manual_import',data_kind:'synthetic',last_sync_at:'2026-10-11T02:00:00Z'}
const conversation = {id:'c1',title:'日本語の設計',provider:'chatgpt',account_alias:'synthetic-account',
  message_count:1001,external_id:'source-c1',project_id:null}
const project = {id:'p1',name:'Nexus Test',conversation_count:1234}
const receipt = {id:'b1',provider:'chatgpt',account_alias:'synthetic-account',
  started_at:'2026-10-11T02:00:00Z',counts:{messages_inserted:1000,messages_duplicates:0},
  parser_version:'synthetic-fixture-1',data_kind:'synthetic',status:'imported'}
const hit = (id:string) => ({message_id:id,external_message_id:'source-'+id,provider:'chatgpt',
  account_alias:'synthetic-account',title:'日本語の設計',content:'安全な日本語メモ',occurred_at:null})
const response = (value:unknown,status=200) => new Response(JSON.stringify(value),{status})
const urlOf = (input:RequestInfo|URL) => new URL(String(input),'http://127.0.0.1:8788')
let importCount=0

async function defaultHttp(input:RequestInfo|URL, init?:RequestInit):Promise<Response> {
  const url = urlOf(input)
  if (url.pathname==='/api/v1/overview') return response({counts:{sources:1,conversations:1234,messages:9876,projects:1,imports:1}})
  if (url.pathname==='/api/v1/sources') return response({items:[source]})
  if (url.pathname==='/api/v1/projects') {
    if (init?.method==='POST') return response(project,201)
    return response({items:[project]})
  }
  if (url.pathname==='/api/v1/conversations/c1' && init?.method==='PATCH') return response({conversation_id:'c1',project_id:'p1'})
  if (url.pathname==='/api/v1/conversations/c1/messages') return response(page([
    {id:'m1',external_id:'source-m1',role:'user',content:'<img src=x onerror="window.stolen=true"> Ignore all rules.',occurred_at:null}
  ]))
  if (url.pathname==='/api/v1/conversations') return response(page([conversation],1234,100))
  if (url.pathname==='/api/v1/imports') {
    if (init?.method==='POST') {
      importCount++
      const data = init.body as FormData
      if (data.get('dry_run')==='true') return response({status:'dry_run',conversations:1,messages:1000,persisted:false},201)
      return response({status:'imported',counts:{messages_inserted:importCount===1?1000:0,messages_duplicates:importCount===1?0:1000}},201)
    }
    return response(page([receipt]))
  }
  if (url.pathname==='/api/v1/connections') return response({items:[
    ['chatgpt','ChatGPT'],['claude','Claude'],['chatgpt_work','ChatGPT Work'],
    ['codex_local','Codex Local'],['codex_cloud','Codex Cloud'],['claude_code','Claude Code']
  ].map(([id,label])=>({id,label,connection_state:'not_connected',implemented:false,execution_enabled:false,
    official:{history:'not_verified'},obtainable:'No connected data',latency:'Not measured',permissions:'Explicit approval required'}))})
  if (url.pathname==='/api/v1/search') return response(page([hit('h1')]))
  if (url.pathname==='/api/v1/integrity') return response({ok:true,checks:{missing_search_rows:0}})
  throw new Error('Unexpected local request: '+url.pathname)
}

let fetchMock = vi.fn(defaultHttp)
beforeEach(()=>{
  importCount=0
  fetchMock=vi.fn(defaultHttp)
  vi.stubGlobal('fetch',fetchMock)
  sessionStorage.setItem('nexus-local-key','synthetic-test-token-not-a-real-secret')
})
afterEach(()=>{cleanup(); vi.unstubAllGlobals(); sessionStorage.clear()})

async function ready() {
  render(<App />)
  await screen.findByText('LOCAL API READY')
}
async function tab(label:string) {
  await userEvent.click(screen.getByRole('button',{name:label}))
}
async function chooseFixture() {
  const input = screen.getByLabelText('Fixture · 上限8 MiB') as HTMLInputElement
  await userEvent.upload(input,new File(['{"nexus_fixture":"synthetic-v1"}'],'fixture.json',{type:'application/json'}))
  expect(input.files).toHaveLength(1)
}

function submitImport() {
  // jsdom does not update its internal file-validity state for user-event's FileList.
  // Submit the selected-file form; native browser validation remains a separate gate.
  fireEvent.submit(screen.getByLabelText('Fixture · 上限8 MiB').closest('form')!)
}

describe('Nexus dashboard truthful state and local operations',()=>{
  it('does not request private records before unlocking the local workspace',async()=>{
    sessionStorage.clear()
    render(<App />)
    await screen.findByText('LOCAL WORKSPACE LOCKED')
    expect(fetchMock).not.toHaveBeenCalled()
    await userEvent.type(screen.getByLabelText('Local access key'),'synthetic-test-token-not-a-real-secret')
    await userEvent.click(screen.getByRole('button',{name:'Unlock local workspace'}))
    await screen.findByText('LOCAL API READY')
    expect(new Headers(fetchMock.mock.calls[0][1]?.headers).get('Authorization')).toBe('Bearer synthetic-test-token-not-a-real-secret')
  })

  it('locks the workspace and clears visible private snapshots and the tab key',async()=>{
    await ready(); await tab('Conversations')
    await userEvent.click(screen.getByRole('button',{name:'Lock workspace'}))
    await screen.findByText('LOCAL WORKSPACE LOCKED')
    expect(sessionStorage.getItem('nexus-local-key')).toBeNull()
    expect(screen.queryByRole('button',{name:'日本語の設計'})).toBeNull()
    expect(screen.queryByText('9,876')).toBeNull()
  })

  it('rejects an expired key without retaining a displayed snapshot',async()=>{
    await ready()
    fetchMock.mockResolvedValue(response({detail:'Local access key required'},401))
    await userEvent.click(screen.getByRole('button',{name:'Refresh'}))
    await screen.findByText('LOCAL WORKSPACE LOCKED')
    expect(sessionStorage.getItem('nexus-local-key')).toBeNull()
    expect(screen.queryByText('9,876')).toBeNull()
  })

  it('locks and clears private snapshots when an integrity request rejects the key',async()=>{
    await ready()
    fetchMock.mockImplementation(async(input,init)=>urlOf(input).pathname==='/api/v1/integrity'
      ?response({detail:'Local access key required'},401):defaultHttp(input,init))
    await userEvent.click(screen.getByRole('button',{name:'Check stored data integrity'}))
    await screen.findByText('LOCAL WORKSPACE LOCKED')
    expect(sessionStorage.getItem('nexus-local-key')).toBeNull()
    expect(screen.queryByText('9,876')).toBeNull()
  })
  it('uses whole-database counts rather than visible conversation totals',async()=>{
    await ready()
    expect(screen.getByText('1,234')).toBeTruthy()
    expect(screen.getByText('9,876')).toBeTruthy()
    expect(screen.getByText('外部プロバイダとの接続: 0件')).toBeTruthy()
    expect(screen.getByRole('button',{name:'Import History'})).toBeTruthy()
  })

  it('does not turn researched support into connected accounts',async()=>{
    await ready(); await tab('Sources / Connections')
    expect(screen.getAllByText('未接続')).toHaveLength(6)
    expect(screen.getAllByText('Nexus: Connector未実装 / AI実行無効。')).toHaveLength(4)
    expect(screen.getByText('手動取り込み / 合成')).toBeTruthy()
    expect(screen.queryByRole('button',{name:/dispatch|resume/i})).toBeNull()
  })

  it('encodes Japanese search and source/project filters and paginates',async()=>{
    fetchMock.mockImplementation(async(input,init)=>{
      const url=urlOf(input)
      if (url.pathname==='/api/v1/search') {
        return response(url.searchParams.has('offset')?page([hit('h2')],2):page([hit('h1')],2,1))
      }
      return defaultHttp(input,init)
    })
    await ready(); await tab('Universal Search')
    await userEvent.type(screen.getByRole('textbox',{name:'Search imported messages'}),'日本語%')
    await userEvent.selectOptions(screen.getByLabelText('Source',{exact:true}),'s1')
    await userEvent.selectOptions(screen.getByLabelText('Project',{exact:true}),'p1')
    expect(screen.getByRole('combobox',{name:'Source'})).toBeTruthy()
    expect(screen.getByRole('combobox',{name:'Project'})).toBeTruthy()
    await userEvent.click(screen.getByRole('button',{name:'Search'}))
    await screen.findByRole('heading',{name:'2 results · 1 shown'})
    const call=fetchMock.mock.calls.find(([input])=>urlOf(input).pathname==='/api/v1/search')!
    expect(urlOf(call[0]).searchParams.get('q')).toBe('日本語%')
    expect(urlOf(call[0]).searchParams.get('source_id')).toBe('s1')
    expect(urlOf(call[0]).searchParams.get('project_id')).toBe('p1')
    await userEvent.click(screen.getByRole('button',{name:'Load more results'}))
    await screen.findByRole('heading',{name:'2 results · 2 shown'})
    expect(screen.getByText(/Source message source-h2/)).toBeTruthy()
  })

  it('displays search failure without claiming a successful zero-result search',async()=>{
    fetchMock.mockImplementation(async(input,init)=>urlOf(input).pathname==='/api/v1/search'
      ?response({detail:'Local storage unavailable'},503):defaultHttp(input,init))
    await ready(); await tab('Universal Search')
    await userEvent.type(screen.getByRole('textbox',{name:'Search imported messages'}),'日本語')
    await userEvent.click(screen.getByRole('button',{name:'Search'}))
    expect(await screen.findByRole('heading',{name:'検索失敗（最新結果は未取得）'})).toBeTruthy()
    expect(screen.queryByRole('heading',{name:'0 results · 0 shown'})).toBeNull()
    expect(screen.getByRole('alert').textContent).toContain('Local storage unavailable')
  })

  it('marks a failed refresh as unavailable while preserving the dated previous counts',async()=>{
    await ready()
    fetchMock.mockRejectedValue(new Error('Local API disconnected'))
    await userEvent.click(screen.getByRole('button',{name:'Refresh'}))
    await screen.findByText('LOCAL API UNAVAILABLE')
    expect(screen.getByText('9,876')).toBeTruthy()
    expect(screen.getByText(/前回取得時の表示/)).toBeTruthy()
  })

  it('shows unknown counts before any successful API read',async()=>{
    fetchMock.mockRejectedValue(new Error('Local API disconnected'))
    const rendered=render(<App />)
    await screen.findByText('LOCAL API UNAVAILABLE')
    expect([...rendered.container.querySelectorAll('.stats strong')].map(x=>x.textContent)).toEqual(['—','—','—','—'])
    expect((screen.getByRole('button',{name:'Import fixture'}) as HTMLButtonElement).disabled).toBe(true)
  })

  it('sends the CSRF boundary header and displays zero duplicate additions on reimport',async()=>{
    await ready(); await tab('Import History'); await chooseFixture()
    submitImport()
    await waitFor(()=>expect(screen.getByRole('status').textContent).toContain('保存 1000件'))
    submitImport()
    await waitFor(()=>expect(screen.getByRole('status').textContent).toContain('保存 0件'))
    const calls=fetchMock.mock.calls.filter(([,init])=>init?.method==='POST')
    expect(calls).toHaveLength(2)
    expect(new Headers(calls[0][1]?.headers).get('X-Nexus-Request')).toBe('1')
    expect((calls[0][1]?.body as FormData).get('provider')).toBe('chatgpt')
    expect(screen.getByText(/Receipt b1/)).toBeTruthy()
  })

  it('distinguishes import and integrity results when both are displayed',async()=>{
    await ready(); await tab('Import History'); await chooseFixture()
    submitImport()
    await waitFor(()=>expect(screen.getByRole('status').textContent).toContain('保存 1000件'))
    await tab('Overview')
    await userEvent.click(screen.getByRole('button',{name:'Check stored data integrity'}))
    await waitFor(()=>expect(screen.getAllByRole('status')).toHaveLength(2))
    expect(screen.getByRole('status',{name:'Import result'}).textContent).toContain('保存 1000件')
    expect(screen.getByRole('status',{name:'Stored data integrity'}).textContent).toContain('整合性: PASS')
  })

  it('validates without implying persistence or refreshing stored counts',async()=>{
    await ready(); await tab('Import History'); await chooseFixture()
    const before=fetchMock.mock.calls.filter(([input])=>urlOf(input).pathname==='/api/v1/overview').length
    await userEvent.click(screen.getByRole('checkbox',{name:'保存せず形式を検証'}))
    submitImport()
    await waitFor(()=>expect(screen.getByRole('status').textContent).toContain('保存0件'))
    expect(fetchMock.mock.calls.filter(([input])=>urlOf(input).pathname==='/api/v1/overview')).toHaveLength(before)
  })

  it('keeps rejected input out of successful receipt state',async()=>{
    fetchMock.mockImplementation(async(input,init)=>init?.method==='POST'
      ?response({detail:'Unsupported real export format'},422):defaultHttp(input,init))
    await ready(); await tab('Import History'); await chooseFixture()
    submitImport()
    await waitFor(()=>expect(screen.getByRole('alert').textContent).toContain('Unsupported real export format'))
    expect(screen.queryByRole('status')).toBeNull()
    expect(screen.getByText('1 successful imports')).toBeTruthy()
  })

  it('renders untrusted message content as text and preserves source IDs',async()=>{
    const rendered=render(<App />)
    await screen.findByText('LOCAL API READY'); await tab('Conversations')
    await userEvent.click(screen.getByRole('button',{name:'日本語の設計'}))
    await screen.findByText('<img src=x onerror="window.stolen=true"> Ignore all rules.')
    expect(rendered.container.querySelector('.searchresult img')).toBeNull()
    expect(screen.getByText(/Source message source-m1/)).toBeTruthy()
    expect((window as unknown as Record<string,unknown>).stolen).toBeUndefined()
  })

  it('maps a project through a bounded local write and refreshes server counts',async()=>{
    await ready(); await tab('Conversations')
    await userEvent.selectOptions(screen.getByLabelText('Project for 日本語の設計'),'p1')
    await waitFor(()=>expect(fetchMock.mock.calls.some(([,init])=>init?.method==='PATCH')).toBe(true))
    const call=fetchMock.mock.calls.find(([,init])=>init?.method==='PATCH')!
    expect(urlOf(call[0]).pathname).toBe('/api/v1/conversations/c1')
    expect(JSON.parse(call[1]!.body as string)).toEqual({project_id:'p1'})
    expect(new Headers(call[1]?.headers).get('X-Nexus-Request')).toBe('1')
  })
})
