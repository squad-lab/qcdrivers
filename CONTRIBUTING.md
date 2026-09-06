# Contributing to QCDrivers

Thank you for contributing to QCDrivers. Contributions may include new drivers,
improvements to existing drivers, bug fixes, tests, and documentation.

## Before you begin

For a larger change, please open an
[issue](https://gitlab.com/squad-lab/qcdrivers/-/issues) first so that the
implementation can be discussed before work begins. Bug reports should include
the instrument model, relevant firmware version, connection method, and enough
information to reproduce the problem.

## Development setup

QCDrivers requires Python 3.13. Clone the repository and install the development
dependencies with `uv`:

```console
git clone https://gitlab.com/squad-lab/qcdrivers
cd qcdrivers
uv sync --extra dev
uv run pre-commit install
```

Create a separate branch for each contribution. This keeps changes focused and
makes them easier to review.

## Adding or updating a driver

Drivers belong in `src/qcdrivers/` and are grouped first by manufacturer and then
by instrument category. Please use the existing packages as a reference and keep
instrument-specific implementation details in their own modules.

Every package should expose its public classes from `__init__.py` and list them in
`__all__`. Users should be able to import a driver from its category package
without knowing the name of its implementation module. For example:

```python
from qcdrivers.basel.dacs import BaselDac2
```

New drivers should follow the QCoDeS conventions, include clear documentation,
and avoid introducing dependencies that are not required by the driver. Please
update the README or any relevant driver documentation when public behavior or
usage changes.

## Tests

Add automated tests under `tests/` whenever the behavior can be tested without
physical hardware. Hardware communication should be mocked or replaced with a
small stub where practical.

Interactive hardware bring-up scripts belong in `tests/hardware/`. Their names
must not match pytest's `test_*.py` or `*_test.py` patterns, because these scripts
may use hard-coded addresses and must never run in CI.

Run the test suite before submitting a change:

```console
uv run pytest
```

## Code quality

Run the same linting and formatting checks used by CI:

```console
uv run ruff check .
uv run ruff format --check .
uv run pre-commit run --all-files
```

To apply Ruff's automatic fixes and formatting locally, run:

```console
uv run ruff check --fix .
uv run ruff format .
```

## Merge requests

Open a merge request with a clear description of the change, the reason for it,
and how it was tested. Keep unrelated changes in separate merge requests and
call out anything that could not be tested without hardware.

Feature branches normally merge into `preview`, where the package is built and
tested before release. The `main` branch is used for releases. All merge requests
must pass the lint, test, security, and secret-detection jobs configured in the
GitLab pipeline.
