# Contributing to QCDrivers

Thank you for contributing to QCDrivers. This repository collects QCoDeS drivers
for instruments used in the [SQUAD Lab](https://squad-lab.org/) that are not
available from [qcodes](https://github.com/microsoft/qcodes) or the
[contrib drivers](https://github.com/QCoDeS/Qcodes_contrib_drivers). Contributions
may include new drivers, improvements to existing ones, bug fixes, tests, and
documentation.

Contributions may not require hardware. Where they do, say so in the merge
request and describe what you were able to verify.

---

## Table of Contents

- [Contributing to QCDrivers](#contributing-to-qcdrivers)
  - [Table of Contents](#table-of-contents)
  - [Development](#development)
    - [Setup](#setup)
    - [Before you push](#before-you-push)
    - [Adding or updating a driver](#adding-or-updating-a-driver)
    - [Tests](#tests)
  - [Issues](#issues)
  - [Merge requests](#merge-requests)

---

## Development

QCDrivers requires Python 3.13 and uses [uv](https://docs.astral.sh/uv/) for
dependency management.

### Setup

Run this once per clone:

```console
git clone https://gitlab.com/squad-lab/qcdrivers
cd qcdrivers
uv sync --extra dev && uv run pre-commit install
```

Work on a branch of your own, one per change.

### Before you push

```console
uv run pytest
uv run pre-commit run --all-files
```

The first runs the test suite. The second applies Ruff's lint fixes and its
formatter to the whole repository. If it changes anything, commit the result.

### Adding or updating a driver

Drivers belong in `src/qcdrivers/` and are grouped first by manufacturer and then
by instrument category. Use the existing packages as a reference and keep
instrument-specific implementation details in their own modules.

Every package should expose its public classes from `__init__.py` and list them
in `__all__`. Users should be able to import a driver from its category package
without knowing the name of its implementation module. For example:

```python
from qcdrivers.basel.dacs import BaselDac2
```

New drivers should follow the QCoDeS conventions, include clear documentation,
and avoid introducing dependencies that are not required by the driver. Update
the README or the relevant driver documentation when public behavior or usage
changes.

### Tests

Add automated tests under `tests/` whenever the behavior can be tested without
physical hardware. Mock the hardware communication, or replace it with a small
stub where practical.

Interactive hardware bring-up scripts belong in `tests/hardware/`. Their names
must not match pytest's `test_*.py` or `*_test.py` patterns: these scripts may
use hard-coded addresses and must never run in CI.

## Issues

Report bugs and propose changes through the
[issue tracker](https://gitlab.com/squad-lab/qcdrivers/-/issues). For a larger
change, please open an issue before you start, so the approach can be discussed
first.

A bug report should give the instrument model, its firmware version, the
connection method, and enough detail to reproduce the problem.

## Merge requests

Feature branches merge into `preview`, where the package is built and tested.
`main` is for releases.

Describe what the change does, why, and how it was tested. Keep unrelated
changes in separate merge requests, and call out anything you could not test
without hardware.

Releases are cut from the commit messages, so they follow
[Conventional Commits](https://www.conventionalcommits.org/):
- `fix:` for a patch release
- `feat:` for a minor one, and,
- a `BREAKING CHANGE:` footer for a major one.
- Anything else -- `docs:`, `test:`, `chore:`, `refactor:` -- is a valid
subject that does not create a releases.

Please use the right prefix. Every merge request must pass the lint, test, security, and secret-detection jobs in the pipeline.
