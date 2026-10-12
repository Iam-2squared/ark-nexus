import fragmentSource from './singularity.frag.glsl?raw'

const vertexSource = `#version 300 es
void main() {
  vec2 p = vec2((gl_VertexID << 1) & 2, gl_VertexID & 2);
  gl_Position = vec4(p * 2. - 1., 0., 1.);
}`

export function createSingularityRenderer(canvas:HTMLCanvasElement) {
  if(typeof WebGL2RenderingContext==='undefined') return null
  let gl:WebGL2RenderingContext|null
  try {
    // Static scene: retain the single frame, including during idle screenshots.
    gl=canvas.getContext('webgl2',{alpha:false,antialias:false,depth:false,stencil:false,
      preserveDrawingBuffer:true,powerPreference:'low-power'})
  } catch { return null }
  if(!gl) return null
  const context=gl
  const shaders:WebGLShader[]=[]
  let program:WebGLProgram|null=null
  let disposed=false
  function dispose() {
    if(disposed) return
    disposed=true
    if(program) context.deleteProgram(program)
    for(const shader of shaders) context.deleteShader(shader)
    // StrictMode replays effects on the same connected canvas. Release the owned context
    // after removal, while deleting shader/program resources on every cleanup.
    if(!canvas.isConnected && !context.isContextLost()) context.getExtension('WEBGL_lose_context')?.loseContext()
  }
  try {
    for(const [type,source] of [[context.VERTEX_SHADER,vertexSource],[context.FRAGMENT_SHADER,fragmentSource]] as const) {
      const shader=context.createShader(type)
      if(!shader) { dispose(); return null }
      shaders.push(shader)
      context.shaderSource(shader,source)
      context.compileShader(shader)
      if(!context.getShaderParameter(shader,context.COMPILE_STATUS)) { dispose(); return null }
    }
    program=context.createProgram()
    if(!program) { dispose(); return null }
    for(const shader of shaders) context.attachShader(program,shader)
    context.linkProgram(program)
    if(!context.getProgramParameter(program,context.LINK_STATUS)) { dispose(); return null }
    const resolution=context.getUniformLocation(program,'uResolution')
    if(resolution===null) { dispose(); return null }
    const linkedProgram=program
    let lastWidth=0,lastHeight=0
    return {
      draw(cssWidth:number,cssHeight:number,dpr:number) {
        if(disposed || context.isContextLost() || ![cssWidth,cssHeight,dpr].every(Number.isFinite)
          || cssWidth<=0 || cssHeight<=0 || dpr<=0) return false
        // At most 900k pixels, DPR 1.25 and 1600x900: bounded cost even on a 4K display.
        const scale=Math.min(Math.max(dpr,1),1.25,1600/cssWidth,900/cssHeight,
          Math.sqrt(900_000/(cssWidth*cssHeight)))
        const width=Math.max(1,Math.floor(cssWidth*scale)),height=Math.max(1,Math.floor(cssHeight*scale))
        if(width===lastWidth && height===lastHeight) return true
        try {
          canvas.width=width; canvas.height=height
          context.viewport(0,0,width,height)
          context.useProgram(linkedProgram)
          context.uniform2f(resolution,width,height)
          context.drawArrays(context.TRIANGLES,0,3)
          if(context.getError()!==context.NO_ERROR) return false
          lastWidth=width; lastHeight=height
          return true
        } catch { return false }
      },
      dispose,
    }
  } catch { dispose(); return null }
}
