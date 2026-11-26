# ADR-0013: Multi-part assemblies

## Status

Accepted.

## Context

ATURB builds one part at a time. A part is a standalone source file that a
runner builds through the runner contract, and the neutral verification layer
judges the exported STEP of that part. A real product is rarely one part: it is
a set of parts that have to fit together.

Without an assembly model, nothing in the core can say whether two parts clash,
whether the gap between them is the gap the designer wanted, or whether an edit
to one part broke the fit of the whole product.

## Decision

1. **A part stays a part.** Every component of an assembly is a standalone
   native source file, built on its own through the existing runner contract
   (`BuildRequest` -> `BuildResult`). An assembly never introduces a second way
   of building geometry.

2. **An assembly is a portable manifest.** The assembly is declared in a
   relative-path TOML file at `assemblies/<assembly_id>.toml`. It holds
   `assembly_id`, `name`, a list of `[[components]]` and a list of `[[mates]]`.
   A component names a part, a position and an optional rotation. A mate names
   two components and the clearance window between them. The manifest holds no
   host path and no absolute path.

3. **Composition and verification are neutral.** The core places every
   component on its exported STEP, joins the placed solids into one multi-solid
   compound and writes that compound to a STEP file. The pairwise interference
   and the pairwise clearance are then measured with the same neutral modules
   that judge a single part, so an assembly is judged by the same rules as a
   part. The report is deterministic: the same manifest and the same part files
   always give the same pairwise numbers.

4. **An edit is verified as a whole.** A change to one part of an assembly is
   built and verified in an isolated staging copy of the project. The change is
   promoted into the live project only when the whole assembly verifies: no
   clash, and every mate inside its clearance window. A rejected change leaves
   the live project byte-for-byte as it was, so the last verified assembly
   survives.

## Consequences

- The core stays CAD-neutral: the manifest, the composition and the checks know
  nothing about the system that built the parts.
- The manifest is a declaration, not a geometry language: it places parts and
  states clearances, and it never describes a feature.
- An assembly is reproducible from its manifest and the part files, because the
  composition reads only exported STEP files.
- A coupled change to several parts is expressed as one edit that is verified
  as one assembly, so a change that only works together is never promoted one
  part at a time.
