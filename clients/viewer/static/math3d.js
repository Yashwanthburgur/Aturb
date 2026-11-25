/* Pure math and mesh preparation for the ATURB viewer.
 *
 * Column-major 4x4 matrices, an orbit camera and the geometry the WebGL
 * viewport draws. No dependency and no bundler: a classic script that
 * publishes window.AturbMath3D.
 */
(function (global) {
  "use strict";
  var EPSILON = 1e-6;
  var DEFAULT_FOV = Math.PI / 4;
  var PITCH_LIMIT = Math.PI / 2 - 0.01;
  var DEFAULT_SHARP_ANGLE = 25;
  function add(a, b) { return [a[0] + b[0], a[1] + b[1], a[2] + b[2]]; }
  function sub(a, b) { return [a[0] - b[0], a[1] - b[1], a[2] - b[2]]; }
  function mul(a, k) { return [a[0] * k, a[1] * k, a[2] * k]; }
  function dot(a, b) { return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]; }
  function cross(a, b) {
    return [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]];
  }
  function length(a) { return Math.sqrt(dot(a, a)); }
  function normalize(a) { var n = length(a); return n < EPSILON ? [0, 0, 0] : mul(a, 1 / n); }
  function identity() {
    return new Float32Array([1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1]);
  }
  /* Multiply two column-major matrices: the result is a * b. */
  function multiply(a, b) {
    var out = new Float32Array(16);
    for (var c = 0; c < 4; c++) {
      for (var r = 0; r < 4; r++) {
        out[c * 4 + r] = a[r] * b[c * 4] + a[4 + r] * b[c * 4 + 1] +
          a[8 + r] * b[c * 4 + 2] + a[12 + r] * b[c * 4 + 3];
      }
    }
    return out;
  }
  function perspective(fov, aspect, near, far) {
    var focal = 1 / Math.tan(fov / 2);
    var out = new Float32Array(16);
    out[0] = focal / aspect; out[5] = focal;
    out[10] = (far + near) / (near - far); out[11] = -1;
    out[14] = (2 * far * near) / (near - far);
    return out;
  }
  function lookAt(eye, target, up) {
    var forward = normalize(sub(target, eye));
    var right = normalize(cross(forward, up));
    var trueUp = cross(right, forward);
    var out = new Float32Array(16);
    out[0] = right[0]; out[4] = right[1]; out[8] = right[2];
    out[1] = trueUp[0]; out[5] = trueUp[1]; out[9] = trueUp[2];
    out[2] = -forward[0]; out[6] = -forward[1]; out[10] = -forward[2];
    out[12] = -dot(right, eye); out[13] = -dot(trueUp, eye);
    out[14] = dot(forward, eye); out[15] = 1;
    return out;
  }
  /* The three camera basis vectors, used for panning. */
  function cameraBasis(eye, target, up) {
    var forward = normalize(sub(target, eye));
    var right = normalize(cross(forward, up));
    return { right: right, up: cross(right, forward), forward: forward };
  }
  /* The upper-left 3x3 of a rigid view matrix, as a column-major mat3. */
  function normalMatrix(view) {
    return new Float32Array([
      view[0], view[1], view[2], view[4], view[5], view[6], view[8], view[9], view[10]
    ]);
  }
  function transformPoint(m, p) {
    var w = m[3] * p[0] + m[7] * p[1] + m[11] * p[2] + m[15];
    if (Math.abs(w) < EPSILON) { w = 1; }
    return [
      (m[0] * p[0] + m[4] * p[1] + m[8] * p[2] + m[12]) / w,
      (m[1] * p[0] + m[5] * p[1] + m[9] * p[2] + m[13]) / w,
      (m[2] * p[0] + m[6] * p[1] + m[10] * p[2] + m[14]) / w
    ];
  }
  function makeCamera() {
    return { target: [0, 0, 0], distance: 100, yaw: Math.PI * 0.25, pitch: Math.PI * 0.2, fov: DEFAULT_FOV };
  }
  function eyeOf(c) {
    var flat = Math.cos(c.pitch);
    return [
      c.target[0] + c.distance * flat * Math.sin(c.yaw),
      c.target[1] + c.distance * Math.sin(c.pitch),
      c.target[2] + c.distance * flat * Math.cos(c.yaw)
    ];
  }
  /* Orbit around the target, with a guard against the gimbal lock. */
  function orbit(c, dx, dy) {
    c.yaw -= dx * 0.008;
    c.pitch = Math.min(PITCH_LIMIT, Math.max(-PITCH_LIMIT, c.pitch + dy * 0.008));
    return c;
  }
  /* Pan in the camera plane, scaled by the distance and the viewport height. */
  function pan(c, dx, dy, viewportHeight) {
    var basis = cameraBasis(eyeOf(c), c.target, [0, 1, 0]);
    var world = 2 * c.distance * Math.tan(c.fov / 2) / Math.max(viewportHeight, 1);
    c.target = add(c.target, add(mul(basis.right, -dx * world), mul(basis.up, dy * world)));
    return c;
  }
  /* Zoom smoothly, scaled to the radius of the part. */
  function zoom(c, delta, radius) {
    var span = Math.max(radius, 1e-3);
    var low = span * 0.05;
    var high = Math.max(span * 40, low * 10);
    c.distance = Math.min(high, Math.max(low, c.distance * Math.exp(delta * 0.0012)));
    return c;
  }
  /* Frame the camera on the bounding sphere of the part. */
  function frameCamera(c, bounds, aspect) {
    var ratio = aspect > 0 ? aspect : 1;
    var horizontal = 2 * Math.atan(Math.tan(c.fov / 2) * ratio);
    var half = Math.min(c.fov, horizontal) / 2;
    c.target = bounds.center.slice();
    c.distance = Math.max(bounds.radius, 1e-3) / Math.sin(half) * 1.2;
    return c;
  }
  /* The axis-aligned bounding box of a flat position list. */
  function computeBounds(points) {
    var lo = [Infinity, Infinity, Infinity];
    var hi = [-Infinity, -Infinity, -Infinity];
    for (var i = 0; i + 2 < points.length; i += 3) {
      for (var a = 0; a < 3; a++) {
        if (points[i + a] < lo[a]) { lo[a] = points[i + a]; }
        if (points[i + a] > hi[a]) { hi[a] = points[i + a]; }
      }
    }
    if (!isFinite(lo[0])) { lo = [0, 0, 0]; hi = [0, 0, 0]; }
    var size = [hi[0] - lo[0], hi[1] - lo[1], hi[2] - lo[2]];
    var center = [(lo[0] + hi[0]) / 2, (lo[1] + hi[1]) / 2, (lo[2] + hi[2]) / 2];
    var radius = Math.sqrt(size[0] * size[0] + size[1] * size[1] + size[2] * size[2]) / 2;
    return { min: lo, max: hi, center: center, size: size, radius: radius };
  }
  function faceNormal(p, a, b, c) {
    var o = a * 3;
    var ux = p[b * 3] - p[o], uy = p[b * 3 + 1] - p[o + 1], uz = p[b * 3 + 2] - p[o + 2];
    var vx = p[c * 3] - p[o], vy = p[c * 3 + 1] - p[o + 1], vz = p[c * 3 + 2] - p[o + 2];
    return normalize([uy * vz - uz * vy, uz * vx - ux * vz, ux * vy - uy * vx]);
  }
  /* Expand the triangles into flat-shaded vertices with face normals.
   *
   * The result is drawn with drawArrays, so a mesh with more than 65535
   * vertices is drawn without the index overflow of WebGL1.
   */
  function buildFlatShadedMesh(p, idx) {
    var triangles = Math.floor(idx.length / 3);
    var pos = new Float32Array(triangles * 9);
    var normal = new Float32Array(triangles * 9);
    for (var t = 0; t < triangles; t++) {
      var c = [idx[t * 3], idx[t * 3 + 1], idx[t * 3 + 2]];
      var n = faceNormal(p, c[0], c[1], c[2]);
      for (var k = 0; k < 3; k++) {
        var base = t * 9 + k * 3;
        var v = c[k] * 3;
        pos[base] = p[v]; pos[base + 1] = p[v + 1]; pos[base + 2] = p[v + 2];
        normal[base] = n[0]; normal[base + 1] = n[1]; normal[base + 2] = n[2];
      }
    }
    return { positions: pos, normals: normal, vertexCount: triangles * 3, triangleCount: triangles };
  }
  function recordEdge(edges, a, b, normal, count) {
    var key = Math.min(a, b) * count + Math.max(a, b);
    var edge = edges.get(key);
    if (!edge) { edges.set(key, { a: Math.min(a, b), b: Math.max(a, b), first: normal, second: null }); }
    else if (edge.second === null) { edge.second = normal; }
  }
  /* The feature edges: the edges between two faces that meet at a sharp
   * angle, and the edges that bound the surface.
   */
  function buildEdgeLines(p, idx, sharpAngle) {
    var angle = sharpAngle === undefined ? DEFAULT_SHARP_ANGLE : sharpAngle;
    var threshold = Math.cos(angle * Math.PI / 180);
    var count = Math.floor(p.length / 3);
    var edges = new Map();
    var triangles = Math.floor(idx.length / 3);
    for (var t = 0; t < triangles; t++) {
      var a = idx[t * 3], b = idx[t * 3 + 1], c = idx[t * 3 + 2];
      var n = faceNormal(p, a, b, c);
      recordEdge(edges, a, b, n, count);
      recordEdge(edges, b, c, n, count);
      recordEdge(edges, c, a, n, count);
    }
    var out = [];
    edges.forEach(function (e) {
      if (e.second !== null && dot(e.first, e.second) >= threshold) { return; }
      out.push(p[e.a * 3], p[e.a * 3 + 1], p[e.a * 3 + 2], p[e.b * 3], p[e.b * 3 + 1], p[e.b * 3 + 2]);
    });
    return new Float32Array(out);
  }
  /* The three coordinate axes, scaled to the part, in red, green and blue. */
  function buildAxes(bounds) {
    var o = bounds.min;
    var span = Math.max(bounds.size[0], bounds.size[1], bounds.size[2], bounds.radius * 2);
    var reach = span * 1.2 + 1e-3;
    var dirs = [[1, 0, 0], [0, 1, 0], [0, 0, 1]];
    var pos = new Float32Array(18);
    var col = new Float32Array(18);
    for (var i = 0; i < 3; i++) {
      var b = i * 6, d = dirs[i];
      pos[b] = o[0]; pos[b + 1] = o[1]; pos[b + 2] = o[2];
      pos[b + 3] = o[0] + d[0] * reach; pos[b + 4] = o[1] + d[1] * reach; pos[b + 5] = o[2] + d[2] * reach;
      col[b] = d[0]; col[b + 1] = d[1]; col[b + 2] = d[2];
      col[b + 3] = d[0]; col[b + 4] = d[1]; col[b + 5] = d[2];
    }
    return { positions: pos, colors: col };
  }
  /* The twelve edges of the axis-aligned bounding box. */
  function buildBoxLines(bounds) {
    var lo = bounds.min, hi = bounds.max;
    var pairs = [[0, 1], [2, 3], [4, 5], [6, 7], [0, 2], [1, 3], [4, 6], [5, 7], [0, 4], [1, 5], [2, 6], [3, 7]];
    var out = new Float32Array(pairs.length * 6);
    for (var k = 0; k < pairs.length; k++) {
      var a = pairs[k][0], b = pairs[k][1], base = k * 6;
      out[base] = (a & 1) ? hi[0] : lo[0]; out[base + 1] = (a & 2) ? hi[1] : lo[1]; out[base + 2] = (a & 4) ? hi[2] : lo[2];
      out[base + 3] = (b & 1) ? hi[0] : lo[0]; out[base + 4] = (b & 2) ? hi[1] : lo[1]; out[base + 5] = (b & 4) ? hi[2] : lo[2];
    }
    return out;
  }
  global.AturbMath3D = {
    identity: identity, multiply: multiply, perspective: perspective, lookAt: lookAt,
    cameraBasis: cameraBasis, normalMatrix: normalMatrix, transformPoint: transformPoint,
    makeCamera: makeCamera, eyeOf: eyeOf, orbit: orbit, pan: pan, zoom: zoom,
    frameCamera: frameCamera, computeBounds: computeBounds,
    buildFlatShadedMesh: buildFlatShadedMesh, buildEdgeLines: buildEdgeLines,
    buildAxes: buildAxes, buildBoxLines: buildBoxLines
  };
})(window);
