## QCDrivers Changelog

<!-- version list -->

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
