// fluid-shader.js
(function() {
  const canvas = document.getElementById('webgl-fluid-bg');
  if (!canvas) return;

  const ctxOpts = {
    alpha: false,
    depth: false,
    stencil: false,
    antialias: false,
    preserveDrawingBuffer: false,
    powerPreference: 'default',
  };
  const gl = canvas.getContext('webgl', ctxOpts) || canvas.getContext('experimental-webgl', ctxOpts);
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

  // Fragment shader: frame-constant blob centers & rotations are precomputed on CPU and passed as uniforms
  const fsSource = `
    #ifdef GL_FRAGMENT_PRECISION_HIGH
    precision highp float;
    #else
    precision mediump float;
    #endif
    varying vec2 v_uv;
    uniform float u_time;
    uniform vec3 u_color1;
    uniform vec3 u_color2;
    uniform vec3 u_color3;
    uniform vec3 u_color4;
    uniform vec2 u_p2;
    uniform vec2 u_p3;
    uniform vec2 u_p4;
    uniform mat2 u_rot2;
    uniform mat2 u_rot3;
    uniform mat2 u_rot4;

    // Interleaved Gradient Noise for band-free 8-bit dark gradient dithering
    float ign(vec2 p) {
      return fract(52.9829189 * fract(dot(p, vec2(0.06711056, 0.00583715))));
    }

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
      float bgWeight = 7.0;

      vec2 p2 = u_p2 + vec2(n1, n2) * 0.2;
      vec2 p3 = u_p3 - vec2(n2, n1) * 0.2;
      vec2 p4 = u_p4 + vec2(-n1, n2) * 0.2;

      // Calculate distance for each bubble (with pre-rotated ellipse projection)
      vec2 st2 = u_rot2 * (st - p2) * vec2(1.0, 1.6);
      vec2 st3 = u_rot3 * (st - p3) * vec2(1.5, 1.0);
      vec2 st4 = u_rot4 * (st - p4) * vec2(1.2, 1.5);

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
      float vignette = clamp(length(st - 0.5) * 1.2, 0.0, 1.0);
      color = mix(color, color * 0.2, vignette);

      // Triangular IGN screen-space dithering preserves true black while removing dark gradient banding
      float d1 = ign(gl_FragCoord.xy);
      float d2n = ign(gl_FragCoord.xy + vec2(5.588238, 17.13191));
      float dither = (d1 + d2n - 1.0) / 255.0;
      float nonBlack = step(0.001, max(color.r, max(color.g, color.b)));
      color = clamp(color + vec3(dither * nonBlack), 0.0, 1.0);

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
  if (!vertexShader || !fragmentShader) return;

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
  const p2Loc = gl.getUniformLocation(program, "u_p2");
  const p3Loc = gl.getUniformLocation(program, "u_p3");
  const p4Loc = gl.getUniformLocation(program, "u_p4");
  const rot2Loc = gl.getUniformLocation(program, "u_rot2");
  const rot3Loc = gl.getUniformLocation(program, "u_rot3");
  const rot4Loc = gl.getUniformLocation(program, "u_rot4");

  let currentColors = [
    [42/255, 8/255, 69/255], [100/255, 65/255, 165/255],
    [10/255, 17/255, 40/255], [18/255, 14/255, 43/255]
  ];
  let displayedColors = currentColors.map(c => [c[0], c[1], c[2]]);
  let targetColors = currentColors.map(c => [c[0], c[1], c[2]]);
  let transitionProgress = 1.0;

  // Pre-allocated uniform typed arrays to eliminate per-frame heap allocations
  const c1Buf = new Float32Array(currentColors[0]);
  const c2Buf = new Float32Array(currentColors[1]);
  const c3Buf = new Float32Array(currentColors[2]);
  const c4Buf = new Float32Array(currentColors[3]);
  const rot2Buf = new Float32Array(4);
  const rot3Buf = new Float32Array(4);
  const rot4Buf = new Float32Array(4);

  function fillRotMat2(buf, angle) {
    const c = Math.cos(angle);
    const s = Math.sin(angle);
    buf[0] = c;
    buf[1] = -s;
    buf[2] = s;
    buf[3] = c;
  }

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

  function srgbToLinear(c) {
    return Math.pow(Math.max(0, Math.min(1, c)), 2.2);
  }

  function linearToSrgb(c) {
    return Math.pow(Math.max(0, Math.min(1, c)), 1 / 2.2);
  }

  function writeLerpedLinear(outBuf, a, b, t) {
    outBuf[0] = linearToSrgb(srgbToLinear(a[0]) + (srgbToLinear(b[0]) - srgbToLinear(a[0])) * t);
    outBuf[1] = linearToSrgb(srgbToLinear(a[1]) + (srgbToLinear(b[1]) - srgbToLinear(a[1])) * t);
    outBuf[2] = linearToSrgb(srgbToLinear(a[2]) + (srgbToLinear(b[2]) - srgbToLinear(a[2])) * t);
  }

  let animTime = 0.0;
  let lastFrameTime = performance.now();
  let lastRenderTime = 0;
  let isRunning = false;
  let rafId = null;
  let isPlaying = false;
  let isFocused = typeof document.hasFocus === 'function' ? document.hasFocus() : true;
  let needsOneFrame = true;
  const transitionSpeed = 0.55;

  function drawFrame(timeSec) {
    gl.uniform1f(timeLoc, timeSec);
    gl.uniform3fv(c1Loc, c1Buf);
    gl.uniform3fv(c2Loc, c2Buf);
    gl.uniform3fv(c3Loc, c3Buf);
    gl.uniform3fv(c4Loc, c4Buf);

    gl.uniform2f(p2Loc, 0.5 + 0.4 * Math.cos(timeSec * 0.3), 0.5 + 0.4 * Math.sin(timeSec * 0.4));
    gl.uniform2f(p3Loc, 0.5 + 0.4 * Math.sin(timeSec * 0.5), 0.5 + 0.4 * Math.cos(timeSec * 0.2));
    gl.uniform2f(p4Loc, 0.5 + 0.4 * Math.cos(timeSec * 0.4), 0.5 + 0.4 * Math.sin(timeSec * 0.6));

    fillRotMat2(rot2Buf, timeSec * 0.5);
    fillRotMat2(rot3Buf, -timeSec * 0.3);
    fillRotMat2(rot4Buf, timeSec * 0.7);
    gl.uniformMatrix2fv(rot2Loc, false, rot2Buf);
    gl.uniformMatrix2fv(rot3Loc, false, rot3Buf);
    gl.uniformMatrix2fv(rot4Loc, false, rot4Buf);

    gl.drawArrays(gl.TRIANGLES, 0, 6);
  }

  function renderSingleFrame() {
    c1Buf.set(displayedColors[0]);
    c2Buf.set(displayedColors[1]);
    c3Buf.set(displayedColors[2]);
    c4Buf.set(displayedColors[3]);
    drawFrame(animTime);
    needsOneFrame = false;
  }

  function wakeLoop() {
    if (document.hidden) return;
    if (!isRunning) {
      isRunning = true;
      lastFrameTime = performance.now();
      lastRenderTime = 0;
      rafId = requestAnimationFrame(render);
    }
  }

  function stopLoop() {
    isRunning = false;
    if (rafId) {
      cancelAnimationFrame(rafId);
      rafId = null;
    }
  }

  window.updateFluidColors = function(hexColors) {
    if (!hexColors || hexColors.length === 0) return;
    // Snapshot mid-transition colors so rapid track changes blend seamlessly without snapping
    currentColors = displayedColors.map(c => [c[0], c[1], c[2]]);
    targetColors = [
      hexToVec3(hexColors[0]),
      hexToVec3(hexColors[1] || hexColors[0]),
      hexToVec3(hexColors[2] || hexColors[0]),
      hexToVec3(hexColors[3] || hexColors[1] || hexColors[0])
    ];
    transitionProgress = 0.0;
    needsOneFrame = true;
    wakeLoop();
  };

  window.setFluidPlaybackState = function(playing) {
    isPlaying = !!playing;
    if (isPlaying && !document.hidden) {
      wakeLoop();
    }
  };

  function resize() {
    const targetW = Math.max(1, Math.round(window.innerWidth * 0.4));
    const targetH = Math.max(1, Math.round(window.innerHeight * 0.4));
    const scaleCap = targetW > 512 ? (512 / targetW) : 1.0;
    canvas.width = Math.max(1, Math.round(targetW * scaleCap));
    canvas.height = Math.max(1, Math.round(targetH * scaleCap));
    gl.viewport(0, 0, canvas.width, canvas.height);
    if (!isRunning && !document.hidden) {
      renderSingleFrame();
    } else {
      needsOneFrame = true;
    }
  }
  window.addEventListener('resize', resize);
  resize();

  function render(now) {
    if (!isRunning) return;
    if (document.hidden) {
      stopLoop();
      return;
    }

    if (typeof now !== 'number') now = performance.now();
    const isTransitioning = transitionProgress < 1.0;

    // Adaptive FPS: 60fps during track color transitions, 24fps playing+focused,
    // 12fps playing+unfocused, and 0fps sleeping once settled while paused/idle.
    let targetInterval = 41.0;
    if (isTransitioning) {
      targetInterval = 15.5;
    } else if (isPlaying) {
      targetInterval = isFocused ? 41.0 : 83.0;
    } else if (!needsOneFrame) {
      stopLoop();
      return;
    }

    const elapsed = now - lastRenderTime;
    if (!needsOneFrame && lastRenderTime !== 0 && elapsed < targetInterval) {
      rafId = requestAnimationFrame(render);
      return;
    }

    lastRenderTime = lastRenderTime === 0 ? now : now - (elapsed % targetInterval);
    const dt = Math.min(Math.max(now - lastFrameTime, 0), 50);
    lastFrameTime = now;

    if (isPlaying || isTransitioning) {
      animTime += dt / 1000.0;
    }

    if (isTransitioning) {
      transitionProgress += (dt / 1000.0) * transitionSpeed;
      if (transitionProgress >= 1.0) transitionProgress = 1.0;
    }

    const t = transitionProgress;
    const easeT = t * t * t * (t * (t * 6 - 15) + 10);

    writeLerpedLinear(c1Buf, currentColors[0], targetColors[0], easeT);
    writeLerpedLinear(c2Buf, currentColors[1], targetColors[1], easeT);
    writeLerpedLinear(c3Buf, currentColors[2], targetColors[2], easeT);
    writeLerpedLinear(c4Buf, currentColors[3], targetColors[3], easeT);

    displayedColors = [
      [c1Buf[0], c1Buf[1], c1Buf[2]],
      [c2Buf[0], c2Buf[1], c2Buf[2]],
      [c3Buf[0], c3Buf[1], c3Buf[2]],
      [c4Buf[0], c4Buf[1], c4Buf[2]],
    ];

    if (transitionProgress >= 1.0) {
      currentColors = targetColors.map(c => [c[0], c[1], c[2]]);
    }

    drawFrame(animTime);
    needsOneFrame = false;

    if (isPlaying || transitionProgress < 1.0) {
      rafId = requestAnimationFrame(render);
    } else {
      stopLoop();
    }
  }

  window.addEventListener('focus', () => { isFocused = true; });
  window.addEventListener('blur', () => { isFocused = false; });

  document.addEventListener('visibilitychange', () => {
    if (document.hidden) {
      stopLoop();
    } else if (isPlaying || transitionProgress < 1.0 || needsOneFrame) {
      wakeLoop();
    }
  });

  window.addEventListener('DOMContentLoaded', () => {
    if (window.store && typeof window.store.subscribe === 'function') {
      window.setFluidPlaybackState(!!window.store.getState().isPlaying);
      window.store.subscribe('isPlaying', (state) => {
        window.setFluidPlaybackState(!!state.isPlaying);
      });
    }
  });

  wakeLoop();
})();
