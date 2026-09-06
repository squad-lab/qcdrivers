# QCDrivers 🔧

[![pipeline](https://gitlab.com/squad-lab/qcdrivers/badges/main/pipeline.svg?ignore_skipped=true&key_text=pipeline&key_width=60)](https://gitlab.com/squad-lab/qcdrivers/-/pipelines?ref=main)
[![tests](https://gitlab.com/squad-lab/qcdrivers/badges/main/pipeline.svg?job=pytest%3A%20%5B3.13%5D&ignore_skipped=true&key_text=tests&key_width=40)](https://gitlab.com/squad-lab/qcdrivers/-/pipelines?ref=main)
[![coverage](https://gitlab.com/squad-lab/qcdrivers/badges/main/coverage.svg?key_text=coverage&key_width=64)](https://gitlab.com/squad-lab/qcdrivers/-/jobs)
[![latest release](https://gitlab.com/squad-lab/qcdrivers/-/badges/release.svg?key_text=release&key_width=54)](https://gitlab.com/squad-lab/qcdrivers/-/releases)

This repository collects and shares QCoDeS drivers that are not available through
[qcodes](https://github.com/microsoft/qcodes) or the
[contrib drivers](https://github.com/QCoDeS/Qcodes_contrib_drivers) repository.
It may also contain proprietary drivers written by lab members, including drivers
developed in collaboration with partner companies.

## Installation

QCDrivers requires Python 3.13 and can be installed with either `uv` or `pip`:

```console
uv add qcdrivers
```

```console
pip install qcdrivers
```

## Layout

The drivers are grouped by manufacturer. Hardware-triggered (buffered) sweep
nodes can be found under `buffered/`, where they follow the same grouping.

```
src/qcdrivers
├── basel/          amplifiers, dacs
├── bluefors/       fridges
├── entropy/        adr, heater
├── harvard/        dacs
├── keysight/       dmms, vna
├── qdevil/         qdac2
├── rwth/           mux
├── squad/          curry, helpers, mux
├── stanford/       vccs
└── buffered/       basel, keysight, qdevil, squad, zurich
```

Please follow this structure when adding a new driver, using the existing drivers
as a reference. Each package re-exports its public classes and declares `__all__`
to keep imports short and convenient.

## Usage

```python
from qcdrivers.basel.dacs import BaselDac2
from qcdrivers.keysight.dmms import Keysight34461A
from qcdrivers.buffered import NodeQDAC2, NodeKeysightDMM
```

The drivers can be imported directly from their category package, as shown
above. There is no need to import them from their individual module files.

The complete list of parameters for an instrument can be displayed through
QCoDeS:

```python
dac = BaselDac2("dac", address="...")
print(dac.parameters)
```

### Buffered nodes

A buffered node wraps a QCoDeS instrument and provides the interface used by a
QCUtils buffered sweep: `register_sweep`, `register_dependent`, `run_sweep`,
`fetch`, `abort`, and `toplevel`.

## Development

To set up a local development environment, clone the repository and install the
development dependencies with `uv`:

```console
git clone https://gitlab.com/squad-lab/qcdrivers
cd qcdrivers
uv sync --extra dev
uv run pre-commit install
```

| Task | Command |
| ---- | ------- |
| Run the tests | `uv run pytest` |
| Lint (+ import sorting) | `uv run ruff check .` |
| Format | `uv run ruff format .` |

## Contributing

To contribute to the repository, please follow the directory structure above and
open a merge request. Drivers should be well documented and, where possible,
tested without hardware before submission. Please see the
[contributing guide](CONTRIBUTING.md) for the complete development and submission
process. Everyone is welcome to report bugs or request features by opening an
[issue](https://gitlab.com/squad-lab/qcdrivers/-/issues).
