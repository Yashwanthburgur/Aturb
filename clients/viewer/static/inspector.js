/* The engineering inspector of the ATURB viewer.
 *
 * Reads the manifest, the mesh and the revision history of the open workspace
 * and fills the facts panel. Every manifest string reaches the page through
 * textContent only, so a manifest cannot inject markup.
 */
(function (global) {
  "use strict";
  var ARTIFACTS = [
    { kind: "part_file", label: "candidate source" },
    { kind: "step_file", label: "STEP export" },
    { kind: "native_file", label: "native artifact" }
  ];
  var manifest = {};
  var mesh = null;
  var state = { editable: false, active_revision: null, has_history: false };
  function byId(id) { return document.getElementById(id); }
  function text(value, fallback) {
    return value === null || value === undefined || value === "" ? fallback : String(value);
  }
  function number(value, fallback) {
    if (typeof value === "number" && isFinite(value)) { return value; }
    if (typeof value === "string" && value.trim() !== "") {
      var parsed = Number(value);
      if (isFinite(parsed)) { return parsed; }
    }
    return fallback;
  }
  function fix(value) { return number(value, 0).toFixed(3); }
  function clear(node) {
    if (!node) { return; }
    while (node.firstChild) { node.removeChild(node.firstChild); }
  }
  function fact(list, label, value) {
    if (!list) { return; }
    var term = document.createElement("dt");
    term.textContent = label;
    var detail = document.createElement("dd");
    detail.textContent = value;
    list.appendChild(term);
    list.appendChild(detail);
  }
  function item(list, value, className) {
    if (!list) { return; }
    var entry = document.createElement("li");
    entry.textContent = value;
    if (className) { entry.className = className; }
    list.appendChild(entry);
  }
  function renderRun() {
    var list = byId("run-facts");
    clear(list);
    var status = text(manifest.status, "unknown");
    fact(list, "Status", status);
    fact(list, "Stop reason", text(manifest.stop_reason, "not recorded"));
    fact(list, "Part ID", text(manifest.part_id, "not recorded"));
    fact(list, "Attempts", String(number(manifest.attempts, 0)));
    fact(list, "Prompt version", text(manifest.prompt_version, "not called"));
    if (state.active_revision) { fact(list, "Active revision", state.active_revision); }
    var badge = byId("status-badge");
    if (badge) {
      badge.textContent = status;
      badge.className = status === "ok" ? "badge badge-ok" : "badge badge-error";
    }
  }
  function renderUsage() {
    var list = byId("usage-facts");
    clear(list);
    var cost = number(manifest.cost_usd, 0);
    fact(list, "Input tokens", String(number(manifest.input_tokens, 0)));
    fact(list, "Output tokens", String(number(manifest.output_tokens, 0)));
    fact(list, "Cost (USD)", cost.toFixed(6));
    var note = byId("usage-note");
    if (note) {
      note.hidden = cost > 0;
      note.textContent = cost > 0 ? "" : "the cost is 0.0: no provider pricing is configured for this run";
    }
  }
  function renderBuild() {
    var list = byId("build-facts");
    clear(list);
    fact(list, "Build status", text(manifest.build_status, "not recorded"));
    fact(list, "Failure kind", text(manifest.failure_kind, "none"));
    var message = text(manifest.error, "");
    var errorNode = byId("build-error");
    if (errorNode) {
      errorNode.textContent = message;
      errorNode.hidden = !message;
    }
    var findings = byId("convention-list");
    clear(findings);
    var conventions = Array.isArray(manifest.conventions) ? manifest.conventions : [];
    if (!conventions.length) { item(findings, "None", "finding-none"); return; }
    conventions.forEach(function (finding) { item(findings, text(finding, "")); });
  }
  function renderGeometry() {
    var list = byId("geometry-facts");
    clear(list);
    var size = Array.isArray(manifest.bbox_size) ? manifest.bbox_size : [];
    if (!size.length && typeof manifest.volume !== "number") {
      fact(list, "Measured geometry", "not measured for this workspace");
    } else {
      fact(list, "Valid", manifest.is_valid === true ? "yes" : "no");
      fact(list, "Single solid", manifest.is_single_solid === true ? "yes" : "no");
      fact(list, "Volume", fix(manifest.volume) + " mm³");
      fact(list, "Bounding box", size.length === 3 ? size.map(fix).join(" × ") + " mm" : "not recorded");
    }
    if (mesh) {
      fact(list, "Mesh vertices", String(number(mesh.vertex_count, 0)));
      fact(list, "Mesh triangles", String(number(mesh.triangle_count, 0)));
    }
    var holes = byId("hole-list");
    clear(holes);
    var entries = Array.isArray(manifest.holes) ? manifest.holes : [];
    if (!entries.length) { item(holes, "None", "finding-none"); return; }
    entries.forEach(function (hole) {
      item(holes, "diameter " + fix(hole.diameter) + " mm at (" + fix(hole.x) + ", " + fix(hole.y) + ") mm");
    });
  }
  function renderArtifacts() {
    var list = byId("artifact-list");
    clear(list);
    ARTIFACTS.forEach(function (artifact) {
      var declared = text(manifest[artifact.kind], "");
      var entry = document.createElement("li");
      var link = document.createElement("a");
      link.setAttribute("href", "/api/files/" + artifact.kind);
      link.textContent = declared ? declared : artifact.label + " (not produced)";
      if (!declared) {
        link.className = "is-unavailable";
        link.setAttribute("aria-disabled", "true");
        link.addEventListener("click", function (event) { event.preventDefault(); });
      }
      entry.appendChild(link);
      if (list) { list.appendChild(entry); }
    });
  }
  function renderStatus() {
    var node = byId("status-text");
    if (!node) { return; }
    if (mesh) {
      node.textContent = "mesh: " + number(mesh.vertex_count, 0) + " vertices, " + number(mesh.triangle_count, 0) + " triangles";
      return;
    }
    var reason = text(manifest.error, "");
    node.textContent = reason ? "no geometry: " + reason : "no geometry to draw";
  }
  function renderAll() {
    renderRun();
    renderUsage();
    renderBuild();
    renderGeometry();
    renderArtifacts();
    renderStatus();
  }
  function objectOf(result) {
    return result.ok && result.body && typeof result.body === "object" ? result.body : {};
  }
  function fetchJson(path) {
    return fetch(path, { headers: { Accept: "application/json" } })
      .then(function (response) {
        return response.text().then(function (raw) {
          var body = {};
          try { body = raw ? JSON.parse(raw) : {}; } catch (error) { body = {}; }
          return { ok: response.ok, status: response.status, body: body };
        });
      })
      .catch(function (error) {
        return { ok: false, status: 0, body: { error: String(error && error.message ? error.message : error) } };
      });
  }
  /* Re-read the manifest, the mesh and the history, then update the panel, the
   * viewport and the revision list. */
  function reload() {
    return Promise.all([
      fetchJson("/api/manifest"),
      fetchJson("/api/mesh"),
      fetchJson("/api/history")
    ]).then(function (results) {
      var meshResult = results[1];
      manifest = objectOf(results[0]);
      mesh = meshResult.ok && meshResult.body && Array.isArray(meshResult.body.positions) ? meshResult.body : null;
      var history = objectOf(results[2]);
      state.editable = history.editable === true;
      state.active_revision = typeof history.active_revision === "string" ? history.active_revision : null;
      state.has_history = history.has_history === true;
      renderAll();
      refreshHistory(history);
      var viewer = global.AturbViewer;
      if (!viewer) { return { manifest: manifest, mesh: mesh, history: history }; }
      if (mesh) {
        viewer.setMesh(mesh);
      } else {
        viewer.setEmptyState(text(meshResult.body && meshResult.body.error, "the mesh request answered " + meshResult.status));
      }
      return { manifest: manifest, mesh: mesh, history: history };
    });
  }
  /* Hand the history to the revision panel and tell the prompt panel what the
   * open workspace allows. */
  function refreshHistory(history) {
    var panel = global.AturbHistory;
    if (panel && typeof panel.reload === "function") { panel.reload(history); }
    var prompt = global.AturbPrompt;
    if (prompt && typeof prompt.refresh === "function") { prompt.refresh(); }
  }
  global.AturbApp = { reload: reload, state: state };
  if (document.readyState === "loading") { document.addEventListener("DOMContentLoaded", reload); } else { reload(); }
})(window);
