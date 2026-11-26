/* The prompt panel of the ATURB viewer.
 *
 * Two actions share one text field: "Edit current" posts a natural-language
 * instruction to POST /api/edit and "New part" posts a natural-language
 * requirement to POST /api/generate. Both refresh the viewport, the inspector
 * and the revision history in place when the server answers. Every string
 * reaches the page through textContent only.
 */
(function (global) {
  "use strict";
  var PANEL_STYLE =
    ".prompt-textarea{display:block;width:100%;box-sizing:border-box;" +
    "margin-top:4px;padding:7px 9px;border:1px solid var(--line);" +
    "border-radius:4px;font:inherit;resize:vertical;}" +
    ".prompt-submit{margin-top:8px;background:var(--accent);color:#ffffff;}" +
    ".prompt-modes{display:flex;gap:6px;margin-bottom:6px;}" +
    ".prompt-hint{margin:6px 0 0;color:var(--muted);font-size:11px;}";
  var MODE_EDIT = "edit";
  var MODE_NEW = "new";
  var EDIT_LABEL = "Edit current part";
  var NEW_LABEL = "Generate new part";
  var EDIT_PLACEHOLDER = "Make the plate 10 mm thick.";
  var NEW_PLACEHOLDER = "A plate 120 mm by 60 mm with two 8 mm holes.";
  var NO_EDIT_HINT =
    "This workspace holds no verified part, so it cannot be edited.";
  var style = null;
  var panel = null;
  var input = null;
  var button = null;
  var statusLine = null;
  var hintLine = null;
  var modeButtons = {};
  var mode = MODE_NEW;
  var busy = false;

  function byId(id) {
    return document.getElementById(id);
  }

  function build() {
    panel = byId("prompt-panel");
    if (!panel) {
      return;
    }
    panel.hidden = false;
    panel.textContent = "";
    var heading = document.createElement("h2");
    heading.textContent = "Generate or edit a part";
    panel.appendChild(heading);
    style = document.createElement("style");
    style.textContent = PANEL_STYLE;
    panel.appendChild(style);
    var modes = document.createElement("div");
    modes.className = "prompt-modes";
    panel.appendChild(modes);
    modeButtons[MODE_EDIT] = modeButton(modes, "Edit current", MODE_EDIT);
    modeButtons[MODE_NEW] = modeButton(modes, "New part", MODE_NEW);
    var label = document.createElement("label");
    label.textContent = "Requirement";
    label.setAttribute("for", "prompt-requirement");
    panel.appendChild(label);
    input = document.createElement("textarea");
    input.id = "prompt-requirement";
    input.className = "prompt-textarea";
    input.rows = 4;
    input.placeholder = NEW_PLACEHOLDER;
    panel.appendChild(input);
    button = document.createElement("button");
    button.type = "button";
    button.className = "tool-button prompt-submit";
    button.textContent = NEW_LABEL;
    button.addEventListener("click", submit);
    panel.appendChild(button);
    statusLine = document.createElement("p");
    statusLine.className = "note";
    statusLine.hidden = true;
    panel.appendChild(statusLine);
    hintLine = document.createElement("p");
    hintLine.className = "prompt-hint";
    hintLine.hidden = true;
    panel.appendChild(hintLine);
    setMode(MODE_NEW);
  }

  function modeButton(parent, label, value) {
    var element = document.createElement("button");
    element.type = "button";
    element.className = "tool-button";
    element.textContent = label;
    element.addEventListener("click", function () {
      setMode(value);
    });
    parent.appendChild(element);
    return element;
  }

  function setMode(value) {
    mode = value;
    Object.keys(modeButtons).forEach(function (key) {
      var element = modeButtons[key];
      if (!element) {
        return;
      }
      element.className =
        key === mode ? "tool-button is-active" : "tool-button";
    });
    if (input) {
      input.placeholder =
        mode === MODE_EDIT ? EDIT_PLACEHOLDER : NEW_PLACEHOLDER;
    }
    refreshAvailability();
  }

  function isEditable() {
    var app = global.AturbApp;
    if (!app || !app.state) {
      return false;
    }
    return app.state.editable === true;
  }

  function refreshAvailability() {
    var editable = isEditable();
    if (modeButtons[MODE_EDIT]) {
      modeButtons[MODE_EDIT].disabled = busy || !editable;
    }
    if (button) {
      button.disabled = busy || (mode === MODE_EDIT && !editable);
    }
    if (hintLine) {
      hintLine.textContent = editable ? "" : NO_EDIT_HINT;
      hintLine.hidden = editable;
    }
  }

  function setBusy(value) {
    busy = value;
    if (button) {
      button.disabled = value;
      button.textContent = value
        ? mode === MODE_EDIT
          ? "Editing..."
          : "Generating..."
        : mode === MODE_EDIT
          ? EDIT_LABEL
          : NEW_LABEL;
    }
    if (input) {
      input.disabled = value;
    }
    refreshAvailability();
  }

  function setStatus(message, isError) {
    if (!statusLine) {
      return;
    }
    statusLine.textContent = message || "";
    statusLine.hidden = !message;
    statusLine.className = isError ? "error-text" : "note";
  }

  function refresh() {
    var app = global.AturbApp;
    if (!app || typeof app.reload !== "function") {
      return;
    }
    app.reload();
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
    return fetch(path, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json",
      },
      body: JSON.stringify(payload),
    }).then(readBody);
  }

  function submit() {
    if (busy || !input) {
      return;
    }
    var text = input.value.trim();
    if (!text) {
      setStatus("Type a requirement first.", true);
      return;
    }
    if (mode === MODE_EDIT) {
      submitEdit(text);
      return;
    }
    submitGenerate(text);
  }

  function submitGenerate(requirement) {
    setBusy(true);
    setStatus("Generating...", false);
    post("/api/generate", { requirement: requirement })
      .then(function (result) {
        setBusy(false);
        var body = result.body || {};
        if (body.workspace) {
          setStatus(
            "Workspace " +
              body.workspace +
              ": " +
              (body.status || "unknown") +
              " (" +
              (body.stop_reason || "no reason") +
              ")",
            body.status !== "ok",
          );
          refresh();
          return;
        }
        setStatus(body.error || "the request answered " + result.status, true);
      })
      .catch(function (error) {
        setBusy(false);
        setStatus(String(error && error.message ? error.message : error), true);
      });
  }

  function submitEdit(instruction) {
    setBusy(true);
    setStatus("Editing...", false);
    post("/api/edit", { instruction: instruction })
      .then(function (result) {
        setBusy(false);
        var body = result.body || {};
        if (!body.revision_id) {
          setStatus(
            body.error || "the request answered " + result.status,
            true,
          );
          return;
        }
        if (body.promoted) {
          setStatus(
            "Revision " +
              body.active_revision +
              " active (" +
              (body.stop_reason || "no reason") +
              ")",
            false,
          );
        } else {
          setStatus(
            "Edit failed (" +
              body.revision_id +
              ") — active part kept at " +
              (body.active_revision || "the last verified revision"),
            true,
          );
        }
        refresh();
      })
      .catch(function (error) {
        setBusy(false);
        setStatus(String(error && error.message ? error.message : error), true);
      });
  }

  global.AturbPrompt = { refresh: refreshAvailability };
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", build);
  } else {
    build();
  }
})(window);
