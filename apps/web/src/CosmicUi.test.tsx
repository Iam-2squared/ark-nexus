// @vitest-environment jsdom
import { cleanup, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import App from './App'
import { SingularityHub } from './components/CosmicShell'

beforeEach(()=>{ sessionStorage.clear(); vi.stubGlobal('fetch',vi.fn()) })
afterEach(()=>{ cleanup(); vi.unstubAllGlobals() })

describe('White Singularity UI, locked synthetic-only workspace',()=>{
  it('fades the gravity field on both axes and keeps its caption inside the scene',async()=>{
    const files = await import('node:'+'fs') as {readFileSync:(path:string,encoding:'utf8')=>string}
    const style=document.createElement('style')
    style.textContent=files.readFileSync('src/style.css','utf8')
    document.head.appendChild(style)
    try {
      const {container}=render(<SingularityHub />)
      const visual=container.querySelector('.white-hole-visual')!
      expect(getComputedStyle(visual).maskImage.split('linear-gradient(')).toHaveLength(3)
      expect(getComputedStyle(visual).maskComposite).toBe('intersect')
      expect(getComputedStyle(container.querySelector('.hub-caption')!).position).toBe('absolute')
    } finally { style.remove() }
  })

  it('softens the enlarged light disk at the SVG frame edges',async()=>{
    const files = await import('node:'+'fs') as {readFileSync:(path:string,encoding:'utf8')=>string}
    const style=document.createElement('style')
    style.textContent=files.readFileSync('src/style.css','utf8')
    document.head.appendChild(style)
    try {
      const {container}=render(<SingularityHub />)
      const visual=container.querySelector('.white-hole-visual')!
      expect(getComputedStyle(visual).maskImage).toMatch(/^linear-gradient\(/)
    } finally { style.remove() }
  })

  it('draws a black void with bent light and a foreground disk rather than a lettered sphere',()=>{
    const {container}=render(<><SingularityHub /><SingularityHub /></>)
    const visuals=container.querySelectorAll('svg.white-hole-visual')
    expect(visuals).toHaveLength(2)
    for(const visual of visuals) {
      expect(visual.getAttribute('aria-hidden')).toBe('true')
      expect(visual.querySelector('.white-hole-void')?.getAttribute('fill')).toBe('#000')
      expect(visual.querySelectorAll('.lensed-light path').length).toBeGreaterThanOrEqual(12)
      expect(visual.querySelectorAll('.accretion-front path').length).toBeGreaterThanOrEqual(12)
      expect(visual.querySelector('text,image,foreignObject')).toBeNull()
    }
    const ids=[...container.querySelectorAll('svg defs [id]')].map(n=>n.id)
    expect(ids.length).toBeGreaterThan(0)
    expect(new Set(ids).size).toBe(ids.length)
    expect(container.querySelector('[href],[xlink\\:href]')).toBeNull()
  })

  it('uses a plain white canvas without the previous background nebula',async()=>{
    const files = await import('node:'+'fs') as {readFileSync:(path:string,encoding:'utf8')=>string}
    const style=document.createElement('style')
    style.textContent=files.readFileSync('src/style.css','utf8')
    document.head.appendChild(style)
    try {
      const {container}=render(<App />)
      const background=container.querySelector('.cosmic-background')!
      expect(getComputedStyle(background).backgroundColor).toBe('rgb(255, 255, 255)')
      expect(getComputedStyle(background).backgroundImage).toBe('none')
      expect(container.querySelector('.cosmic-nebula')).toBeNull()
      expect(container.querySelector('.constellation-lines path')).toBeNull()
    } finally { style.remove() }
  })

  it('has a decorative white cosmos and a labelled central hub without fake counts',async()=>{
    const {container}=render(<App />)
    await screen.findByText('LOCAL WORKSPACE LOCKED')
    expect(container.querySelector('.cosmic-background')?.getAttribute('aria-hidden')).toBe('true')
    expect(screen.getByRole('img',{name:'White Singularity · ARK Nexusの中心核'})).toBeTruthy()
    expect([...container.querySelectorAll('.stats strong')].map(n=>n.textContent)).toEqual(['—','—','—','—'])
    expect(fetch).not.toHaveBeenCalled()
  })

  it('keeps all six star routes labelled and clickable without unlocking private data',async()=>{
    render(<App />)
    const nav=screen.getByRole('navigation',{name:'Workspace constellation'})
    expect(nav.querySelectorAll('button')).toHaveLength(6)
    for(const label of ['Conversations','Universal Search','Projects','Sources / Connections','Import History','Overview']) {
      const button=screen.getByRole('button',{name:label})
      await userEvent.click(button)
      expect(button.getAttribute('aria-current')).toBe('page')
      expect(document.activeElement).toBe(button)
    }
    expect(fetch).not.toHaveBeenCalled()
    expect(screen.getByRole('button',{name:'Import fixture'}).hasAttribute('disabled')).toBe(true)
  })

  it('offers a keyboard skip link and never makes decorative stars focusable',()=>{
    const {container}=render(<App />)
    const link=screen.getByRole('link',{name:'Skip to workspace'})
    expect(link.getAttribute('href')).toBe('#workspace-content')
    expect(container.querySelector('#workspace-content')?.getAttribute('tabindex')).toBe('-1')
    expect(container.querySelector('.cosmic-background button, .cosmic-background [tabindex]')).toBeNull()
    expect(screen.getByText('SYNTHETIC ONLY')).toBeTruthy()
  })

  it('clips the unfocused skip link instead of hiding it outside the screenshot viewport',async()=>{
    // Node-only test I/O; no Node import enters the production app bundle.
    const files = await import('node:'+'fs') as {readFileSync:(path:string,encoding:'utf8')=>string}
    const style=document.createElement('style')
    style.textContent=files.readFileSync('src/style.css','utf8')
    document.head.appendChild(style)
    try {
      render(<App />)
      const link=screen.getByRole('link',{name:'Skip to workspace'})
      expect(getComputedStyle(link).clipPath).toBe('inset(50%)')
    } finally { style.remove() }
  })
})
