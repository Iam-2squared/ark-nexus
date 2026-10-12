import { expect, test } from '@playwright/test'
import { syntheticKey } from '../playwright.config'

const routes=['Overview','Conversations','Universal Search','Projects','Sources / Connections','Import History']

test('white space: all six native star routes retain keyboard focus while locked',async({page})=>{
  const privateReads:string[]=[]
  page.on('request',request=>{
    if(new URL(request.url()).pathname.startsWith('/api/v1/')) privateReads.push(request.method())
  })
  await page.goto('/')
  await expect(page.getByText('LOCAL WORKSPACE LOCKED',{exact:true})).toBeVisible()
  await expect(page.getByRole('img',{name:'White Singularity · ARK Nexusの中心核'})).toBeVisible()
  const nav=page.getByRole('navigation',{name:'Workspace constellation'})
  await expect(nav.getByRole('button')).toHaveCount(6)
  for(const label of routes) {
    const button=nav.getByRole('button',{name:label,exact:true})
    await button.focus()
    await page.keyboard.press('Enter')
    await expect(button).toHaveAttribute('aria-current','page')
    await expect(button).toBeFocused()
    const rect=await button.boundingBox()
    expect(rect!.height).toBeGreaterThanOrEqual(44)
    expect(rect!.width).toBeGreaterThanOrEqual(44)
  }
  expect(privateReads).toEqual([])
  await nav.getByRole('button',{name:'Overview',exact:true}).click()
  await expect(page.locator('.stats strong')).toHaveText(['—','—','—','—'])
  await expect(page.getByRole('link',{name:'Skip to workspace'})).toHaveCSS('clip-path','inset(50%)')
  await page.evaluate(()=>window.scrollTo(0,0))
  await expect(page.locator('.topbar')).toBeVisible()
  await page.screenshot({path:'test-results/overview-locked.png'})
})

test('white space: responsive constellation has no overflow or obscured star controls',async({page})=>{
  await page.emulateMedia({reducedMotion:'reduce'})
  await page.goto('/')
  for(const width of [320,390,768,1024,1440]) {
    await page.setViewportSize({width,height:1000})
    const nav=page.getByRole('navigation',{name:'Workspace constellation'})
    for(const label of routes) {
      const button=nav.getByRole('button',{name:label,exact:true})
      await button.click()
      await expect(button).toHaveAttribute('aria-current','page')
      expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth)).toBe(true)
    }
    await nav.getByRole('button',{name:'Overview',exact:true}).click()
    expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth)).toBe(true)
    const hole=page.locator('svg.white-hole-visual')
    await expect(hole).toBeVisible()
    const holeBox=await hole.boundingBox()
    expect(holeBox!.x).toBeGreaterThanOrEqual(0)
    expect(holeBox!.x+holeBox!.width).toBeLessThanOrEqual(width)
    await expect(page.locator('.cosmic-background')).toHaveCSS('background-color','rgb(255, 255, 255)')
    await expect(page.locator('.cosmic-background')).toHaveCSS('background-image','none')
    await expect(page.locator('.constellation-lines path')).toHaveCount(0)
  }
  expect(await page.locator('.star-link').first().evaluate(el=>getComputedStyle(el).transitionDuration)).toBe('0s')
  await page.getByRole('link',{name:'Skip to workspace'}).focus()
  await expect(page.getByRole('link',{name:'Skip to workspace'})).toHaveCSS('clip-path','none')
  await page.keyboard.press('Enter')
  await expect(page.locator('#workspace-content')).toBeFocused()
})

test('white space: real synthetic API snapshot and desktop singularity screenshot',async({page})=>{
  const failures:string[]=[]
  page.on('pageerror',error=>failures.push(error.message))
  await page.goto('/')
  await page.getByLabel('Local access key').fill(syntheticKey)
  await page.getByRole('button',{name:'Unlock local workspace'}).click()
  await expect(page.getByText('LOCAL API READY',{exact:true})).toBeVisible()
  await expect(page.locator('.stats strong')).toHaveCount(4)
  for(const metric of await page.locator('.stats strong').allTextContents()) expect(metric).toMatch(/^[0-9,]+$/)
  await expect(page.getByText('SYNTHETIC ONLY',{exact:true})).toBeVisible()
  await expect(page.getByText('V1 GATE / BLOCKED',{exact:true})).toBeVisible()
  await expect(page.locator('.white-hole-void')).toHaveAttribute('fill','#fff')
  await expect(page.locator('.white-hole-visual text,.white-hole-visual image')).toHaveCount(0)
  await expect(page.locator('.white-hole-visual')).toHaveCSS('pointer-events','none')
  // Unlock scrolls to its form; evidence must show the actual top of the home UI.
  await page.evaluate(()=>window.scrollTo(0,0))
  expect(await page.evaluate(()=>window.scrollY)).toBe(0)
  await expect(page.locator('.topbar')).toBeVisible()
  await page.screenshot({path:'test-results/overview-desktop.png'})
  await page.getByRole('button',{name:'Lock workspace'}).click()
  await expect(page.locator('.stats strong')).toHaveText(['—','—','—','—'])
  expect(await page.evaluate(()=>sessionStorage.getItem('nexus-local-key'))).toBeNull()
  expect(failures).toEqual([])
})
