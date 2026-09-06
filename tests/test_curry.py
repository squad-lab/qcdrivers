"""Tests for the hardware-independent SQUAD measurement wrappers."""

import pytest
from qcodes.instrument import Instrument

from qcdrivers.squad.curry import (
    VCCS,
    CurrentMeasure,
    CurrentSource,
    DiffConductance,
    DiffResistance,
    VoltageDivider,
    VoltageMeasure,
    VoltageSource,
)


@pytest.fixture(autouse=True)
def close_curry_instruments():
    yield
    Instrument.close_all()


def test_vccs_and_voltage_divider_store_their_settings():
    vccs = VCCS("test_vccs")
    divider = VoltageDivider("test_divider")

    assert vccs.gain() == 1
    assert divider.value() == 1

    vccs.gain(2e-6)
    divider.value(100)

    assert vccs.gain() == 2e-6
    assert divider.value() == 100


def test_current_source_scales_sets_and_gets_by_the_vccs_gain(instrument):
    raw = instrument("raw").raw
    raw(0.0)
    vccs = VCCS("source_vccs")
    vccs.gain(2e-6)
    source = CurrentSource("current_source", raw, vccs, curr_offset=0.1e-6)

    source.value(4e-6)

    assert raw() == pytest.approx(2.0)
    assert source.value() == pytest.approx(3.9e-6)


def test_current_source_defaults_to_unity_gain(instrument):
    raw = instrument("raw").raw
    raw(0.0)
    source = CurrentSource("unity_current_source", raw)

    source.value(2.5)

    assert raw() == pytest.approx(2.5)
    assert source.value() == pytest.approx(2.5)


def test_current_measure_applies_amplification_and_offset(instrument):
    raw = instrument("raw", "gain")
    raw.raw(4.0)
    raw.gain(2.0)
    measured = CurrentMeasure("current_measure", raw.raw, raw.gain, curr_offset=0.25)

    assert measured.value() == pytest.approx(1.75)


def test_current_measure_defaults_to_unity_amplification(instrument):
    raw = instrument("raw").raw
    raw(4.0)
    measured = CurrentMeasure("unity_current_measure", raw, curr_offset=0.25)

    assert measured.value() == pytest.approx(3.75)


def test_voltage_source_scales_sets_gets_and_dac_conversion(instrument):
    raw = instrument("raw", "divider")
    raw.raw(0.0)
    raw.divider(10.0)
    source = VoltageSource("voltage_source", raw.raw, raw.divider, volt_offset=0.2)

    source.value(5.0)

    assert raw.raw() == pytest.approx(0.5)
    assert source.value() == pytest.approx(4.8)
    assert source.get_dac_voltage(2.0) == pytest.approx(0.2)


def test_voltage_source_defaults_to_unity_division(instrument):
    raw = instrument("raw").raw
    raw(0.0)
    source = VoltageSource("unity_voltage_source", raw)

    source.value(1.5)

    assert raw() == pytest.approx(1.5)
    assert source.value() == pytest.approx(1.5)


def test_voltage_measure_applies_amplification_and_offset(instrument):
    raw = instrument("raw", "gain")
    raw.raw(5.0)
    raw.gain(2.0)
    measured = VoltageMeasure("voltage_measure", raw.raw, raw.gain, volt_offset=1.0)

    assert measured.value() == pytest.approx(2.0)


def test_voltage_measure_defaults_to_unity_amplification(instrument):
    raw = instrument("raw").raw
    raw(5.0)
    measured = VoltageMeasure("unity_voltage_measure", raw, volt_offset=1.0)

    assert measured.value() == pytest.approx(4.0)


@pytest.mark.parametrize("use_parameters", [False, True])
def test_differential_conductance_corrects_amplification_and_line_resistance(
    instrument, use_parameters
):
    current_amplifier = VCCS(f"conductance_current_amplifier_{use_parameters}")
    voltage_amplifier = VCCS(f"conductance_voltage_amplifier_{use_parameters}")
    current_amplifier.gain(2.0)
    voltage_amplifier.gain(3.0)

    if use_parameters:
        raw = instrument("current", "voltage")
        raw.current(2.0)
        raw.voltage(12.0)
        current = raw.current
        voltage = raw.voltage
    else:
        current = 2.0
        voltage = 12.0

    conductance = DiffConductance(
        f"conductance_{use_parameters}",
        current,
        voltage,
        current_amplifier,
        voltage_amplifier,
        volt_divider=2.0,
        resistance=1.0,
    )

    assert conductance.get_current() == pytest.approx(1.0)
    assert conductance.get_voltage() == pytest.approx(8.0)
    assert conductance.get_resistance() == pytest.approx(7.0)
    assert conductance.value() == pytest.approx(1 / 7)
    assert conductance.norm_value() == pytest.approx((1 / 7) / conductance.cond_quantum)
    assert conductance.get_idn()["vendor"] == "Differential Conductance Wrapper"


def test_differential_resistance_exposes_resistance_as_its_value():
    current_amplifier = VCCS("resistance_current_amplifier")
    voltage_amplifier = VCCS("resistance_voltage_amplifier")
    current_amplifier.gain(2.0)
    voltage_amplifier.gain(4.0)
    resistance = DiffResistance(
        "resistance",
        current=2.0,
        voltage=16.0,
        curr_ampl=current_amplifier,
        volt_ampl=voltage_amplifier,
        resistance=1.0,
    )

    assert "norm_value" not in resistance.parameters
    assert resistance.value() == pytest.approx(3.0)
    assert resistance.get_idn()["vendor"] == "Differential Resistance Wrapper"
