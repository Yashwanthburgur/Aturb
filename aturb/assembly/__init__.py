"""The assembly model of ATURB: a portable manifest, a build and a safe edit.

The package holds three things:

- `manifest.py` reads the portable TOML manifest of an assembly.
- `build.py` builds every part of an assembly and verifies the whole assembly.
- `edit.py` applies a change to the parts of an assembly and never promotes a
  change that breaks the assembly.

The package is CAD-neutral: it knows nothing about the system that builds the
parts, and it never creates a feature of its own.
"""
