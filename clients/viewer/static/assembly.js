/* The assembly panel of the ATURB viewer.
 *
 * Reads the assembly payload of the manifest and fills the Assembly panel of
 * the sidebar. The panel is built here, so the page itself never changes.
 * Every manifest string reaches the page through textContent only, so a
 * manifest cannot inject markup.
 */
(function (global) {
  "use strict";
  var PANEL_ID = "assembly-panel";
  function byId(id) {
    return document.getElementById(id);
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
    if (typeof value === "string" && value.trim() !== "") {
      var parsed = Number(value);
      if (isFinite(parsed)) {
        return parsed;
      }
    }
    return fallback;
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
    var detail = document.createElement("dd");
    detail.textContent = value;
    list.appendChild(term);
    list.appendChild(detail);
  }
  function item(list, value, className) {
    if (!list) {
      return;
    }
    var entry = document.createElement("li");
    entry.textContent = value;
    if (className) {
      entry.className = className;
    }
    list.appendChild(entry);
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
    var title = document.createElement("h2");
    title.textContent = "Assembly";
    panel.appendChild(title);
    var facts = document.createElement("dl");
    facts.className = "fact-list";
    facts.id = "assembly-facts";
    panel.appendChild(facts);
    var subtitle = document.createElement("h3");
    subtitle.textContent = "Pairwise clearances";
    panel.appendChild(subtitle);
    var pairs = document.createElement("ul");
    pairs.className = "finding-list";
    pairs.id = "assembly-pairs";
    panel.appendChild(pairs);
    var artifacts = byId("artifacts-panel");
    if (artifacts && artifacts.parentNode) {
      artifacts.parentNode.insertBefore(panel, artifacts);
    } else {
      inspector.appendChild(panel);
    }
    return panel;
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
    fact(
      list,
      "Assembly",
      text(assembly.assembly_name, text(assembly.assembly_id, "unnamed")),
    );
    fact(list, "Status", text(assembly.status, "unknown"));
    fact(list, "Components", String(number(assembly.component_count, 0)));
    fact(
      list,
      "Interference",
      assembly.has_interference === true ? "INTERFERENCE DETECTED" : "None",
    );
    fact(
      list,
      "Mates",
      assembly.all_mates_ok === true ? "satisfied" : "not satisfied",
    );
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
      item(
        pairs,
        names +
          ": clearance " +
          fix(pair.min_clearance_mm) +
          " mm, overlap " +
          fix(pair.overlap_volume_mm3) +
          " mm³",
      );
    });
  }
  global.AturbAssembly = { render: render };
})(window);
