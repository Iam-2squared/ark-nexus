// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from 'vitest'
import { createSingularityRenderer } from './components/singularityRenderer'

afterEach(()=>{ vi.restoreAllMocks(); vi.unstubAllGlobals() })

function fixture({compile=true,link=true,uniform=true}={}) {
  vi.stubGlobal('WebGL2RenderingContext',class {})
  const loseContext=vi.fn()
  const gl={
    VERTEX_SHADER:1,FRAGMENT_SHADER:2,COMPILE_STATUS:3,LINK_STATUS:4,TRIANGLES:5,NO_ERROR:0,
    createShader:vi.fn(()=>({})),shaderSource:vi.fn(),compileShader:vi.fn(),
    getShaderParameter:vi.fn(()=>compile),createProgram:vi.fn(()=>({})),
    attachShader:vi.fn(),linkProgram:vi.fn(),getProgramParameter:vi.fn(()=>link),
    getUniformLocation:vi.fn(()=>uniform?{}:null),viewport:vi.fn(),useProgram:vi.fn(),
    uniform2f:vi.fn(),drawArrays:vi.fn(),getError:vi.fn(()=>0),isContextLost:vi.fn(()=>false),
    deleteProgram:vi.fn(),deleteShader:vi.fn(),
    getExtension:vi.fn(()=>({loseContext})),
  }
  const canvas=document.createElement('canvas')
  vi.spyOn(canvas,'getContext').mockReturnValue(gl as unknown as WebGL2RenderingContext)
  return {gl,canvas,loseContext}
}

describe('bounded static singularity renderer',()=>{
  it('falls back without console/error contents when context creation is denied',()=>{
    vi.stubGlobal('WebGL2RenderingContext',class {})
    const canvas=document.createElement('canvas')
    vi.spyOn(canvas,'getContext').mockImplementation(()=>{ throw new Error('private driver diagnostic') })
    const log=vi.spyOn(console,'error')
    expect(createSingularityRenderer(canvas)).toBeNull()
    expect(log).not.toHaveBeenCalled()
  })

  it.each([{compile:false},{link:false},{uniform:false}])('cleans up a failed shader/program (%j)',options=>{
    const {gl,canvas}=fixture(options)
    expect(createSingularityRenderer(canvas)).toBeNull()
    expect(gl.deleteShader).toHaveBeenCalled()
    expect(gl.drawArrays).not.toHaveBeenCalled()
    if(options.compile!==false) expect(gl.deleteProgram).toHaveBeenCalledOnce()
  })

  it('caps a 4K/DPR4 buffer, draws once while idle and releases resources once',()=>{
    const {gl,canvas,loseContext}=fixture()
    const scene=createSingularityRenderer(canvas)!
    expect(scene.draw(3840,2160,4)).toBe(true)
    expect(canvas.width).toBeLessThanOrEqual(1600)
    expect(canvas.height).toBeLessThanOrEqual(900)
    expect(canvas.width*canvas.height).toBeLessThanOrEqual(900_000)
    expect(canvas.width/canvas.height).toBeCloseTo(3840/2160,2)
    for(let i=0;i<10;i++) expect(scene.draw(3840,2160,4)).toBe(true)
    expect(gl.drawArrays).toHaveBeenCalledOnce()
    scene.dispose();scene.dispose()
    expect(gl.deleteProgram).toHaveBeenCalledOnce()
    expect(gl.deleteShader).toHaveBeenCalledTimes(2)
    expect(loseContext).toHaveBeenCalledOnce()
    expect(scene.draw(320,390,1)).toBe(false)
    expect(gl.drawArrays).toHaveBeenCalledOnce()
  })

  it('rejects invalid dimensions before allocating a buffer or drawing',()=>{
    const {gl,canvas}=fixture()
    const scene=createSingularityRenderer(canvas)!
    for(const [w,h,dpr] of [[0,600,1],[320,-1,1],[NaN,600,1],[Infinity,600,1],[320,600,NaN]]) {
      expect(scene.draw(w,h,dpr)).toBe(false)
    }
    expect(gl.drawArrays).not.toHaveBeenCalled()
    scene.dispose()
  })

  it('allows StrictMode effect replay on a connected canvas and releases it after removal',()=>{
    const {gl,canvas,loseContext}=fixture()
    document.body.appendChild(canvas)
    try {
      const first=createSingularityRenderer(canvas)!
      expect(first.draw(400,600,1)).toBe(true)
      first.dispose()
      expect(loseContext).not.toHaveBeenCalled()
      const replay=createSingularityRenderer(canvas)!
      expect(replay.draw(400,600,1)).toBe(true)
      canvas.remove()
      replay.dispose()
      expect(gl.deleteProgram).toHaveBeenCalledTimes(2)
      expect(loseContext).toHaveBeenCalledOnce()
    } finally { canvas.remove() }
  })

  it('handles a lost context and a failed draw without reporting a rendered scene',()=>{
    const {gl,canvas}=fixture()
    const scene=createSingularityRenderer(canvas)!
    gl.isContextLost.mockReturnValue(true)
    expect(scene.draw(400,600,1)).toBe(false)
    expect(gl.drawArrays).not.toHaveBeenCalled()
    gl.isContextLost.mockReturnValue(false)
    gl.getError.mockReturnValue(1282)
    expect(scene.draw(400,600,1)).toBe(false)
    scene.dispose()
  })
})
