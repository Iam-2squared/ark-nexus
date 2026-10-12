import { type ReactNode } from 'react'
import { BlackHoleScene } from './BlackHoleScene'

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
      <BlackHoleScene />
    </div>
    <div className="hub-caption" aria-hidden="true"><b>NEXUS</b><span>EVERY THREAD. ONE GRAVITY.</span></div>
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
