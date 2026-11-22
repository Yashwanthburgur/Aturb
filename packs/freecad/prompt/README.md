# FreeCAD pack — prompt files

`agent.md` is the prompt the agent reads for this pack. The core composes it
into the prompt of a run as the second section, between the core instruction
and the project conventions, and it never edits it: the core holds no prompt
of its own.

The file holds the conventions of this pack: the file contract of a part file,
the verified recipe of each operation, and the selection helper of the pack.
It names no task of the evaluation set and no expected value, so the agent
never sees the answer it is scored against.

Every FreeCAD call the prompt names is recorded in
[`docs/api_notes/freecad.md`](../../../docs/api_notes/freecad.md), and the task
ID of the row that verified it is given next to the call.
[`tests/test_agent_prompt_files.py`](../../../tests/test_agent_prompt_files.py)
checks that every task ID the prompt cites exists in those notes, and that the
prompt states the boundary of the helper.
