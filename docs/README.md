# docs — the written record of the repository

| file                                                             | what it holds                                                                          |
| ---------------------------------------------------------------- | -------------------------------------------------------------------------------------- |
| [`ARCHITECTURE.md`](ARCHITECTURE.md)                             | the layers, the runner contract, the verification layer and the scoring rule           |
| [`SECURITY.md`](SECURITY.md)                                     | the build sandbox and the loopback viewer server model, and what is not guaranteed     |
| [`ENVIRONMENT.md`](ENVIRONMENT.md)                               | the machine, the tools and the CAD installation this repository was verified on        |
| [`CONVENTIONS.md`](CONVENTIONS.md)                               | the conventions the advisory checker reports on a part file                            |
| [`FEEDBACK.md`](FEEDBACK.md)                                     | what the repair feedback may carry and what it may never carry                         |
| [`IMPLEMENTATION_GUIDE_PART1.md`](IMPLEMENTATION_GUIDE_PART1.md) | the guide to the first part of the implementation                                      |
| [`adr/`](adr/)                                                   | the decision records, one per decision, listed in [`adr/README.md`](adr/README.md)     |
| [`api_notes/`](api_notes/)                                       | the verified third-party calls, listed in [`api_notes/README.md`](api_notes/README.md) |
| `PHASE*_ROADMAP.md`, `PHASE*_TASKS.md`, `PHASE*_BASELINE.md`     | the plan, the work and the measured result of each phase                               |

A baseline records what was measured on one run on one date. A model call is
not deterministic, so a baseline is evidence and not a promise.
