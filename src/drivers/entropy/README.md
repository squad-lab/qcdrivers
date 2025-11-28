# Entropy ADR Utilities

QCoDeS and Python implementation of control for Entropy m-type ADR cryostats and a physical heater placed on its 4K stage with an arbitrary current/voltage source.  
These driver allows for communicating with the Entropy ADR controller through its TCP/IP command interface, exposing full readout and control functionality (except for pill recharge which requires using the Entropy GUI). This driver provides a clean, programmable way to operate the ADR directly from Python which becomes especially relevant for reading temperatures in your measurement script or performing temperature sweeps integrated with other QCoDeS parameter sweeps (either with the intergrated pill PID or the heater).

---

# Usage

For a general introduction to QCoDeS and its driver model, refer to the QCoDeS documentation, which provides many examples and tutorials.  
This README describes specifically how to use the ADR and Heater drivers provided here.

---

# ADR Driver

The `ADR` class is initialized with the following required arguments:

### **Initialization Parameters**

| Parameter | Description |
|----------|-------------|
| **name** | QCoDeS name of the ADR instrument |
| **address** | Hostname or IP address of the ADR controller |
| **port** | TCP port used by the ADR controller |

### Behavior on Initialization

Upon initialization, the driver automatically:

- Opens a TCP/IP socket to the ADR controller
- Reads and prints the startup banner
- Selects the ADR device (`DEVSEL ADR`)
- Exposes all temperature, resistance, vacuum, and magnet readout channels
- Provides simple control functions for starting/stopping the compressor
- Provides high-level ADR PID control routines (tempreg, voltreg)

---

## Example Usage

```python
from adr_driver import ADR

adr = ADR(
    name="adr",
    address="192.168.0.10",
    port=8080
)
```
# QCoDeS Parameters Description

## ADR Parameters

### Temperature Parameters

| Parameter | Description |
|----------|-------------|
| `t4K` | Temperature of 4K stage (K) |
| `GGG` | Temperature of GGG stage (K) |
| `FAA` | Temperature of FAA stage (K) |

### Resistance Parameters

| Parameter | Description |
|----------|-------------|
| `R4K` | Sensor resistance of 4K stage (Ω) |
| `RGGG` | Sensor resistance of GGG stage (Ω) |
| `RFAA` | Sensor resistance of FAA stage (Ω) |

### Magnet & Vacuum Parameters

| Parameter | Description |
|----------|-------------|
| `supplycurrent` | Magnet supply current (A) |
| `supplyvoltage` | Magnet supply voltage (V) |
| `magnetsense` | Magnet sense voltage (V) |
| `pressure` | OVC pressure (mbar) |
| `compressor` | Compressor status (0/1) |



# High-Level Functionality

## ADR Control Functions

### `tempreg(enable, temperature, rate)`
Enables/disables ADR temperature regulation and sets its setpoint and ramp rate.

### `voltreg(enable, voltage)`
Enables/disables magnet voltage regulation.

### `startcompressor()` / `stopcompressor()`
Controls the pulse tube compressor.  
(**Note:** Command polarity may be reversed depending on wiring.)

---

# Heater Driver

The `Heater` class provides high-level PID-based heater control that works with:

- A current-source instrument (e.g., Keithley SMU)
- An ADR driver instance for temperature sensing

The controller:

- Reads ADR temperature continuously
- Outputs heater current via SMU
- Applies PID corrections to hold temperature at a target value
- Uses a built-in temperature-current calibration curve to improve stability
- Includes safety current limiting and optional auto-shutdown

---

## Initialization Parameters

| Parameter | Description |
|----------|-------------|
| **name** | QCoDeS name of the heater controller |
| **current_source** | QCoDeS instrument providing `curr()` and `volt()` |
| **adr** | ADR driver instance for temperature readout |

---

## Example Usage

```python
heater = Heater(
    name="heater",
    current_source=keithley,
    adr=adr
)
```
# QCoDeS Parameters Description
---

## (Derived) Heater Parameters

| Parameter | Description |
|----------|-------------|
| `current` | Current delivered to heater by SMU (A) |
| `voltage` | Voltage across heater (V) |
| `t4K` | ADR 4K temperature reading (feedback sensor) |

---

## Heater PID Controller

### `set_T(temperature, duration=None, turnoff=True)`
Runs a full PID loop to bring the 4K stage to the requested temperature.


### Arguments

| Argument | Description |
|----------|-------------|
| **temperature** | Target temperature (K) |
| **duration** | Optional time to run PID (s) |
| **turnoff** | Automatically switch heater off when finished |

### The PID loop performs:

1. Estimate required heater current using calibration data  
2. Compute proportional, integral, and derivative correction terms  
3. Send updated current values to the current source  
4. Monitor temperature and voltage  
5. Enforce current limits  
6. Optionally deactivate heater at completion  

---
