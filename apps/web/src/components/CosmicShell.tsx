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

const lensCurve='M-200 516C170 484 382 478 480 438C542 410 512 359 542 269C581 163 673 146 800 146C927 146 1019 166 1058 269C1088 359 1058 410 1120 438C1218 478 1430 484 1800 516'
const frontDisk='M-200 516C185 450 550 434 800 434C1080 434 1400 470 1800 516C1450 630 1140 690 800 692C460 692 136 628-200 516Z'
const lensBands=Array.from({length:32},(_,i)=>i)
const diskBands=Array.from({length:38},(_,i)=>i)
const inflowCurves=[
  'M-160 168C160-65 1310-134 1640 210C1880 465 1380 792 1055 661C886 593 821 507 800 452',
  'M1760 718C1290 1104 86 952 60 479C48 273 468 250 621 324C731 377 782 430 800 452',
  'M-220 684C330 920 1545 991 1650 486C1730 110 1040 98 922 296C856 407 825 438 800 452',
]
const dust=Array.from({length:42},(_,i)=>{
  const angle=i*2.399
  return {x:800+Math.cos(angle)*(360+i%7*68),y:445+Math.sin(angle)*(195+i%6*38),r:i%5===0?2.4:1}
})

// Bounded static vectors: no animation loop, textures, network or simulation.
function WhiteBlackHole() {
  const id=useId()
  return <svg className="white-hole-visual" viewBox="0 0 1600 900" preserveAspectRatio="xMidYMid slice" aria-hidden="true" focusable="false">
    <defs>
      <linearGradient id={id+'-light'} x1="0" y1="0" x2="1" y2="0">
        <stop offset="0" stopColor="#65829f" stopOpacity="0" />
        <stop offset=".16" stopColor="#8ca7c5" stopOpacity=".55" />
        <stop offset=".37" stopColor="#e2edff" />
        <stop offset=".52" stopColor="#fff" />
        <stop offset=".68" stopColor="#b5c9e5" />
        <stop offset=".86" stopColor="#809cb9" stopOpacity=".55" />
        <stop offset="1" stopColor="#65829f" stopOpacity="0" />
      </linearGradient>
      <linearGradient id={id+'-disk'} gradientUnits="userSpaceOnUse" x1="0" y1="430" x2="0" y2="710">
        <stop offset="0" stopColor="#fff" />
        <stop offset=".18" stopColor="#dce8f9" />
        <stop offset=".36" stopColor="#9eb5d0" />
        <stop offset=".5" stopColor="#edf4ff" />
        <stop offset=".7" stopColor="#829cbf" stopOpacity=".8" />
        <stop offset="1" stopColor="#e6edf8" stopOpacity="0" />
      </linearGradient>
      <radialGradient id={id+'-rim'}>
        <stop offset=".83" stopColor="#829dbc" stopOpacity="0" />
        <stop offset=".92" stopColor="#7998bc" stopOpacity=".65" />
        <stop offset=".95" stopColor="#fff" />
        <stop offset="1" stopColor="#dce7f5" stopOpacity="0" />
      </radialGradient>
      <radialGradient id={id+'-field'}>
        <stop offset=".3" stopColor="#8099b2" stopOpacity="0" />
        <stop offset=".44" stopColor="#8ca5c2" stopOpacity=".36" />
        <stop offset=".65" stopColor="#c5d5e6" stopOpacity=".2" />
        <stop offset="1" stopColor="#fff" stopOpacity="0" />
      </radialGradient>
      <filter id={id+'-glow'} x="-15%" y="-40%" width="130%" height="180%" colorInterpolationFilters="sRGB">
        <feGaussianBlur stdDeviation="14" />
      </filter>
      <filter id={id+'-grain'} x="0" y="0" width="100%" height="100%" colorInterpolationFilters="sRGB">
        <feTurbulence type="fractalNoise" baseFrequency=".025 .15" numOctaves="2" seed="7" result="grain" />
        <feColorMatrix in="grain" type="saturate" values="0" />
        <feComponentTransfer result="soft-grain">
          <feFuncR type="linear" slope=".22" intercept=".39" />
          <feFuncG type="linear" slope=".22" intercept=".39" />
          <feFuncB type="linear" slope=".22" intercept=".39" />
        </feComponentTransfer>
        <feBlend in="SourceGraphic" in2="soft-grain" mode="soft-light" />
      </filter>
      <clipPath id={id+'-volume-clip'}><path d={frontDisk} /></clipPath>
      <linearGradient id={id+'-fade'} x1="0" y1="0" x2="1" y2="0">
        <stop offset="0" stopColor="#fff" stopOpacity="0" />
        <stop offset=".1" stopColor="#fff" /><stop offset=".9" stopColor="#fff" />
        <stop offset="1" stopColor="#fff" stopOpacity="0" />
      </linearGradient>
      <mask id={id+'-disk-mask'} maskUnits="userSpaceOnUse" x="-200" y="0" width="2000" height="900">
        <rect x="-200" width="2000" height="900" fill={'url(#'+id+'-fade)'} />
      </mask>
    </defs>
    <circle className="gravity-field" cx="800" cy="445" r="680" fill={'url(#'+id+'-field)'} />
    <g className="gravity-inflow" fill="none" stroke={'url(#'+id+'-light)'}>
      {Array.from({length:12},(_,i)=><path key={i} d={inflowCurves[i%3]} strokeWidth={i%3===0?1.4:.6}
        opacity={.26+i%3*.08} transform={`translate(800 450) scale(${1+Math.floor(i/3)*.09}) translate(-800 -450)`} />)}
    </g>
    <g className="gravity-dust" fill="#86a3c2" opacity=".55">
      {dust.map((point,i)=><circle key={i} cx={point.x} cy={point.y} r={point.r} opacity={.3+i%4*.16} />)}
    </g>
    <g transform="rotate(-9 800 450)">
      <g className="white-hole-glow" filter={'url(#'+id+'-glow)'} fill="none" stroke={'url(#'+id+'-light)'}>
        <path d={lensCurve} strokeWidth="100" opacity=".85" />
        <path d="M-200 514Q800 355 1800 514" strokeWidth="70" opacity=".65" />
      </g>
      <g className="lensed-light" fill="none" stroke={'url(#'+id+'-light)'}>
        <path d={lensCurve} strokeWidth="58" opacity=".72" />
        <path d={lensCurve} stroke="#fff" strokeWidth="24" opacity=".85" />
        {lensBands.map(i=><path key={i} d={lensCurve} strokeWidth={i%5===0?3.2:1}
          opacity={.25+i%6*.12} transform={`translate(800 480) scale(${1+i*.006}) translate(-800 -480)`} />)}
        <path d={lensCurve} stroke="#fff" strokeWidth="6" />
        <path d="M340 540C450 536 514 671 596 708C717 772 885 772 1008 708C1090 671 1155 536 1260 540"
          strokeWidth="18" opacity=".32" />
      </g>
      <circle className="photon-halo" cx="800" cy="440" r="338" fill={'url(#'+id+'-rim)'} />
      <circle className="white-hole-void" cx="800" cy="440" r="310" fill="#000" />
      <circle className="photon-edge" cx="800" cy="440" r="311" fill="none" stroke="#f7fbff" strokeWidth="4" />
      <g className="accretion-front" mask={'url(#'+id+'-disk-mask)'}>
        <g className="accretion-volume" clipPath={'url(#'+id+'-volume-clip)'}>
          <path d={frontDisk} fill={'url(#'+id+'-disk)'} filter={'url(#'+id+'-grain)'} />
        </g>
        {diskBands.map(i=><path key={i} fill="none" stroke={i%4===0?'#fff':'url(#'+id+'-light)'}
          strokeWidth={i%7===0?5:i%4===0?2.2:.8} opacity={i%4===0?.88:.42+i%3*.15}
          d={`M-200 ${506+i*1.35}C200 ${438+i*4.7} 550 ${430+i*6.5} 800 ${430+i*6.5}S1490 ${457+i*4.1} 1800 ${510+i*1.35}`} />)}
        <path d="M-200 502C205 437 550 424 800 424S1410 457 1800 502" fill="none" stroke="#fff" strokeWidth="9" />
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
