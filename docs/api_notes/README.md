# api_notes — verified third-party calls

An agent may only use a call that is recorded here or that was verified in the
same session. Nothing is copied from upstream documentation.

| file                           | what it holds                                                                    |
| ------------------------------ | -------------------------------------------------------------------------------- |
| [`build123d.md`](build123d.md) | the verified calls of the neutral STEP library, the ones `aturb/verify/` uses    |
| [`freecad.md`](freecad.md)     | the verified calls of the CAD application, the ones `packs/freecad/` uses        |
| [`model.md`](model.md)         | the verified model provider call: the request, the response and the error shapes |

Every row states the version it was verified against, the task it was verified
in and whether it was actually executed. A row marked **not verified** was not
observed and must not be used by client code. Re-verify after any version bump
in `pyproject.toml`.
