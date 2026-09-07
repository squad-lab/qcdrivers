"""Tests for IDN queries on hardware-independent instruments."""

import importlib
import inspect
import pkgutil
from datetime import datetime

import pytest
from qcodes.instrument import Instrument, VisaInstrument

import qcdrivers
from qcdrivers.bluefors.fridges import BlueFors
from qcdrivers.entropy.heater import Heater
from qcdrivers.squad.curry import (
    VCCS,
    CurrentMeasure,
    CurrentSource,
    VoltageDivider,
    VoltageMeasure,
    VoltageSource,
)
from qcdrivers.squad.helpers import Delay, ShellInstrument


@pytest.fixture(autouse=True)
def close_instruments():
    yield
    Instrument.close_all()


def test_all_non_visa_instruments_override_the_scpi_idn_query():
    """Non-SCPI instruments must not fall back to sending ``*IDN?``."""
    missing = []

    for module_info in pkgutil.walk_packages(
        qcdrivers.__path__, prefix=f"{qcdrivers.__name__}."
    ):
        module = importlib.import_module(module_info.name)
        for _, instrument_class in inspect.getmembers(module, inspect.isclass):
            if (
                instrument_class.__module__ == module.__name__
                and issubclass(instrument_class, Instrument)
                and not issubclass(instrument_class, VisaInstrument)
                and instrument_class.get_idn is Instrument.get_idn
            ):
                missing.append(
                    f"{instrument_class.__module__}.{instrument_class.__name__}"
                )

    assert missing == []


@pytest.mark.parametrize(
    ("instrument_class", "model"),
    [
        (VCCS, "Voltage Controlled Current Source"),
        (VoltageDivider, "Voltage Divider"),
        (CurrentSource, "Current Source"),
        (CurrentMeasure, "Current Measure"),
        (VoltageSource, "Voltage Source"),
        (VoltageMeasure, "Voltage Measure"),
    ],
)
def test_curry_instruments_respond_to_idn_get(instrument_class, model):
    wrapper = instrument_class(f"test_{instrument_class.__name__.lower()}")

    assert wrapper.IDN.get() == {
        "vendor": "SQUAD Lab",
        "model": model,
        "serial": None,
        "firmware": None,
    }


@pytest.mark.parametrize(
    ("instrument_class", "model", "kwargs"),
    [
        (ShellInstrument, "Shell Instrument", {"parameters": {}}),
        (Delay, "Delay", {}),
    ],
)
def test_squad_helpers_respond_to_idn_get(instrument_class, model, kwargs):
    helper = instrument_class(f"test_{instrument_class.__name__.lower()}", **kwargs)

    assert helper.IDN.get() == {
        "vendor": "SQUAD Lab",
        "model": model,
        "serial": None,
        "firmware": None,
    }


def test_heater_responds_to_idn_get(instrument):
    heater = Heater("test_heater", current_source=instrument(), adr=instrument())

    assert heater.IDN.get() == {
        "vendor": "SQUAD Lab",
        "model": "Entropy ADR Heater Controller",
        "serial": None,
        "firmware": None,
    }


def test_bluefors_responds_to_idn_get(tmp_path):
    (tmp_path / datetime.today().strftime("%y-%m-%d")).mkdir()
    fridge = BlueFors(
        "test_bluefors",
        log_location=str(tmp_path),
        bftc_ip="127.0.0.1",
        fse_ip="127.0.0.1",
    )

    assert fridge.IDN.get() == {
        "vendor": "Bluefors",
        "model": "Cryostat",
        "serial": None,
        "firmware": None,
    }
