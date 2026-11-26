/* The revision history panel of the ATURB viewer.
 *
 * Reads GET /api/history and lists the revisions of the open workspace: the
 * revision id, a status badge, the kind of the revision and a short summary
 * of the instruction. Every verified revision that is not the active one
 * carries a rollback button, and a rollback switches the viewport, the
 * inspector and the active badge in place. Every string reaches the page
 * through textContent only.
 */
(function (global) {
  "use strict";
  var PANEL_STYLE =
    ".history-item{padding:6px 0;border-bottom:1px solid var(--line);}" +
    ".history-head{display:flex;align-items:center;gap:6px;flex-wrap:wrap;}" +
    ".history-id{font-weight:600;}" +
    ".history-instruction{margin:3px 0 0;color:var(--muted);font-size:11px;overflow-wrap:anywhere;}" +
    ".history-rollback{margin-top:5px;padding:3px 9px;border:1px solid var(--line);border-radius:4px;background:transparent;color:var(--muted);font:inherit;font-size:11px;cursor:pointer;}";
  var SUMMARY_LIMIT = 80;
  var panel = null;
  var list = null;
  var note = null;
  var busy = false;

  function byId(id) {
    return document.getElementById(id);
  }
  function add(tag, className, text) {
    var node = document.createElement(tag);
    if (className) {
      node.className = className;
    }
    node.textContent = text || "";
    return node;
  }
  function clear(node) {
    if (!node) {
      return;
    }
    while (node.firstChild) {
      node.removeChild(node.firstChild);
    }
  }
  function ensureBuilt() {
    if (panel) {
      return;
    }
    panel = byId("history-panel");
    if (!panel) {
      return;
    }
    panel.appendChild(add("style", "", PANEL_STYLE));
    panel.appendChild(add("h2", "", "Revisions"));
    list = add("ul", "artifact-list", "");
    panel.appendChild(list);
    note = add("p", "note", "");
    note.hidden = true;
    panel.appendChild(note);
  }
  function badge(label, className) {
    return add("span", className, label);
  }
  function summarize(revision) {
    var instruction = String(revision.instruction || "");
    var reason = String(revision.stop_reason || "");
    var parts = [];
    if (instruction.length > SUMMARY_LIMIT) {
      instruction = instruction.slice(0, SUMMARY_LIMIT - 3) + "...";
    }
    if (instruction) {
      parts.push(instruction);
    }
    if (reason) {
      parts.push(reason);
    }
    return parts.length ? parts.join(" - ") : "no instruction";
  }
  function rollbackButton(id) {
    var button = add("button", "tool-button history-rollback", "Rollback");
    button.type = "button";
    button.setAttribute("data-revision", id);
    button.addEventListener("click", function () {
      rollback(id);
    });
    return button;
  }
  function entry(revision, active) {
    var id = String(revision.id || "");
    var ok = String(revision.status || "") === "ok";
    var item = add("li", "history-item", "");
    var head = add("div", "history-head", "");
    head.appendChild(add("span", "history-id", id));
    var mark = id === active ? "active" : ok ? "ok" : "error";
    head.appendChild(badge(mark, ok ? "badge badge-ok" : "badge badge-error"));
    head.appendChild(add("span", "badge", String(revision.kind || "")));
    item.appendChild(head);
    item.appendChild(add("p", "history-instruction", summarize(revision)));
    if (ok && id !== active) {
      item.appendChild(rollbackButton(id));
    }
    return item;
  }
  function setNote(message) {
    if (!note) {
      return;
    }
    note.textContent = message || "";
    note.hidden = !message;
  }
  function render(state) {
    ensureBuilt();
    if (!panel) {
      return;
    }
    clear(list);
    var revisions = Array.isArray(state.revisions) ? state.revisions : [];
    if (state.has_history !== true) {
      panel.hidden = true;
      setNote("");
      return;
    }
    panel.hidden = false;
    if (!revisions.length) {
      setNote("No revisions yet");
      return;
    }
    setNote("");
    var active =
      typeof state.active_revision === "string" ? state.active_revision : "";
    revisions
      .slice()
      .reverse()
      .forEach(function (revision) {
        list.appendChild(entry(revision, active));
      });
  }
  function setButtonsDisabled(value) {
    if (!list) {
      return;
    }
    list.querySelectorAll("button").forEach(function (button) {
      button.disabled = value;
    });
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
  function rollback(id) {
    if (busy) {
      return;
    }
    busy = true;
    setButtonsDisabled(true);
    fetch("/api/rollback", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json",
      },
      body: JSON.stringify({ revision_id: id }),
    })
      .then(readBody)
      .then(function (result) {
        busy = false;
        setButtonsDisabled(false);
        if (!result.ok) {
          setNote(
            result.body && result.body.error
              ? result.body.error
              : "the rollback was refused",
          );
          return;
        }
        setNote("");
        var app = global.AturbApp;
        if (app && typeof app.reload === "function") {
          app.reload();
        }
      })
      .catch(function (error) {
        busy = false;
        setButtonsDisabled(false);
        setNote(String(error && error.message ? error.message : error));
      });
  }
  function reload(state) {
    ensureBuilt();
    if (state && typeof state === "object") {
      render(state);
      return Promise.resolve(state);
    }
    return fetch("/api/history", { headers: { Accept: "application/json" } })
      .then(readBody)
      .then(function (result) {
        render(result.body || {});
        return result.body;
      })
      .catch(function () {
        render({});
      });
  }
  global.AturbHistory = { reload: reload };
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", function () {
      reload();
    });
  } else {
    reload();
  }
})(window);
