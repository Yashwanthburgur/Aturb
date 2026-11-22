"""Harness that runs INSIDE the CAD process. It must never import aturb.

Reads the job JSON from os.environ["ATURB_REQUEST"], builds the part, and always
writes a result JSON to job["result_path"], even if everything inside fails.

The selection helper of the pack is loaded by path and put into the namespace of
the part file, so the part file can use it without an import (T6.05, mechanism A).
"""

import importlib.util
import json
import os
import traceback

import FreeCAD as App

PACK_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATE_MODULE = os.path.join(PACK_DIR, "harness", "fc_state.py")
HELPER_MODULE = os.path.join(PACK_DIR, "helper", "select.py")
HELPER_NAME = "helper"


def _load_module(name, path):
    """Load a module by path, so no import path is assumed."""
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_state_module():
    """Load the sibling state helper by path, so no import path is assumed."""
    return _load_module("fc_state", STATE_MODULE)


def _load_helper_module():
    """Load the selection helper of the pack by path, so no import is assumed."""
    return _load_module("fc_helper", HELPER_MODULE)


def main():
    """Run one build job and always write a result file."""
    doc = None
    with open(os.environ["ATURB_REQUEST"], "r", encoding="utf-8") as handle:
        job = json.load(handle)

    result = {
        "status": "failed",
        "failure_kind": "runtime_error",
        "error_text": "",
        "native_diagnostics": {},
        "artifacts": {},
    }
    try:
        helper = _load_helper_module()
        doc = App.newDocument(job["part_id"])
        try:
            spec = importlib.util.spec_from_file_location(
                "aturb_part", job["part_file"])
            module = importlib.util.module_from_spec(spec)
            # Mechanism A of T6.05: the helper is in the namespace of the part
            # file before the part file runs, so the part file needs no import.
            module.__dict__[HELPER_NAME] = helper
            spec.loader.exec_module(module)
        except SyntaxError:
            result["failure_kind"] = "syntax_error"
            result["error_text"] = traceback.format_exc()
            raise _Done() from None

        obj = module.build(doc)
        if obj is None:
            raise RuntimeError("build(doc) must return the final object")

        doc.recompute()

        failed = _load_state_module().failed_feature_names(doc.Objects)
        result["native_diagnostics"]["failed_features"] = failed
        result["native_diagnostics"]["cad_version"] = str(App.Version())
        if failed:
            result["failure_kind"] = "invalid_geometry"
            result["error_text"] = "failed features: " + ", ".join(failed)
            raise _Done()

        os.makedirs(job["out_dir"], exist_ok=True)
        if "native" in job["outputs"]:
            native_path = os.path.join(
                job["out_dir"], job["part_id"] + ".FCStd")
            doc.saveAs(native_path)
            result["artifacts"]["native"] = native_path

        if "step" in job["outputs"]:
            step_path = os.path.join(
                job["out_dir"], job["part_id"] + ".step")
            try:
                obj.Shape.exportStep(step_path)
                if (not os.path.isfile(step_path)
                        or os.path.getsize(step_path) == 0):
                    raise RuntimeError("STEP export produced no file")
                result["artifacts"]["step"] = step_path
            except Exception:
                result["failure_kind"] = "export_failed"
                result["error_text"] = traceback.format_exc()
                raise _Done() from None

        result["status"] = "ok"
        result["failure_kind"] = None
    except _Done:
        pass
    except Exception:
        result["error_text"] = traceback.format_exc()
    finally:
        if doc is not None:
            App.closeDocument(doc.Name)
        if result["status"] != "ok":
            result["artifacts"] = {}
        with open(job["result_path"], "w", encoding="utf-8") as handle:
            json.dump(result, handle, indent=2)


class _Done(Exception):
    """Internal control-flow signal: stop building, keep the current result."""


main()
