// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import App from './App'

const page = <T,>(items:T[],total=items.length,next_offset:number|null=null,offset=0) => ({items,total,next_offset,offset})
const source = {id:'quality-source',provider:'chatgpt',account_alias:'synthetic-quality',connection_state:'manual_import',data_kind:'synthetic',last_sync_at:null}
const conversation = {id:'quality-conversation',title:'合成会話',provider:'chatgpt',account_alias:'synthetic-quality',message_count:2,external_id:'synthetic-conversation-id',project_id:null}
const project = {id:'quality-project',name:'合成プロジェクト',conversation_count:0}
const hit = (id:string) => ({message_id:id,external_message_id:'source-'+id,provider:'chatgpt',account_alias:'synthetic-quality',title:'合成会話',content:'合成本文 '+id,occurred_at:null})
const message = (id:string) => ({id,external_id:'source-'+id,role:'user',content:'合成メッセージ '+id,occurred_at:null})
const response = (value:unknown,status=200) => new Response(JSON.stringify(value),{status})
const urlOf = (input:RequestInfo|URL) => new URL(String(input),'http://127.0.0.1:8788')
const deferred = () => {
  let resolve!:(value:Response)=>void
  const promise = new Promise<Response>(complete=>{resolve=complete})
  return {promise,resolve}
}

async function localHttp(input:RequestInfo|URL,init?:RequestInit):Promise<Response> {
  const path=urlOf(input).pathname
  if(path==='/api/v1/sources') return response({items:[source]})
  if(path==='/api/v1/overview') return response({counts:{sources:1,conversations:1,messages:2,projects:1,imports:0}})
  if(path==='/api/v1/conversations') return response(page([conversation]))
  if(path==='/api/v1/conversations/quality-conversation/messages') return response(page([message('first')],2,1))
  if(path==='/api/v1/conversations/quality-conversation' && init?.method==='PATCH') return response({conversation_id:conversation.id,project_id:project.id})
  if(path==='/api/v1/projects') return response(init?.method==='POST'?project:{items:[project]},init?.method==='POST'?201:200)
  if(path==='/api/v1/imports') return response(init?.method==='POST'?{status:'imported',counts:{messages_inserted:2,messages_duplicates:0}}:page([]))
  if(path==='/api/v1/connections') return response({items:[]})
  if(path==='/api/v1/search') return response(page([hit('first')],2,1))
  if(path==='/api/v1/integrity') return response({ok:true,checks:{missing_search_rows:0}})
  throw new Error('Unexpected synthetic request')
}

let fetchMock=vi.fn(localHttp)
beforeEach(()=>{
  window.history.replaceState(null,'','/')
  sessionStorage.setItem('nexus-local-key','synthetic-quality-token-not-a-real-secret')
  fetchMock=vi.fn(localHttp)
  vi.stubGlobal('fetch',fetchMock)
})
afterEach(()=>{cleanup(); vi.unstubAllGlobals(); sessionStorage.clear(); window.history.replaceState(null,'','/')})
async function ready(tab='Overview') {
  render(<App />)
  await screen.findByText('LOCAL API READY')
  if(tab!=='Overview') await userEvent.click(screen.getByRole('button',{name:tab}))
}
async function searchFor(text='日本語') {
  await userEvent.type(screen.getByRole('textbox',{name:'Search imported messages'}),text)
  await userEvent.click(screen.getByRole('button',{name:'Search'}))
}
function callsFor(path:string,method?:string) {
  return fetchMock.mock.calls.filter(([input,init])=>urlOf(input).pathname==='/api/v1'+path && (!method || init?.method===method))
}

describe('Additive synthetic interaction and privacy regressions',()=>{
  it('does not issue API reads from a directly submitted locked search form',async()=>{
    sessionStorage.clear()
    render(<App />)
    await screen.findByText('LOCAL WORKSPACE LOCKED')
    await userEvent.click(screen.getByRole('button',{name:'Universal Search'}))
    fireEvent.change(screen.getByRole('textbox',{name:'Search imported messages'}),{target:{value:'synthetic-marker'}})
    fireEvent.submit(screen.getByRole('textbox',{name:'Search imported messages'}).closest('form')!)
    await act(async()=>{})
    expect(fetchMock).not.toHaveBeenCalled()
    expect(screen.queryByText('合成本文 first')).toBeNull()
  })

  it('guards a double project submit synchronously before a second POST',async()=>{
    const pending=deferred()
    fetchMock.mockImplementation((input,init)=>urlOf(input).pathname==='/api/v1/projects' && init?.method==='POST'?pending.promise:localHttp(input,init))
    await ready('Projects')
    fireEvent.change(screen.getByRole('textbox',{name:'Project name'}),{target:{value:'合成プロジェクト'}})
    const form=screen.getByRole('textbox',{name:'Project name'}).closest('form')!
    act(()=>{fireEvent.submit(form); fireEvent.submit(form)})
    expect(callsFor('/projects','POST')).toHaveLength(1)
    await act(async()=>{pending.resolve(response(project,201))})
    expect(await screen.findByText('プロジェクトを作成しました。')).toBeTruthy()
  })

  it('guards double import submission and freezes the request identity while pending',async()=>{
    const pending=deferred()
    fetchMock.mockImplementation((input,init)=>urlOf(input).pathname==='/api/v1/imports' && init?.method==='POST'?pending.promise:localHttp(input,init))
    await ready('Import History')
    const input=screen.getByLabelText('Fixture · 上限8 MiB')
    await userEvent.upload(input,new File(['{}'],'quality.json',{type:'application/json'}))
    const form=input.closest('form')!
    act(()=>{fireEvent.submit(form); fireEvent.submit(form)})
    expect(callsFor('/imports','POST')).toHaveLength(1)
    expect((screen.getByLabelText('Provider') as HTMLSelectElement).disabled).toBe(true)
    expect((screen.getByLabelText('Account alias') as HTMLInputElement).disabled).toBe(true)
    await act(async()=>{pending.resolve(response({status:'imported',counts:{messages_inserted:2,messages_duplicates:0}}))})
    expect(await screen.findByRole('status',{name:'Import result'})).toBeTruthy()
  })

  it('discards an in-flight search when its query changes and allows a fresh query immediately',async()=>{
    const old=deferred()
    fetchMock.mockImplementation((input,init)=>urlOf(input).pathname==='/api/v1/search' && urlOf(input).searchParams.get('q')==='古い条件'?old.promise:localHttp(input,init))
    await ready('Universal Search')
    await searchFor('古い条件')
    fireEvent.change(screen.getByRole('textbox',{name:'Search imported messages'}),{target:{value:'新しい条件'}})
    expect((screen.getByRole('button',{name:'Search'}) as HTMLButtonElement).disabled).toBe(false)
    await userEvent.click(screen.getByRole('button',{name:'Search'}))
    await screen.findByText('合成本文 first')
    await act(async()=>{old.resolve(response(page([hit('STALE')],1)))})
    expect(screen.queryByText('合成本文 STALE')).toBeNull()
    expect(screen.getByRole('heading',{name:'2 results · 1 shown'})).toBeTruthy()
  })

  it('clears result provenance and pagination when a search filter is edited',async()=>{
    await ready('Universal Search'); await searchFor()
    await screen.findByText('合成本文 first')
    await userEvent.selectOptions(screen.getByLabelText('Source',{exact:true}),source.id)
    expect(screen.queryByText('合成本文 first')).toBeNull()
    expect(screen.queryByRole('button',{name:'Load more results'})).toBeNull()
    expect(screen.getByRole('heading',{name:'保存済み履歴を検索'})).toBeTruthy()
  })

  it('invalidates search results on Refresh while retaining the search draft',async()=>{
    await ready('Universal Search'); await searchFor('日本語の下書き')
    await screen.findByText('合成本文 first')
    await userEvent.click(screen.getByRole('button',{name:'Refresh'}))
    await waitFor(()=>expect(callsFor('/overview')).toHaveLength(2))
    expect(screen.queryByText('合成本文 first')).toBeNull()
    expect((screen.getByRole('textbox',{name:'Search imported messages'}) as HTMLInputElement).value).toBe('日本語の下書き')
  })

  it('clears a selected old message snapshot on Refresh',async()=>{
    await ready('Conversations')
    await userEvent.click(screen.getByRole('button',{name:conversation.title}))
    await screen.findByText('合成メッセージ first')
    await userEvent.click(screen.getByRole('button',{name:'Refresh'}))
    await waitFor(()=>expect(callsFor('/overview')).toHaveLength(2))
    expect(screen.queryByText('合成メッセージ first')).toBeNull()
  })

  it('preserves page drafts across all six star routes without extra API reads',async()=>{
    await ready('Universal Search')
    await userEvent.type(screen.getByRole('textbox',{name:'Search imported messages'}),'日本語の下書き')
    await userEvent.selectOptions(screen.getByLabelText('Source',{exact:true}),source.id)
    const before=fetchMock.mock.calls.length
    for(const name of ['Conversations','Projects','Import History','Sources / Connections','Overview','Universal Search'])
      await userEvent.click(screen.getByRole('button',{name}))
    expect((screen.getByRole('textbox',{name:'Search imported messages'}) as HTMLInputElement).value).toBe('日本語の下書き')
    expect((screen.getByLabelText('Source',{exact:true}) as HTMLSelectElement).value).toBe(source.id)
    expect(fetchMock.mock.calls).toHaveLength(before)
  })

  it('uses only a page identifier in browser navigation history',async()=>{
    await ready('Universal Search')
    await userEvent.type(screen.getByRole('textbox',{name:'Search imported messages'}),'PRIVATE-SYNTHETIC-QUERY')
    expect(window.location.hash).toBe('#search')
    expect(window.location.href).not.toContain('PRIVATE-SYNTHETIC-QUERY')
    await userEvent.click(screen.getByRole('button',{name:'Projects'}))
    window.history.replaceState(null,'','#search')
    fireEvent.popState(window)
    expect(screen.getByRole('button',{name:'Universal Search'}).getAttribute('aria-current')).toBe('page')
    expect((screen.getByRole('textbox',{name:'Search imported messages'}) as HTMLInputElement).value).toBe('PRIVATE-SYNTHETIC-QUERY')
  })

  it('restores the empty-hash Overview entry and preserves drafts when moving forward',async()=>{
    await ready('Universal Search')
    await userEvent.type(screen.getByRole('textbox',{name:'Search imported messages'}),'合成ナビ下書き')
    const before=fetchMock.mock.calls.length
    window.history.replaceState(null,'','/')
    fireEvent.popState(window)
    expect(screen.getByRole('button',{name:'Overview'}).getAttribute('aria-current')).toBe('page')
    window.history.replaceState(null,'','#search')
    fireEvent.popState(window)
    expect(screen.getByRole('button',{name:'Universal Search'}).getAttribute('aria-current')).toBe('page')
    expect((screen.getByRole('textbox',{name:'Search imported messages'}) as HTMLInputElement).value).toBe('合成ナビ下書き')
    expect(fetchMock.mock.calls).toHaveLength(before)
  })

  it('ignores unknown hashes and the skip-link content anchor without changing the current page',async()=>{
    await ready('Universal Search')
    const before=fetchMock.mock.calls.length
    window.history.replaceState(null,'','#workspace-content')
    fireEvent(window,new HashChangeEvent('hashchange'))
    expect(screen.getByRole('button',{name:'Universal Search'}).getAttribute('aria-current')).toBe('page')
    window.history.replaceState(null,'','#unknown-synthetic-anchor')
    fireEvent.popState(window)
    expect(screen.getByRole('button',{name:'Universal Search'}).getAttribute('aria-current')).toBe('page')
    expect(screen.getByRole('textbox',{name:'Search imported messages'})).toBeTruthy()
    expect(fetchMock.mock.calls).toHaveLength(before)
  })

  it('loads source and project conversation filters from the local API',async()=>{
    await ready('Conversations')
    await userEvent.selectOptions(screen.getByLabelText('Conversation source'),source.id)
    await waitFor(()=>expect(callsFor('/conversations').some(([input])=>urlOf(input).searchParams.get('source_id')===source.id)).toBe(true))
    await userEvent.selectOptions(screen.getByLabelText('Conversation project'),project.id)
    await waitFor(()=>expect(callsFor('/conversations').some(([input])=>urlOf(input).searchParams.get('project_id')===project.id && urlOf(input).searchParams.get('source_id')===source.id)).toBe(true))
    await userEvent.click(screen.getByRole('button',{name:'Refresh'}))
    await waitFor(()=>expect(callsFor('/overview')).toHaveLength(2))
    expect((screen.getByLabelText('Conversation source') as HTMLSelectElement).value).toBe(source.id)
    expect((screen.getByLabelText('Conversation project') as HTMLSelectElement).value).toBe(project.id)
  })

  it('keeps exact conversation filter labels independent of nested option text',async()=>{
    await ready('Conversations')
    for(const name of ['Conversation source','Conversation project']) {
      const select=screen.getByLabelText(name,{exact:true})
      // Playwright includes descendant option text in an implicit label.
      // Explicit names must remain exact as synthetic accounts/projects grow.
      expect(select.getAttribute('aria-label')).toBe(name)
      expect(screen.getByRole('combobox',{name})).toBe(select)
    }
  })

  it('offers an explicit safe retry after a conversation read fails',async()=>{
    let fail=true
    fetchMock.mockImplementation((input,init)=>urlOf(input).pathname.endsWith('/messages') && fail?Promise.resolve(response({detail:'Local storage unavailable'},503)):localHttp(input,init))
    await ready('Conversations')
    await userEvent.click(screen.getByRole('button',{name:conversation.title}))
    await screen.findByRole('alert')
    fail=false
    await userEvent.click(screen.getByRole('button',{name:'Retry messages'}))
    expect(await screen.findByText('合成メッセージ first')).toBeTruthy()
  })

  it('retains loaded search rows after a paging error and retries the same offset',async()=>{
    let fail=true
    fetchMock.mockImplementation((input,init)=>urlOf(input).pathname==='/api/v1/search' && urlOf(input).searchParams.has('offset')
      ?Promise.resolve(fail?response({detail:'Local storage unavailable'},503):response(page([hit('second')],2,null,1))):localHttp(input,init))
    await ready('Universal Search'); await searchFor()
    await screen.findByText('合成本文 first')
    await userEvent.click(screen.getByRole('button',{name:'Load more results'}))
    await screen.findByRole('alert')
    expect(screen.getByText('合成本文 first')).toBeTruthy()
    fail=false
    await userEvent.click(screen.getByRole('button',{name:'Load more results'}))
    await screen.findByText('合成本文 second')
    expect(callsFor('/search').slice(1).map(([input])=>urlOf(input).searchParams.get('offset'))).toEqual(['1','1'])
  })

  it('never posts a whitespace-only account alias even when native validation is bypassed',async()=>{
    await ready('Import History')
    await userEvent.upload(screen.getByLabelText('Fixture · 上限8 MiB'),new File(['{}'],'quality.json',{type:'application/json'}))
    fireEvent.change(screen.getByLabelText('Account alias'),{target:{value:'   '}})
    fireEvent.submit(screen.getByLabelText('Fixture · 上限8 MiB').closest('form')!)
    await act(async()=>{})
    expect(callsFor('/imports','POST')).toHaveLength(0)
    expect(screen.getByRole('alert').textContent).toContain('Account alias')
  })

  it('announces search outcomes accessibly without conflating them with import receipts',async()=>{
    await ready('Universal Search'); await searchFor()
    const heading=await screen.findByRole('heading',{name:'2 results · 1 shown'})
    expect(heading.getAttribute('aria-live')).toBe('polite')
    expect(heading.getAttribute('aria-atomic')).toBe('true')
    expect(screen.queryByRole('status',{name:'Import result'})).toBeNull()
  })

  it('locks on a late 401 even if another Refresh request failed first',async()=>{
    const unauthorized=deferred()
    await ready()
    fetchMock.mockImplementation((input,init)=>{
      const path=urlOf(input).pathname
      if(path==='/api/v1/sources') return Promise.reject(new Error('Local API disconnected'))
      if(path==='/api/v1/conversations') return unauthorized.promise
      return localHttp(input,init)
    })
    await userEvent.click(screen.getByRole('button',{name:'Refresh'}))
    await screen.findByText('LOCAL API UNAVAILABLE')
    await act(async()=>{unauthorized.resolve(response({detail:'Local access key required'},401))})
    expect(screen.getByText('LOCAL WORKSPACE LOCKED')).toBeTruthy()
    expect(sessionStorage.getItem('nexus-local-key')).toBeNull()
    expect(screen.queryByText('合成会話')).toBeNull()
  })

  it('aborts outstanding reads when the user locks and discards responses from an abort-ignoring transport',async()=>{
    const pending=deferred()
    let signal:AbortSignal|null|undefined
    fetchMock.mockImplementation((input,init)=>{
      if(urlOf(input).pathname==='/api/v1/search') {signal=init?.signal; return pending.promise}
      return localHttp(input,init)
    })
    await ready('Universal Search'); await searchFor()
    await userEvent.click(screen.getByRole('button',{name:'Lock workspace'}))
    expect(signal?.aborted).toBe(true)
    await act(async()=>{pending.resolve(response(page([hit('LATE')],1)))})
    expect(screen.queryByText('合成本文 LATE')).toBeNull()
    expect(screen.getByText('LOCAL WORKSPACE LOCKED')).toBeTruthy()
  })

  it('discards a superseded conversation filter response',async()=>{
    const first=deferred()
    fetchMock.mockImplementation((input,init)=>{
      const url=urlOf(input)
      if(url.pathname==='/api/v1/conversations' && url.searchParams.get('source_id')===source.id && !url.searchParams.has('project_id')) return first.promise
      if(url.pathname==='/api/v1/conversations' && url.searchParams.get('project_id')===project.id) return Promise.resolve(response(page([])))
      return localHttp(input,init)
    })
    await ready('Conversations')
    fireEvent.change(screen.getByLabelText('Conversation source'),{target:{value:source.id}})
    fireEvent.change(screen.getByLabelText('Conversation project'),{target:{value:project.id}})
    await screen.findByRole('heading',{name:'0 conversations · 0 shown'})
    await act(async()=>{first.resolve(response(page([{...conversation,title:'STALE-CONVERSATION'}])))})
    expect(screen.queryByRole('button',{name:'STALE-CONVERSATION'})).toBeNull()
    expect(screen.getByRole('heading',{name:'0 conversations · 0 shown'})).toBeTruthy()
  })

  it('rejects a nonadvancing search cursor without duplicating displayed results',async()=>{
    fetchMock.mockImplementation((input,init)=>urlOf(input).pathname==='/api/v1/search' && urlOf(input).searchParams.has('offset')
      ?Promise.resolve(response(page([hit('first')],2,1,1))):localHttp(input,init))
    await ready('Universal Search'); await searchFor()
    await screen.findByText('合成本文 first')
    await userEvent.click(screen.getByRole('button',{name:'Load more results'}))
    expect(await screen.findByRole('alert')).toBeTruthy()
    expect(screen.getAllByText('合成本文 first')).toHaveLength(1)
    expect(screen.getByRole('heading',{name:'検索失敗（最新結果は未取得）'})).toBeTruthy()
  })

  it('merges overlapping page IDs once while retaining truthful server totals',async()=>{
    fetchMock.mockImplementation((input,init)=>urlOf(input).pathname==='/api/v1/search' && urlOf(input).searchParams.has('offset')
      ?Promise.resolve(response(page([hit('first'),hit('second')],2,null,1))):localHttp(input,init))
    await ready('Universal Search'); await searchFor()
    await screen.findByText('合成本文 first')
    await userEvent.click(screen.getByRole('button',{name:'Load more results'}))
    await screen.findByText('合成本文 second')
    expect(screen.getAllByText('合成本文 first')).toHaveLength(1)
    expect(screen.getByRole('heading',{name:'2 results · 2 shown'})).toBeTruthy()
  })

  it('rejects invalid pagination metadata instead of crashing the result view',async()=>{
    fetchMock.mockImplementation((input,init)=>urlOf(input).pathname==='/api/v1/search'
      ?Promise.resolve(response({items:null,total:1,offset:0,next_offset:null})):localHttp(input,init))
    await ready('Universal Search'); await searchFor()
    expect(await screen.findByRole('alert')).toBeTruthy()
    expect(screen.getByRole('heading',{name:'検索失敗（最新結果は未取得）'})).toBeTruthy()
    expect(screen.queryByText('合成本文 first')).toBeNull()
  })
})
