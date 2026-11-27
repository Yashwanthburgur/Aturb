/* The assembly panel of the ATURB viewer.
 *
 * Reads the assembly payload of the manifest and fills the Assembly panel of
 * the sidebar. The panel is built here, so the page itself never changes.
 * Every manifest string reaches the page through textContent only, so a
 * manifest cannot inject markup.
 *
 * The panel also holds the edit form of the assembly and the list of its
 * revisions. The form posts the instruction to the assembly edit endpoint and
 * every verified revision that is not the active one carries a rollback
 * button. Every answer of the server reaches the page through textContent
 * only.
 */
(function (global) {
  "use strict";
  var PANEL_ID = "assembly-panel";
  var HISTORY_PATH = "/api/assembly/history";
  var EDIT_PATH = "/api/assembly/edit";
  var ROLLBACK_PATH = "/api/assembly/rollback";
  var PANEL_STYLE =
    ".assembly-form{display:flex;flex-direction:column;gap:6px;margin:6px 0;}" +
    ".assembly-form textarea{width:100%;min-height:52px;font:inherit;font-size:11px;}" +
    ".assembly-form button,.assembly-rollback{padding:4px 10px;border:1px solid var(--line);border-radius:4px;background:transparent;color:var(--muted);font:inherit;font-size:11px;cursor:pointer;}" +
    ".assembly-revision{display:flex;align-items:center;gap:6px;flex-wrap:wrap;padding:4px 0;border-bottom:1px solid var(--line);}" +
    ".assembly-revision-id{font-weight:600;}" +
    ".assembly-note{margin:4px 0 0;color:var(--muted);font-size:11px;overflow-wrap:anywhere;}";
  var busy = false;

  function byId(id) {
    return document.getElementById(id);
  }
  function add(tag, className, value) {
    var node = document.createElement(tag);
    if (className) {
      node.className = className;
    }
    node.textContent = value || "";
    return node;
  }
  function text(value, fallback) {
    return value === null || value === undefined || value === ""
      ? fallback
      : String(value);
  }
  function number(value, fallback) {
    if (typeof value === "number" && isFinite(value)) {
      return value;
    }
    var parsed = Number(value);
    return typeof value === "string" && value.trim() !== "" && isFinite(parsed)
      ? parsed
      : fallback;
  }
  function fix(value) {
    return number(value, 0).toFixed(2);
  }
  function clear(node) {
    if (!node) {
      return;
    }
    while (node.firstChild) {
      node.removeChild(node.firstChild);
    }
  }
  function fact(list, label, value) {
    if (!list) {
      return;
    }
    var term = document.createElement("dt");
    term.textContent = label;
    list.appendChild(term);
    list.appendChild(add("dd", "", value));
  }
  function item(list, value, className) {
    if (!list) {
      return;
    }
    list.appendChild(add("li", className, value));
  }
  function setNote(node, message) {
    if (!node) {
      return;
    }
    node.textContent = message || "";
    node.hidden = !message;
  }
  /* The panel is built here, so the page itself never changes. */
  function section() {
    var panel = byId(PANEL_ID);
    if (panel) {
      return panel;
    }
    var inspector = byId("inspector");
    if (!inspector) {
      return null;
    }
    panel = document.createElement("section");
    panel.className = "panel-section";
    panel.id = PANEL_ID;
    panel.appendChild(add("style", "", PANEL_STYLE));
    panel.appendChild(add("h2", "", "Assembly"));
    var facts = add("dl", "fact-list", "");
    facts.id = "assembly-facts";
    panel.appendChild(facts);
    panel.appendChild(add("h3", "", "Pairwise clearances"));
    var pairs = add("ul", "finding-list", "");
    pairs.id = "assembly-pairs";
    panel.appendChild(pairs);
    panel.appendChild(add("h3", "", "Edit assembly"));
    panel.appendChild(editForm());
    panel.appendChild(add("h3", "", "Revisions"));
    var revisions = add("ul", "artifact-list", "");
    revisions.id = "assembly-revisions";
    panel.appendChild(revisions);
    var note = add("p", "assembly-note", "");
    note.id = "assembly-note";
    note.hidden = true;
    panel.appendChild(note);
    var artifacts = byId("artifacts-panel");
    if (artifacts && artifacts.parentNode) {
      artifacts.parentNode.insertBefore(panel, artifacts);
    } else {
      inspector.appendChild(panel);
    }
    return panel;
  }
  function editForm() {
    var form = add("div", "assembly-form", "");
    var input = document.createElement("textarea");
    input.id = "assembly-instruction";
    input.placeholder = "Describe the change to the assembly";
    form.appendChild(input);
    var button = add("button", "", "Edit assembly");
    button.type = "button";
    button.addEventListener("click", function () {
      edit(input.value);
    });
    form.appendChild(button);
    return form;
  }
  function revisionEntry(revision, active) {
    var id = String(revision.id || "");
    var ok = String(revision.status || "") === "ok";
    var entry = add("li", "assembly-revision", "");
    entry.appendChild(add("span", "assembly-revision-id", id));
    entry.appendChild(add("span", "badge", String(revision.kind || "")));
    entry.appendChild(add("span", "badge", ok ? "ok" : "failed"));
    if (ok && id !== active) {
      var button = add("button", "assembly-rollback", "Rollback");
      button.type = "button";
      button.addEventListener("click", function () {
        rollback(id);
      });
      entry.appendChild(button);
    }
    return entry;
  }
  function renderHistory(state) {
    var list = byId("assembly-revisions");
    if (!list) {
      return;
    }
    clear(list);
    var revisions = Array.isArray(state.revisions) ? state.revisions : [];
    var active = String(state.active_revision || "");
    revisions
      .slice()
      .reverse()
      .forEach(function (revision) {
        list.appendChild(revisionEntry(revision, active));
      });
    if (!revisions.length) {
      item(list, "No revisions yet", "finding-none");
    }
  }
  function readBody(response) {
    return response.text().then(function (raw) {
      var body = {};
      try {
        body = raw ? JSON.parse(raw) : {};
      } catch (error) {
        body = {};
      }
      return { ok: response.ok, status: response.status, body: body };
    });
  }
  function post(path, payload) {
    var note = byId("assembly-note");
    if (busy) {
      return;
    }
    busy = true;
    setNote(note, "working...");
    fetch(path, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json",
      },
      body: JSON.stringify(payload),
    })
      .then(readBody)
      .then(function (result) {
        busy = false;
        if (!result.ok) {
          setNote(
            note,
            result.body && result.body.error
              ? result.body.error
              : "the request was refused",
          );
          return;
        }
        setNote(note, "done");
        loadHistory();
        var app = global.AturbApp;
        if (app && typeof app.reload === "function") {
          app.reload();
        }
      })
      .catch(function (error) {
        busy = false;
        setNote(note, String(error && error.message ? error.message : error));
      });
  }
  function edit(instruction) {
    var value = String(instruction || "").trim();
    if (!value) {
      setNote(byId("assembly-note"), "the instruction is empty");
      return;
    }
    post(EDIT_PATH, { instruction: value });
  }
  function rollback(id) {
    post(ROLLBACK_PATH, { revision_id: String(id || "") });
  }
  function loadHistory() {
    return fetch(HISTORY_PATH, { headers: { Accept: "application/json" } })
      .then(readBody)
      .then(function (result) {
        renderHistory(result.body || {});
        return result.body;
      })
      .catch(function () {
        renderHistory({});
      });
  }
  function render(manifest) {
    var assembly = manifest && manifest.assembly ? manifest.assembly : null;
    var panel = byId(PANEL_ID);
    if (!assembly) {
      if (panel) {
        panel.hidden = true;
      }
      return;
    }
    panel = section();
    if (!panel) {
      return;
    }
    panel.hidden = false;
    var list = byId("assembly-facts");
    clear(list);
    var name = text(
      assembly.assembly_name,
      text(assembly.assembly_id, "unnamed"),
    );
    fact(list, "Assembly", name);
    fact(list, "Status", text(assembly.status, "unknown"));
    fact(list, "Components", String(number(assembly.component_count, 0)));
    var clash =
      assembly.has_interference === true ? "INTERFERENCE DETECTED" : "None";
    fact(list, "Interference", clash);
    var mates = assembly.all_mates_ok === true ? "satisfied" : "not satisfied";
    fact(list, "Mates", mates);
    fact(list, "Total volume", fix(assembly.total_volume) + " mm³");
    var pairs = byId("assembly-pairs");
    clear(pairs);
    var entries = Array.isArray(assembly.pairs) ? assembly.pairs : [];
    if (!entries.length) {
      item(pairs, "None", "finding-none");
      return;
    }
    entries.forEach(function (pair) {
      var names = text(pair.part_a, "?") + " <-> " + text(pair.part_b, "?");
      var line = names + ": clearance " + fix(pair.min_clearance_mm) + " mm";
      item(pairs, line + ", overlap " + fix(pair.overlap_volume_mm3) + " mm³");
    });
    loadHistory();
  }
  global.AturbAssembly = { render: render };
})(window);
