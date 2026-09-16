## QCDrivers Changelog

<!-- version list -->

## v0.3.0 (2026-09-16)

### Continuous Integration

- Apply ruff fixes on the branch instead of failing
  ([`a846c15`](https://gitlab.com/squad-lab/qcdrivers/-/commit/a846c159230a56afe544d6d3cb3415c54da0a410))

### Documentation

- Restructure the contributing guide
  ([`a091d00`](https://gitlab.com/squad-lab/qcdrivers/-/commit/a091d00257a4d2a00ef28bdc9b6424bc1ed55778))

### Features

- Document the development and release workflow for contributors
  ([`aaa9560`](https://gitlab.com/squad-lab/qcdrivers/-/commit/aaa9560ebf3f7905d635cfaa266a8f84692062bf))


## v0.2.3 (2026-09-07)

### Bug Fixes

- Refactor ADR driver for improved socket handling and response parsing
  ([`6898c04`](https://gitlab.com/squad-lab/qcdrivers/-/commit/6898c04156448ca975369bd0f039437158f168b4))


## v0.2.2 (2026-09-07)

### Bug Fixes

- Add `get_idn` to instruments that didn't have them, to make them compatible with the latest
  version of qcodes. Allowed for some of the get calls to the ADR to fail.
  ([`0d063ab`](https://gitlab.com/squad-lab/qcdrivers/-/commit/0d063ab1f0363d15f3aee1cac6426f700d01238a))

- Add `get_idn` to isntruments that didn't have them, to make them compatible with the latest
  version of qcodes. Allowed for some of the get calls to the ADR to fail.
  ([`afda022`](https://gitlab.com/squad-lab/qcdrivers/-/commit/afda0229c1b2c15cd9cd4a8846452e67cda7aed7))


## v0.2.1 (2026-09-07)

### Bug Fixes

- Add set_parser to QDac2Channel parameters; fix snapshot issues with measurement_nplc; update
  README and code formatting for consistency;
  ([`5bd79c0`](https://gitlab.com/squad-lab/qcdrivers/-/commit/5bd79c04c16816447fb714b49c948071111933d3))

### Chores

- **lock**: Sync the release version
  ([`577f389`](https://gitlab.com/squad-lab/qcdrivers/-/commit/577f3897b1f864fe8a8165a59b495ca87193523a))


## v0.2.0 (2026-09-06)

### Documentation

- Add PyPI badge
  ([`f868624`](https://gitlab.com/squad-lab/qcdrivers/-/commit/f8686244237235c88b4b7e8536e97ec14b984550))

### Refactoring

- Group buffered node exports by manufacturer
  ([`57c909d`](https://gitlab.com/squad-lab/qcdrivers/-/commit/57c909d3c9fbc2642d645db1df9a0a15bf8ecf50))

### Breaking Changes

- Concrete buffered nodes are no longer exported from qcdrivers.buffered. Import them from
  qcdrivers.buffered.<manufacturer>.


## v0.1.0 (2026-09-06)

- Initial Release
