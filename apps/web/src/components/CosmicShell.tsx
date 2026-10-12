import { useId, type ReactNode } from 'react'

export type WorkspacePage = 'overview'|'search'|'conversations'|'projects'|'connections'|'imports'
type ApiState = 'loading'|'ready'|'unavailable'|'locked'
export type StarRoute = {id:WorkspacePage; label:string}
const stars = [[84,168],[201,419],[325,95],[434,689],[551,218],[652,857],[751,69],
  [842,502],[944,165],[1068,772],[1189,292],[1340,614],[1298,82],[115,824],[349,946],
  [1398,934],[610,439],[989,937],[45,549],[1239,488],[789,759],[515,56]]

export function CosmicBackground() {
  return <div className="cosmic-background" aria-hidden="true">
    <svg className="cosmic-stars" viewBox="0 0 1440 1000" preserveAspectRatio="none" focusable="false">
      {stars.map(([x,y],i)=><g key={i} transform={`translate(${x} ${y})`}>
        <circle r={i%3===0?2:1} />{i%4===0?<path d="M-6 0H6M0-6V6" />:null}
      </g>)}
      <path className="distant-orbit" d="M-100 720Q620-170 1550 460M-140 940Q730 220 1580 780" />
    </svg>
  </div>
}

const lensCurve='M-24 262C142 255 220 251 248 230C276 210 269 184 286 145C307 93 348 68 400 68C454 68 495 95 515 145C532 184 525 210 552 230C585 253 682 255 824 262'
const frontDisk='M0 260C158 242 268 234 400 234S645 242 800 260C649 296 523 310 400 310S150 296 0 260Z'
const lensBands=Array.from({length:18},(_,i)=>i)
const diskBands=Array.from({length:24},(_,i)=>i)

// Bounded static vectors: no animation loop, textures, network or simulation.
function WhiteBlackHole() {
  const id=useId()
  return <svg className="white-hole-visual" viewBox="80 0 640 380" aria-hidden="true" focusable="false">
    <defs>
      <linearGradient id={id+'-light'} x1="0" y1="0" x2="1" y2="0">
        <stop offset="0" stopColor="#9db8d3" stopOpacity="0" />
        <stop offset=".18" stopColor="#99b4d0" stopOpacity=".38" />
        <stop offset=".4" stopColor="#d0deee" stopOpacity=".85" />
        <stop offset=".55" stopColor="#b9cfea" stopOpacity=".9" />
        <stop offset=".82" stopColor="#9bb5d2" stopOpacity=".38" />
        <stop offset="1" stopColor="#9db8d3" stopOpacity="0" />
      </linearGradient>
      <linearGradient id={id+'-disk'} x1="0" y1="0" x2="0" y2="1">
        <stop offset="0" stopColor="#fff" />
        <stop offset=".3" stopColor="#e2ebf7" stopOpacity=".9" />
        <stop offset=".7" stopColor="#b5cce7" stopOpacity=".55" />
        <stop offset="1" stopColor="#eef3fa" stopOpacity="0" />
      </linearGradient>
      <radialGradient id={id+'-rim'}>
        <stop offset=".9" stopColor="#fff" stopOpacity="0" />
        <stop offset=".96" stopColor="#c4d5e9" stopOpacity=".5" />
        <stop offset="1" stopColor="#e9f0f9" stopOpacity="0" />
      </radialGradient>
      <filter id={id+'-glow'} x="-20%" y="-50%" width="140%" height="200%" colorInterpolationFilters="sRGB">
        <feGaussianBlur stdDeviation="5" />
      </filter>
      <linearGradient id={id+'-fade'} x1="0" y1="0" x2="1" y2="0">
        <stop offset="0" stopColor="#fff" stopOpacity="0" />
        <stop offset=".16" stopColor="#fff" /><stop offset=".84" stopColor="#fff" />
        <stop offset="1" stopColor="#fff" stopOpacity="0" />
      </linearGradient>
      <mask id={id+'-disk-mask'}><rect width="800" height="440" fill={'url(#'+id+'-fade)'} /></mask>
    </defs>
    <g transform="rotate(-12 400 240)">
      <g className="white-hole-glow" filter={'url(#'+id+'-glow)'} fill="none" stroke={'url(#'+id+'-light)'}>
        <path d={lensCurve} strokeWidth="36" opacity=".7" />
        <path d="M-20 270Q400 205 820 270" strokeWidth="30" opacity=".5" />
      </g>
      <g className="lensed-light" fill="none" stroke={'url(#'+id+'-light)'}>
        {lensBands.map(i=><path key={i} d={lensCurve} strokeWidth={i%3===0?2:1}
          opacity={.38+i%4*.12} transform={`translate(400 262) scale(${1+i*.012}) translate(-400 -262)`} />)}
        <path d={lensCurve} stroke="#fff" strokeWidth="3" opacity=".95" />
        <path d="M112 275C220 273 256 303 288 321C341 357 460 357 512 321C546 303 584 273 688 275"
          strokeWidth="7" opacity=".3" />
      </g>
      <circle cx="400" cy="219" r="143" fill={'url(#'+id+'-rim)'} />
      <circle className="white-hole-void" cx="400" cy="219" r="130" fill="#000" />
      <circle className="photon-edge" cx="400" cy="219" r="130" fill="none" stroke="#bdcfe5" strokeWidth=".8" opacity=".6" />
      <g className="accretion-front" mask={'url(#'+id+'-disk-mask)'}>
        <path d={frontDisk} fill={'url(#'+id+'-disk)'} />
        {diskBands.map(i=><path key={i} fill="none" stroke={i%4===0?'#fff':'url(#'+id+'-light)'}
          strokeWidth={i%4===0?1.8:1} opacity={i%4===0?.85:.7}
          d={`M0 ${258+i*.45}C150 ${242+i*1.6} 274 ${236+i*2.4} 400 ${236+i*2.4}S650 ${242+i*1.6} 800 ${258+i*.45}`} />)}
        <path d="M0 256C162 239 284 230 400 230S642 239 800 256" fill="none" stroke="#fff" strokeWidth="3" />
      </g>
    </g>
  </svg>
}

function RouteIcon({page}:{page:WorkspacePage}) {
  const paths:Record<WorkspacePage,string> = {
    overview:'M12 2L14.5 9.5 22 12 14.5 14.5 12 22 9.5 14.5 2 12 9.5 9.5Z',
    conversations:'M4 4H20V15H10L4 20Z M8 8H16 M8 11H13',
    search:'M16 16L21 21 M18 10A8 8 0 1 1 2 10A8 8 0 1 1 18 10',
    projects:'M3 6H9L11 9H21V20H3Z M3 6V4H9L11 6H19V9',
    connections:'M6 6L18 12 6 18 M8 6A2 2 0 1 1 4 6A2 2 0 1 1 8 6 M20 12A2 2 0 1 1 16 12A2 2 0 1 1 20 12 M8 18A2 2 0 1 1 4 18A2 2 0 1 1 8 18',
    imports:'M12 2V15 M7 10L12 15 17 10 M4 15V21H20V15',
  }
  return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.4"
    strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" focusable="false"><path d={paths[page]} /></svg>
}

export function StarNav({routes,page,onNavigate}:{routes:StarRoute[];page:WorkspacePage;onNavigate:(page:WorkspacePage)=>void}) {
  return <nav className="star-nav" aria-label="Workspace constellation">
    <svg className="constellation-lines" viewBox="0 0 1000 420" preserveAspectRatio="none" aria-hidden="true" focusable="false">
      <ellipse cx="500" cy="200" rx="350" ry="157" />
    </svg>
    {routes.map((route,i)=><button type="button" key={route.id} aria-label={route.label}
      aria-current={page===route.id?'page':undefined} className={'star-link star-'+route.id} onClick={()=>onNavigate(route.id)}>
      <span className="star-node" aria-hidden="true"><RouteIcon page={route.id} /></span>
      <span className="star-label">{route.label}<small aria-hidden="true">{String(i+1).padStart(2,'0')} / {route.id==='overview'?'HOME ORBIT':'WORKSPACE'}</small></span>
    </button>)}
  </nav>
}

export function SingularityHub() {
  return <div className="singularity-hub" role="img" aria-label="White Singularity · ARK Nexusの中心核">
    <div className="hub-coordinate" aria-hidden="true">01 / WHITE SINGULARITY</div>
    <div className="singularity-visual" aria-hidden="true">
      <WhiteBlackHole />
    </div>
    <div className="hub-caption" aria-hidden="true"><b>NEXUS</b><span>ONE CENTER. EVERY ORBIT.</span></div>
  </div>
}

export function StatusConstellation() {
  return <div className="status-constellation" aria-label="Current capability limits">
    <span><i />LOCAL-FIRST</span><span><i />SYNTHETIC ONLY</span>
    <span><i />LIVE SYNC OFF</span><span className="gate-state">V1 GATE / BLOCKED</span>
  </div>
}

export function MetricCard({label,value,detail,index}:{label:string;value:number|null;detail:string;index:number}) {
  return <div className="metric-card"><div className="metric-caption"><small>{label}</small>
    <span className="metric-index" aria-hidden="true">{String(index+1).padStart(2,'0')}</span></div>
    <strong>{value===null?'—':value.toLocaleString()}</strong><span>{detail}</span>
  </div>
}

export function OrbitPanel({children}:{children:ReactNode}) {
  return <article className="panel orbit-panel">{children}</article>
}

export function AppShell({page,apiState,children}:{page:WorkspacePage;apiState:ApiState;children:ReactNode}) {
  const labels:Record<ApiState,string> = {ready:'LOCAL API READY',loading:'CHECKING LOCAL API',
    locked:'LOCAL WORKSPACE LOCKED',unavailable:'LOCAL API UNAVAILABLE'}
  return <div className="layout cosmic-shell">
    <a className="skip-link" href="#workspace-content">Skip to workspace</a><CosmicBackground />
    <header className="topbar">
      <div className="brand"><span className="brand-orbit" aria-hidden="true">N</span>
        <div><b>ARK NEXUS</b><small>YOUR INTELLIGENCE, IN ORBIT</small></div></div>
      <div className="shell-location"><span className="location-dot" />WORKSPACE / {page.toUpperCase()}</div>
      <span className={'pill '+apiState} aria-live="polite">{labels[apiState]}</span>
    </header>
    <main id="workspace-content" tabIndex={-1}><div className="body">{children}</div></main>
  </div>
}
