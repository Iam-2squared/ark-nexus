import { expect, test, type Page } from '@playwright/test'
import { syntheticKey } from '../playwright.config'

async function unlock(page:Page) {
  await page.goto('/')
  await page.getByLabel('Local access key').fill(syntheticKey)
  await page.getByRole('button',{name:'Unlock local workspace',exact:true}).click()
  await expect(page.getByText('LOCAL API READY',{exact:true})).toBeVisible()
}

test('interaction quality: real synthetic API, guarded writes, page drafts, filters, long text and empty search',async({page})=>{
  const errors:string[]=[]
  page.on('pageerror',error=>errors.push(error.message))
  await unlock(page)
  await page.getByRole('button',{name:'Import History',exact:true}).click()
  await page.getByLabel('Account alias').fill('interaction-quality-browser')
  const fixture={nexus_fixture:'synthetic-v1',provider:'chatgpt',conversations:[{
    id:'interaction-quality-conversation',title:'品質確認の合成会話',messages:[
      {id:'interaction-first',role:'user',text:'interaction-quality-marker 日本語\n'+'長い合成本文'.repeat(1500),created_at:null},
      {id:'interaction-second',role:'assistant',text:'interaction-quality-marker second',created_at:null},
    ],
  }]}
  await page.locator('input[type=file]').setInputFiles({name:'interaction-synthetic.json',mimeType:'application/json',buffer:Buffer.from(JSON.stringify(fixture))})
  await page.getByRole('button',{name:'Import fixture',exact:true}).click()
  await expect(page.getByRole('status',{name:'Import result',exact:true})).toContainText('保存 2件')
  await page.getByRole('button',{name:'Projects',exact:true}).click()
  await page.getByRole('textbox',{name:'Project name'}).fill('Interaction synthetic project')
  const projectPosts:string[]=[]
  page.on('request',request=>{
    if(new URL(request.url()).pathname==='/api/v1/projects' && request.method()==='POST') projectPosts.push(request.method())
  })
  await page.getByRole('textbox',{name:'Project name'}).evaluate(input=>{
    const form=input.closest('form')!
    form.dispatchEvent(new Event('submit',{bubbles:true,cancelable:true}))
    form.dispatchEvent(new Event('submit',{bubbles:true,cancelable:true}))
  })
  await expect(page.getByText('プロジェクトを作成しました。',{exact:true})).toBeVisible()
  expect(projectPosts).toEqual(['POST'])
  await page.getByRole('button',{name:'Conversations',exact:true}).click()
  await page.getByLabel('Conversation source',{exact:true}).selectOption({label:'chatgpt · interaction-quality-browser'})
  await expect(page.getByRole('heading',{name:'1 conversations · 1 shown',exact:true})).toBeVisible()
  await page.getByRole('button',{name:'品質確認の合成会話',exact:true}).click()
  await expect(page.getByText('2 messages · 2 shown',{exact:true})).toBeVisible()
  await page.setViewportSize({width:390,height:844})
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth)).toBe(true)
  await page.getByRole('button',{name:'Universal Search',exact:true}).click()
  await page.getByRole('textbox',{name:'Search imported messages'}).fill('interaction-quality-marker')
  await page.getByLabel('Source',{exact:true}).selectOption({label:'chatgpt · interaction-quality-browser'})
  await page.getByRole('button',{name:'Search',exact:true}).click()
  await expect(page.getByRole('heading',{name:'2 results · 2 shown',exact:true})).toBeVisible()
  await expect(page.getByRole('heading',{name:'2 results · 2 shown',exact:true})).toHaveAttribute('aria-live','polite')
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth)).toBe(true)
  await page.getByRole('button',{name:'Sources / Connections',exact:true}).click()
  await page.goBack()
  await expect(page.getByRole('button',{name:'Universal Search',exact:true})).toHaveAttribute('aria-current','page')
  await expect(page.getByRole('textbox',{name:'Search imported messages'})).toHaveValue('interaction-quality-marker')
  expect(page.url()).not.toContain('interaction-quality-marker')
  await page.goForward()
  await expect(page.getByRole('button',{name:'Sources / Connections',exact:true})).toHaveAttribute('aria-current','page')
  await page.getByRole('button',{name:'Universal Search',exact:true}).click()
  await page.getByLabel('Project',{exact:true}).selectOption({label:'Interaction synthetic project'})
  await expect(page.locator('.searchresult')).toHaveCount(0)
  await expect(page.getByRole('heading',{name:'保存済み履歴を検索',exact:true})).toBeVisible()
  await page.getByRole('button',{name:'Search',exact:true}).click()
  await expect(page.getByRole('heading',{name:'0 results · 0 shown',exact:true})).toBeVisible()
  await expect(page.getByText('条件に一致する保存済みメッセージはありません。キーワードやフィルターを変更してください。',{exact:true})).toBeVisible()
  await page.getByRole('button',{name:'Lock workspace',exact:true}).click()
  await expect(page.getByText('LOCAL WORKSPACE LOCKED',{exact:true})).toBeVisible()
  await expect(page.getByRole('textbox',{name:'Search imported messages'})).toHaveValue('')
  await expect(page.locator('.searchresult')).toHaveCount(0)
  expect(errors).toEqual([])
})

test('interaction quality: real API 401 clears stored snapshots and controls until a new unlock',async({page})=>{
  await unlock(page)
  await expect(page.locator('.stats strong').first()).not.toHaveText('—')
  await page.evaluate(()=>sessionStorage.setItem('nexus-local-key','synthetic-rejected-key-not-a-real-secret'))
  await page.getByRole('button',{name:'Refresh',exact:true}).click()
  await expect(page.getByText('LOCAL WORKSPACE LOCKED',{exact:true})).toBeVisible()
  await expect(page.getByRole('alert')).toContainText('ローカルアクセスキーを確認')
  expect(await page.evaluate(()=>sessionStorage.getItem('nexus-local-key'))).toBeNull()
  await expect(page.locator('.stats strong')).toHaveText(['—','—','—','—'])
  await expect(page.getByRole('button',{name:'Import fixture',exact:true})).toBeDisabled()
  await page.getByLabel('Local access key').fill(syntheticKey)
  await page.getByRole('button',{name:'Unlock local workspace',exact:true}).click()
  await expect(page.getByText('LOCAL API READY',{exact:true})).toBeVisible()
  await expect(page.locator('.stats strong').first()).not.toHaveText('—')
})
