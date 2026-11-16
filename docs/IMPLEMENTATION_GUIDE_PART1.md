
Aturb

Before writing this, one design decision you should know about, because it shapes every prompt: the main way these agents hallucinate on this project is by inventing FreeCAD and build123d function names. So the guide builds a verified-API register (docs/api_notes/) in Phase 1, and every later prompt is only allowed to use calls recorded there or verified on the spot. That also explains why this is Part 1 rather than all 500 at once: the prompts for Phases 3 onward should be written from the facts your Phase 1–2 spikes record, not from my memory of the APIs. Writing them now would bake in exactly the guesses the prompts are meant to prevent.
ATURB_Implementation_Guide_Part1.md has 96 task cards covering Phases 0–2, each one a self-contained prompt you can paste after the Session Preamble.
A few things that make it work the way you want:
•	The agent never commits; you do. Every prompt ends with the agent pasting git status and the acceptance output. You run the acceptance yourself, check git diff --stat against the task’s file list, then commit with the task ID. That’s your control point as orchestrator — and it’s exactly what stopped happening in PieCAD.
•	The riskiest tasks are T1.20, T1.21 and T1.23 — the first real FreeCAD geometry and the failed-feature detection. I gave starting code for the first two, explicitly marked “verify each call”, because FreeCAD renamed several properties between versions and I can’t be certain which version you’ll install. T1.23’s finding feeds straight into T2.24, so don’t skip recording it.
•	The acceptance numbers are calculated, not guessed. The demo plate’s 35,214.602 mm³ comes from the hand calculation shown in the task, so when a test passes, it means the geometry is actually right.
When Phase 2 is done, send me docs/api_notes/freecad.md, docs/api_notes/build123d.md and docs/ENVIRONMENT.md, and I’ll write Part 2 against what your machine actually verified.
Aturb implementation guide part1
Document·MD



ATURB Implementation Guide — Part 1
Phases 0–2: Bootstrap, Environment, Runner Contract · 96 tasks
Repo: yashwanthburgur/Aturb · Machine: Windows, PowerShell in VS Code · Orchestrator: you · Executors: Cline / Zoo / any coding agent on free or cheap models.
This guide implements ATURB_MVP_Roadmap.md, which implements ATURB Requirements and Locked Decisions v2. If anything here conflicts with v2, v2 wins.
________________________________________
How to use this guide
The loop for every task
1.	Start a fresh agent session. One task per session, two at most. Long sessions are where drift starts.
2.	Paste the Session Preamble (below), then the task's prompt block. Nothing else.
3.	Read the file list the agent proposes before it edits. If it names a file outside the task's FILES, reject and repeat the scope.
4.	When it reports back, run every acceptance command yourself. Don't trust the pasted output alone.
5.	Run git diff --stat. The files listed must match FILES exactly.
6.	Read the diff. It should be under ~200 lines. If you can't understand a line, ask the agent to explain it before committing.
7.	Commit: git add -A then git commit -m "T1.08: config loader".
8.	Tick the box in this file.
If a task fails twice: stop the agent. Run git checkout -- . and git clean -fd to discard its changes (your gitignored aturb.local.toml survives, since -fd doesn't touch ignored files). Then either split the task in two, or run it once on a stronger model. Never let an agent flail through a third attempt — that's how duplicate functions and dead code accumulate.
Task types
•	Agent task — has a prompt block. Paste it.
•	(You) task — no prompt. You do it by hand: installing software, writing documents you must own, pushing.
•	Spike — a throwaway experiment that turns an assumption into a fact. Its real output is a line in docs/api_notes/ or docs/ENVIRONMENT.md, not the code.
•	(FC) — needs FreeCAD installed. Runs only on your machine, never in CI.
Why the API notes matter
docs/api_notes/freecad.md and docs/api_notes/build123d.md are the ground truth for which library calls exist on your installed versions. Every prompt from Phase 1 onward tells the agent: use only calls recorded there, or verify a new one on the spot and report it. This is the single biggest defence against hallucinated APIs. Treat the notes as precious — if a spike records something, it was tested.
________________________________________
SESSION PREAMBLE — paste this at the start of every agent session
You are implementing exactly one task in the ATURB repository.

ATURB is an AI agent that does mechanical CAD work by writing CAD code, running it in a real CAD system, and checking results with tests it cannot change. The core package `aturb/` is CAD-neutral. Everything specific to one CAD system lives in `packs/<name>/`.

RULES — follow all of them:
1. Do only the task below. Do not refactor, rename, reformat, or "improve" anything outside it.
2. Before editing anything, list every file you will create or modify. They must all be in the task's FILES list. If you need any other file, stop and explain why instead of editing it.
3. Never guess an API. If you are not certain a function, class, argument or property exists in FreeCAD, build123d, or any library, verify it first with a tiny command (help(), dir(), or a 3-line script) and show the output. Only use calls listed in docs/api_notes/ or verified in this session. If something does not exist, stop and report it. Do not invent a workaround.
4. Never add: functions the CAD agent can call to perform CAD operations (no create_box, make_hole, fillet helpers); any intermediate geometry language, DSL, or JSON geometry schema; multi-agent logic; any CAD brand name or CAD concept inside the aturb/ package.
5. Keep every file under 300 lines and the whole change under about 200 lines.
6. This is Windows with PowerShell. Use pathlib. Never hardcode machine paths. Never put absolute paths in committed files.
7. Run core Python with `uv run`. Never use pip. Add a dependency only if the task says so, and only with `uv add`.
8. Never write a number you did not calculate or measure. If a value is a chosen default, add the comment `# starting default`.
9. Do not commit. The orchestrator commits.
10. When finished, reply with exactly three sections:
    (a) the output of `git status --short`
    (b) each ACCEPTANCE command you ran, with its complete output
    (c) any assumption you made, or "none"
    Never claim success without showing the output.

THE TASK:
________________________________________
Whole-project task map
This part covers Phases 0–2. Later parts are written after each phase's spikes have filled the API notes, so their prompts use verified calls rather than guesses.
Phase	Roadmap topic	Task IDs	Approx. tasks	Guide part
0	Bootstrap	T0.01–T0.13	13	Part 1
1	Environment, first headless part	T1.01–T1.39	39	Part 1
2	Runner contract	T2.01–T2.44	44	Part 1
3	Neutral checks on STEP	T3.xx	~45	Part 2
4	Task set and scoring	T4.xx	~40	Part 2
5	Stock-agent baseline	T5.xx	~32	Part 3
6	Conventions and selection helper	T6.xx	~48	Part 3
7	Improvement loop	T7.xx	~40	Part 4
8	Edits, shared parameters, assemblies	T8.xx	~50	Part 4
9	Approve, undo, events	T9.xx	~48	Part 5
10	Stub proof	T10.xx	~20	Part 5
11	CLI and FreeCAD Qt panel	T11.xx	~36	Part 6
12	Brownfield editing	T12.xx	~30	Part 6
			~485	
________________________________________
PHASE 0 — Bootstrap
You've already created the repo and initialized git. This phase gives it a skeleton, a pinned Python, and a first passing test.
________________________________________
•	[ ] T0.01 · (You) Confirm your tools
Run these in the VS Code terminal and keep the output — you'll record it in T1.29:
•	git --version
•	git remote -v → should show yashwanthburgur/Aturb
•	uv --version → if missing, install uv using the PowerShell command on the official uv installation page (astral.sh), then reopen the terminal.
________________________________________
•	[ ] T0.02 · Folder skeleton · Roadmap 1.01
TASK T0.02 — Create the folder skeleton

GOAL: Create the top-level folders, each with a one-line README.md explaining its purpose.

DO EXACTLY:
Create these folders. In each, create README.md containing exactly the one line shown (no heading, no extra lines):
- aturb/README.md            → Core service. CAD-neutral and language-neutral. Never names a CAD system.
- packs/README.md            → Backend packs. Everything specific to one CAD lives in one folder here.
- packs/freecad/README.md    → FreeCAD backend pack (first pack).
- packs/stub/README.md       → Stub backend that returns canned results. Proves the core never depends on a real CAD.
- clients/README.md          → Thin clients of the core service.
- projects/README.md         → Example CAD projects: folders of part files, expectations, and requirements.
- evals/README.md            → Evaluation tasks, correct answers, and dated results.
- tools/README.md            → Repository tools: lints, limits, and spikes.
- tests/README.md            → Pytest tests. FreeCAD-dependent tests are marked @pytest.mark.freecad.
- docs/README.md             → Architecture, environment, security notes, and decision records.
- docs/adr/README.md         → Architecture decision records, one per decision, 10 to 20 lines each.
- docs/api_notes/README.md   → Verified third-party API calls. Agents may only use calls recorded here or verified in-session.

FILES (only these): the 12 README.md files above.

DO NOT: create any .py files, config files, or other folders.

ACCEPTANCE:
- Get-ChildItem -Recurse -Filter README.md | Measure-Object | Select-Object -ExpandProperty Count
  → 12
- Get-ChildItem -Recurse -Filter README.md | ForEach-Object { "$($_.FullName.Replace($PWD.Path,'')) : $((Get-Content $_.FullName).Count)" }
  → every line ends with ": 1"
________________________________________
•	[ ] T0.03 · Root README · Roadmap 1.01
TASK T0.03 — Root README

GOAL: Create the root README.md with exactly the text below.

DO EXACTLY:
Create README.md at the repository root containing exactly:

# ATURB (working name)

ATURB is an AI agent that does mechanical CAD work on a person's behalf. You describe a part or a change in plain language. The agent edits the project's CAD code, builds it in a real CAD system, checks the result with tests it cannot change, fixes its own mistakes, and presents a verified result you can inspect, approve, or undo.

ATURB is not a CAD program, not a text-to-mesh generator, not tied to one CAD vendor, and not a replacement for an engineer's sign-off.

Status: early development. First backend: FreeCAD, run headless.

FILES (only these): README.md

ACCEPTANCE:
- (Get-Content README.md).Count  → 9 or fewer
- Select-String -Path README.md -Pattern "not a CAD program"  → one match
________________________________________
•	[ ] T0.04 · .gitignore · Roadmap 1.02
TASK T0.04 — .gitignore

GOAL: Create .gitignore so build products, local config, and caches are never committed.

DO EXACTLY:
Create .gitignore at the repository root with exactly:

# Python
__pycache__/
*.py[cod]
.venv/
.pytest_cache/
.ruff_cache/

# Local machine config (paths and keys)
aturb.local.toml

# Build products (any folder named out)
out/

# FreeCAD backup files
*.FCStd1
*.FCBak

# Eval scratch space
evals/tmp/

# OS clutter
Thumbs.db
.DS_Store

FILES (only these): .gitignore

ACCEPTANCE:
- New-Item -ItemType Directory -Force projects\x\out | Out-Null; New-Item -Force projects\x\out\a.txt | Out-Null; git status --short
  → the output does NOT list projects/x/out/a.txt
- Remove-Item -Recurse -Force projects\x
________________________________________
•	[ ] T0.05 · .gitattributes · Roadmap 1.03
TASK T0.05 — .gitattributes

GOAL: Stop git from changing line endings in source files or corrupting CAD files.

DO EXACTLY:
Create .gitattributes at the repository root with exactly:

* text=auto
*.py text eol=lf
*.toml text eol=lf
*.md text eol=lf
*.yaml text eol=lf
*.yml text eol=lf
*.json text eol=lf
*.FCStd binary
*.step binary
*.stp binary
*.png binary

FILES (only these): .gitattributes

ACCEPTANCE:
- git check-attr -a -- sample.step
  → output includes "binary: set"
- git check-attr -a -- sample.py
  → output includes "eol: lf"
________________________________________
•	[ ] T0.06 · pyproject.toml · Roadmap 1.04
TASK T0.06 — pyproject.toml

GOAL: Create the project definition so the core and packs install as one package.

DO EXACTLY:
Create pyproject.toml at the repository root with exactly:

[project]
name = "aturb"
version = "0.0.1"
description = "AI agent that does mechanical CAD work by writing, running and checking CAD code."
requires-python = ">=3.11,<3.13"
dependencies = []

[project.scripts]
aturb = "aturb.cli:main"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["aturb", "packs"]

FILES (only these): pyproject.toml

DO NOT: add dependencies or tool sections. Later tasks add them.

ACCEPTANCE:
- uv run python -c "import tomllib; d=tomllib.load(open('pyproject.toml','rb')); print(d['project']['name'], d['tool']['hatch']['build']['targets']['wheel']['packages'])"
  → aturb ['aturb', 'packs']
  (This may fail until T0.08 creates the environment. If so, report the error and continue; T0.08 re-checks it.)
________________________________________
•	[ ] T0.07 · Package init files · Roadmap 1.04
TASK T0.07 — Package init files

GOAL: Make aturb and packs importable Python packages.

DO EXACTLY:
1. Create aturb/__init__.py containing exactly:
   """ATURB core: CAD-neutral, language-neutral."""
   __version__ = "0.0.1"
2. Create packs/__init__.py containing exactly:
   """Backend packs. Each subfolder holds everything specific to one CAD system."""
3. Create packs/freecad/__init__.py containing exactly:
   """FreeCAD backend pack."""
4. Create packs/stub/__init__.py containing exactly:
   """Stub backend pack."""

FILES (only these): aturb/__init__.py, packs/__init__.py, packs/freecad/__init__.py, packs/stub/__init__.py

ACCEPTANCE: run after T0.08 (no environment exists yet). Report "deferred to T0.08".
________________________________________
•	[ ] T0.08 · Pin Python and create the environment · Roadmap 1.04
TASK T0.08 — Pin Python and create the environment

GOAL: Pin the core Python version and create the virtual environment.

DO EXACTLY:
1. Run: uv python pin 3.12
2. Run: uv sync
3. If uv sync fails, paste the full error and stop. Do not change requires-python or the pinned version yourself.

FILES (only these): .python-version (created by uv), uv.lock (created by uv)

ACCEPTANCE:
- uv run python --version                                        → Python 3.12.x
- uv run python -c "import aturb, packs; print(aturb.__version__)" → 0.0.1
________________________________________
•	[ ] T0.09 · Dev tools: pytest and ruff · Roadmap 1.23, 1.24
TASK T0.09 — Add pytest and ruff with configuration

GOAL: Add the test runner and linter, configured once.

DO EXACTLY:
1. Run: uv add --dev pytest ruff
2. Append these sections to the end of pyproject.toml exactly:

[tool.ruff]
line-length = 100
target-version = "py311"

[tool.ruff.lint]
select = ["E", "F", "I", "B"]

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "--strict-markers"
markers = [
    "freecad: needs FreeCAD installed; never runs in CI",
]

FILES (only these): pyproject.toml, uv.lock

ACCEPTANCE:
- uv run ruff --version   → prints a version
- uv run pytest --version → prints a version
- uv run ruff check .     → All checks passed!
________________________________________
•	[ ] T0.10 · First test · Roadmap 1.24
TASK T0.10 — First passing test

GOAL: Prove the test setup works.

DO EXACTLY:
Create tests/test_package.py with one test, test_version, asserting that aturb.__version__ == "0.0.1".

FILES (only these): tests/test_package.py

ACCEPTANCE:
- uv run pytest -q → 1 passed
________________________________________
•	[ ] T0.11 · (You) Write AGENTS.md
This is your document. Below is a draft. Read every line, change anything you disagree with, then save it as AGENTS.md at the repo root. v2 and both earlier research documents insist this file is human-owned, and for good reason: it's the one place your intent is stated directly rather than through an agent.
# AGENTS.md — rules for coding agents working on this repository

## What this repository is
ATURB core (`aturb/`) is CAD-neutral and language-neutral.
Everything specific to one CAD system lives in `packs/<name>/`.
Read docs/ARCHITECTURE.md before changing structure.

## Commands
- Sync environment: `uv sync`
- Tests without CAD: `uv run pytest -m "not freecad" -q`
- All tests (needs FreeCAD): `uv run pytest -q`
- Lint: `uv run ruff check .`
- File size limit: `uv run python tools/size_limit.py`
- Agnosticism lint: `uv run python tools/agnostic_lint.py`

## Hard rules
1. Do only the assigned task. List files before editing.
2. Never add an operations layer: no agent-callable create_box, fillet or hole functions.
3. Never add an intermediate geometry language, JSON geometry schema or DSL.
4. Never add multi-agent logic, background summarizers or design graphs.
5. Never put a CAD brand name or CAD concept inside `aturb/`.
6. Pack helpers may select, measure and assert. They may never create features.
7. Never guess a library API. Verify with a tiny command first.
   Use only calls recorded in docs/api_notes/ or verified in-session.
8. Files at most 300 lines. Changes at most ~200 lines per task.
9. No absolute paths or machine-specific values in committed files. Use config.
10. Mark every chosen default with `# starting default`.
11. Do not commit. Report `git status --short` and acceptance output.

## Layout
- aturb/     core service (CAD-neutral)
- packs/     backend packs: freecad, stub
- clients/   thin clients of the core service
- projects/  example CAD projects
- evals/     tasks, correct answers, results
- tools/     lints, limits, spikes
- tests/     pytest; FreeCAD tests marked @pytest.mark.freecad
- docs/      architecture, environment, ADRs, api_notes
________________________________________
•	[ ] T0.12 · AGENTS.md guard test · Roadmap 1.27
TASK T0.12 — Guard test for AGENTS.md

GOAL: Fail the test suite if AGENTS.md grows too long or loses its key rules.

DO EXACTLY:
Create tests/test_agents_md.py with three tests:
- test_agents_md_exists: AGENTS.md exists at the repository root (locate the root as the parent of the tests folder using pathlib, not the current directory).
- test_agents_md_short: AGENTS.md has at most 60 lines.
- test_agents_md_key_rules: AGENTS.md contains the strings "uv run pytest" and "operations layer".

FILES (only these): tests/test_agents_md.py

DO NOT: edit AGENTS.md.

ACCEPTANCE:
- uv run pytest tests/test_agents_md.py -q → 3 passed
________________________________________
•	[ ] T0.13 · (You) First commit and push
git add -A · git commit -m "T0: bootstrap skeleton" · git push. Confirm the files appear on GitHub.
________________________________________
PHASE 1 — Environment, with one hand-written part built headless
Exit criteria: build123d smoke test green; FreeCAD builds the demo plate headless and build123d measures it at the hand-calculated volume; spikes recorded; CI green.
________________________________________
•	[ ] T1.01 · Runtime dependencies · Roadmap 1.05
TASK T1.01 — Add build123d and pyyaml

GOAL: Add the geometry library used for neutral measuring, and YAML parsing for later eval tasks.

DO EXACTLY:
1. Run: uv add build123d pyyaml
2. If installation fails, paste the full error and stop. Do not change the Python version.

FILES (only these): pyproject.toml, uv.lock

ACCEPTANCE:
- uv run python -c "import importlib.metadata as m; print('build123d', m.version('build123d')); print('pyyaml', m.version('pyyaml'))"
  → two lines with version numbers
- uv run python -c "import build123d, yaml; print('ok')" → ok
________________________________________
•	[ ] T1.02 · Verify the build123d calls we need (spike) · Roadmap 1.05
TASK T1.02 — Verify build123d API and record it

GOAL: Find out which build123d calls exist on the installed version for: making a box, making a cylinder, positioning, subtracting, exporting STEP, importing STEP, reading volume, reading a bounding box size, and checking validity. Record only what you verified.

DO EXACTLY:
1. For each item, run a tiny command to confirm it, for example:
   uv run python -c "import build123d as b; print([n for n in dir(b) if 'step' in n.lower()])"
   uv run python -c "import build123d as b; help(b.Box)" (read only the signature)
2. Run one 6-line script that: makes a 10 x 10 x 10 box, exports it to STEP in a temp folder, imports it back, prints its volume, prints its bounding-box size, prints its validity check result.
3. Create docs/api_notes/build123d.md containing:
   - first line: "# build123d — verified API"
   - a line: "Verified on build123d <version> on <today's date>."
   - a table with columns: Call | Purpose | Verified output
   - one row per call you actually ran, with the real output you saw.

FILES (only these): docs/api_notes/build123d.md

DO NOT: add any call you did not run. Do not add code files.

ACCEPTANCE:
- The 6-line script output (paste it) shows volume 1000 (within floating point) and size 10, 10, 10.
- Get-Content docs/api_notes/build123d.md shows the table with at least 7 rows.
________________________________________
•	[ ] T1.03 · build123d smoke test · Roadmap 1.05
TASK T1.03 — build123d smoke test

GOAL: A permanent test that build123d can make, export, import and measure a solid.

DO EXACTLY:
Create tests/test_smoke_build123d.py with one test, test_cube_step_round_trip, that uses ONLY calls listed in docs/api_notes/build123d.md:
1. make a 10 x 10 x 10 box
2. export it to STEP inside pytest's tmp_path
3. import that STEP back
4. assert volume == 1000 within 1e-6
5. assert bounding-box size is 10, 10, 10 within 1e-6
6. assert the validity check returns true

FILES (only these): tests/test_smoke_build123d.py

ACCEPTANCE:
- uv run pytest tests/test_smoke_build123d.py -q → 1 passed
________________________________________
•	[ ] T1.04 · (You) Install FreeCAD · Roadmap 1.06
Install the latest stable FreeCAD release for Windows from the official site (freecad.org). Avoid weekly/development builds. Note the exact version shown under Help → About — you'll record it in T1.05. Open the GUI once to confirm it works.
________________________________________
•	[ ] T1.05 · Locate FreeCAD's command-line program and start ENVIRONMENT.md · Roadmap 1.06
TASK T1.05 — Locate FreeCAD's command-line executable

GOAL: Find the headless FreeCAD executable and start the environment document.

DO EXACTLY:
1. Run (the name differs between FreeCAD versions, so search):
   Get-ChildItem "C:\Program Files" -Directory -Filter "FreeCAD*" | ForEach-Object { Get-ChildItem $_.FullName -Recurse -Filter "*cmd*.exe" -ErrorAction SilentlyContinue } | Select-Object FullName
2. Create docs/ENVIRONMENT.md with exactly these section headings, filling only what you verified:
   # Environment
   ## Operating system
   ## Tools (git, uv, Python)
   ## FreeCAD
   ## Running FreeCAD headless
   ## Passing data into FreeCAD scripts
   ## Exit codes and error output
   ## Timeouts and killing processes
   ## PartDesign headless findings
   ## STEP export
   ## Paths with spaces
   Under "FreeCAD", record: the FreeCAD version (ask the orchestrator if you cannot see it) and the full path pattern of the command-line executable found in step 1. Leave other sections with the line "Not yet verified."

FILES (only these): docs/ENVIRONMENT.md

ACCEPTANCE:
- Paste the output of the step 1 command.
- Select-String -Path docs/ENVIRONMENT.md -Pattern "^## " | Measure-Object → Count 10
________________________________________
•	[ ] T1.06 · Config template · Roadmap 1.07
TASK T1.06 — Config template

GOAL: Commit a config template. Real machine values go in a gitignored local copy.

DO EXACTLY:
Create aturb.example.toml at the repository root with exactly:

# Copy this file to aturb.local.toml (gitignored) and fill in values for your machine.
active_pack = "freecad"

[packs.freecad]
# Full path to FreeCAD's command-line executable. See docs/ENVIRONMENT.md.
cmd = ""

[packs.stub]

[timeouts]
build_s = 60  # starting default

FILES (only these): aturb.example.toml

ACCEPTANCE:
- uv run python -c "import tomllib; print(tomllib.load(open('aturb.example.toml','rb')))"
  → a dict containing 'active_pack': 'freecad'
________________________________________
•	[ ] T1.07 · (You) Create your local config
Copy aturb.example.toml to aturb.local.toml and set cmd to the full path found in T1.05. Use forward slashes or doubled backslashes inside the TOML string. Confirm with git status --short that aturb.local.toml is not listed.
________________________________________
•	[ ] T1.08 · Config loader · Roadmap 1.08
TASK T1.08 — Core config loader

GOAL: One place in core that finds and reads configuration. Core must stay CAD-neutral, so this module never mentions any CAD name.

DO EXACTLY:
Create aturb/config.py with:
1. class ConfigError(Exception).
2. def load_config(path: Path | None = None) -> dict
   Search order: (a) the explicit path if given; (b) the path in environment variable ATURB_CONFIG if set; (c) Path.cwd() / "aturb.local.toml".
   Read with tomllib. If no file is found, raise ConfigError whose message lists every location tried.
3. def active_pack(cfg: dict) -> str — returns cfg["active_pack"]; raise ConfigError with a clear message if missing.
4. def pack_settings(cfg: dict, name: str) -> dict — returns cfg.get("packs", {}).get(name, {}).
5. def timeout_s(cfg: dict, kind: str = "build") -> int — returns int(cfg["timeouts"][f"{kind}_s"]); raise ConfigError if missing.

Create tests/test_config.py with tests using tmp_path and monkeypatch only. Use the pack name "example" in test data, never a real CAD name:
- explicit path loads
- ATURB_CONFIG env var loads
- missing file raises ConfigError naming all tried locations
- active_pack missing raises ConfigError
- pack_settings for an unknown name returns {}
- timeout_s reads build_s

FILES (only these): aturb/config.py, tests/test_config.py

DO NOT: write the word freecad anywhere in aturb/config.py or its tests.

ACCEPTANCE:
- uv run pytest tests/test_config.py -q → 6 passed
- Select-String -Path aturb/config.py -Pattern "freecad" → no output
________________________________________
•	[ ] T1.09 · Spike runner script · Roadmap 1.09
TASK T1.09 — Spike runner for FreeCAD scripts

GOAL: One reliable way to run any spike script inside FreeCAD headless, so PowerShell quoting never gets in the way.

DO EXACTLY:
Create tools/spikes/run_fc.py, runnable as:
  uv run python tools/spikes/run_fc.py <script.py> [--env KEY=VALUE ...] [--timeout SECONDS]
Behaviour:
1. Load config with aturb.config.load_config(); read the command from pack_settings(cfg, "freecad")["cmd"]. If empty or missing, print a clear error and exit 2.
2. Run [cmd, <script path resolved to absolute>] with subprocess.run, capture_output=True, text=True, cwd = repository root (parent of tools/).
3. Environment = a copy of os.environ plus each --env KEY=VALUE pair.
4. Timeout default 120 seconds  # starting default. On timeout, print "TIMEOUT" and exit 3. (Process-tree killing comes in T1.28.)
5. Print, in this order: "EXIT: <code>", "--- STDOUT ---", the stdout, "--- STDERR ---", the stderr.
6. Exit with the child's exit code.

FILES (only these): tools/spikes/run_fc.py

ACCEPTANCE:
- uv run python tools/spikes/run_fc.py --help → shows usage
- uv run ruff check tools/spikes/run_fc.py → All checks passed!
________________________________________
•	[ ] T1.10 · Spike: FreeCAD hello · Roadmap 1.09 · (FC)
TASK T1.10 — Spike: run a script inside headless FreeCAD

GOAL: Confirm a script runs under FreeCAD's command-line executable and exits on its own.

DO EXACTLY:
1. Create tools/spikes/fc_hello.py containing exactly:
   import FreeCAD
   print("FREECAD_VERSION:", FreeCAD.Version())
2. Run: uv run python tools/spikes/run_fc.py tools/spikes/fc_hello.py
3. If the process does not exit by itself (it hangs until TIMEOUT), stop and report that. Do not work around it.
4. In docs/ENVIRONMENT.md, replace "Not yet verified." under "## Running FreeCAD headless" with: the exact command form that worked, and whether the process exits on its own.

FILES (only these): tools/spikes/fc_hello.py, docs/ENVIRONMENT.md

ACCEPTANCE:
- The run in step 2 prints "EXIT: 0" and a line starting "FREECAD_VERSION:".
________________________________________
•	[ ] T1.11 · Spike: passing a request file into FreeCAD · Roadmap 1.10 · (FC)
TASK T1.11 — Spike: pass data into a FreeCAD script with an environment variable

GOAL: Confirm a FreeCAD script can read a JSON file whose path arrives in an environment variable. This is how the real runner will pass build requests.

DO EXACTLY:
1. Create tools/spikes/sample_request.json containing exactly: {"hello": "world"}
2. Create tools/spikes/fc_args.py that: reads os.environ["ATURB_REQUEST"], prints "REQUEST_PATH:" and the path, opens the file with utf-8 encoding, and prints "REQUEST_JSON:" followed by the parsed dict.
3. Run: uv run python tools/spikes/run_fc.py tools/spikes/fc_args.py --env ATURB_REQUEST=$PWD\tools\spikes\sample_request.json
4. Under "## Passing data into FreeCAD scripts" in docs/ENVIRONMENT.md, record that this method works (or exactly how it failed).

FILES (only these): tools/spikes/sample_request.json, tools/spikes/fc_args.py, docs/ENVIRONMENT.md

ACCEPTANCE:
- Step 3 prints "EXIT: 0" and "REQUEST_JSON: {'hello': 'world'}".
________________________________________
•	[ ] T1.12 · Spike: exit codes and where tracebacks go · Roadmap 1.11 · (FC)
TASK T1.12 — Spike: what happens when a FreeCAD script raises

GOAL: Learn the exit code and the output stream used when a script raises an exception.

DO EXACTLY:
1. Create tools/spikes/fc_raise.py containing exactly:
   raise RuntimeError("planted failure")
2. Run: uv run python tools/spikes/run_fc.py tools/spikes/fc_raise.py
3. Under "## Exit codes and error output" in docs/ENVIRONMENT.md, record: the exit code observed, and whether "planted failure" appeared in STDOUT, STDERR, or both.

FILES (only these): tools/spikes/fc_raise.py, docs/ENVIRONMENT.md

ACCEPTANCE:
- Paste the full step 2 output.
- docs/ENVIRONMENT.md states the observed exit code as a number.
________________________________________
•	[ ] T1.13 · FreeCAD API notes, first entries · Roadmap 1.10
TASK T1.13 — Start the FreeCAD API notes

GOAL: Start the verified-call register for FreeCAD.

DO EXACTLY:
Create docs/api_notes/freecad.md containing:
- first line: "# FreeCAD — verified API"
- a line: "Verified on FreeCAD <version from docs/ENVIRONMENT.md>."
- a table with columns: Call or behaviour | Purpose | Verified in task | Notes
- rows ONLY for what tasks T1.10, T1.11 and T1.12 verified: FreeCAD.Version(), running a script file with the command-line executable, reading an environment variable inside the script, the exit-code behaviour on an exception.

FILES (only these): docs/api_notes/freecad.md

DO NOT: add any call that has not been run in a recorded task.

ACCEPTANCE:
- Get-Content docs/api_notes/freecad.md → shows the table with 4 rows.
________________________________________
•	[ ] T1.14 · Demo project skeleton · Roadmap 1.12
TASK T1.14 — Demo project skeleton

GOAL: Create the folder structure of a project — the same structure every ATURB project will use.

DO EXACTLY:
Create these folders under projects/demo/, each with a README.md containing exactly the one line shown:
- parts/README.md         → One file per part. Parameters at the top. Holes by diameter.
- shared/README.md        → Shared dimensions used by more than one part.
- assemblies/README.md    → Assembly files that place parts.
- expect/README.md        → Expected values for checks. The agent may not change these without a declared reason.
- requirements/README.md  → Plain-language intent for each part.
- imports/README.md       → Original human-made files. Never edited.

FILES (only these): the 6 README.md files above.

ACCEPTANCE:
- Get-ChildItem projects/demo -Directory | Select-Object -ExpandProperty Name
  → assemblies, expect, imports, parts, requirements, shared
________________________________________
•	[ ] T1.15 · Demo part: header and parameters · Roadmap 1.12
TASK T1.15 — Demo part file: header and parameter block

GOAL: Create the first part file with its parameter block. The geometry comes in T1.20 and T1.21.

DO EXACTLY:
Create projects/demo/parts/plt0001_base_plate.py containing exactly:

"""PLT0001 Base plate.

Rectangular plate with two through-holes.
Units: millimetres. Plate is centred on the origin in X and Y; it spans Z = 0 to THICKNESS_MM.
"""

# --- PARAMS ---
LENGTH_MM = 120.0      # along X
WIDTH_MM = 60.0        # along Y
THICKNESS_MM = 5.0     # along Z
HOLE_DIA_MM = 10.0     # diameter of both holes
HOLE_PITCH_MM = 80.0   # centre-to-centre distance of the holes, along X
# --- END PARAMS ---


def build(doc):
    """Build the part in the given document and return the final object."""
    raise NotImplementedError("geometry added in T1.20 and T1.21")

FILES (only these): projects/demo/parts/plt0001_base_plate.py

ACCEPTANCE:
- uv run ruff check projects/demo/parts/plt0001_base_plate.py → All checks passed!
- Select-String -Path projects/demo/parts/plt0001_base_plate.py -Pattern "_MM = " | Measure-Object | Select-Object -ExpandProperty Count → 5
________________________________________
•	[ ] T1.16 · Spike harness prototype · Roadmap 1.13 · (FC)
TASK T1.16 — Spike: a prototype build harness, tested with a trivial box

GOAL: Prove the build mechanics inside FreeCAD — new document, load a part file by path, call build(doc), recompute, save — using the simplest possible part.

DO EXACTLY:
1. Create tools/spikes/parts/box_part.py containing exactly:
   def build(doc):
       return doc.addObject("Part::Box", "Box")
2. Create tools/spikes/fc_build.py (runs INSIDE FreeCAD, so it must not import aturb). It:
   a. reads environment variables ATURB_PART (absolute path to a part file) and ATURB_OUT (absolute output folder)
   b. imports FreeCAD as App, plus json, os, importlib.util, traceback
   c. creates a new document with App.newDocument("Spike")
   d. loads the part file as a module with importlib.util.spec_from_file_location and exec_module
   e. calls build(doc) and keeps the returned object
   f. calls doc.recompute()
   g. creates ATURB_OUT if missing and saves the document there as <part file stem>.FCStd using doc.saveAs
   h. prints one line: "RESULT: " followed by json.dumps of {"status": "ok", "fcstd": <path>}
   i. on any exception, prints "RESULT: " followed by json.dumps of {"status": "failed", "error": traceback.format_exc()}
   j. closes the document with App.closeDocument(doc.Name) if it was created
3. Run:
   uv run python tools/spikes/run_fc.py tools/spikes/fc_build.py --env ATURB_PART=$PWD\tools\spikes\parts\box_part.py --env ATURB_OUT=$PWD\tools\spikes\out
4. If any FreeCAD call fails, verify it with dir() inside a spike instead of guessing, and report.

FILES (only these): tools/spikes/parts/box_part.py, tools/spikes/fc_build.py

ACCEPTANCE:
- Step 3 output contains "RESULT:" with "status": "ok".
- Test-Path tools\spikes\out\box_part.FCStd → True
________________________________________
•	[ ] T1.17 · Spike: STEP export · Roadmap 1.15 · (FC)
TASK T1.17 — Spike: export STEP headless

GOAL: Add STEP export to the spike harness and verify the call.

DO EXACTLY:
1. First verify the export method exists on a shape: in a spike, print hasattr(obj.Shape, "exportStep") for the box. If it is False, stop and report.
2. In tools/spikes/fc_build.py, after saving the FCStd, export the returned object's shape to <ATURB_OUT>/<stem>.step and add "step": <path> to the RESULT JSON.
3. Re-run the command from T1.16.
4. Add rows to docs/api_notes/freecad.md for: App.newDocument, doc.addObject("Part::Box", ...), doc.recompute, doc.saveAs, App.closeDocument, Shape.exportStep — each with "Verified in task: T1.16/T1.17".
5. Under "## STEP export" in docs/ENVIRONMENT.md, record the method that worked.

FILES (only these): tools/spikes/fc_build.py, docs/api_notes/freecad.md, docs/ENVIRONMENT.md

ACCEPTANCE:
- RESULT line contains "step".
- (Get-Item tools\spikes\out\box_part.step).Length → greater than 0
________________________________________
•	[ ] T1.18 · (You) Look at the result in the FreeCAD GUI
Open tools/spikes/out/box_part.FCStd in FreeCAD. Confirm the box is there and appears in the model tree. This is the first time a file ATURB built headless has been opened by a human — worth seeing with your own eyes.
________________________________________
•	[ ] T1.19 · Test helper for FreeCAD, plus the box test · Roadmap 1.16 · (FC)
TASK T1.19 — FreeCAD test helper and the first FreeCAD-marked test

GOAL: A small test helper that runs the spike harness, and a test that measures its STEP output with build123d.

DO EXACTLY:
1. Create tests/fc_utils.py with:
   def run_spike_build(part_path: Path, out_dir: Path) -> dict
   It loads config with aturb.config.load_config() (search from the repository root: pass an explicit path to aturb.local.toml at the root), gets pack_settings(cfg, "freecad")["cmd"], runs [cmd, <repo>/tools/spikes/fc_build.py] with env ATURB_PART and ATURB_OUT set (absolute paths), timeout 120  # starting default, finds the stdout line starting with "RESULT: ", and returns the parsed JSON dict. If no RESULT line exists, raise AssertionError including stdout and stderr.
2. Create tests/test_spike_box.py with one test marked @pytest.mark.freecad:
   test_box_step_volume — runs run_spike_build on tools/spikes/parts/box_part.py into tmp_path, asserts status "ok", imports the STEP with build123d (only calls in docs/api_notes/build123d.md), asserts volume 1000 within 1e-6.

FILES (only these): tests/fc_utils.py, tests/test_spike_box.py

ACCEPTANCE:
- uv run pytest tests/test_spike_box.py -q            → 1 passed
- uv run pytest -m "not freecad" -q                    → passes, and the box test is deselected
________________________________________
•	[ ] T1.20 · Demo part: body, sketch, pad · Roadmap 1.12, 1.13 · (FC)
TASK T1.20 — Demo part geometry, step 1: the plate

GOAL: Make plt0001 build a real PartDesign plate (no holes yet).

CONTEXT: The plate is centred on the origin in X and Y, spanning Z from 0 to THICKNESS_MM. Below is a STARTING POINT. Every call in it must be verified before you rely on it. Several FreeCAD properties were renamed between versions; if something fails, inspect with dir() rather than guessing.

STARTING POINT (verify each call):
    import FreeCAD as App
    import Part

    def _rect_sketch(body, name, length, width):
        sk = body.newObject("Sketcher::SketchObject", name)
        x, y = length / 2, width / 2
        pts = [App.Vector(-x, -y, 0), App.Vector(x, -y, 0),
               App.Vector(x, y, 0), App.Vector(-x, y, 0)]
        for i in range(4):
            sk.addGeometry(Part.LineSegment(pts[i], pts[(i + 1) % 4]), False)
        return sk

    def build(doc):
        body = doc.addObject("PartDesign::Body", "Body")
        sk = _rect_sketch(body, "PlateSketch", LENGTH_MM, WIDTH_MM)
        pad = body.newObject("PartDesign::Pad", "Pad")
        pad.Profile = sk
        pad.Length = THICKNESS_MM
        return body

DO EXACTLY:
1. Replace the NotImplementedError body of build() in projects/demo/parts/plt0001_base_plate.py with the plate geometry. Keep the header and PARAMS block unchanged.
2. Build it:
   uv run python tools/spikes/run_fc.py tools/spikes/fc_build.py --env ATURB_PART=$PWD\projects\demo\parts\plt0001_base_plate.py --env ATURB_OUT=$PWD\tools\spikes\out
3. Measure the STEP with a throwaway command using only calls from docs/api_notes/build123d.md; print volume and bounding-box size.
4. Add verified rows to docs/api_notes/freecad.md for every new call that worked (PartDesign::Body, body.newObject, Sketcher::SketchObject, addGeometry, Part.LineSegment, PartDesign::Pad, Pad.Profile, Pad.Length).

FILES (only these): projects/demo/parts/plt0001_base_plate.py, docs/api_notes/freecad.md

ACCEPTANCE:
- RESULT status "ok".
- Measured volume 36000 within 0.01. Bounding-box size 120, 60, 5 within 0.01.
________________________________________
•	[ ] T1.21 · Demo part: two through-holes · Roadmap 1.12 · (FC)
TASK T1.21 — Demo part geometry, step 2: the holes

GOAL: Add two through-holes of diameter HOLE_DIA_MM at X = ±HOLE_PITCH_MM/2, Y = 0.

STARTING POINT (verify each call; the hole sketch sits on the top face height so a through-all pocket cuts downward):
    hs = body.newObject("Sketcher::SketchObject", "HoleSketch")
    hs.Placement = App.Placement(App.Vector(0, 0, THICKNESS_MM), App.Rotation())
    for x in (-HOLE_PITCH_MM / 2, HOLE_PITCH_MM / 2):
        hs.addGeometry(Part.Circle(App.Vector(x, 0, 0), App.Vector(0, 0, 1), HOLE_DIA_MM / 2), False)
    pocket = body.newObject("PartDesign::Pocket", "Holes")
    pocket.Profile = hs
    pocket.Type = "ThroughAll"

DO EXACTLY:
1. Add the holes inside build() in projects/demo/parts/plt0001_base_plate.py, after the pad. Return the body.
2. If the pocket cuts nothing (volume unchanged), check the pocket direction with dir(pocket) and report what you found before changing anything.
3. Build with the same command as T1.20 and measure.
4. Add verified rows to docs/api_notes/freecad.md for each new call that worked.

FILES (only these): projects/demo/parts/plt0001_base_plate.py, docs/api_notes/freecad.md

ACCEPTANCE:
- RESULT status "ok".
- Measured volume 35214.602 within 0.01.
  Hand calculation: 120 x 60 x 5 = 36000; each hole pi x 5^2 x 5 = 392.699; two holes 785.398; 36000 - 785.398 = 35214.602.
- Bounding-box size still 120, 60, 5.
________________________________________
•	[ ] T1.22 · Permanent test for the demo plate · Roadmap 1.16 · (FC)
TASK T1.22 — FreeCAD-marked test for the demo plate

GOAL: Lock the demo plate's measured geometry into a test.

DO EXACTLY:
Create tests/test_demo_plate.py with one test marked @pytest.mark.freecad:
test_demo_plate_geometry — runs tests.fc_utils.run_spike_build on projects/demo/parts/plt0001_base_plate.py into tmp_path, asserts status "ok", imports the STEP with build123d, and asserts:
- volume == 35214.602 within 0.01 (copy the hand calculation from T1.21 as a comment)
- bounding-box size 120, 60, 5 within 0.01

FILES (only these): tests/test_demo_plate.py

ACCEPTANCE:
- uv run pytest tests/test_demo_plate.py -q → 1 passed
________________________________________
•	[ ] T1.23 · Spike: detecting failed features · Roadmap 1.14 · (FC)
TASK T1.23 — Spike: how FreeCAD reports a failed feature

GOAL: Learn which object property shows that a feature failed to recompute. The real harness depends on this.

DO EXACTLY:
1. Create tools/spikes/parts/broken_part.py: a PartDesign body with a sketch that has NO geometry, and a Pad using that empty sketch as its Profile. Return the body.
2. In tools/spikes/fc_build.py, after doc.recompute(), add to the RESULT JSON a key "states" mapping each object's Name to str(obj.State). Do not remove anything else.
3. Run the harness on broken_part.py, then on plt0001_base_plate.py.
4. Compare the two "states" outputs. Record in docs/api_notes/freecad.md exactly which State value(s) marked the failed Pad. Also check whether obj.isValid() exists (verify with hasattr) and what it returns for the failed Pad; record that too.

FILES (only these): tools/spikes/parts/broken_part.py, tools/spikes/fc_build.py, docs/api_notes/freecad.md

ACCEPTANCE:
- Paste both "states" outputs.
- docs/api_notes/freecad.md has a row naming the exact State value that indicates failure.
________________________________________
•	[ ] T1.24 · Spike: determinism · Roadmap 1.17 · (FC)
TASK T1.24 — Spike: does the same part build identically twice?

GOAL: Confirm two builds of the demo give identical measured geometry.

DO EXACTLY:
1. Build plt0001 twice into two different output folders using tools/spikes/run_fc.py.
2. Measure both STEP files with build123d (calls from api_notes): volume, area, bounding-box size, number of faces.
3. Record the result under a new line in docs/ENVIRONMENT.md "## PartDesign headless findings": "Two builds identical: yes/no" plus any difference.

FILES (only these): docs/ENVIRONMENT.md

ACCEPTANCE:
- Paste both measurements side by side. They must match exactly, or the difference is recorded.
________________________________________
•	[ ] T1.25 · Spike: fillet on edges chosen by geometry · Roadmap 1.18 · (FC)
TASK T1.25 — Spike: fillet edges selected by their geometry, not by index

GOAL: Prove that edges can be found by what they are (here: the four vertical corner edges of the plate) and filleted, headless. This is the basis of the selection rule (D6).

DO EXACTLY:
1. Create tools/spikes/parts/fillet_part.py: copy the demo plate's PARAMS and geometry, then add a fillet of radius 3.0  # starting default on the four vertical corner edges.
2. Find the edges from the latest feature's shape (body.Tip.Shape — verify Tip exists). An edge qualifies if its two vertices have the same X and the same Y (within 1e-6) and different Z. Collect their names as "Edge" + str(index + 1). Assert exactly 4 were found; if not, raise an error listing what was found.
3. Create a PartDesign::Fillet whose Base is (body.Tip, [the edge names]) and whose Radius is the fillet radius. Verify the Base format with dir() and a test build before relying on it.
4. Build with the spike harness. Measure the STEP volume.
5. Record in docs/api_notes/freecad.md: how edges were enumerated, the Fillet Base format that worked, and the measured volume compared to the unfilleted plate.

FILES (only these): tools/spikes/parts/fillet_part.py, docs/api_notes/freecad.md

ACCEPTANCE:
- RESULT status "ok".
- Measured volume is less than 35214.602.
- The spike printed or asserted that exactly 4 edges were found.
________________________________________
•	[ ] T1.26 · Spike: PartDesign Hole feature · Roadmap 1.19 · (FC)
TASK T1.26 — Spike: compare the Hole feature with Pocket

GOAL: Learn whether FreeCAD's PartDesign::Hole feature works headless for simple through-holes, and whether it is simpler than Pocket.

DO EXACTLY:
1. Create tools/spikes/parts/hole_part.py: the demo plate, but make the two holes with a PartDesign::Hole feature (Profile = the circle sketch) instead of a Pocket. First list the Hole feature's properties with dir() and print them; use only properties you saw, for diameter and through-all depth.
2. Build with the spike harness and measure the volume.
3. Under "## PartDesign headless findings" in docs/ENVIRONMENT.md, record: whether Hole worked, the property names used, the measured volume, and a one-line recommendation (Hole or Pocket) for simple through-holes.

FILES (only these): tools/spikes/parts/hole_part.py, docs/ENVIRONMENT.md, docs/api_notes/freecad.md

ACCEPTANCE:
- Paste the property list and the build output.
- If Hole worked: volume 35214.602 within 0.01. If it did not: the failure is recorded.
________________________________________
•	[ ] T1.27 · Spike: paths with spaces · Roadmap 1.20 · (FC)
TASK T1.27 — Spike: project paths containing spaces

GOAL: Confirm builds work when the project path contains spaces (common on Windows).

DO EXACTLY:
1. Copy projects/demo/parts/plt0001_base_plate.py to tools/spikes/my project/parts/plt0001_base_plate.py (note the space in "my project").
2. Build it with the spike harness, output into tools/spikes/my project/out.
3. Record the result under "## Paths with spaces" in docs/ENVIRONMENT.md.
4. Delete the folder tools/spikes/my project afterwards.

FILES (only these): docs/ENVIRONMENT.md

ACCEPTANCE:
- RESULT status "ok" from the build in step 2.
- Test-Path "tools\spikes\my project" → False at the end.
________________________________________
•	[ ] T1.28 · Spike: timeout kills the whole process tree · Roadmap 1.21 · (FC)
TASK T1.28 — Spike: kill FreeCAD and all its children on timeout

GOAL: A runaway part script must not leave FreeCAD processes running.

DO EXACTLY:
1. Create tools/spikes/fc_loop.py containing exactly:
   while True:
       pass
2. Change tools/spikes/run_fc.py to use subprocess.Popen instead of subprocess.run. On timeout, kill the whole process tree with:
   subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"], capture_output=True)
   then print "TIMEOUT" and exit 3. Keep all other behaviour from T1.09.
3. Run: uv run python tools/spikes/run_fc.py tools/spikes/fc_loop.py --timeout 5
4. Then run: Get-Process | Where-Object { $_.ProcessName -like "*freecad*" }
5. Record the method under "## Timeouts and killing processes" in docs/ENVIRONMENT.md.

FILES (only these): tools/spikes/fc_loop.py, tools/spikes/run_fc.py, docs/ENVIRONMENT.md

ACCEPTANCE:
- Step 3 prints "TIMEOUT".
- Step 4 prints nothing (no FreeCAD process remains). Close any FreeCAD GUI window you have open before testing.
________________________________________
•	[ ] T1.29 · Complete ENVIRONMENT.md · Roadmap 1.22
TASK T1.29 — Complete the environment document

GOAL: Someone on a clean Windows machine can reproduce this setup by following only this document.

DO EXACTLY:
1. Under "## Operating system": Windows version (from: (Get-CimInstance Win32_OperatingSystem).Caption).
2. Under "## Tools (git, uv, Python)": versions of git, uv, and the pinned Python (run the commands).
3. Add a final section "## Reproduce from scratch" with numbered steps: install git, install uv, clone the repo, uv sync, install FreeCAD, copy aturb.example.toml to aturb.local.toml and set cmd, run uv run pytest -q.
4. Confirm no section still says "Not yet verified." If one does, list it in your report instead of filling it.

FILES (only these): docs/ENVIRONMENT.md

DO NOT: write any value you did not see in a command output.

ACCEPTANCE:
- Select-String -Path docs/ENVIRONMENT.md -Pattern "Not yet verified" → no output, OR your report lists each remaining one.
________________________________________
•	[ ] T1.30 · (You) Clean-machine check (recommended)
Create a second Windows user account, or use a spare laptop, and follow only "Reproduce from scratch". Anything that fails or is unclear, fix in the doc. If you skip this now, note it — it becomes important the day a co-founder joins.
________________________________________
•	[ ] T1.31 · Lint clean · Roadmap 1.23
TASK T1.31 — Make the whole repository pass ruff

GOAL: Zero lint errors across the repository.

DO EXACTLY:
1. Run: uv run ruff check .
2. Fix only what ruff reports, in the reported files. Do not change behaviour.

FILES (only these): only files ruff reports.

ACCEPTANCE:
- uv run ruff check . → All checks passed!
- uv run pytest -q    → all pass
________________________________________
•	[ ] T1.32 · Check the FreeCAD marker split · Roadmap 1.24
TASK T1.32 — Confirm FreeCAD tests are excluded from the CI selection

GOAL: Prove that `-m "not freecad"` runs everything except FreeCAD-marked tests.

DO EXACTLY:
1. Run: uv run pytest -m "not freecad" -q --collect-only
2. Run: uv run pytest -m "freecad" -q --collect-only
3. Report both outputs. No file changes are needed if the split is correct. If any FreeCAD-dependent test is missing its marker, add the marker to that test only.

FILES (only these): only test files missing a freecad marker, if any.

ACCEPTANCE:
- Output 1 lists no test from test_spike_box.py or test_demo_plate.py.
- Output 2 lists both.
________________________________________
•	[ ] T1.33 · File size limit · Roadmap 1.25
TASK T1.33 — File size limit tool

GOAL: Fail fast when any Python file grows past the limit.

DO EXACTLY:
1. Create tools/size_limit.py with:
   - LIMIT = 300  # starting default
   - SCANNED = ["aturb", "packs", "tools", "tests", "clients"]
   - def find_oversized(root: Path, limit: int = LIMIT) -> list[tuple[str, int]]: every .py file under the scanned folders with more than limit lines, as (path relative to root using forward slashes, line count). Missing folders are skipped.
   - When run as a script: scan the repository root (parent of tools/); print each offender as "path: N lines"; exit 1 if any, else print "size_limit: OK" and exit 0.
2. Create tests/test_size_limit.py:
   - a 301-line file in a tmp "aturb" folder is reported
   - a 300-line file is not reported
   - a missing scanned folder does not raise

FILES (only these): tools/size_limit.py, tests/test_size_limit.py

ACCEPTANCE:
- uv run pytest tests/test_size_limit.py -q → 3 passed
- uv run python tools/size_limit.py → size_limit: OK
________________________________________
•	[ ] T1.34 · Continuous integration · Roadmap 1.26
TASK T1.34 — GitHub Actions CI

GOAL: Every push runs lint, non-FreeCAD tests, and the size limit on Windows.

DO EXACTLY:
Create .github/workflows/ci.yml:

name: ci
on: [push, pull_request]
jobs:
  test:
    runs-on: windows-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@vX        # orchestrator fills in the current major version
      - run: uv sync
      - run: uv run ruff check .
      - run: uv run pytest -m "not freecad" -q
      - run: uv run python tools/size_limit.py

Leave "vX" exactly as written and say so in your report. The orchestrator replaces it with the current version.

FILES (only these): .github/workflows/ci.yml

ACCEPTANCE:
- uv run python -c "import yaml; d=yaml.safe_load(open('.github/workflows/ci.yml')); print(len(d['jobs']['test']['steps']))" → 6
________________________________________
•	[ ] T1.35 · (You) Set the action version, push, see CI green
Check the current major version on the astral-sh/setup-uv GitHub page's README, replace vX, commit, push. Open the Actions tab. If it's red, paste the failing step's log into a new agent session with the instruction "fix only what this log reports".
________________________________________
•	[ ] T1.36 · ADR template and ADR-0001 · Roadmap 1.28
TASK T1.36 — ADR template and ADR-0001 (code-first)

GOAL: Record the first locked decision in a standard format.

DO EXACTLY:
1. Create docs/adr/0000-template.md:
   # ADR-NNNN: <title>
   Date: YYYY-MM-DD
   Status: Accepted
   ## Context
   ## Decision
   ## Consequences
2. Create docs/adr/0001-code-first.md from the template, 10 to 20 lines, containing ONLY these points (reword for clarity, add nothing):
   - Context: PieCAD spent about a month on about 20 hand-built tools, an intermediate representation, an MCP layer and a bridge. Public evidence noted in our requirements (Adam's May 2026 post, Zoo's move to a code language, the AgenticCADedit paper, a GUI-agent benchmark on FreeCAD) points toward letting the model write CAD code.
   - Decision: the model writes CAD code in the target CAD's own scripting language. No intermediate language, JSON geometry schema, or tool per CAD operation.
   - Consequences: structure lives in project conventions, independent checks, and the eval set. Burden-of-proof rule: any proposal to add a structured-operations layer must first beat the code path on the eval score, on the same tasks.

FILES (only these): docs/adr/0000-template.md, docs/adr/0001-code-first.md

ACCEPTANCE:
- (Get-Content docs/adr/0001-code-first.md).Count → between 10 and 20
- Select-String -Path docs/adr/0001-code-first.md -Pattern "Burden-of-proof" → one match
________________________________________
•	[ ] T1.37 · ADR-0002 and ADR-0003 · Roadmap 1.28
TASK T1.37 — ADR-0002 (FreeCAD first) and ADR-0003 (two Python environments)

GOAL: Record two more decisions.

DO EXACTLY:
1. docs/adr/0002-freecad-first.md (10 to 20 lines), containing only:
   - Context: users need a native, editable feature tree in their own CAD. Each CAD exposes its own automation interface.
   - Decision: FreeCAD, run headless, is the first backend pack. Quality comes from a measured improvement loop, not a pass/fail exam.
   - Consequences: every future backend is also native, one pack per CAD. Until a pack exists for a user's CAD, they receive STEP.
2. docs/adr/0003-two-pythons.md (10 to 20 lines), containing only:
   - Context: the core needs build123d for neutral measuring; part files must run inside FreeCAD's own embedded Python.
   - Decision: two separate Python environments. The core runs in the uv environment. Part files and the harness run in FreeCAD's Python, launched as a subprocess.
   - Consequences: the core never imports FreeCAD, and FreeCAD-side code never imports the core. They exchange only a request file in and a result file out. This is the physical form of the runner contract.

FILES (only these): docs/adr/0002-freecad-first.md, docs/adr/0003-two-pythons.md

ACCEPTANCE:
- Both files have 10 to 20 lines: (Get-Content <file>).Count
________________________________________
•	[ ] T1.38 · Architecture doc v0 · Roadmap 1.29
TASK T1.38 — docs/ARCHITECTURE.md, version 0

GOAL: One short document describing the system, readable in five minutes.

DO EXACTLY:
Create docs/ARCHITECTURE.md containing:
1. Heading "# Architecture"
2. This diagram exactly, in a code block:

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

3. One paragraph (3 to 5 sentences) per box: Clients, Core service, Runner contract, Backend pack, Neutral measuring. Use only these facts: clients are thin and built later; the core never knows which CAD, language or front end; the runner contract takes a build request and returns a result, and never exposes CAD operations; a backend pack holds everything for one CAD (language, conventions, prompt, runner); checks run on exported STEP so they are the same for every CAD.
4. A section "## Two Python environments" pointing to docs/adr/0003-two-pythons.md in one sentence.

FILES (only these): docs/ARCHITECTURE.md

ACCEPTANCE:
- (Get-Content docs/ARCHITECTURE.md).Count → under 80
________________________________________
•	[ ] T1.39 · Phase 1 cleanup: delete what is unused · Roadmap 1.30
TASK T1.39 — Phase 1 cleanup

GOAL: Remove anything Phase 1 created that nothing uses or documents.

DO EXACTLY:
1. List every file in tools/spikes/ and tools/spikes/parts/.
2. For each, check whether it is referenced in docs/ENVIRONMENT.md, docs/api_notes/, or any test. Show the search command you used.
3. Delete files that are referenced nowhere, EXCEPT: run_fc.py, fc_build.py, fc_hello.py and the parts used by tests.
4. Delete tools/spikes/out/ if it exists (it is gitignored, but remove it anyway).

FILES (only these): deletions inside tools/spikes/ only.

DO NOT: delete anything outside tools/spikes/.

ACCEPTANCE:
- uv run pytest -q      → all pass
- uv run ruff check .   → All checks passed!
- List the deleted files in your report.
________________________________________
PHASE 2 — The runner contract, with the FreeCAD pack as first implementation
Exit criteria: conformance suite passes for the stub pack in CI and for the FreeCAD pack locally; every failure kind is reachable; agnosticism lint green; aturb build works.
Phase rule: the runner runs code and reports what happened. It never exposes CAD operations.
________________________________________
•	[ ] T2.01 · Contract package and version · Roadmap 2.05
TASK T2.01 — Contract package with a version constant

GOAL: Create the contract package and its version number.

DO EXACTLY:
Create aturb/contract/__init__.py containing exactly:
   """Runner contract: the only boundary between the core and any CAD system."""
   CONTRACT_VERSION = "0.1"

FILES (only these): aturb/contract/__init__.py

ACCEPTANCE:
- uv run python -c "from aturb.contract import CONTRACT_VERSION; print(CONTRACT_VERSION)" → 0.1
________________________________________
•	[ ] T2.02 · Failure kinds · Roadmap 2.03
TASK T2.02 — FailureKind enum

GOAL: One fixed list of ways a build can fail.

DO EXACTLY:
Create aturb/contract/types.py containing a class FailureKind(str, Enum) with exactly these eight members (name = value in lowercase):
   REJECTED_UNSAFE = "rejected_unsafe"     # static safety check refused the part file
   SYNTAX_ERROR = "syntax_error"
   RUNTIME_ERROR = "runtime_error"
   TIMEOUT = "timeout"
   INVALID_GEOMETRY = "invalid_geometry"   # built, but the CAD reported failed features
   EXPORT_FAILED = "export_failed"
   RUNNER_CRASH = "runner_crash"           # runner produced no result at all
   INPUT_ERROR = "input_error"             # bad request: part not found, ambiguous, wrong language

Create tests/contract/test_types.py with test_failure_kinds asserting the set of values equals exactly those eight strings.

FILES (only these): aturb/contract/types.py, tests/contract/test_types.py

ACCEPTANCE:
- uv run pytest tests/contract/test_types.py -q → 1 passed
________________________________________
•	[ ] T2.03 · BuildRequest · Roadmap 2.01
TASK T2.03 — BuildRequest dataclass

GOAL: The data the core sends to a runner.

DO EXACTLY:
In aturb/contract/types.py add a frozen dataclass BuildRequest with exactly these fields:
- project_root: str      # absolute path; internal to core and runner only, never shown in events
- part_id: str           # e.g. "plt0001"; the pack resolves this to a file
- language: str          # language tag; must match the pack's info().language
- outputs: tuple[str, ...] = ("native", "step")
- timeout_s: int = 60    # starting default
Add methods to_dict(self) -> dict and classmethod from_dict(cls, d: dict) -> "BuildRequest". outputs must round-trip as a tuple.

Add to tests/contract/test_types.py:
- test_build_request_round_trip: from_dict(to_dict(r)) == r
- test_build_request_json: json.dumps(r.to_dict()) works and json.loads of it passed to from_dict gives r

FILES (only these): aturb/contract/types.py, tests/contract/test_types.py

ACCEPTANCE:
- uv run pytest tests/contract/test_types.py -q → 3 passed
________________________________________
•	[ ] T2.04 · BuildResult · Roadmap 2.02
TASK T2.04 — BuildResult dataclass

GOAL: The data a runner returns to the core.

DO EXACTLY:
In aturb/contract/types.py add a frozen dataclass BuildResult with exactly these fields:
- status: str                              # "ok" or "failed"
- failure_kind: FailureKind | None = None
- error_text: str = ""
- log_path: str = ""                       # relative to project_root, forward slashes
- artifacts: dict[str, str] = field(default_factory=dict)   # keys "native", "step"; values relative paths
- native_diagnostics: dict = field(default_factory=dict)    # informational only; never used for correctness
- duration_ms: int = 0
- contract_version: str = CONTRACT_VERSION
Add __post_init__ validation: status must be "ok" or "failed"; if status is "failed", failure_kind must not be None; if "ok", failure_kind must be None. Raise ValueError otherwise.
Add to_dict and from_dict; failure_kind serializes as its string value or None.

Add tests to tests/contract/test_types.py:
- round trip for an ok result
- round trip for a failed result with failure_kind TIMEOUT
- ValueError for status "failed" with no failure_kind
- ValueError for status "maybe"

FILES (only these): aturb/contract/types.py, tests/contract/test_types.py

ACCEPTANCE:
- uv run pytest tests/contract/test_types.py -q → 7 passed
________________________________________
•	[ ] T2.05 · PackInfo · Roadmap 2.04
TASK T2.05 — PackInfo dataclass

GOAL: How a runner describes itself.

DO EXACTLY:
In aturb/contract/types.py add a frozen dataclass PackInfo with fields: name: str, language: str, version: str. Add to_dict.
Add test_pack_info_to_dict to tests/contract/test_types.py.

FILES (only these): aturb/contract/types.py, tests/contract/test_types.py

ACCEPTANCE:
- uv run pytest tests/contract/test_types.py -q → 8 passed
________________________________________
•	[ ] T2.06 · Atomic JSON file helpers · Roadmap 2.01
TASK T2.06 — JSON read/write helpers

GOAL: Request and result files are written atomically, so a half-written file is never read.

DO EXACTLY:
Create aturb/contract/io.py with:
- def write_json(path: Path, data: dict) -> None — writes to a temp file in the same folder, then os.replace onto path. UTF-8, indent=2.
- def read_json(path: Path) -> dict — reads UTF-8 JSON.
Create tests/contract/test_io.py:
- write then read returns the same dict
- writing over an existing file replaces it
- no leftover temp file remains in the folder after write

FILES (only these): aturb/contract/io.py, tests/contract/test_io.py

ACCEPTANCE:
- uv run pytest tests/contract/test_io.py -q → 3 passed
________________________________________
•	[ ] T2.07 · Runner protocol · Roadmap 2.04
TASK T2.07 — The Runner protocol

GOAL: Define the contract every backend pack implements: exactly two methods.

DO EXACTLY:
Create aturb/contract/runner.py with a typing.Protocol class Runner having exactly two methods:
- def info(self) -> PackInfo: ...
- def build(self, request: BuildRequest) -> BuildResult: ...
Docstring of Runner, exactly: "A runner builds one part from its file and reports what happened. It never exposes CAD operations."
Document in a comment that every runner class is constructed as RunnerClass(settings: dict, pack_dir: Path).

Create tests/contract/test_runner_protocol.py with test_runner_has_two_methods: the public (non-underscore) callables defined on Runner are exactly {"info", "build"}.

FILES (only these): aturb/contract/runner.py, tests/contract/test_runner_protocol.py

ACCEPTANCE:
- uv run pytest tests/contract/test_runner_protocol.py -q → 1 passed
________________________________________
•	[ ] T2.08 · ADR-0004: runner contract · Roadmap 2.05
TASK T2.08 — ADR-0004 runner contract

GOAL: Record the contract decision.

DO EXACTLY:
Create docs/adr/0004-runner-contract.md from the template, 10 to 20 lines, containing only:
- Context: core must work with any CAD; PieCAD's tool layer exposed CAD operations and grew without bound.
- Decision: one boundary. In: BuildRequest (project root, part ID, language tag, outputs, timeout). Out: BuildResult (status, failure kind, error text, log, artifacts, informational diagnostics, duration, contract version). A runner never exposes CAD operations. Runners are constructed with (settings, pack_dir). CONTRACT_VERSION is checked when a pack is loaded.
- Consequences: adding a CAD means writing one runner plus its pack files; core does not change. The contract changes only with a version bump and an ADR.

FILES (only these): docs/adr/0004-runner-contract.md

ACCEPTANCE:
- (Get-Content docs/adr/0004-runner-contract.md).Count → 10 to 20
________________________________________
•	[ ] T2.09 · Pack manifest loader · Roadmap 2.06
TASK T2.09 — pack.toml format and loader

GOAL: Each pack describes itself in a small TOML file that core can read.

DO EXACTLY:
Create aturb/packs.py with:
- class PackError(Exception)
- a frozen dataclass PackManifest with fields: name, language, part_extension, runner, prompt_dir, contract_version (all str), and pack_dir: Path
- REQUIRED_KEYS = {"name", "language", "part_extension", "runner", "prompt_dir", "contract_version"}
- def load_manifest(path: Path) -> PackManifest: reads TOML; raises PackError if any required key is missing or any unknown key is present (message names the key); pack_dir = path.parent.

Create tests/test_packs.py using tmp_path, with a fake pack named "example":
- a valid manifest loads
- a missing key raises PackError naming it
- an unknown key raises PackError naming it

FILES (only these): aturb/packs.py, tests/test_packs.py

DO NOT: import anything from packs/ in aturb/packs.py.

ACCEPTANCE:
- uv run pytest tests/test_packs.py -q → 3 passed
________________________________________
•	[ ] T2.10 · Pack discovery and loading · Roadmap 2.07
TASK T2.10 — Discover packs and load a runner by name

GOAL: Core loads a pack's runner from a "module:Class" string in its manifest. Core has no static import of any pack.

DO EXACTLY:
In aturb/packs.py add:
- def discover(packs_root: Path) -> dict[str, PackManifest]: loads every packs_root/*/pack.toml, keyed by manifest name. Folders whose names start with "_" are skipped. Duplicate names raise PackError.
- def load_runner(name: str, cfg: dict, packs_root: Path):
  1. find the manifest via discover(); unknown name raises PackError listing available names
  2. if manifest.contract_version != aturb.contract.CONTRACT_VERSION, raise PackError naming both versions
  3. split manifest.runner on ":" into module path and class name; import with importlib.import_module
  4. construct the class with settings=aturb.config.pack_settings(cfg, name) and pack_dir=manifest.pack_dir
  5. return the instance
- def default_packs_root() -> Path: the "packs" folder next to the aturb package (parent of the aturb package folder, then "packs").

Add tests to tests/test_packs.py. Build a fake pack inside tmp_path whose runner module is a small file created by the test; add its parent folder to sys.path with monkeypatch.syspath_prepend:
- discover finds it
- folders starting with "_" are skipped
- load_runner returns an instance whose settings equal the config section
- wrong contract_version raises PackError
- unknown pack name raises PackError listing available names

FILES (only these): aturb/packs.py, tests/test_packs.py

ACCEPTANCE:
- uv run pytest tests/test_packs.py -q → 8 passed
________________________________________
•	[ ] T2.11 · Test: no static pack imports in core · Roadmap 2.07
TASK T2.11 — Guard: core never statically imports a pack

GOAL: Fail if anything in aturb/ imports from packs/ directly.

DO EXACTLY:
Create tests/test_core_imports.py with test_core_has_no_pack_imports: parse every .py file under aturb/ with the ast module; fail if any Import or ImportFrom node's module name equals "packs" or starts with "packs.". The failure message lists file and line.

FILES (only these): tests/test_core_imports.py

ACCEPTANCE:
- uv run pytest tests/test_core_imports.py -q → 1 passed
________________________________________
•	[ ] T2.12 · Agnosticism lint · Roadmap 2.08
TASK T2.12 — Agnosticism lint

GOAL: Fail if any CAD brand name or CAD-specific term appears in the core package.

DO EXACTLY:
Create tools/agnostic_lint.py with:
- PATTERN = re.compile(r"\b(freecad|fcstd|partdesign|sketcher|solidworks|onshape|fusion|featurescript|catia)\b", re.IGNORECASE)
- def scan(core_dir: Path) -> list[tuple[str, int, str]]: every match in every .py file under core_dir, as (relative path with forward slashes, line number, line text stripped).
- When run as a script: scan the aturb/ folder at the repository root; print each finding as "path:line: text"; exit 1 if any, else print "agnostic_lint: OK" and exit 0.

Create tests/test_agnostic_lint.py:
- a tmp file containing "import FreeCAD" is found
- a tmp file containing "confusion" is NOT found (word boundary)
- a clean tmp file gives no findings

FILES (only these): tools/agnostic_lint.py, tests/test_agnostic_lint.py

ACCEPTANCE:
- uv run pytest tests/test_agnostic_lint.py -q → 3 passed
- uv run python tools/agnostic_lint.py → agnostic_lint: OK
________________________________________
•	[ ] T2.13 · Add the agnosticism lint to CI · Roadmap 2.09
TASK T2.13 — Add agnostic_lint to CI

GOAL: Every push checks that the core stays CAD-neutral.

DO EXACTLY:
In .github/workflows/ci.yml, append one step after the size limit step:
      - run: uv run python tools/agnostic_lint.py

FILES (only these): .github/workflows/ci.yml

ACCEPTANCE:
- uv run python -c "import yaml; d=yaml.safe_load(open('.github/workflows/ci.yml')); print(d['jobs']['test']['steps'][-1])"
  → {'run': 'uv run python tools/agnostic_lint.py'}
________________________________________
•	[ ] T2.14 · Fixture STEP for tests · Roadmap 2.10
TASK T2.14 — A STEP fixture generated with build123d

GOAL: A committed STEP file so tests (including the stub pack) can measure real geometry without FreeCAD.

DO EXACTLY:
1. First verify, and add to docs/api_notes/build123d.md, the calls for: a cylinder, positioning a solid at (x, y, z), and subtracting one solid from another. Show the verification output.
2. Create tests/fixtures/make_fixtures.py with def make_plate_2holes(path: Path) -> None that builds a 120 x 60 x 5 plate with two through-holes of diameter 10 at X = -40 and X = +40, Y = 0, and exports it to STEP at path. Use only calls in docs/api_notes/build123d.md. When run as a script, it writes tests/fixtures/plate_2holes.step.
3. Run it to create tests/fixtures/plate_2holes.step.
4. Create tests/test_fixtures.py with test_plate_fixture: regenerate into tmp_path; import both the committed file and the regenerated one; assert both volumes equal 35214.602 within 0.01 (hand calculation in a comment, same as T1.21).

FILES (only these): docs/api_notes/build123d.md, tests/fixtures/make_fixtures.py, tests/fixtures/plate_2holes.step, tests/test_fixtures.py

ACCEPTANCE:
- uv run pytest tests/test_fixtures.py -q → 1 passed
- git check-attr -a -- tests/fixtures/plate_2holes.step → includes "binary: set"
________________________________________
•	[ ] T2.15 · Folder jail · Roadmap 2.26
TASK T2.15 — Keep every path inside the project

GOAL: No part file or artifact path may point outside its project folder.

DO EXACTLY:
Create aturb/workspace/__init__.py (empty docstring) and aturb/workspace/paths.py with:
- class PathEscapeError(Exception)
- def resolve_inside(root: Path, rel: str | Path) -> Path: returns (root / rel).resolve() if it is inside root.resolve(); otherwise raises PathEscapeError. An absolute rel that is outside root also raises.
- def to_rel(root: Path, path: Path) -> str: path relative to root, with forward slashes; raises PathEscapeError if outside.

Create tests/test_paths.py:
- "parts/a.py" resolves inside
- "../outside.py" raises
- an absolute path outside root raises
- to_rel returns forward slashes on Windows
- to_rel of an outside path raises

FILES (only these): aturb/workspace/__init__.py, aturb/workspace/paths.py, tests/test_paths.py

ACCEPTANCE:
- uv run pytest tests/test_paths.py -q → 5 passed
________________________________________
•	[ ] T2.16 · Stub pack manifest · Roadmap 2.11
TASK T2.16 — Stub pack manifest

GOAL: Describe the stub pack.

DO EXACTLY:
Create packs/stub/pack.toml containing exactly:
name = "stub"
language = "stub-text"
part_extension = ".stub"
runner = "packs.stub.runner:StubRunner"
prompt_dir = "prompt"
contract_version = "0.1"

Create packs/stub/prompt/README.md containing one line: Prompt files for the stub pack (none needed).

FILES (only these): packs/stub/pack.toml, packs/stub/prompt/README.md

ACCEPTANCE:
- uv run python -c "from pathlib import Path; from aturb.packs import load_manifest; print(load_manifest(Path('packs/stub/pack.toml')).name)" → stub
________________________________________
•	[ ] T2.17 · Stub runner: success path · Roadmap 2.11
TASK T2.17 — Stub runner, success path

GOAL: A runner that is not a CAD at all. It "builds" by copying the fixture STEP. This proves core never needs a real CAD.

DO EXACTLY:
Create packs/stub/runner.py with class StubRunner:
- __init__(self, settings: dict, pack_dir: Path)
- info() -> PackInfo(name="stub", language="stub-text", version="0.1")
- build(request) -> BuildResult:
  1. if request.language != "stub-text": failed, INPUT_ERROR, error_text names both languages
  2. find exactly one file matching parts/<part_id>_*.stub or parts/<part_id>.stub under project_root; none or more than one → failed, INPUT_ERROR with a clear message
  3. out_dir = project_root/out/<part_id>; create it
  4. copy tests/fixtures/plate_2holes.step (located relative to the repository: pack_dir.parent.parent / "tests" / "fixtures" / "plate_2holes.step") to out_dir/<part_id>.step
  5. write out_dir/<part_id>.stubnative containing the text "stub native file"
  6. write out_dir/build.log containing "stub build ok"
  7. return ok with artifacts {"native": rel path, "step": rel path} and log_path, all relative via aturb.workspace.paths.to_rel, and duration_ms measured with time.perf_counter.

Create tests/packs/test_stub_runner.py using a tmp project containing parts/plt0001_base_plate.stub:
- ok build returns both artifacts and they exist
- wrong language → INPUT_ERROR
- missing part → INPUT_ERROR
- two matching part files → INPUT_ERROR

FILES (only these): packs/stub/runner.py, tests/packs/test_stub_runner.py

ACCEPTANCE:
- uv run pytest tests/packs/test_stub_runner.py -q → 4 passed
________________________________________
•	[ ] T2.18 · Stub runner: scripted failures · Roadmap 10.02 (brought forward)
TASK T2.18 — Stub runner, scripted failure scenarios

GOAL: Let tests make the stub fail in any chosen way, so every failure path in core can be tested without a CAD.

DO EXACTLY:
In packs/stub/runner.py: after finding the part file, read its first line. If it is exactly "# STUB: fail=<kind>" where <kind> is a FailureKind value, return a failed result with that failure_kind and error_text "scripted failure: <kind>" (no artifacts). Otherwise continue with the success path.

Add a parametrized test to tests/packs/test_stub_runner.py covering every FailureKind value except INPUT_ERROR.

FILES (only these): packs/stub/runner.py, tests/packs/test_stub_runner.py

ACCEPTANCE:
- uv run pytest tests/packs/test_stub_runner.py -q → 11 passed
________________________________________
•	[ ] T2.19 · Contract conformance suite · Roadmap 2.12
TASK T2.19 — Conformance tests every pack must pass

GOAL: One test suite that checks any runner obeys the contract.

DO EXACTLY:
1. Create tests/fixtures/conformance/stub/parts/plt0001_base_plate.stub containing one line: stub part file
2. Create tests/contract/test_conformance.py:
   - PACKS = ["stub"] plus any names listed (comma-separated) in env var ATURB_CONFORMANCE_PACKS
   - a fixture that, for a pack name, copies its conformance project into tmp_path:
       stub    → tests/fixtures/conformance/stub
       freecad → projects/demo   (added in T2.39; skip with a clear reason until then)
     and loads the runner with aturb.packs.load_runner(name, cfg, default_packs_root()) where cfg is {"packs": {}} plus, for freecad only, the real settings from aturb.local.toml at the repository root.
   - apply pytest.mark.freecad automatically to parameters whose pack is "freecad"
   - tests, parametrized over PACKS:
     a. info() returns non-empty name, language, version
     b. build of plt0001 returns status "ok"
     c. both artifacts exist and resolve inside the project (use resolve_inside)
     d. BuildResult.from_dict(result.to_dict()) == result
     e. duration_ms >= 0 and contract_version equals CONTRACT_VERSION
     f. a request with the wrong language returns INPUT_ERROR
     g. a request for part "zzz9999" returns INPUT_ERROR

FILES (only these): tests/fixtures/conformance/stub/parts/plt0001_base_plate.stub, tests/contract/test_conformance.py

ACCEPTANCE:
- uv run pytest tests/contract/test_conformance.py -q → 7 passed (stub only)
________________________________________
•	[ ] T2.20 · FreeCAD pack manifest · Roadmap 2.13
TASK T2.20 — FreeCAD pack manifest

GOAL: Describe the FreeCAD pack.

DO EXACTLY:
Create packs/freecad/pack.toml containing exactly:
name = "freecad"
language = "python-freecad"
part_extension = ".py"
runner = "packs.freecad.runner:FreeCADRunner"
prompt_dir = "prompt"
contract_version = "0.1"

Create packs/freecad/prompt/README.md containing one line: Prompt files for the CAD agent using this pack (filled in Phase 5 and 6).

FILES (only these): packs/freecad/pack.toml, packs/freecad/prompt/README.md

ACCEPTANCE:
- uv run python -c "from aturb.packs import discover, default_packs_root; print(sorted(discover(default_packs_root())))" → ['freecad', 'stub']
________________________________________
•	[ ] T2.21 · FreeCAD runner skeleton · Roadmap 2.13
TASK T2.21 — FreeCAD runner skeleton (no build yet)

GOAL: A loadable runner class, so registry tests pass before the build logic exists. Loading must NOT require FreeCAD.

DO EXACTLY:
Create packs/freecad/runner.py with class FreeCADRunner:
- __init__(self, settings: dict, pack_dir: Path): store both; do NOT check that FreeCAD exists here.
- info() -> PackInfo(name="freecad", language="python-freecad", version="0.1")
- build(request) -> raise NotImplementedError("added in T2.29 onward")

Add tests/packs/test_fc_runner_load.py (NOT freecad-marked): load_runner("freecad", {"packs": {"freecad": {"cmd": "unused"}}}, default_packs_root()) returns an object whose info().name is "freecad".

FILES (only these): packs/freecad/runner.py, tests/packs/test_fc_runner_load.py

ACCEPTANCE:
- uv run pytest tests/packs/test_fc_runner_load.py -q → 1 passed
________________________________________
•	[ ] T2.22 · Harness: job file and result skeleton · Roadmap 2.14 · (FC for manual check)
TASK T2.22 — Harness skeleton: read the job, always write a result

GOAL: The script that runs INSIDE FreeCAD. This first version reads its job and always writes a result file, even if everything inside fails.

CONTEXT: The harness runs in FreeCAD's own Python. It must import only the standard library and FreeCAD modules. It must never import aturb.

The job file (written by the runner) is JSON with exactly these keys:
  job_version (int, 1), part_id (str), part_file (absolute str), project_root (absolute str), out_dir (absolute str), outputs (list of "native"/"step"), result_path (absolute str)

The result file (written by the harness) is JSON with exactly these keys:
  status ("ok"/"failed"), failure_kind (str or null), error_text (str), native_diagnostics (dict), artifacts (dict of name -> absolute str)

DO EXACTLY:
Create packs/freecad/harness/build_part.py:
1. def main(): read the job path from os.environ["ATURB_REQUEST"], load the job JSON.
2. Start a result dict: status "failed", failure_kind "runtime_error", error_text "", native_diagnostics {}, artifacts {}.
3. In a try block: for now, only set status "ok" and failure_kind None. (Later tasks add the real work here.)
4. In except: set error_text to traceback.format_exc().
5. In finally: write the result dict to job["result_path"] as UTF-8 JSON.
6. Call main() at module level (FreeCAD runs the file directly).

Create tests/packs/test_harness_isolation.py (not freecad-marked): parse packs/freecad/harness/build_part.py with ast and assert no import of any module named "aturb" or starting with "aturb.".

FILES (only these): packs/freecad/harness/build_part.py, tests/packs/test_harness_isolation.py

ACCEPTANCE:
- uv run pytest tests/packs/test_harness_isolation.py -q → 1 passed
________________________________________
•	[ ] T2.23 · Harness: load the part and call build() · Roadmap 2.14 · (FC)
TASK T2.23 — Harness: load the part file and build it

GOAL: Create a fresh document, load the part file by path, call build(doc), and keep the returned object.

DO EXACTLY:
In packs/freecad/harness/build_part.py, inside the try block (use only calls recorded in docs/api_notes/freecad.md):
1. doc = App.newDocument(job["part_id"])
2. load the part file with importlib.util.spec_from_file_location("aturb_part", job["part_file"]) and exec_module
3. obj = module.build(doc). If obj is None, raise RuntimeError("build(doc) must return the final object")
4. doc.recompute()
5. In finally (before writing the result): if doc was created, App.closeDocument(doc.Name)

Test manually: write a job JSON by hand in tools/spikes/ for projects/demo plt0001 (absolute paths), then run:
  uv run python tools/spikes/run_fc.py packs/freecad/harness/build_part.py --env ATURB_REQUEST=<path to that job json>
and show the result file content.

FILES (only these): packs/freecad/harness/build_part.py, tools/spikes/job_demo.json

ACCEPTANCE:
- The result file shows status "ok".
- uv run pytest tests/packs/test_harness_isolation.py -q → 1 passed
________________________________________
•	[ ] T2.24 · Harness: detect failed features · Roadmap 2.15 · (FC)
TASK T2.24 — Harness: report failed features as invalid geometry

GOAL: If FreeCAD reports failed features after recompute, the result says invalid_geometry and names them.

DO EXACTLY:
In packs/freecad/harness/build_part.py after doc.recompute():
1. Collect names of objects whose State shows failure, using EXACTLY the State value recorded in docs/api_notes/freecad.md by task T1.23. Do not guess another value.
2. Store the list in native_diagnostics["failed_features"].
3. If the list is non-empty: status "failed", failure_kind "invalid_geometry", error_text "failed features: " + comma-separated names; skip saving and exporting.
4. Also store native_diagnostics["cad_version"] as the string form of App.Version().

Test manually with tools/spikes/parts/broken_part.py (adjust the job file's part_file).

FILES (only these): packs/freecad/harness/build_part.py, tools/spikes/job_demo.json

ACCEPTANCE:
- broken_part job → result status "failed", failure_kind "invalid_geometry", failed_features non-empty.
- demo job → status "ok", failed_features empty.
________________________________________
•	[ ] T2.25 · Harness: save the native file · Roadmap 2.16 · (FC)
TASK T2.25 — Harness: save the native file

GOAL: Save the built document as the native file.

DO EXACTLY:
In packs/freecad/harness/build_part.py, when status is still ok and "native" is in job["outputs"]:
1. create job["out_dir"] if missing
2. save with doc.saveAs to <out_dir>/<part_id>.FCStd
3. set artifacts["native"] to that absolute path

FILES (only these): packs/freecad/harness/build_part.py

ACCEPTANCE:
- demo job → result artifacts include "native"; Test-Path on that path → True
________________________________________
•	[ ] T2.26 · Harness: export STEP · Roadmap 2.17 · (FC)
TASK T2.26 — Harness: export STEP

GOAL: Export the returned object's shape to STEP; a failed export is reported as export_failed.

DO EXACTLY:
In packs/freecad/harness/build_part.py, when status is still ok and "step" is in job["outputs"]:
1. export obj.Shape to <out_dir>/<part_id>.step using the method recorded in docs/api_notes/freecad.md (T1.17)
2. if exporting raises, or the file does not exist or is empty afterwards: status "failed", failure_kind "export_failed", error_text describes which
3. otherwise set artifacts["step"] to the absolute path

FILES (only these): packs/freecad/harness/build_part.py

ACCEPTANCE:
- demo job → artifacts include "step"; the file size is greater than 0.
________________________________________
•	[ ] T2.27 · Harness: classify syntax and runtime errors · Roadmap 2.19 · (FC)
TASK T2.27 — Harness: distinguish syntax errors from runtime errors

GOAL: A syntax error in a part file is reported as syntax_error; any other exception as runtime_error. Both include the traceback.

DO EXACTLY:
In packs/freecad/harness/build_part.py:
1. Wrap the module loading (exec_module) separately: a SyntaxError there sets failure_kind "syntax_error".
2. Any other exception anywhere in the try block sets failure_kind "runtime_error".
3. Both set error_text to traceback.format_exc().

Create tests/packs/fc_planted/syntax_err.py containing: def build(doc) return 1
Create tests/packs/fc_planted/runtime_err.py containing a build(doc) that raises ValueError("planted").
Test both manually with the job file.

FILES (only these): packs/freecad/harness/build_part.py, tests/packs/fc_planted/syntax_err.py, tests/packs/fc_planted/runtime_err.py, tools/spikes/job_demo.json

ACCEPTANCE:
- syntax_err job → failure_kind "syntax_error"
- runtime_err job → failure_kind "runtime_error", error_text contains "planted"
________________________________________
•	[ ] T2.28 · Harness size and isolation check · Roadmap 2.14
TASK T2.28 — Check the harness stays small and isolated

GOAL: Confirm the harness meets the limits before the runner is built on top of it.

DO EXACTLY:
1. Run: uv run python tools/size_limit.py
2. Run: uv run pytest tests/packs/test_harness_isolation.py -q
3. Run: uv run ruff check packs/freecad/harness/build_part.py
4. If the harness is over 150 lines, report it; do not shorten it yourself.

FILES (only these): none, unless ruff reports a fix in the harness file.

ACCEPTANCE:
- all three commands pass; report the harness line count: (Get-Content packs/freecad/harness/build_part.py).Count
________________________________________
•	[ ] T2.29 · Runner: minimal child environment · Roadmap 2.23
TASK T2.29 — Runner: pass only a minimal environment to FreeCAD

GOAL: API keys, tokens, and proxy settings never reach the part's process.

DO EXACTLY:
In packs/freecad/runner.py add a pure function:
  ALLOWED_ENV = {"SYSTEMROOT", "SYSTEMDRIVE", "WINDIR", "TEMP", "TMP", "PATH", "PATHEXT",
                 "USERPROFILE", "APPDATA", "LOCALAPPDATA", "HOMEDRIVE", "HOMEPATH",
                 "COMPUTERNAME", "PROCESSOR_ARCHITECTURE", "NUMBER_OF_PROCESSORS"}
  def child_env(base: Mapping[str, str], job_path: Path) -> dict[str, str]:
      keys from base whose UPPERCASE name is in ALLOWED_ENV, plus ATURB_REQUEST = str(job_path).

Create tests/packs/test_fc_env.py (not freecad-marked): base contains PATH, OPENAI_API_KEY, HTTPS_PROXY, MY_TOKEN, SECRET_X; assert the result contains PATH and ATURB_REQUEST and none of the other four.

FILES (only these): packs/freecad/runner.py, tests/packs/test_fc_env.py

ACCEPTANCE:
- uv run pytest tests/packs/test_fc_env.py -q → 1 passed
________________________________________
•	[ ] T2.30 · Runner: resolve the part file · Roadmap 2.20
TASK T2.30 — Runner: find the part file for a part ID

GOAL: The runner turns a part ID into exactly one file, or a clear input error.

DO EXACTLY:
In packs/freecad/runner.py add:
  def find_part_file(project_root: Path, part_id: str) -> Path | str
  Returns the single match of parts/<part_id>_*.py or parts/<part_id>.py, resolved with aturb.workspace.paths.resolve_inside. If none match, returns the string "no part file for <part_id>". If more than one, returns "ambiguous part id <part_id>: <names>".

Add tests to tests/packs/test_fc_runner_load.py (not freecad-marked) using tmp_path: one match, no match, two matches.

FILES (only these): packs/freecad/runner.py, tests/packs/test_fc_runner_load.py

ACCEPTANCE:
- uv run pytest tests/packs/test_fc_runner_load.py -q → 4 passed
________________________________________
•	[ ] T2.31 · Runner: launch FreeCAD · Roadmap 2.20 · (FC)
TASK T2.31 — Runner: write the job, launch FreeCAD, read the result

GOAL: FreeCADRunner.build() works end to end for a good part.

DO EXACTLY:
Replace build() in packs/freecad/runner.py:
1. if request.language != "python-freecad": return failed INPUT_ERROR naming both languages
2. project_root = Path(request.project_root); resolve the part with find_part_file; a string result → failed INPUT_ERROR with that message
3. out_dir = resolve_inside(project_root, f"out/{request.part_id}"); if it exists, delete its contents (only inside out_dir); create it
4. write the job JSON (keys exactly as in T2.22) to out_dir/job.json using aturb.contract.io.write_json; result_path = out_dir/result.json
5. cmd = self.settings.get("cmd"); if empty → failed RUNNER_CRASH with error_text "packs.freecad.cmd is not configured"
6. run [cmd, <pack_dir>/harness/build_part.py] with subprocess.Popen: cwd = project_root, env = child_env(os.environ, job path), stdout and stderr both written to out_dir/build.log
7. wait up to request.timeout_s (timeout handling comes in T2.32; for now a plain wait)
8. read result.json with read_json; convert absolute artifact paths to project-relative with to_rel
9. return BuildResult with status, failure_kind (FailureKind or None), error_text, log_path, artifacts, native_diagnostics, duration_ms (time.perf_counter)

FILES (only these): packs/freecad/runner.py

ACCEPTANCE (FC):
- uv run python -c "<6 lines: load config from aturb.local.toml, load_runner('freecad', ...), build BuildRequest(project_root=str(Path('projects/demo').resolve()), part_id='plt0001', language='python-freecad'), print result.status, result.artifacts>"
  → ok {'native': 'out/plt0001/plt0001.FCStd', 'step': 'out/plt0001/plt0001.step'}
________________________________________
•	[ ] T2.32 · Runner: timeout and process-tree kill · Roadmap 2.21 · (FC)
TASK T2.32 — Runner: enforce the timeout

GOAL: A runaway part is killed with all its child processes and reported as timeout.

DO EXACTLY:
In packs/freecad/runner.py: wrap the wait with request.timeout_s. On subprocess.TimeoutExpired, run
  subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"], capture_output=True)
then also call proc.kill() inside a try (for non-Windows), wait for exit, and return failed TIMEOUT with error_text "build exceeded <N> s". Use the method recorded in docs/ENVIRONMENT.md "## Timeouts and killing processes".

Create tests/packs/fc_planted/infinite_loop.py: a build(doc) containing while True: pass.

FILES (only these): packs/freecad/runner.py, tests/packs/fc_planted/infinite_loop.py

ACCEPTANCE (FC):
- building infinite_loop with timeout_s=5 (copy it into a tmp project as parts/zzz0001_loop.py) returns TIMEOUT.
- Get-Process | Where-Object { $_.ProcessName -like "*freecad*" } → nothing.
________________________________________
•	[ ] T2.33 · Runner: missing result means crash · Roadmap 2.22 · (FC)
TASK T2.33 — Runner: no result file means runner_crash

GOAL: If the harness never writes its result, the runner reports runner_crash with the end of the log.

DO EXACTLY:
In packs/freecad/runner.py, after the process exits: if result.json does not exist, return failed RUNNER_CRASH with error_text = "no result file; last log lines:\n" + the last 20 lines of build.log  # 20 is a starting default.

Test by temporarily pointing the runner at tools/spikes/fc_hello.py as the harness inside a test-only subclass in tests/packs/test_fc_crash.py (freecad-marked) that overrides the harness path. Do not change the real harness path.

FILES (only these): packs/freecad/runner.py, tests/packs/test_fc_crash.py

ACCEPTANCE:
- uv run pytest tests/packs/test_fc_crash.py -q → 1 passed
________________________________________
•	[ ] T2.34 · Part-file precheck: rules · Roadmap 2.24
TASK T2.34 — Static safety check for part files

GOAL: Reject obviously unsafe part files before FreeCAD is ever launched.

DO EXACTLY:
Create packs/freecad/precheck.py with:
  ALLOWED_IMPORTS = {"FreeCAD", "Part", "PartDesign", "Sketcher", "math"}
  BANNED_CALLS = {"open", "exec", "eval", "compile", "__import__", "input", "globals",
                  "locals", "vars", "getattr", "setattr", "delattr", "breakpoint"}
  def precheck(source: str) -> tuple[str, list[str]]:
      Returns ("ok", []) or ("syntax_error", [message]) or ("rejected_unsafe", [reasons]).
      1. ast.parse; SyntaxError → ("syntax_error", [str(e)])
      2. walk the tree and collect a reason (with line number) for:
         - any import whose top-level module is not in ALLOWED_IMPORTS
         - any call to a name in BANNED_CALLS
         - any attribute access whose name starts and ends with "__"
      3. reasons found → ("rejected_unsafe", reasons); otherwise ("ok", [])

FILES (only these): packs/freecad/precheck.py

ACCEPTANCE:
- uv run python -c "from packs.freecad.precheck import precheck; print(precheck(open('projects/demo/parts/plt0001_base_plate.py', encoding='utf-8').read()))" → ('ok', [])
________________________________________
•	[ ] T2.35 · Precheck tests · Roadmap 2.25
TASK T2.35 — Tests for the precheck

GOAL: Prove the precheck rejects every planted unsafe pattern and accepts the demo.

DO EXACTLY:
Create tests/packs/test_fc_precheck.py with a parametrized test over exactly these ten sources, each expecting "rejected_unsafe":
  1. "import os"
  2. "import subprocess"
  3. "from socket import socket"
  4. "import urllib.request"
  5. "open('x.txt', 'w')"
  6. "eval('1+1')"
  7. "exec('x=1')"
  8. "__import__('os')"
  9. "().__class__.__bases__[0].__subclasses__()"
 10. "import FreeCAD\ngetattr(FreeCAD, 'ActiveDocument')"
Plus:
- the demo part file → "ok"
- "def build(doc) return 1" → "syntax_error"
- "import math\nimport FreeCAD as App\nfrom Part import LineSegment" → "ok"

FILES (only these): tests/packs/test_fc_precheck.py

ACCEPTANCE:
- uv run pytest tests/packs/test_fc_precheck.py -q → 13 passed
________________________________________
•	[ ] T2.36 · Runner calls the precheck first · Roadmap 2.24
TASK T2.36 — Runner: precheck before launching FreeCAD

GOAL: Unsafe or syntactically broken part files never reach FreeCAD.

DO EXACTLY:
In packs/freecad/runner.py build(), immediately after resolving the part file and before touching out_dir:
1. read the part file as UTF-8 and call precheck
2. "syntax_error" → return failed SYNTAX_ERROR with the message
3. "rejected_unsafe" → return failed REJECTED_UNSAFE with error_text = the reasons joined by newlines

Add a NON-freecad test to tests/packs/test_fc_runner_load.py: a tmp project whose part file contains "import os" built with settings {"cmd": "does-not-exist"} returns REJECTED_UNSAFE (proving FreeCAD was never launched).

FILES (only these): packs/freecad/runner.py, tests/packs/test_fc_runner_load.py

ACCEPTANCE:
- uv run pytest tests/packs/test_fc_runner_load.py -q → 5 passed
________________________________________
•	[ ] T2.37 · Runner: artifacts must stay inside the project · Roadmap 2.26
TASK T2.37 — Runner: verify every artifact path is inside the project

GOAL: A result pointing outside the project is treated as a crash, never trusted.

DO EXACTLY:
In packs/freecad/runner.py, when converting artifact paths from result.json: if to_rel raises PathEscapeError for any artifact, return failed RUNNER_CRASH with error_text naming the artifact key.

Add a NON-freecad unit test for the conversion: make the path-conversion step a small function convert_artifacts(project_root: Path, artifacts: dict) -> dict | str and test it with one inside and one outside path in tests/packs/test_fc_runner_load.py.

FILES (only these): packs/freecad/runner.py, tests/packs/test_fc_runner_load.py

ACCEPTANCE:
- uv run pytest tests/packs/test_fc_runner_load.py -q → 7 passed
________________________________________
•	[ ] T2.38 · Planted failures, end to end · Roadmap 2.28 · (FC)
TASK T2.38 — Every failure kind reachable through the real FreeCAD runner

GOAL: Prove each failure path works end to end.

DO EXACTLY:
1. Create tests/packs/fc_planted/invalid_geom.py: copy tools/spikes/parts/broken_part.py (empty-sketch pad).
2. Create tests/packs/fc_planted/unsafe_import.py: a valid build(doc) plus "import os" at the top.
3. Create tests/packs/test_fc_planted.py, freecad-marked, parametrized over:
   syntax_err.py → SYNTAX_ERROR; runtime_err.py → RUNTIME_ERROR; infinite_loop.py (timeout_s=5) → TIMEOUT;
   invalid_geom.py → INVALID_GEOMETRY; unsafe_import.py → REJECTED_UNSAFE.
   For each: copy the file into a tmp project as parts/zzz0001_planted.py and build part "zzz0001".

FILES (only these): tests/packs/fc_planted/invalid_geom.py, tests/packs/fc_planted/unsafe_import.py, tests/packs/test_fc_planted.py

ACCEPTANCE:
- uv run pytest tests/packs/test_fc_planted.py -q → 5 passed
________________________________________
•	[ ] T2.39 · Conformance suite against FreeCAD · Roadmap 2.27 · (FC)
TASK T2.39 — Run the conformance suite against the FreeCAD pack

GOAL: The real pack obeys the same contract as the stub.

DO EXACTLY:
1. In tests/contract/test_conformance.py, remove the skip for "freecad" added in T2.19 so it copies projects/demo into tmp_path.
2. Run: $env:ATURB_CONFORMANCE_PACKS="freecad"; uv run pytest tests/contract/test_conformance.py -q
3. If a test fails, fix the runner, not the test. Report exactly what you changed.

FILES (only these): tests/contract/test_conformance.py, packs/freecad/runner.py (only if a test fails)

ACCEPTANCE:
- with ATURB_CONFORMANCE_PACKS=freecad → 14 passed (7 stub + 7 freecad)
- without it → 7 passed
________________________________________
•	[ ] T2.40 · CLI: aturb build · Roadmap 2.30
TASK T2.40 — Command line: aturb build

GOAL: Build any part from the terminal through whichever pack is active.

DO EXACTLY:
Create aturb/cli.py with def main(argv: list[str] | None = None) -> int using argparse with one subcommand:
  aturb build <project_dir> <part_id> [--config PATH]
1. load_config(Path(args.config) if given else None)
2. name = active_pack(cfg); runner = load_runner(name, cfg, default_packs_root())
3. build BuildRequest(project_root=str(Path(project_dir).resolve()), part_id, language=runner.info().language, timeout_s=timeout_s(cfg))
4. print one line:
   ok:     "ok <part_id> <duration_ms>ms step=<artifacts['step']>"
   failed: "failed <part_id> <failure_kind>: <first line of error_text>"
5. return 0 for ok, 1 for failed; ConfigError or PackError → print the message, return 2

Create tests/test_cli.py using a tmp config with active_pack = "stub" and a tmp copy of tests/fixtures/conformance/stub:
- ok build prints a line starting "ok plt0001" and returns 0
- a scripted failure part ("# STUB: fail=timeout") prints "failed plt0001 timeout" and returns 1
- a missing config returns 2

FILES (only these): aturb/cli.py, tests/test_cli.py

ACCEPTANCE:
- uv run pytest tests/test_cli.py -q → 3 passed
- uv run python tools/agnostic_lint.py → agnostic_lint: OK
- (FC) uv run aturb build projects/demo plt0001 → a line starting "ok plt0001"
________________________________________
•	[ ] T2.41 · SECURITY.md · Roadmap 2.25
TASK T2.41 — Document what isolation does and does not guarantee

GOAL: An honest statement of the current safety limits.

DO EXACTLY:
Create docs/SECURITY.md (under 40 lines) with these sections and only these facts:
## What is in place
- Part files pass a static check before running: an import allowlist, banned built-in calls, no dunder attribute access (packs/freecad/precheck.py).
- Builds run in a separate process with a minimal environment: no API keys, tokens or proxy settings are passed.
- A build is killed, with its child processes, after a timeout.
- Every part path and artifact path must stay inside the project folder.
## What is NOT guaranteed
- The static check can be bypassed by sufficiently creative code. It is a first filter, not a sandbox.
- There is no operating-system-level network block or filesystem jail yet.
## Planned
- Run builds inside a container (or an equivalent OS sandbox) before any untrusted user can submit requests.

FILES (only these): docs/SECURITY.md

ACCEPTANCE:
- (Get-Content docs/SECURITY.md).Count → under 40
________________________________________
•	[ ] T2.42 · ADR-0005: checks run on STEP · Roadmap 2.31
TASK T2.42 — ADR-0005 correctness is judged from STEP

GOAL: Record why native diagnostics never decide correctness.

DO EXACTLY:
Create docs/adr/0005-checks-on-step.md, 10 to 20 lines, containing only:
- Context: each CAD reports errors differently; the agent must never certify its own work (v2 P3).
- Decision: correctness is judged only from facts measured on the exported STEP with one neutral library. BuildResult.native_diagnostics are informational and shown to the agent as hints, never used to pass or fail a check.
- Consequences: the same checks apply to every backend. A backend that cannot export STEP cannot pass checks.

FILES (only these): docs/adr/0005-checks-on-step.md

ACCEPTANCE:
- (Get-Content docs/adr/0005-checks-on-step.md).Count → 10 to 20
________________________________________
•	[ ] T2.43 · Architecture doc: contract section · Roadmap 2.32
TASK T2.43 — Update ARCHITECTURE.md with the contract as built

GOAL: The architecture document matches the code.

DO EXACTLY:
Add a section "## Runner contract as built" to docs/ARCHITECTURE.md (under 25 lines) covering only:
- the two methods (info, build) and the constructor (settings, pack_dir)
- where the types live (aturb/contract/types.py) and the eight failure kinds, in one line
- how a pack is found (packs/<name>/pack.toml, runner = "module:Class", contract_version checked)
- the FreeCAD pack's mechanism: precheck → job.json → FreeCAD subprocess running harness/build_part.py → result.json → artifacts made relative
- the stub pack copies a fixture STEP and exists to prove the core never needs a CAD

FILES (only these): docs/ARCHITECTURE.md

ACCEPTANCE:
- (Get-Content docs/ARCHITECTURE.md).Count → under 110
________________________________________
•	[ ] T2.44 · Phase 2 cleanup: delete what is unused · Roadmap 2.33
TASK T2.44 — Phase 2 cleanup

GOAL: Remove what Phase 2 made obsolete, and move tests onto the real runner.

DO EXACTLY:
1. Change tests/test_demo_plate.py and tests/test_spike_box.py to build through the real FreeCAD runner (load_runner + BuildRequest) instead of tests/fc_utils.run_spike_build. For the box test, copy tools/spikes/parts/box_part.py into a tmp project as parts/box0001_box.py.
2. If nothing else uses tests/fc_utils.py, delete it.
3. Delete tools/spikes/job_demo.json.
4. Search for unused functions in aturb/contract/ and aturb/packs.py (defined but never called outside their own tests). List them in your report. Do NOT delete them — the orchestrator decides.
5. Keep tools/spikes/run_fc.py and fc_build.py (still referenced in docs/ENVIRONMENT.md).

FILES (only these): tests/test_demo_plate.py, tests/test_spike_box.py, tests/fc_utils.py (delete), tools/spikes/job_demo.json (delete)

ACCEPTANCE:
- uv run pytest -q                       → all pass (FreeCAD machine)
- uv run pytest -m "not freecad" -q      → all pass
- uv run ruff check .                    → All checks passed!
- uv run python tools/size_limit.py      → size_limit: OK
- uv run python tools/agnostic_lint.py   → agnostic_lint: OK
________________________________________
End of Part 1
When Phase 2's exit criteria hold, you'll have:
•	a repo where the core is CAD-neutral by test, not by intention
•	a contract with two implementations, one of which isn't a CAD at all
•	FreeCAD building the demo plate headless through the real runner, with every failure kind reachable
•	docs/api_notes/ holding the verified FreeCAD and build123d calls on your actual installed versions
Part 2 (Phases 3–4: neutral checks, task set and scoring) is written next, using what your API notes actually record. When you're ready for it, send me the current docs/api_notes/freecad.md, docs/api_notes/build123d.md, and docs/ENVIRONMENT.md — those three files are what make the next ~85 prompts precise instead of guessed.


cad agent architecture