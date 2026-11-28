# aturb — the core service

CAD-neutral and language-neutral. Nothing in this folder names a CAD system.

| module                     | what it owns                                                                                        |
| -------------------------- | --------------------------------------------------------------------------------------------------- |
| [`cli.py`](cli.py)         | the command line: `build`, `check`, `assemble`, `edit-assembly`, `eval`, `generate`, `view`         |
| [`config.py`](config.py)   | the configuration file, the active pack and the timeouts                                            |
| [`packs.py`](packs.py)     | the discovery of `packs/<name>/` and the loading of a runner                                        |
| [`contract/`](contract/)   | the runner contract: the build request, the build result and the eight failure kinds                |
| [`verify/`](verify/)       | the neutral verification layer: the measurements taken from an exported STEP                        |
| [`agent/`](agent/)         | the bounded improvement loop, the model boundary, the prompts and the revision history of a part    |
| [`assembly/`](assembly/)   | the assembly manifest, the assembly build, the coupled edit and the revision history of an assembly |
| [`evals/`](evals/)         | the task set, the answer schema, the batch runner and the scoring rule                              |
| [`workspace/`](workspace/) | the paths of a workspace and the atomic single-file persistence                                     |

The core never imports a client. The only import of `clients/` inside the core
is the lazy `from clients.viewer.cli import run_view_command` in the `view`
branch of [`cli.py`](cli.py).
