# ADR-0014: The assembly agent

## Status

Accepted.

## Context

ADR-0013 made an assembly verifiable: a change to the parts of an assembly is
promoted only when the whole assembly verifies. Nothing yet asks a model for
that change.

A single-part edit has one file to write. An assembly edit has several, and
the parts are coupled: a shaft that grows needs a bore that grows with it, or
the assembly clashes. The model therefore has to see the assembly, not one
part, and it has to be told exactly how its answer is read back.

## Decision

1. **One stateless message.** The assembly edit reuses `ModelClient` unchanged.
   The request is a single `role: "user"` message that carries the whole
   context. There is no tool-calling schema, no function name and no
   JSON-escaped Python string: the answer is plain text.

2. **A text delimiter contract.** The answer holds one block per part that
   must change, and every block is wrapped in two exact markers:

   ```text
   # === PART: <part_id> ===
   <complete source for part_id>
   # === END PART: <part_id> ===
   ```

   The parser is strict: an unknown part id, a duplicate part id, an unclosed
   block, a mismatched end marker and an empty body are all refused.

3. **A bounded repair loop.** A rejected update is never accumulated. The next
   attempt replaces the feedback with the exact failures of the attempt before
   it: the build error of a part that failed, or the interference volume and
   the mate clearance of a pair that failed. The loop is bounded by the attempt
   limit and by the token and cost budgets of the agent settings.

4. **Non-destructive promotion and immutable revisions.** A change is applied
   through `apply_assembly_edit()`, so the live project is written only when
   the whole assembly verifies. Every assembly keeps an immutable revision
   history in `out/assemblies/<assembly_id>/`: `revisions/rNNNN/` holds a
   snapshot of the verified state and `assembly_history.toml` names the active
   revision. A rollback restores a snapshot, so the last verified assembly is
   always one command away.

## Consequences

- The core stays CAD-neutral: the prompt, the parser and the feedback name
  parts, mates and clearances, and no CAD system.
- The model sees the assembly context it needs: the components, the mates, the
  verified measurements and the current source of every part.
- A rejected edit leaves the live project byte-for-byte as it was.
- The history is portable: it holds relative paths only.
