"""Spike build harness: runs INSIDE FreeCAD, so it must not import aturb.

Reads ATURB_PART (absolute path to a part file) and ATURB_OUT (absolute output folder),
creates a new document, loads the part file as a module, calls build(doc), recomputes,
saves <part file stem>.FCStd into ATURB_OUT, and exports the returned object's shape to
<part file stem>.step there.

Every outcome prints exactly one line: "RESULT: " followed by a JSON object.
"""

import importlib.util
import json
import os
import traceback

import FreeCAD as App

RESULT_PREFIX = "RESULT: "


def _print_result(payload):
    print(RESULT_PREFIX + json.dumps(payload), flush=True)


def main():
    doc = None
    try:
        part_path = os.environ["ATURB_PART"]
        out_dir = os.environ["ATURB_OUT"]

        doc = App.newDocument("Spike")

        spec = importlib.util.spec_from_file_location("spike_part", part_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        obj = module.build(doc)
        if obj is None:
            raise RuntimeError("build(doc) must return the final object")

        doc.recompute()

        # Collect states of all document objects
        states = {o.Name: str(o.State) for o in doc.Objects}

        os.makedirs(out_dir, exist_ok=True)
        stem = os.path.splitext(os.path.basename(part_path))[0]
        fcstd_path = os.path.join(out_dir, stem + ".FCStd")
        doc.saveAs(fcstd_path)

        # exportStep returns None, so the file itself is the evidence that it worked.
        step_path = os.path.join(out_dir, stem + ".step")
        obj.Shape.exportStep(step_path)
        if not os.path.isfile(step_path) or os.path.getsize(step_path) == 0:
            raise RuntimeError("STEP export produced no file: " + step_path)

        _print_result({"status": "ok", "fcstd": fcstd_path,
                      "step": step_path, "states": states})
    except Exception:
        # Collect states if doc exists and recompute happened
        states = {}
        if doc is not None:
            states = {o.Name: str(o.State) for o in doc.Objects}
        _print_result(
            {"status": "failed", "error": traceback.format_exc(), "states": states})
    finally:
        if doc is not None:
            App.closeDocument(doc.Name)


main()
