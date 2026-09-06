"""Tests for pure Basel DAC conversions and configuration objects."""

from types import SimpleNamespace

import numpy as np
import pytest

from qcdrivers.basel.dacs import BaselDac2Controller
from qcdrivers.basel.dacs.dacs import (
    BaspiLnhrdac2AWG,
    BaspiLnhrdac2Fast2dConfig,
    BaspiLnhrdac2LockingValidator,
    BaspiLnhrdac2SWGConfig,
)


@pytest.mark.parametrize(
    ("voltage", "code"),
    [(-10.0, 0), (0.0, 8_388_607), (10.0, 16_777_215)],
)
def test_voltage_to_dac_code_conversion(voltage, code):
    assert BaselDac2Controller.vval_to_dacval(voltage) == code


@pytest.mark.parametrize("voltage", [-10.0, -1.234567, 0.0, 4.2, 10.0])
def test_dac_conversion_round_trip(voltage):
    code = BaselDac2Controller.vval_to_dacval(voltage)
    encoded = f"{code:X}"

    assert BaselDac2Controller.dacval_to_vval(encoded) == pytest.approx(
        voltage, abs=2e-6
    )
    assert BaselDac2Controller.dacval_to_vval(code) == pytest.approx(voltage, abs=2e-6)


def test_locking_validator_rejects_only_locked_submodules():
    submodule = SimpleNamespace(locked=False)
    validator = BaspiLnhrdac2LockingValidator(submodule)

    assert validator.validate(1.0) is None

    submodule.locked = True
    with pytest.raises(ValueError, match="has been locked"):
        validator.validate(1.0)


def test_awg_configuration_helpers_compare_waveforms_by_value():
    first = BaspiLnhrdac2AWG.create_awg_config(1, 2, 1e-4, [0.0, 1.0])
    same = BaspiLnhrdac2AWG.create_awg_config(1, 2, 1e-4, np.array([0.0, 1.0]))
    changed = BaspiLnhrdac2AWG.create_awg_config(1, 2, 1e-4, [0.0, 2.0])

    assert BaspiLnhrdac2AWG.awg_configs_equal(first, same)
    assert not BaspiLnhrdac2AWG.awg_configs_equal(first, changed)
    assert not BaspiLnhrdac2AWG.awg_configs_equal(first, None)


class RecordingParameter:
    def __init__(self):
        self.calls = []

    def set(self, value):
        self.calls.append(value)


def test_awg_configuration_is_written_once_and_cached():
    awg = object.__new__(BaspiLnhrdac2AWG)
    awg.cached_awg_config = None
    awg.channel = RecordingParameter()
    awg.cycles = RecordingParameter()
    awg.sampling_rate = RecordingParameter()
    awg.length = RecordingParameter()
    awg.waveform = RecordingParameter()
    config = BaspiLnhrdac2AWG.create_awg_config(3, 4, 5e-5, [0.0, 0.5, 1.0])

    awg.write_awg_config(config)
    awg.write_awg_config(config.copy())

    assert awg.channel.calls == [3]
    assert awg.cycles.calls == [4]
    assert awg.sampling_rate.calls == [5e-5]
    assert awg.length.calls == [3]
    assert awg.waveform.calls == [[0.0, 0.5, 1.0]]
    assert awg.cached_awg_config == config


def test_swg_configuration_defaults_are_valid():
    config = BaspiLnhrdac2SWGConfig(shape="sine")

    assert config.frequency == 100.0
    assert config.amplitude == 1.0
    assert config.offset == 0.0
    assert config.phase == 0.0
    assert config.dutycycle == 0.0


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("frequency", 0.0, "frequency is too small"),
        ("frequency", 10_001.0, "frequency is too big"),
        ("amplitude", -51.0, "amplitude is too small"),
        ("amplitude", 51.0, "amplitude is too big"),
        ("offset", -11.0, "offset is too small"),
        ("phase", 361.0, "phase is too big"),
        ("dutycycle", 101.0, "dutycycle is too big"),
        ("frequency", "fast", "frequency is of not the correct type"),
    ],
)
def test_swg_configuration_rejects_invalid_values(field, value, message):
    config = BaspiLnhrdac2SWGConfig(shape="sine")

    with pytest.raises(ValueError, match=message):
        setattr(config, field, value)


def test_fast_2d_configuration_defaults_are_valid():
    config = BaspiLnhrdac2Fast2dConfig()

    assert config.x_channel == 1
    assert config.x_start_voltage == 0.0
    assert config.x_stop_voltage == 1.0
    assert config.x_steps == 10
    assert config.y_channel == 2
    assert config.y_start_voltage == 0.0
    assert config.y_stop_voltage == 1.0
    assert config.y_steps == 10
    assert config.acquisition_delay == 1e-5
    assert config.adaptive_shift == 0.0


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("x_channel", 0, "x_channel is too small"),
        ("x_channel", 13, "x_channel is too big"),
        ("x_start_voltage", -10.1, "x_start_voltage is too small"),
        ("x_stop_voltage", 10.1, "x_stop_voltage is too big"),
        ("x_steps", 9, "x_steps is too small"),
        ("y_channel", 13, "y_channel is too big"),
        ("y_start_voltage", -10.1, "y_start_voltage is too small"),
        ("y_stop_voltage", 10.1, "y_stop_voltage is too big"),
        ("y_steps", 0, "y_steps is too small"),
        ("acquisition_delay", 0.0, "acquisition_delay is too small"),
        ("adaptive_shift", 10.1, "adaptive_shift is too big"),
        ("x_channel", "one", "x_channel is of not the correct type"),
    ],
)
def test_fast_2d_configuration_rejects_invalid_values(field, value, message):
    config = BaspiLnhrdac2Fast2dConfig(
        x_channel=1,
        x_start_voltage=0.0,
        x_stop_voltage=1.0,
        x_steps=10,
        y_channel=2,
        y_start_voltage=0.0,
        y_stop_voltage=1.0,
        y_steps=10,
        acquisition_delay=1e-5,
        adaptive_shift=0.0,
    )

    with pytest.raises(ValueError, match=message):
        setattr(config, field, value)
