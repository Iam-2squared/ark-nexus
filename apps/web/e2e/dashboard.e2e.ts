import { expect, test } from '@playwright/test'
import { syntheticKey } from '../playwright.config'

test('actual browser: unlock, import 1000 messages, deduplicate, search, map, provenance and inert text',async({page})=>{
  const pageErrors:string[]=[]
  page.on('pageerror',error=>pageErrors.push(error.message))
  await page.goto('/')
  await expect(page.getByText('LOCAL WORKSPACE LOCKED',{exact:true})).toBeVisible()
  await page.getByLabel('Local access key').fill(syntheticKey)
  await page.getByRole('button',{name:'Unlock local workspace'}).click()
  await expect(page.getByText('LOCAL API READY',{exact:true})).toBeVisible()
  await page.getByRole('button',{name:'Import History',exact:true}).click()
  const fixture={nexus_fixture:'synthetic-v1',provider:'chatgpt',conversations:[
    {id:'e2e-thread',title:'E2E 日本語',messages:Array.from({length:1000},(_,i)=>({
      id:'m'+i,role:'user',text:i===0?'<img src=x onerror="window.stolen=true"> 日本語の会話':
        'synthetic token'+String(i).padStart(4,'0'),created_at:'2026-10-11T02:00:00Z',
    }))}
  ]}
  await page.locator('input[type=file]').setInputFiles({name:'synthetic.json',mimeType:'application/json',
    buffer:Buffer.from(JSON.stringify(fixture))})
  await page.getByRole('button',{name:'Import fixture',exact:true}).click()
  await expect(page.getByRole('status')).toContainText('保存 1000件')
  await expect(page.locator('.importreceipt')).toHaveCount(1)
  await page.getByRole('button',{name:'Import fixture',exact:true}).click()
  await expect(page.getByRole('status')).toContainText('保存 0件')
  await expect(page.locator('.importreceipt')).toHaveCount(2)
  await page.getByRole('button',{name:'Projects',exact:true}).click()
  await page.getByRole('textbox',{name:'Project name'}).fill('E2E Project')
  await page.getByRole('button',{name:'Add',exact:true}).click()
  await expect(page.getByRole('heading',{name:'E2E Project',exact:true})).toBeVisible()
  await page.getByRole('button',{name:'Conversations',exact:true}).click()
  await page.getByLabel('Project for E2E 日本語').selectOption({label:'E2E Project'})
  await expect(page.getByLabel('Project for E2E 日本語')).toBeEnabled()
  await page.getByRole('button',{name:'E2E 日本語',exact:true}).click()
  await expect(page.getByText('1000 messages · 200 shown',{exact:true})).toBeVisible()
  await expect(page.locator('.searchresult img')).toHaveCount(0)
  expect(await page.evaluate(()=>Reflect.get(window,'stolen'))).toBeUndefined()
  await page.getByRole('button',{name:'Load more messages'}).click()
  await expect(page.getByText('1000 messages · 400 shown',{exact:true})).toBeVisible()
  await page.getByRole('button',{name:'Universal Search',exact:true}).click()
  await page.getByRole('textbox',{name:'Search imported messages'}).fill('日本語')
  await page.getByLabel('Project',{exact:true}).selectOption({label:'E2E Project'})
  await page.getByRole('button',{name:'Search',exact:true}).click()
  // A title match returns the entire conversation, with honest total and pagination.
  await expect(page.getByRole('heading',{name:'1000 results · 100 shown',exact:true})).toBeVisible()
  await page.getByRole('button',{name:'Load more results'}).click()
  await expect(page.getByRole('heading',{name:'1000 results · 200 shown',exact:true})).toBeVisible()
  await page.getByRole('button',{name:'Sources / Connections',exact:true}).click()
  await expect(page.locator('.panels .chip')).toHaveCount(6)
  await expect(page.getByText('手動取り込み / 合成',{exact:true})).toBeVisible()
  await page.getByRole('button',{name:'Overview',exact:true}).click()
  await page.getByRole('button',{name:'Check stored data integrity'}).click()
  await expect(page.getByRole('status')).toContainText('整合性: PASS')
  await page.setViewportSize({width:390,height:844})
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth)).toBe(true)
  await page.screenshot({path:'test-results/overview-mobile.png',fullPage:true})
  await page.setViewportSize({width:1440,height:1000})
  await page.getByRole('button',{name:'Sources / Connections',exact:true}).click()
  await page.screenshot({path:'test-results/connections-desktop.png',fullPage:true})
  await page.getByRole('button',{name:'Overview',exact:true}).click()
  await page.getByRole('button',{name:'Lock workspace'}).click()
  await expect(page.getByText('LOCAL WORKSPACE LOCKED',{exact:true})).toBeVisible()
  expect(await page.evaluate(()=>sessionStorage.getItem('nexus-local-key'))).toBeNull()
  await expect(page.locator('.stats strong').nth(2)).toHaveText('—')
  expect(pageErrors).toEqual([])
})

test('actual browser: missing/foreign authorization cannot expose private API data',async({page,request})=>{
  const unauthenticated=await request.get('http://127.0.0.1:8788/api/v1/conversations')
  expect(unauthenticated.status()).toBe(401)
  const foreign=await request.get('http://127.0.0.1:8788/api/v1/conversations',
    {headers:{Origin:'http://attacker.invalid',Authorization:'Bearer '+syntheticKey}})
  expect(foreign.status()).toBe(403)
  await page.goto('/')
  await page.getByLabel('Local access key').fill('synthetic-wrong-key-not-a-real-secret')
  await page.getByRole('button',{name:'Unlock local workspace'}).click()
  await expect(page.getByRole('alert')).toContainText('ローカルアクセスキーを確認')
  await expect(page.getByText('LOCAL WORKSPACE LOCKED',{exact:true})).toBeVisible()
  await expect(page.locator('.stats strong').nth(1)).toHaveText('—')
})
