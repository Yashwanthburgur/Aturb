# clients — thin clients of the core service

A client forwards a request to the core and shows what comes back. No client
holds CAD knowledge or geometry logic.

| module                                                       | what it owns                                                               |
| ------------------------------------------------------------ | -------------------------------------------------------------------------- |
| [`viewer/`](viewer/)                                         | the browser viewer: the server, the endpoints and the browser assets       |
| [`viewer/server.py`](viewer/server.py)                       | the loopback-only HTTP server and the request handler                      |
| [`viewer/http_utils.py`](viewer/http_utils.py)               | the shared HTTP guards, the body limit and the redaction of the credential |
| [`viewer/workspace.py`](viewer/workspace.py)                 | the safe loading of a workspace and the containment of its paths           |
| [`viewer/mesh.py`](viewer/mesh.py)                           | the tessellation of an exported STEP into a JSON mesh                      |
| [`viewer/generate_api.py`](viewer/generate_api.py)           | the prompt-to-part endpoint                                                |
| [`viewer/edit_api.py`](viewer/edit_api.py)                   | the edit and rollback endpoints of a single part                           |
| [`viewer/assembly_edit_api.py`](viewer/assembly_edit_api.py) | the edit and rollback endpoints of an assembly                             |
| [`viewer/static/`](viewer/static/)                           | the browser assets: the page, the stylesheet and the scripts               |

The viewer is zero-build and offline: plain HTML, CSS and JavaScript, no
bundler and no content delivery network.
