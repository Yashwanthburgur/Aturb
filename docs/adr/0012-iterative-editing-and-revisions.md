# ADR-0012: Iterative editing and the revision history

Date: 2026-11-25
Status: Accepted

## Context

Phase 8 leaves a portable workspace: a `result.toml` manifest, the editable
candidate source, the exported STEP and the native artifact of the active
pack. The workspace is a snapshot. It cannot be changed, and it cannot be
undone: a second generation writes into a second folder, and the first one
is left behind with no record of which one came first.

A user who wants a change to a part asks for it in words. The core has to
answer three questions before it can answer that request at all.

- What is the part now? Only a verified workspace can be edited, because an
  edit of a part that was never built has nothing to preserve.
- What changed? Every edit must leave the earlier state readable, so a
  mistake can be undone without a rebuild.
- What is the truth after a crash? A run that stops halfway must not leave
  the workspace in a state that nobody can explain.

The constraints below shape the decision.

The core is CAD-neutral, language-neutral and interface-neutral
([`docs/ARCHITECTURE.md`](../ARCHITECTURE.md)). A revision is a folder of
files, so the core needs no knowledge of the system that built them.

The workspace of Phase 8 is already a standalone workspace: the manifest
declares its artifacts with paths relative to its own root, and the viewer
reads any such folder directly
([`clients/viewer/workspace.py`](../../clients/viewer/workspace.py)). A
revision that keeps that layout needs no change in the client.

The generation path is frozen
([`aturb/agent/generate.py`](../../aturb/agent/generate.py) and
[`aturb/agent/generate_cli.py`](../../aturb/agent/generate_cli.py)). An edit
must reuse it rather than reimplement it, so the two paths cannot drift.

## Verified facts

The facts below were measured in-session on 2026-11-25 and are the only
facts this record relies on.

**What a successful generation guarantees.** `generate_part()` returns
`status = "ok"` on one branch only: the branch where the exported geometry
was read and measured. That branch requires `geometry is not None`,
`geometry.is_valid` and `geometry.is_single_solid`, and it is reached only
after the build reported `ok` and the STEP file was read. A generation that
reports `ok` therefore also reports `build_status = "ok"` and holds one
valid solid. A generation that fails returns `status = "error"` with a stop
reason and an error text, and never raises.

**The layout of a workspace.** `write_generate_manifest()` writes
`result.toml` at the root of the workspace it is given, and every path in
the manifest is relative to that root: `part_file` is
`project/parts/<part_id>_candidate<extension>`, `step_file` is
`project/out/<part_id>/<part_id>.step`, and `native_file` is
`project/out/<part_id>/<part_id>.<native extension>`. Copying the manifest
and the `project/` folder into a new root therefore preserves every
relative path verbatim.

**The manifest of a verified part.** `result.toml` holds `status`,
`part_id`, `stop_reason`, `attempts`, `input_tokens`, `output_tokens`,
`cost_usd`, `prompt_version`, `build_status`, `failure_kind`, `error`,
`conventions`, `part_file`, `step_file` and `native_file`, and, when the
geometry was measured, `is_valid`, `is_single_solid`, `volume`,
`bbox_size`, `hole_count` and `holes`.

**The path helpers.** `resolve_inside()` resolves a path against a root and
refuses a result that leaves it; `to_rel()` returns a path relative to a
root with forward slashes. Both resolve symbolic links, so a link that
points outside the root is refused.

**The viewer.** `load_workspace()` reads the `result.toml` of the folder it
is given and resolves the declared artifacts against that folder. It
refuses an absolute path, a `..` component and a link that escapes. A
revision folder is therefore readable by the viewer as it stands.

**The TOML writer.** `toml_string()` escapes a text as a TOML basic string.
The core has no atomic writer, so the history writer writes to a temporary
file in the same folder and moves it over the old one.

## Decision

**Every revision is a complete standalone workspace.** A workspace that can
be edited keeps its revisions in `revisions/r0001/`, `revisions/r0002/` and
so on. Each folder holds a `result.toml` and a `project/` folder with the
source and the exported artifacts, exactly as a Phase 8 workspace does. A
revision is never rewritten: an edit builds a new folder and leaves every
earlier folder byte for byte as it was. Because the layout is the layout of
Phase 8, the viewer opens a revision folder without any change in the
client.

**The history is one portable file.** `<workspace>/history.toml` holds the
`active_revision` and one ordered `[[revisions]]` table per revision, with
the fields `id`, `parent`, `kind` (`initial` or `edit`), `status` (`ok` or
`error`), `stop_reason`, `instruction`, `attempts`, `prompt_version` and
`rel_dir`. Every path in it is relative to the workspace, so the file can
be moved with the workspace and holds no absolute path of any host. The
file is written atomically, through a temporary file in the same folder and
a move over the old one, so a reader never sees half a history.

**Only a verified workspace can be edited.** Bootstrapping copies the
verified `result.toml` and the `project/` folder of a plain Phase 8
workspace into `revisions/r0001/` and leaves the root files untouched. A
workspace whose manifest is missing, malformed, or does not report a valid
single solid is refused: a failed generation is never editable, because
there is no verified part to preserve and to measure. A `revisions/r0001/`
folder that is already there was never recorded, so it is rebuilt from the
root workspace instead of being promoted.

**An edit builds a new revision and promotes it only when it verifies.**
The edit runs the existing generation path into the new folder, and the
promotion is decided by the result of that run: the revision becomes the
active one only when the generation reports `ok` with a valid single solid.
A failed edit is recorded with `status = "error"`, the active revision
stays pinned to the last verified solid, and the earlier folders are
untouched. A model failure or a build failure is a result, not an
exception.

**A crash never promotes an orphan.** A run that stops before the history
is written leaves a folder that the history does not name. Such a folder is
never promoted: the history is the only record of what happened, and the
next edit allocates its number past every folder on disk, so the orphan is
stepped over rather than reused.

**A rollback selects a revision; it does not undo one.** A rollback makes a
previously verified revision the active one and deletes nothing: the later
revisions stay on disk and stay in the history. It selects a verified
workspace revision as the state to work from; it does not restore a live
session in a design application, and it does not rebuild anything.

**An edit is expectation-free.** The requirement of an edit holds the
modification instruction, the measured facts of the current verified part,
the current verified source and the rules of the edit. The facts are the
ones the manifest records, so they come from an independent check of the
exported geometry and not from an assumption. No task, no answer and no
score ever reaches the model.

## Consequences

A workspace becomes editable without a new command and without a new
dependency: the first edit bootstraps the history from the workspace that
is already there.

The history is the only record of the edits, so it is the only thing that
has to be kept with the workspace. The revision folders are the state, and
the history says which of them is active.

The cost is disk: every edit keeps a full copy of the workspace, including
the exported artifacts. A workspace with many edits is large, and the
history does not prune it.

The core gains two modules and no new concept of geometry. The revision
folder is a workspace, the history is a list of workspaces, and the edit is
the generation path with a different requirement.

The rollback is a selection and not an undo. A user who wants the earlier
state back gets it by making it active; the later revisions remain, and
the next edit builds on the selected one.
