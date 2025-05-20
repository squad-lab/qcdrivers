## Curry

This module provides a set of QCoDeS `Instrument` subclasses for simulating and abstracting electrical measurement setups. Each class encapsulates functionality for either controlling or measuring electrical quantities, often incorporating amplifier gains, voltage dividers, or offset corrections.

### `VCCS`

Voltage-Controlled Current Source model.

```python
VCCS(name: str)
```

* **Parameter**: `value` — Amplification factor (unitless)
* **Methods**:

  * `get_value()`
  * `set_value(val)`

### `VoltageDivider`

Simple voltage divider model.

```python
VoltageDivider(name: str)
```

* **Parameter**: `value` — Divider ratio (unitless)
* **Methods**:

  * `get_value()`
  * `set_value(val)`

### `DiffConductance`

Calculates differential conductance from voltage and current measurements, normalized to the quantum of conductance (`G₀`).

```python
DiffConductance(
    name: str,
    current: Parameter,
    voltage: Parameter,
    curr_ampl: Instrument,
    volt_ampl: Instrument,
    volt_divider: float = 1.0,
    resistance: float = 0.0
)
```

* **Parameters**:

  * `value`: Raw conductance in Siemens
  * `norm_value`: Normalized conductance in units of `G₀`
* **Methods**:

  * `get_current()`
  * `get_voltage()`
  * `get_resistance()`
  * `get_conductance()`
  * `get_raw_conductance()`

### `DiffResistance`

Subclass of `DiffConductance` that returns resistance instead of conductance.

```python
DiffResistance(
    name: str,
    current: Parameter,
    voltage: Parameter,
    curr_ampl: Instrument,
    volt_ampl: Instrument,
    volt_divider: float = 1.0,
    resistance: float = 0.0
)
```

* **Parameter**: `value` — Resistance in Ohms
* **Overrides**:

  * Removes `norm_value`
  * Replaces `value` with resistance using `get_resistance()`

### `CurrentSource`

Sets a desired current value by controlling a voltage through a VCCS amplifier.

```python
CurrentSource(
    name: str,
    current: Parameter,
    vccs: VCCS = None,
    curr_offset: float = 0
)
```

* **Parameter**: `value` — Current in Amperes
* **Methods**:

  * `set_current(i)`
  * `get_current()`

### `CurrentMeasure`

Measures current using an IV converter and applies gain and offset corrections.

```python
CurrentMeasure(
    name: str,
    current: Parameter,
    curr_ampl: Parameter,
    curr_offset: float = 0
)
```

* **Parameter**: `value` — Measured current in Amperes
* **Method**: `get_current()`

### `VoltageSource`

Sets voltage considering a voltage divider and optional offset.

```python
VoltageSource(
    name: str,
    voltage: Parameter,
    volt_divider: VoltageDivider = None,
    volt_offset: float = 0
)
```

* **Parameter**: `value` — Output voltage in Volts
* **Methods**:

  * `set_voltage(v)`
  * `get_voltage()`

### `VoltageMeasure`

Measures voltage through a differential amplifier with offset correction.

```python
VoltageMeasure(
    name: str,
    voltage: Parameter,
    volt_ampl: Parameter,
    volt_offset: float = 0
)
```

* **Parameter**: `value` — Measured voltage in Volts
* **Method**: `get_voltage()`
