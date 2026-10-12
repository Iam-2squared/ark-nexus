#version 300 es
precision highp float;

uniform vec2 uResolution;
out vec4 fragmentColor;

float hash(vec3 p) {
  p = fract(p * .1031);
  p += dot(p, p.yzx + 33.33);
  return fract((p.x + p.y) * p.z);
}

float noise(vec3 p) {
  vec3 i = floor(p), f = fract(p);
  f = f * f * (3. - 2. * f);
  return mix(mix(mix(hash(i), hash(i + vec3(1,0,0)), f.x),
                 mix(hash(i + vec3(0,1,0)), hash(i + vec3(1,1,0)), f.x), f.y),
             mix(mix(hash(i + vec3(0,0,1)), hash(i + vec3(1,0,1)), f.x),
                 mix(hash(i + vec3(0,1,1)), hash(i + vec3(1,1,1)), f.x), f.y), f.z);
}

float gas(vec3 p) {
  float r = length(p.xz);
  float angle = atan(p.z, p.x) + 2.8 * log(r);
  vec3 q = vec3(cos(angle) * r, sin(angle) * r, p.y * 9.);
  float n = .52 * noise(q * 1.8);
  n += .27 * noise(q * 4.1 + 7.);
  n += .14 * noise(q * 9.7 + 19.);
  n += .07 * noise(q * 23.1 + 43.);
  return .16 + 2.7 * n * n;
}

void main() {
  vec2 uv = (2. * gl_FragCoord.xy - uResolution) / uResolution.y;
  // A tilted camera and an accretion volume, rather than drawn screen-space lines.
  float tilt = .13;
  uv = mat2(cos(tilt), -sin(tilt), sin(tilt), cos(tilt)) * uv;
  vec3 origin = vec3(0., 3.25, 16.);
  vec3 forward = normalize(-origin);
  vec3 right = vec3(1., 0., 0.);
  vec3 up = normalize(cross(right, forward));
  float focal = 4.2 * min(1., uResolution.x / uResolution.y * .84);
  vec3 velocity = normalize(forward * focal + uv.x * right + uv.y * up);
  vec3 position = origin;
  float momentum = dot(cross(position, velocity), cross(position, velocity));
  vec3 radiance = vec3(0.);
  float transmission = 1.;
  bool captured = false;

  // Bounded approximate Schwarzschild light bending. Artistic visual, not scientific evidence.
  for (int i = 0; i < 200; i++) {
    float radius = length(position);
    if (radius < 1.02) { captured = true; break; }
    if (radius > 30.) break;
    float stepSize = clamp(radius * .085, .045, .65);
    vec3 acceleration = -1.5 * momentum * position / pow(radius, 5.);
    vec3 next = position + velocity * stepSize + .5 * acceleration * stepSize * stepSize;
    float nextRadius = length(next);
    vec3 nextAcceleration = -1.5 * momentum * next / pow(max(nextRadius, .8), 5.);
    velocity += .5 * (acceleration + nextAcceleration) * stepSize;

    // Integrate the tilted volume near the disk crossing, avoiding step-size aliasing.
    vec3 midpoint = (position + next) * .5;
    float diskRadius = length(midpoint.xz);
    float thickness = .13 + .015 * diskRadius;
    if (diskRadius > 2.9 && diskRadius < 13. && abs(midpoint.y) < thickness * 3.) {
      float turbulence = gas(midpoint);
      float density = turbulence * exp(-midpoint.y * midpoint.y / (thickness * thickness));
      density *= smoothstep(2.9, 3.5, diskRadius) * (1. - smoothstep(8., 13., diskRadius));
      float opacity = 1. - exp(-density * stepSize * 1.8);
      float heat = pow(3.5 / diskRadius, 2.3);
      float doppler = clamp(1. + .34 * midpoint.x / diskRadius, .6, 1.4);
      vec3 emission = mix(vec3(.37,.48,.61), vec3(1.,.99,.97), smoothstep(.2,.95,heat));
      emission *= (.6 + 4.2 * heat) * doppler * (.6 + .5 * turbulence);
      radiance += transmission * opacity * emission;
      transmission *= 1. - opacity;
    }
    position = next;
  }

  // A localized shadow/atmosphere gives white light contrast on the white app canvas.
  float impact = sqrt(momentum);
  float atmosphere = .94 * exp(-pow(impact / 5.1, 4.));
  vec3 background = vec3(1.) - atmosphere * vec3(.92,.90,.86);
  if (captured) background = vec3(0.);
  vec3 light = 1. - exp(-radiance * 1.1);
  vec3 color = light + transmission * background * (1. - light);
  // The narrow photon ring is light accumulation, not an overlay of orbit strokes.
  float photon = exp(-pow((impact - 2.61) / .065, 2.)) * .16;
  color += photon * vec3(.80,.87,1.);
  float glow = exp(-pow((impact - 2.65) / .22, 2.)) * .085;
  color += glow * vec3(.77,.86,1.);
  color = clamp(color, 0., 1.);
  fragmentColor = vec4(pow(color, vec3(.93)), 1.);
}
