// @vitest-environment jsdom
import { cleanup, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import App from './App'

beforeEach(()=>{ sessionStorage.clear(); vi.stubGlobal('fetch',vi.fn()) })
afterEach(()=>{ cleanup(); vi.unstubAllGlobals() })

describe('White Singularity UI, locked synthetic-only workspace',()=>{
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
})
