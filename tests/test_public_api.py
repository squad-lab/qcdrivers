"""Tests for the supported package-level driver imports."""

import importlib

import pytest

PUBLIC_APIS = {
    "qcdrivers.basel.amplifiers": {
        "BaselSP1004a",
        "DummyBaselSP1004a",
        "DummyBaselSP983a",
    },
    "qcdrivers.basel.dacs": {"BaselDac2", "BaselDac2Controller"},
    "qcdrivers.bluefors.fridges": {"BlueFors"},
    "qcdrivers.buffered": {"BufferedNodeBase"},
    "qcdrivers.buffered.basel": {"NodeBaselDAC"},
    "qcdrivers.buffered.keysight": {"NodeKeysightDMM", "NodeKeysightVNA"},
    "qcdrivers.buffered.qdevil": {"NodeQDAC2"},
    "qcdrivers.buffered.squad": {"NodeDummySweeper", "NodeDummyAcquisition"},
    "qcdrivers.buffered.zurich": {"NodeMFLI", "NodeUHFLI"},
    "qcdrivers.entropy.adr": {"ADR"},
    "qcdrivers.entropy.heater": {"Heater"},
    "qcdrivers.harvard.dacs": {"DacChannel", "DacReader", "DacSlot", "Decadac"},
    "qcdrivers.keysight.dmms": {"Keysight34410A", "Keysight34461A"},
    "qcdrivers.keysight.vna": {"N5222B", "N5234B", "PNABase"},
    "qcdrivers.qdevil.qdac2": {"QDac2"},
    "qcdrivers.rwth.mux": {"Muxi"},
    "qcdrivers.squad.curry": {
        "VCCS",
        "CurrentMeasure",
        "CurrentSource",
        "DiffConductance",
        "DiffResistance",
        "VoltageDivider",
        "VoltageMeasure",
        "VoltageSource",
    },
    "qcdrivers.squad.helpers": {"Delay", "Lockin", "ShellInstrument"},
    "qcdrivers.squad.mux": {"Muxi"},
    "qcdrivers.stanford": {"CS580"},
}


@pytest.mark.parametrize(
    ("package_name", "expected_exports"),
    PUBLIC_APIS.items(),
    ids=PUBLIC_APIS,
)
def test_public_classes_are_exported_from_their_package(package_name, expected_exports):
    """Every documented short import resolves without connecting to hardware."""
    package = importlib.import_module(package_name)

    assert set(package.__all__) == expected_exports
    for name in expected_exports:
        assert getattr(package, name) is not None


def test_concrete_buffered_nodes_are_not_exported_from_the_root_package():
    """Concrete nodes are imported through their manufacturer package."""
    package = importlib.import_module("qcdrivers.buffered")

    node_names = {
        "NodeBaselDAC",
        "NodeDummySweeper",
        "NodeDummyAcquisition",
        "NodeKeysightDMM",
        "NodeKeysightVNA",
        "NodeMFLI",
        "NodeQDAC2",
        "NodeUHFLI",
    }

    assert node_names.isdisjoint(vars(package))
