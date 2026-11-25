/* The prompt panel of the ATURB viewer.
 *
 * Posts a natural-language requirement to POST /api/generate and refreshes the
 * viewport and the inspector in place when the server answers. Every string
 * reaches the page through textContent only.
 */
(function (global) {
  "use strict";
  var PANEL_STYLE =
    ".prompt-textarea{display:block;width:100%;box-sizing:border-box;" +
    "margin-top:4px;padding:7px 9px;border:1px solid var(--line);" +
    "border-radius:4px;font:inherit;resize:vertical;}" +
    ".prompt-submit{margin-top:8px;background:var(--accent);color:#ffffff;}";
  var style = null;
  var panel = null;
  var input = null;
  var button = null;
  var statusLine = null;
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
    heading.textContent = "Generate a part";
    panel.appendChild(heading);
    var label = document.createElement("label");
    label.textContent = "Requirement";
    label.setAttribute("for", "prompt-requirement");
    panel.appendChild(label);
    style = document.createElement("style");
    style.textContent = PANEL_STYLE;
    panel.appendChild(style);
    input = document.createElement("textarea");
    input.id = "prompt-requirement";
    input.className = "prompt-textarea";
    input.rows = 4;
    input.placeholder = "A plate 120 mm by 60 mm with two 8 mm holes.";
    panel.appendChild(input);
    button = document.createElement("button");
    button.type = "button";
    button.className = "tool-button prompt-submit";
    button.textContent = "Generate";
    button.addEventListener("click", submit);
    panel.appendChild(button);
    statusLine = document.createElement("p");
    statusLine.className = "note";
    statusLine.hidden = true;
    panel.appendChild(statusLine);
  }

  function setBusy(value) {
    busy = value;
    if (button) {
      button.disabled = value;
      button.textContent = value ? "Generating..." : "Generate";
    }
    if (input) {
      input.disabled = value;
    }
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

  function submit() {
    if (busy || !input) {
      return;
    }
    var requirement = input.value.trim();
    if (!requirement) {
      setStatus("Type a requirement first.", true);
      return;
    }
    setBusy(true);
    setStatus("Generating...", false);
    fetch("/api/generate", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json",
      },
      body: JSON.stringify({ requirement: requirement }),
    })
      .then(readBody)
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

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", build);
  } else {
    build();
  }
})(window);
