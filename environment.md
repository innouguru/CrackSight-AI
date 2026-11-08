# Environment Decision Record

Milestone: dataset integrity and annotation auditing (no model training).
Recorded: 2026-10-25. Platform: Windows 11, PowerShell 5.1, x64.

## 1. Initial state (inspected, before any change)

| Item | Finding |
|---|---|
| Project contents | `data/`, `architecture.md`, `project_vision.md` |
| Python source files | none |
| `requirements.txt` / `pyproject.toml` / `setup.cfg` | none |
| `.gitignore` | none |
| `README.md` | none |
| `.venv` | did not exist |
| Git repository | no (`.git` not present in this directory or any parent) |
| Python-version constraints in existing docs | none stated; `architecture.md` and `project_vision.md` are design documents only |
| Dataset layout | `data/concrete400` (3019 files), `data/crack-seg` (8059 files), `data/facade-crack-dataset` (564 files) |
| Dataset file types | `.jpg` 6570, `.txt` 4408, `.png` 660, `.csv` 2, `.md` 1, `.yaml` 1 |

PowerShell execution policy: `CurrentUser = RemoteSigned`, `LocalMachine = Undefined`.
Local scripts created on this machine (including `.venv\Scripts\Activate.ps1`) therefore
run without any policy change. Machine-wide policy was not modified.

## 2. Python version selection

Interpreters discovered through `py -0p` and direct invocation:

| Interpreter | Version | Path | Status |
|---|---|---|---|
| `python` (on PATH) | 3.13.0b4 | `...\Python\Python313` | prerelease (beta) — **rejected** |
| `py -3.12` | 3.12.5 | `...\Python\Python312` | stable — **selected** |
| `py -V:Astral/CPython3.12.7` | 3.12.7 | uv-managed `cpython-3.12.7` | stable, not selected |

**Selected: CPython 3.12.5 (64-bit), the installed stable interpreter.**

Rationale:

- The default `python` on PATH resolves to `3.13.0b4`, a beta release. The task rules out
  prerelease interpreters without a specific technical reason, and no such reason exists
  here: every planned dependency publishes stable wheels for 3.12. Beta interpreters also
  routinely break binary wheels during the 3.13 release cycle, which would undermine the
  reproducibility goal.
- 3.12.5 is already installed with a working `pip` (24.2) and `venv`, so no download of a
  new interpreter was required.
- Pillow 13, NumPy 2.5, Matplotlib 3.11, pytest 9.1 and PyYAML 6.0 all publish CPython
  3.12 Windows x64 wheels (or pure-Python wheels); installation produced no build-from-
  source step.
- Alternative rejected: the uv-managed CPython 3.12.7 is also stable, but selecting it
  would introduce a second package-management toolchain (uv) into a project that has none.
  The system 3.12 install is sufficient and keeps the setup reproducible with stock tools.

Known limitation: PATH still exposes the 3.13.0b4 interpreter when the virtual environment
is **not** activated. Any command that must run in this project must be issued after
activation (see §7). The global Python configuration was deliberately left untouched.

## 3. Virtual environment

Created at `.venv` with:

```powershell
py -3.12 -m venv .venv
```

Verified (evidence, not assumption):

- Activation: `.\.venv\Scripts\Activate.ps1` sets `VIRTUAL_ENV` to the project `.venv`
  and prepends `.venv\Scripts` to `PATH`; no execution-policy change was needed.
- `python --version` → `Python 3.12.5`.
- `python -m pip --version` → `pip 26.2.2 from ...\Crack Detection\.venv\Lib\site-packages\pip (python 3.12)`.
- `sys.executable` resolves to `.venv\Scripts\python.exe`; `sys.prefix != sys.base_prefix`
  → `True` (the environment is isolated from the base interpreter).

pip was upgraded from 24.2 to 26.2.2 **inside the environment only**, to obtain current
resolver behaviour. The base interpreters were not modified: `py -3.12 -m pip` is still
`pip 24.2` and the 3.13 interpreter still reports `pip 26.1.1`.

## 4. Dependencies

Five direct dependencies, chosen for the audit milestone only:

| Package | Version | Purpose in this milestone |
|---|---|---|
| Pillow | 13.0.0 | decode images, read dimensions/modes during integrity checks |
| NumPy | 2.5.4 | array handling for mask/polygon comparison |
| Matplotlib | 3.11.2 | visual spot-checks of annotations |
| pytest | 9.1.1 | framework for the upcoming audit test suite |
| PyYAML | 6.0.3 | parse dataset configuration files (e.g. `data/crack-seg/crack-seg.yaml`) |

Full resolved set (`python -m pip freeze`, 18 packages including transitive dependencies):

```
colorama==0.4.6
contourpy==1.4.0
cycler==0.12.1
fonttools==4.67.0
iniconfig==2.3.1
kiwisolver==1.5.1
matplotlib==3.11.2
numpy==2.5.4
packaging==26.3
pillow==13.0.0
pluggy==1.7.0
Pygments==2.21.0
pyparsing==3.3.3
pytest==9.1.1
python-dateutil==3.0.0
PyYAML==6.0.3
six==1.17.0
tzdata==2026.5
```

All versions are pinned in `requirements.txt`; re-running
`python -m pip install -r requirements.txt` reports every requirement already satisfied.

**Deliberately deferred:** PyTorch, TensorFlow, Ultralytics, OpenCV, pandas, scikit-learn
and similar packages. No existing project file establishes a need for them at this
milestone, and installing them now would add several hundred megabytes of transitive
dependencies that must be re-verified whenever they change. They belong to the later
training milestone.

Alternatives considered for the dependency file: `pyproject.toml` + `pip install -e .`
(rejected: there is no package to install yet) and `conda`/`environment.yml` (rejected:
not installed, and unnecessary for five pure-wheel dependencies).

## 5. Project hygiene (`.gitignore`)

No `.gitignore` existed, so one was created. It ignores virtual environments,
bytecode/tool caches, packaging output, model-weight and training-output patterns
(`runs/`, `*.pt`, `*.pth`, `*.onnx`, `*.ckpt`, ...), temporary audit caches/logs, and
editor/OS noise.

Explicitly **not** ignored: `data/`, `*.md`, `*.yaml`, `*.csv`. Before writing the file,
the dataset was scanned: it contains only `.jpg`, `.txt`, `.png`, `.csv`, `.md` and
`.yaml` files, so no ignore rule matches any dataset file. Datasets and audit reports
remain tracked and available.

Git was not initialized; repository state is unchanged.

## 6. Verification results

Verified:

1. Expected interpreter active: **Python 3.12.5** inside `.venv`.
2. All five direct packages import successfully with the pinned versions.
3. `pytest --version` → `pytest 9.1.1`.
4. Data directories accessible: a sample image opened with Pillow (`416x416 RGB`),
   200 validation label files enumerated and read, `data/crack-seg/crack-seg.yaml`
   parsed with `yaml.safe_load`.
5. Dataset integrity: file counts and total bytes are identical before and after setup —
   `concrete400` 3019 files / 353,974,872 bytes, `crack-seg` 8059 files / 110,543,496
   bytes, `facade-crack-dataset` 564 files / 12,663,804 bytes (before == after).
6. No global installs: `py -3.12 -m pip list` shows only `pip==24.2`; neither global
   site-packages directory has any entry modified in the last 6 hours; both base pip
   versions are unchanged from the pre-setup readings.
7. No pre-existing file overwritten: `architecture.md` (748 bytes) and
   `project_vision.md` (1770 bytes) retain their original sizes and timestamps. The
   proposed filenames `requirements.txt`, `.gitignore` and `environment.md` did not exist
   beforehand.

Not performed (out of scope): full dataset audit, model scripts, model training.

## 7. Using the environment

```powershell
Set-Location "C:\Users\hp\Desktop\AI PROJECTS\Crack Detection"

.\.venv\Scripts\Activate.ps1

python --version
python -m pip --version
python -m pip install -r requirements.txt
```

Deactivate with `deactivate`. If a PowerShell session reports that
`Activate.ps1` is blocked (it should not under the current `RemoteSigned` policy), do not
change machine-wide policy; instead invoke the environment directly:

```powershell
& ".\.venv\Scripts\python.exe" -m pytest
```

## 8. Unresolved items

- PATH still prioritises the 3.13.0b4 interpreter outside an activated session; resolved
  operationally by always activating first, not by editing global configuration.
- Exact transitive dependency versions were resolved once on 2026-10-25; a fresh install
  on another machine should be validated against `requirements.txt` before relying on it.
- The project is not a Git repository, so `.gitignore` currently has no effect; that is a
  separate decision to be taken later.
