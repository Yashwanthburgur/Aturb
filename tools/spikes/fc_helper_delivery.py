"""Spike: how a helper module can reach the part file inside the CAD.

Runs inside headless FreeCAD (see docs/ENVIRONMENT.md). It tries the three
candidate mechanisms of docs/PHASE6_ROADMAP.md and prints one JSON line per
attempt: the verdict of the unchanged precheck on the part file source, and
what the part file actually observed.

The spike changes no product file. It repeats the loading sequence of
packs/freecad/harness/build_part.py, because the harness itself must not
change before the mechanism is known. The precheck is imported from the pack
(not from the core) and is only read.
"""

import importlib.util
import json
import sys
import tempfile
import traceback
from pathlib import Path

import FreeCAD as App

REPO_ROOT = Path(__file__).resolve().parents[2]
MARKER = "HELPER_REACHED"
RESULT_PREFIX = "RESULT: "
SUMMARY_PREFIX = "SUMMARY: "

HELPER_SOURCE = '''def probe(doc):
    """Return a fixed marker, so the part file can prove the helper arrived."""
    return "HELPER_REACHED"
'''

PART_SOURCE_INJECTED = '''def build(doc):
    """Return the marker the helper produced."""
    return helper.probe(doc)
'''

PART_SOURCE_BY_PATH = '''def build(doc):
    """Return the marker the helper produced."""
    import importlib.util

    spec = importlib.util.spec_from_file_location("helper", HELPER_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.probe(doc)
'''

PART_SOURCE_BY_OPEN = '''def build(doc):
    """Return the marker the helper produced."""
    with open(HELPER_PATH, encoding="utf-8") as handle:
        source = handle.read()
    namespace = {}
    exec(source, namespace)
    return namespace["probe"](doc)
'''

PART_SOURCE_DOCUMENT = '''def build(doc):
    """Return the marker the helper produced."""
    return doc.helper.probe(doc)
'''

PART_SOURCE_CARRIER = '''def build(doc):
    """Return the marker the helper produced."""
    return doc.getObject("Helper").helper.probe(doc)
'''

# mechanism, variant, file name, part file source, delivery of the helper
MECHANISMS = (
    ("A", "harness_injects_helper", "part_a.py", PART_SOURCE_INJECTED,
     "inject"),
    ("B", "part_b_importlib.py", "part_b_importlib.py", PART_SOURCE_BY_PATH,
     "none"),
    ("B", "part_b_open_exec.py", "part_b_open_exec.py", PART_SOURCE_BY_OPEN,
     "none"),
    ("C", "document_attribute", "part_c_document.py", PART_SOURCE_DOCUMENT,
     "document"),
    ("C", "document_object_property", "part_c_carrier.py", PART_SOURCE_CARRIER,
     "carrier"),
)


def _precheck(source: str) -> tuple[str, list[str]]:
    """Return the verdict of the unchanged precheck on a part file source."""
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    from packs.freecad.precheck import precheck

    return precheck(source)


def _load_module(name: str, path: Path):
    """Load a module by path, the way the harness loads the part file."""
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _last_error() -> str:
    """Return the last line of the current traceback."""
    return traceback.format_exc().strip().splitlines()[-1]


def _run_part(part_path: Path, doc, helper, delivery: str) -> str:
    """Load the part file the way the harness does and run build(doc).

    The delivery decides where the helper goes: into the namespace of the
    part file, onto the document, or onto a document object.
    """
    if delivery == "document":
        doc.helper = helper
    elif delivery == "carrier":
        carrier = doc.addObject("App::FeaturePython", "Helper")
        carrier.addProperty("App::PropertyPythonObject", "helper", "Helper",
                            "the helper module")
        carrier.helper = helper
    spec = importlib.util.spec_from_file_location("aturb_part", part_path)
    module = importlib.util.module_from_spec(spec)
    if delivery == "inject":
        module.__dict__["helper"] = helper
    spec.loader.exec_module(module)
    return str(module.build(doc))


def _attempt(mechanism: str, variant: str, source: str, part_path: Path,
             helper, delivery: str) -> dict:
    """Check the source with the precheck, run it, and print the result."""
    verdict, reasons = _precheck(source)
    result = {
        "mechanism": mechanism,
        "variant": variant,
        "precheck": verdict,
        "precheck_reasons": reasons,
        "reached": False,
        "observed": "",
    }
    if verdict != "ok":
        result["observed"] = "the precheck refuses this part file"
    else:
        doc = App.newDocument("Spike")
        try:
            value = _run_part(part_path, doc, helper, delivery)
            result["reached"] = value == MARKER
            result["observed"] = value
        except Exception:
            result["observed"] = _last_error()
        finally:
            App.closeDocument(doc.Name)
    print(RESULT_PREFIX + json.dumps(result), flush=True)
    return result


def main() -> None:
    """Try every mechanism and print the summary of the attempts."""
    work = Path(tempfile.mkdtemp(prefix="aturb_helper_delivery_"))
    project = work / "project"
    project.mkdir(exist_ok=True)
    helper_path = project / "helper.py"
    helper_path.write_text(HELPER_SOURCE, encoding="utf-8")
    helper = _load_module("aturb_helper", helper_path)
    results = []
    for mechanism, variant, name, template, delivery in MECHANISMS:
        source = template.replace("HELPER_PATH", repr(str(helper_path)))
        part_path = project / name
        part_path.write_text(source, encoding="utf-8")
        results.append(_attempt(mechanism, variant, source, part_path,
                                helper, delivery))
    summary = {
        "freecad_version": ".".join(App.Version()[0:3]),
        "work_dir": str(work),
        "working": [r["variant"] for r in results if r["reached"]],
        "refused_by_precheck": [r["variant"] for r in results
                                if r["precheck"] != "ok"],
        "failed_at_runtime": [r["variant"] for r in results
                              if r["precheck"] == "ok" and not r["reached"]],
    }
    print(SUMMARY_PREFIX + json.dumps(summary), flush=True)


main()
