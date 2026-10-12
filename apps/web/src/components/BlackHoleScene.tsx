import { useEffect, useId, useRef, useState } from 'react'
import { createSingularityRenderer } from './singularityRenderer'

function QuietFallback() {
  const id=useId()
  return <svg className="white-hole-fallback" viewBox="0 0 1600 900" preserveAspectRatio="xMidYMid slice"
    aria-hidden="true" focusable="false">
    <defs>
      <radialGradient id={id+'-aura'}>
        <stop offset=".65" stopColor="#788796" stopOpacity=".55" />
        <stop offset="1" stopColor="#fff" stopOpacity="0" />
      </radialGradient>
      <linearGradient id={id+'-gas'} x1="0" y1="0" x2="0" y2="1">
        <stop stopColor="#fff" /><stop offset=".5" stopColor="#e1eaf3" />
        <stop offset="1" stopColor="#d4e0ec" stopOpacity="0" />
      </linearGradient>
    </defs>
    <circle className="photon-halo" cx="800" cy="440" r="338" fill={'url(#'+id+'-aura)'} />
    <circle className="white-hole-void" cx="800" cy="440" r="310" fill="#000" />
    <ellipse cx="800" cy="535" rx="800" ry="120" transform="rotate(-9 800 535)" fill={'url(#'+id+'-gas)'} />
  </svg>
}

export function BlackHoleScene() {
  const ref=useRef<HTMLCanvasElement>(null)
  const [renderer,setRenderer]=useState<'fallback'|'webgl2'>('fallback')
  useEffect(()=>{
    const canvas=ref.current!
    if(window.matchMedia?.('(forced-colors: active)').matches) return
    const scene=createSingularityRenderer(canvas)
    if(!scene) return
    let active=true
    let timer:number|undefined
    function draw() {
      if(!active) return
      const rect=canvas.getBoundingClientRect()
      if(scene!.draw(rect.width,rect.height,window.devicePixelRatio||1)) setRenderer('webgl2')
      else { setRenderer('fallback'); scene!.dispose(); active=false }
    }
    function resize() {
      window.clearTimeout(timer)
      timer=window.setTimeout(draw,100)
    }
    function lost(event:Event) {
      event.preventDefault()
      active=false
      setRenderer('fallback')
      scene!.dispose()
    }
    const observer=typeof ResizeObserver==='undefined'?null:new ResizeObserver(resize)
    observer?.observe(canvas)
    canvas.addEventListener('webglcontextlost',lost)
    window.addEventListener('resize',resize)
    draw()
    return ()=>{
      active=false
      window.clearTimeout(timer)
      observer?.disconnect()
      canvas.removeEventListener('webglcontextlost',lost)
      window.removeEventListener('resize',resize)
      scene.dispose()
    }
  },[])
  return <div className="white-hole-visual" data-renderer={renderer} aria-hidden="true">
    <QuietFallback />
    <canvas ref={ref} className="singularity-canvas" aria-hidden="true" />
  </div>
}
