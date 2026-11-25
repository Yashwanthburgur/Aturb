/* The WebGL viewport of the ATURB viewer.
 *
 * Plain WebGL with no library: a shaded solid pass, a line pass for the
 * feature edges, the axes and the bounding box, and an orbit camera driven
 * by the pointer. The matrix and camera math lives in math3d.js.
 */
(function (global) {
  "use strict";
  var M = global.AturbMath3D;
  var BACKGROUND = [0.93, 0.94, 0.95];
  var PART_COLOR = [0.72, 0.75, 0.79];
  var EDGE_COLOR = [0.16, 0.18, 0.21];
  var BOX_COLOR = [0.35, 0.42, 0.52];
  var LIGHT = [0.42, 0.76, 0.5];
  var SOLID_VERTEX = "attribute vec3 aPosition; attribute vec3 aNormal; uniform mat4 uProjection; uniform mat4 uView; varying vec3 vNormal; void main() { vNormal = aNormal; gl_Position = uProjection * uView * vec4(aPosition, 1.0); }";
  var SOLID_FRAGMENT = "precision mediump float; varying vec3 vNormal; uniform vec3 uLight; uniform vec3 uColor; void main() { vec3 n = normalize(vNormal); if (!gl_FrontFacing) { n = -n; } float shade = 0.3 + 0.7 * max(dot(n, normalize(uLight)), 0.0); gl_FragColor = vec4(uColor * shade, 1.0); }";
  var LINE_VERTEX = "attribute vec3 aPosition; attribute vec3 aColor; uniform mat4 uProjection; uniform mat4 uView; varying vec3 vColor; void main() { vColor = aColor; gl_Position = uProjection * uView * vec4(aPosition, 1.0); }";
  var LINE_FRAGMENT = "precision mediump float; varying vec3 vColor; uniform float uAlpha; void main() { gl_FragColor = vec4(vColor, uAlpha); }";
  var canvas = null;
  var gl = null;
  var solidProgram = null;
  var lineProgram = null;
  var solid = { position: null, normal: null, count: 0 };
  var edges = { position: null, color: null, count: 0 };
  var axes = { position: null, color: null, count: 0 };
  var box = { position: null, color: null, count: 0 };
  var bounds = null;
  var camera = M.makeCamera();
  var mode = "shaded";
  var showAxes = true;
  var showBox = true;
  var ready = false;
  var frameNeeded = false;
  var dragging = false;
  var panning = false;
  var lastX = 0;
  var lastY = 0;
  var pendingMesh = null;
  var pendingMessage = null;
  var projection = null;
  var view = null;
  function byId(id) { return document.getElementById(id); }
  function showOverlay(title, detail) {
    var overlay = byId("viewport-overlay");
    if (byId("overlay-title")) { byId("overlay-title").textContent = title; }
    if (byId("overlay-detail")) { byId("overlay-detail").textContent = detail; }
    if (overlay) { overlay.hidden = false; }
  }
  function hideOverlay() {
    var overlay = byId("viewport-overlay");
    if (overlay) { overlay.hidden = true; }
  }
  function compile(type, source) {
    var shader = gl.createShader(type);
    gl.shaderSource(shader, source);
    gl.compileShader(shader);
    if (!gl.getShaderParameter(shader, gl.COMPILE_STATUS)) { throw new Error("the shader did not compile: " + gl.getShaderInfoLog(shader)); }
    return shader;
  }
  function makeProgram(vertex, fragment) {
    var program = gl.createProgram();
    gl.attachShader(program, compile(gl.VERTEX_SHADER, vertex));
    gl.attachShader(program, compile(gl.FRAGMENT_SHADER, fragment));
    gl.linkProgram(program);
    if (!gl.getProgramParameter(program, gl.LINK_STATUS)) { throw new Error("the program did not link: " + gl.getProgramInfoLog(program)); }
    var loc = function (name) { return gl.getAttribLocation(program, name); };
    var uni = function (name) { return gl.getUniformLocation(program, name); };
    return { program: program, position: loc("aPosition"), normal: loc("aNormal"), color: loc("aColor"), projection: uni("uProjection"), view: uni("uView"), light: uni("uLight"), fill: uni("uColor"), alpha: uni("uAlpha") };
  }
  function buffer(data) {
    var target = gl.createBuffer();
    gl.bindBuffer(gl.ARRAY_BUFFER, target);
    gl.bufferData(gl.ARRAY_BUFFER, data, gl.STATIC_DRAW);
    return target;
  }
  function colorBuffer(count, color) {
    var data = new Float32Array(count * 3);
    for (var i = 0; i < count; i++) { data[i * 3] = color[0]; data[i * 3 + 1] = color[1]; data[i * 3 + 2] = color[2]; }
    return buffer(data);
  }
  function bindAttribute(location, target) {
    if (location === null || location < 0 || !target) { return; }
    gl.bindBuffer(gl.ARRAY_BUFFER, target);
    gl.vertexAttribPointer(location, 3, gl.FLOAT, false, 0, 0);
    gl.enableVertexAttribArray(location);
  }
  function resize() {
    var ratio = global.devicePixelRatio || 1;
    var width = Math.max(1, Math.round(canvas.clientWidth * ratio));
    var height = Math.max(1, Math.round(canvas.clientHeight * ratio));
    if (canvas.width !== width || canvas.height !== height) { canvas.width = width; canvas.height = height; }
  }
  function drawLines(target, alpha) {
    if (!target.position || target.count === 0) { return; }
    gl.useProgram(lineProgram.program);
    gl.uniformMatrix4fv(lineProgram.projection, false, projection);
    gl.uniformMatrix4fv(lineProgram.view, false, view);
    gl.uniform1f(lineProgram.alpha, alpha);
    bindAttribute(lineProgram.position, target.position);
    bindAttribute(lineProgram.color, target.color);
    gl.drawArrays(gl.LINES, 0, target.count);
  }
  function render() {
    frameNeeded = false;
    if (!gl) { return; }
    resize();
    gl.viewport(0, 0, canvas.width, canvas.height);
    gl.clearColor(BACKGROUND[0], BACKGROUND[1], BACKGROUND[2], 1);
    gl.clear(gl.COLOR_BUFFER_BIT | gl.DEPTH_BUFFER_BIT);
    if (!ready) { return; }
    var near = Math.max(camera.distance * 0.01, 0.001);
    var far = camera.distance * 10 + (bounds ? bounds.radius * 10 : 100) + 100;
    projection = M.perspective(camera.fov, canvas.width / Math.max(canvas.height, 1), near, far);
    view = M.lookAt(M.eyeOf(camera), camera.target, [0, 1, 0]);
    if (mode !== "wireframe" && solid.count > 0) {
      gl.useProgram(solidProgram.program);
      gl.uniformMatrix4fv(solidProgram.projection, false, projection);
      gl.uniformMatrix4fv(solidProgram.view, false, view);
      gl.uniform3f(solidProgram.light, LIGHT[0], LIGHT[1], LIGHT[2]);
      gl.uniform3f(solidProgram.fill, PART_COLOR[0], PART_COLOR[1], PART_COLOR[2]);
      bindAttribute(solidProgram.position, solid.position);
      bindAttribute(solidProgram.normal, solid.normal);
      gl.drawArrays(gl.TRIANGLES, 0, solid.count);
    }
    if (mode !== "shaded") { drawLines(edges, 1); }
    if (showAxes) { drawLines(axes, 1); }
    if (showBox) { drawLines(box, 0.85); }
  }
  function requestRender() {
    if (frameNeeded) { return; }
    frameNeeded = true;
    global.requestAnimationFrame(render);
  }
  /* Re-frame the camera on the bounding sphere of the mesh. */
  function resetView() {
    if (!bounds) { return; }
    M.frameCamera(camera, bounds, canvas.clientWidth / Math.max(canvas.clientHeight, 1));
    requestRender();
  }
  function setMesh(payload) {
    if (!gl) { pendingMesh = payload; return; }
    var positions = payload && payload.positions ? payload.positions : [];
    var indices = payload && payload.indices ? payload.indices : [];
    if (!positions.length || !indices.length) { setEmptyState("the mesh payload holds no triangle"); return; }
    bounds = M.computeBounds(positions);
    var flat = M.buildFlatShadedMesh(positions, indices);
    solid.position = buffer(flat.positions);
    solid.normal = buffer(flat.normals);
    solid.count = flat.vertexCount;
    var edgeData = M.buildEdgeLines(positions, indices);
    edges.position = buffer(edgeData);
    edges.color = colorBuffer(edgeData.length / 3, EDGE_COLOR);
    edges.count = edgeData.length / 3;
    var axisData = M.buildAxes(bounds);
    axes.position = buffer(axisData.positions);
    axes.color = buffer(axisData.colors);
    axes.count = axisData.positions.length / 3;
    var boxData = M.buildBoxLines(bounds);
    box.position = buffer(boxData);
    box.color = colorBuffer(boxData.length / 3, BOX_COLOR);
    box.count = boxData.length / 3;
    ready = true;
    hideOverlay();
    resetView();
  }
  /* The failed or empty workspace: clear the scene and show the reason. */
  function setEmptyState(message) {
    if (!gl) { pendingMessage = message; return; }
    ready = false;
    bounds = null;
    solid.count = 0; edges.count = 0; axes.count = 0; box.count = 0;
    showOverlay("No geometry to draw", message || "the workspace holds no usable STEP file");
    requestRender();
  }
  function onPointerDown(event) {
    if (!ready) { return; }
    dragging = true;
    panning = event.shiftKey || event.button === 1 || event.button === 2;
    lastX = event.clientX;
    lastY = event.clientY;
    if (canvas.setPointerCapture) { canvas.setPointerCapture(event.pointerId); }
    event.preventDefault();
  }
  function onPointerMove(event) {
    if (!dragging) { return; }
    var dx = event.clientX - lastX;
    var dy = event.clientY - lastY;
    lastX = event.clientX;
    lastY = event.clientY;
    if (panning) { M.pan(camera, dx, dy, canvas.clientHeight); } else { M.orbit(camera, dx, dy); }
    requestRender();
  }
  function onPointerUp(event) {
    dragging = false;
    if (canvas.releasePointerCapture && canvas.hasPointerCapture && canvas.hasPointerCapture(event.pointerId)) { canvas.releasePointerCapture(event.pointerId); }
  }
  function onWheel(event) {
    if (!ready) { return; }
    event.preventDefault();
    M.zoom(camera, event.deltaY, bounds ? bounds.radius : 1);
    requestRender();
  }
  function each(nodes, action) { Array.prototype.forEach.call(nodes, action); }
  /* The toolbar: the view mode, the two overlays and the reset. */
  function wireToolbar() {
    var modeButtons = document.querySelectorAll("[data-mode]");
    each(modeButtons, function (button) {
      button.addEventListener("click", function () {
        mode = button.getAttribute("data-mode");
        each(modeButtons, function (other) { other.classList.toggle("is-active", other === button); });
        requestRender();
      });
    });
    each(document.querySelectorAll("[data-toggle]"), function (button) {
      button.addEventListener("click", function () {
        var on = !button.classList.contains("is-active");
        button.classList.toggle("is-active", on);
        if (button.getAttribute("data-toggle") === "axes") { showAxes = on; } else { showBox = on; }
        requestRender();
      });
    });
    if (byId("reset-view")) { byId("reset-view").addEventListener("click", resetView); }
  }
  function wireControls() {
    canvas.addEventListener("pointerdown", onPointerDown);
    canvas.addEventListener("pointermove", onPointerMove);
    canvas.addEventListener("pointerup", onPointerUp);
    canvas.addEventListener("pointercancel", onPointerUp);
    canvas.addEventListener("wheel", onWheel, { passive: false });
    canvas.addEventListener("contextmenu", function (event) { event.preventDefault(); });
  }
  function init() {
    canvas = byId("viewport-canvas");
    if (!canvas) { return; }
    gl = canvas.getContext("webgl2") || canvas.getContext("webgl") || canvas.getContext("experimental-webgl");
    if (!gl) { showOverlay("WebGL is unavailable", "this browser has no WebGL context, so the viewport cannot draw"); return; }
    try {
      solidProgram = makeProgram(SOLID_VERTEX, SOLID_FRAGMENT);
      lineProgram = makeProgram(LINE_VERTEX, LINE_FRAGMENT);
    } catch (error) {
      showOverlay("The shaders did not build", String(error && error.message ? error.message : error));
      return;
    }
    gl.enable(gl.DEPTH_TEST);
    gl.depthFunc(gl.LEQUAL);
    gl.disable(gl.CULL_FACE);
    gl.enable(gl.BLEND);
    gl.blendFunc(gl.SRC_ALPHA, gl.ONE_MINUS_SRC_ALPHA);
    gl.enable(gl.POLYGON_OFFSET_FILL);
    gl.polygonOffset(1, 1);
    wireControls();
    wireToolbar();
    global.addEventListener("resize", requestRender);
    if (pendingMesh) { var mesh = pendingMesh; pendingMesh = null; setMesh(mesh); }
    else if (pendingMessage) { var note = pendingMessage; pendingMessage = null; setEmptyState(note); }
    requestRender();
  }
  global.AturbViewer = { setMesh: setMesh, setEmptyState: setEmptyState, resetView: resetView };
  if (document.readyState === "loading") { document.addEventListener("DOMContentLoaded", init); } else { init(); }
})(window);
