// fluid-shader.js
(function() {
  const canvas = document.getElementById('webgl-fluid-bg');
  if (!canvas) return;

  const gl = canvas.getContext('webgl') || canvas.getContext('experimental-webgl');
  if (!gl) return;

  // Vertex shader
  const vsSource = `
    attribute vec2 a_position;
    varying vec2 v_uv;
    void main() {
      v_uv = a_position * 0.5 + 0.5;
      v_uv.y = 1.0 - v_uv.y; 
      gl_Position = vec4(a_position, 0.0, 1.0);
    }
  `;

  // Fragment shader
  const fsSource = `
    precision mediump float;
    varying vec2 v_uv;
    uniform float u_time;
    uniform vec3 u_color1;
    uniform vec3 u_color2;
    uniform vec3 u_color3;
    uniform vec3 u_color4;

    // Simplex noise function
    vec3 mod289(vec3 x) { return x - floor(x * (1.0 / 289.0)) * 289.0; }
    vec2 mod289(vec2 x) { return x - floor(x * (1.0 / 289.0)) * 289.0; }
    vec3 permute(vec3 x) { return mod289(((x*34.0)+1.0)*x); }

    float snoise(vec2 v) {
      const vec4 C = vec4(0.211324865405187,  0.366025403784439, -0.577350269189626,  0.024390243902439);
      vec2 i  = floor(v + dot(v, C.yy) );
      vec2 x0 = v -   i + dot(i, C.xx);
      vec2 i1;
      i1 = (x0.x > x0.y) ? vec2(1.0, 0.0) : vec2(0.0, 1.0);
      vec4 x12 = x0.xyxy + C.xxzz;
      x12.xy -= i1;
      i = mod289(i);
      vec3 p = permute( permute( i.y + vec3(0.0, i1.y, 1.0 )) + i.x + vec3(0.0, i1.x, 1.0 ));
      vec3 m = max(0.5 - vec3(dot(x0,x0), dot(x12.xy,x12.xy), dot(x12.zw,x12.zw)), 0.0);
      m = m*m ;
      m = m*m ;
      vec3 x = 2.0 * fract(p * C.www) - 1.0;
      vec3 h = abs(x) - 0.5;
      vec3 ox = floor(x + 0.5);
      vec3 a0 = x - ox;
      m *= 1.79284291400159 - 0.85373472095314 * ( a0*a0 + h*h );
      vec3 g;
      g.x  = a0.x  * x0.x  + h.x  * x0.y;
      g.yz = a0.yz * x12.xz + h.yz * x12.yw;
      return 130.0 * dot(m, g);
    }

    void main() {
      vec2 st = v_uv;
      
      float n1 = snoise(st * 1.5 + u_time * 0.15);
      float n2 = snoise(st * 1.5 - u_time * 0.12);
      
      // Background weight (u_color1 is static and uniform)
      float bgWeight = 7.0; // Increased from 5.0 so the background is more dominant
      
      // Blobs (u_color2, u_color3, u_color4) moving around
      vec2 p2 = vec2(0.5 + 0.4*cos(u_time*0.3), 0.5 + 0.4*sin(u_time*0.4));
      vec2 p3 = vec2(0.5 + 0.4*sin(u_time*0.5), 0.5 + 0.4*cos(u_time*0.2));
      vec2 p4 = vec2(0.5 + 0.4*cos(u_time*0.4), 0.5 + 0.4*sin(u_time*0.6));
      
      p2 += vec2(n1, n2) * 0.2;
      p3 -= vec2(n2, n1) * 0.2;
      p4 += vec2(-n1, n2) * 0.2;

      // Rotation matrices for the bubbles
      float t2 = u_time * 0.5;
      float t3 = -u_time * 0.3;
      float t4 = u_time * 0.7;
      mat2 rot2 = mat2(cos(t2), -sin(t2), sin(t2), cos(t2));
      mat2 rot3 = mat2(cos(t3), -sin(t3), sin(t3), cos(t3));
      mat2 rot4 = mat2(cos(t4), -sin(t4), sin(t4), cos(t4));

      // Calculate distance for each bubble (with scaling to make them ellipses/ovals)
      vec2 st2 = rot2 * (st - p2) * vec2(1.0, 1.6);
      vec2 st3 = rot3 * (st - p3) * vec2(1.5, 1.0);
      vec2 st4 = rot4 * (st - p4) * vec2(1.2, 1.5);

      // +0.08 creates a distinct glowing core instead of a fuzzy blob
      float d2 = 1.0 / (length(st2) + 0.08);
      float d3 = 1.0 / (length(st3) + 0.08);
      float d4 = 1.0 / (length(st4) + 0.08);
      
      // Enhance bubble contrast to make them pop out from the background
      d2 = pow(d2, 2.4);
      d3 = pow(d3, 2.4);
      d4 = pow(d4, 2.4);
      
      float sum = bgWeight + d2 + d3 + d4;
      vec3 color = (u_color1 * bgWeight + u_color2 * d2 + u_color3 * d3 + u_color4 * d4) / sum;
      
      // Stronger vignette to make edges very deep
      float vignette = length(st - 0.5) * 1.2;
      color = mix(color, color * 0.2, vignette);
      
      gl_FragColor = vec4(color, 1.0);
    }
  `;

  function compileShader(gl, type, source) {
    const shader = gl.createShader(type);
    gl.shaderSource(shader, source);
    gl.compileShader(shader);
    if (!gl.getShaderParameter(shader, gl.COMPILE_STATUS)) {
      console.error('Shader compile error:', gl.getShaderInfoLog(shader));
      gl.deleteShader(shader);
      return null;
    }
    return shader;
  }

  const vertexShader = compileShader(gl, gl.VERTEX_SHADER, vsSource);
  const fragmentShader = compileShader(gl, gl.FRAGMENT_SHADER, fsSource);

  const program = gl.createProgram();
  gl.attachShader(program, vertexShader);
  gl.attachShader(program, fragmentShader);
  gl.linkProgram(program);

  if (!gl.getProgramParameter(program, gl.LINK_STATUS)) {
    console.error('Program link error:', gl.getProgramInfoLog(program));
    return;
  }

  gl.useProgram(program);

  const positions = new Float32Array([
    -1, -1,  1, -1, -1,  1,
    -1,  1,  1, -1,  1,  1,
  ]);
  const positionBuffer = gl.createBuffer();
  gl.bindBuffer(gl.ARRAY_BUFFER, positionBuffer);
  gl.bufferData(gl.ARRAY_BUFFER, positions, gl.STATIC_DRAW);

  const positionLocation = gl.getAttribLocation(program, "a_position");
  gl.enableVertexAttribArray(positionLocation);
  gl.vertexAttribPointer(positionLocation, 2, gl.FLOAT, false, 0, 0);

  const timeLoc = gl.getUniformLocation(program, "u_time");
  const c1Loc = gl.getUniformLocation(program, "u_color1");
  const c2Loc = gl.getUniformLocation(program, "u_color2");
  const c3Loc = gl.getUniformLocation(program, "u_color3");
  const c4Loc = gl.getUniformLocation(program, "u_color4");

  let currentColors = [
    [42/255, 8/255, 69/255], [100/255, 65/255, 165/255],
    [10/255, 17/255, 40/255], [18/255, 14/255, 43/255]
  ];
  let targetColors = [...currentColors];
  let transitionProgress = 1.0;

  function hexToVec3(hex) {
    if (!hex) return [0,0,0];
    hex = hex.replace('#', '');
    if (hex.length === 3) hex = hex.split('').map(c => c+c).join('');
    return [
      parseInt(hex.substring(0, 2), 16) / 255,
      parseInt(hex.substring(2, 4), 16) / 255,
      parseInt(hex.substring(4, 6), 16) / 255
    ];
  }

  window.updateFluidColors = function(hexColors) {
    if (!hexColors || hexColors.length === 0) return;
    targetColors = [
      hexToVec3(hexColors[0]),
      hexToVec3(hexColors[1] || hexColors[0]),
      hexToVec3(hexColors[2] || hexColors[0]),
      hexToVec3(hexColors[3] || hexColors[1] || hexColors[0])
    ];
    transitionProgress = 0.0;
  };

  function lerpVec3(a, b, t) {
    return [
      a[0] + (b[0] - a[0]) * t,
      a[1] + (b[1] - a[1]) * t,
      a[2] + (b[2] - a[2]) * t
    ];
  }

  function resize() {
    const pixelRatio = 0.25; 
    canvas.width = window.innerWidth * pixelRatio;
    canvas.height = window.innerHeight * pixelRatio;
    gl.viewport(0, 0, canvas.width, canvas.height);
  }
  window.addEventListener('resize', resize);
  resize();

  let startTime = Date.now();
  let lastFrameTime = Date.now();

  function render() {
    const now = Date.now();
    const dt = now - lastFrameTime;
    lastFrameTime = now;
    
    const time = (now - startTime) / 1000;
    
    if (transitionProgress < 1.0) {
      transitionProgress += (dt / 1000.0) * 0.6; 
      if (transitionProgress >= 1.0) transitionProgress = 1.0;
    }
    
    const easeT = transitionProgress < 0.5 ? 2 * transitionProgress * transitionProgress : -1 + (4 - 2 * transitionProgress) * transitionProgress;

    const c1 = lerpVec3(currentColors[0], targetColors[0], easeT);
    const c2 = lerpVec3(currentColors[1], targetColors[1], easeT);
    const c3 = lerpVec3(currentColors[2], targetColors[2], easeT);
    const c4 = lerpVec3(currentColors[3], targetColors[3], easeT);

    if (transitionProgress >= 1.0) {
      currentColors = [...targetColors];
    }

    gl.uniform1f(timeLoc, time);
    gl.uniform3fv(c1Loc, c1);
    gl.uniform3fv(c2Loc, c2);
    gl.uniform3fv(c3Loc, c3);
    gl.uniform3fv(c4Loc, c4);

    gl.drawArrays(gl.TRIANGLES, 0, 6);
    requestAnimationFrame(render);
  }

  requestAnimationFrame(render);
})();
