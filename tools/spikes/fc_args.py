"""Spike: read a request file whose path arrives in an environment variable.

Runs inside FreeCAD, so it imports only the standard library.
"""

import json
import os

request_path = os.environ["ATURB_REQUEST"]
print("REQUEST_PATH:", request_path)

with open(request_path, encoding="utf-8") as handle:
    request = json.load(handle)

print("REQUEST_JSON:", request)
