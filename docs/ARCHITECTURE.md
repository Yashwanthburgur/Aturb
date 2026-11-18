# Architecture

```text
 Clients (later): CLI | FreeCAD panel | cloud agent | messaging
                          |
                 CORE SERVICE (CAD-neutral, language-neutral)
        request -> plan -> edit files -> run -> verify -> fix/finish
        project workspace + history | model access | approval | cost caps
                          |
                   RUNNER CONTRACT  (the only door to a CAD system)
                          |
          BACKEND PACK: FreeCAD (first) | others later
                          |
                 Neutral measuring on exported STEP
```

## Clients

Clients are thin and built later. Each one only forwards a request to the core service and shows what comes back. None of them contains CAD knowledge or geometry logic. The CLI, the FreeCAD panel, a cloud agent and a messaging bot are all clients of the same core.

## Core service

The core never knows which CAD, language or front end is in use. It takes a request, plans the work, edits the project's files, runs them, verifies the result and either fixes the problem or finishes. It also owns the project workspace and history, model access, approval and cost caps.

## Runner contract

The runner contract takes a build request and returns a result, and never exposes CAD operations. It is the only door to a CAD system, so the core never talks to a CAD application directly. Because the contract carries requests and results rather than geometry commands, it stays the same when the CAD changes.

## Backend pack

A backend pack holds everything for one CAD: its language, its conventions, its prompt and its runner. FreeCAD is the first pack and others come later, one folder per CAD. Adding a CAD means adding a pack, not changing the core.

## Neutral measuring

Checks run on exported STEP so they are the same for every CAD. The same neutral library measures the geometry whatever built it, so a check means the same thing in every pack. A CAD's own diagnostics are informational only and never decide whether a check passed.

## Two Python environments

The two Python environments, and why they exist, are set out in `docs/adr/0003-two-pythons.md`.
