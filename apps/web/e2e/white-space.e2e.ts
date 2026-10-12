import { expect, test } from '@playwright/test'
import { syntheticKey } from '../playwright.config'

const routes=['Overview','Conversations','Universal Search','Projects','Sources / Connections','Import History']

async function renderedCore(page:import('@playwright/test').Page) {
  const scene=page.locator('.white-hole-visual')
  await expect(scene).toHaveAttribute('data-renderer','webgl2',{timeout:20_000})
  await expect.poll(()=>scene.locator('canvas').evaluate(el=>{
    const canvas=el as HTMLCanvasElement
    const box=canvas.getBoundingClientRect()
    return Math.abs(canvas.width/canvas.height-box.width/box.height)
  }),{timeout:20_000}).toBeLessThan(.005)
  return scene.locator('canvas').evaluate(el=>{
    const canvas=el as HTMLCanvasElement
    const gl=canvas.getContext('webgl2')!
    const pixels=new Uint8Array(canvas.width*canvas.height*4)
    gl.readPixels(0,0,canvas.width,canvas.height,gl.RGBA,gl.UNSIGNED_BYTE,pixels)
    let longest=0,black=0,light=0
    for(let y=0;y<canvas.height;y++) {
      let run=0
      for(let x=0;x<canvas.width;x++) {
        const i=4*(y*canvas.width+x)
        if(pixels[i]<18 && pixels[i+1]<18 && pixels[i+2]<18) {
          black++;run++;longest=Math.max(longest,run)
        } else run=0
        if(pixels[i]>220 && pixels[i+1]>220 && pixels[i+2]>220) light++
      }
    }
    return {diameter:longest*canvas.getBoundingClientRect().width/canvas.width,
      blackFraction:black/(canvas.width*canvas.height),lightFraction:light/(canvas.width*canvas.height),
      bufferPixels:canvas.width*canvas.height}
  })
}

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
  const core=await renderedCore(page)
  expect(core.blackFraction).toBeGreaterThan(.03)
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
    const hole=page.locator('.white-hole-visual')
    await expect(hole).toBeVisible()
    await expect(hole).toHaveCSS('mask-image',/^linear-gradient\(/)
    await expect(hole).toHaveCSS('mask-composite',/^intersect(?:, intersect)?$/)
    await expect(page.locator('.hub-caption')).toHaveCSS('position','absolute')
    await expect(page.locator('.constellation-lines')).toHaveCSS('display','none')
    await expect(page.locator('.white-hole-void')).toHaveAttribute('fill','#000')
    // Measure actual black pixels from the rendered shader, not a hidden fallback/source radius.
    const core=await renderedCore(page)
    const minimumDiameter:Record<number,number>={320:120,390:150,768:220,1024:275,1440:275}
    expect(core.diameter).toBeGreaterThanOrEqual(minimumDiameter[width])
    expect(core.blackFraction).toBeGreaterThan(.03)
    expect(core.lightFraction).toBeGreaterThan(.05)
    expect(core.bufferPixels).toBeLessThanOrEqual(900_000)
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
  await expect(page.locator('.white-hole-void')).toHaveAttribute('fill','#000')
  await expect(page.locator('.white-hole-visual text,.white-hole-visual image')).toHaveCount(0)
  await expect(page.locator('.white-hole-visual')).toHaveCSS('pointer-events','none')
  const core=await renderedCore(page)
  expect(core.diameter).toBeGreaterThanOrEqual(275)
  expect(core.blackFraction).toBeGreaterThan(.03)
  expect(core.lightFraction).toBeGreaterThan(.05)
  // Unlock scrolls to its form; evidence must show the actual top of the home UI.
  await page.evaluate(()=>window.scrollTo(0,0))
  expect(await page.evaluate(()=>window.scrollY)).toBe(0)
  await expect(page.locator('.topbar')).toBeVisible()
  await page.screenshot({path:'test-results/overview-desktop.png'})
  await page.setViewportSize({width:390,height:844})
  await renderedCore(page)
  await page.evaluate(()=>window.scrollTo(0,0))
  await page.screenshot({path:'test-results/overview-mobile.png',fullPage:true})
  await page.getByRole('button',{name:'Lock workspace'}).click()
  await expect(page.locator('.stats strong')).toHaveText(['—','—','—','—'])
  expect(await page.evaluate(()=>sessionStorage.getItem('nexus-local-key'))).toBeNull()
  expect(failures).toEqual([])
})

test('white space: denied WebGL and an actually lost context keep the six routes usable',async({page})=>{
  const privateReads:string[]=[]
  const errors:string[]=[]
  page.on('pageerror',error=>errors.push(error.message))
  page.on('request',request=>{
    if(new URL(request.url()).pathname.startsWith('/api/v1/')) privateReads.push(request.method())
  })
  await page.goto('/')
  await renderedCore(page)
  const lost=await page.locator('.singularity-canvas').evaluate(el=>{
    const gl=(el as HTMLCanvasElement).getContext('webgl2')!
    const extension=gl.getExtension('WEBGL_lose_context')
    if(!extension) return false
    extension.loseContext()
    return true
  })
  expect(lost).toBe(true)
  await expect(page.locator('.white-hole-visual')).toHaveAttribute('data-renderer','fallback')
  await expect(page.locator('.white-hole-fallback')).toBeVisible()
  await page.getByRole('button',{name:'Universal Search',exact:true}).click()
  await expect(page.getByRole('button',{name:'Universal Search',exact:true})).toHaveAttribute('aria-current','page')
  await page.addInitScript(()=>{
    const original=HTMLCanvasElement.prototype.getContext
    HTMLCanvasElement.prototype.getContext=function(type:string,...args:unknown[]) {
      if(type==='webgl2') return null
      return Reflect.apply(original,this,[type,...args])
    } as typeof original
  })
  await page.reload()
  await expect(page.locator('.white-hole-visual')).toHaveAttribute('data-renderer','fallback')
  await expect(page.locator('.white-hole-fallback')).toBeVisible()
  for(const label of routes) {
    const button=page.getByRole('button',{name:label,exact:true})
    await button.click()
    await expect(button).toHaveAttribute('aria-current','page')
  }
  expect(privateReads).toEqual([])
  expect(errors).toEqual([])
})
