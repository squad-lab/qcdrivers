"""Regression tests for PNA trace replacement without hardware."""

from unittest.mock import MagicMock

import numpy as np
import pytest
from qcodes.instrument import VisaInstrument

from qcdrivers.keysight.vna import N5234B


@pytest.fixture
def vna(monkeypatch):
    traces = {"original_trace": "S11"}
    selected = "original_trace"
    settings = {
        "SENS:SWE:TYPE": "LIN",
        "SENS:SWE:MODE": "CONT",
        "SENS:AVER": "0",
        "OUTPut": "0",
        "CALC:FORM": "MLOG",
    }
    resource = MagicMock()
    resource.resource_name = "TCPIP::test::INSTR"

    def write(cmd):
        nonlocal selected
        if cmd == "CALC:PAR:DEL:ALL":
            traces.clear()
            selected = None
        elif cmd.startswith("CALCulate:PARameter:DEFine:EXT "):
            name, sparam = cmd.split(" ", 1)[1].split(",")
            traces[name.strip('"')] = sparam
        elif cmd.startswith(("CALC:PAR:SEL ", "CALCulate:PARameter:SELect ")):
            selected = cmd.split(" ", 1)[1].strip("\"'")
            assert selected in traces
        elif cmd.startswith("CALC:PAR:MNUM "):
            selected = list(traces)[int(cmd.split()[1]) - 1]
        elif " " in cmd:
            key, value = cmd.split(" ", 1)
            settings[key] = value

    def query(cmd):
        if cmd in ("CALC:PAR:CAT?", "CALC:PAR:CAT:EXT?"):
            return (
                '"' + ",".join(item for pair in traces.items() for item in pair) + '"'
            )
        if cmd == "CALC:PAR:MNUM?":
            return str(list(traces).index(selected) + 1)
        if cmd == "*IDN?":
            return "Keysight,N5234B,test,1.0"
        if cmd == "CALCulate:DATA? FDAT":
            return "-10,-20,-30"
        if cmd[:-1] in settings:
            return settings[cmd[:-1]]
        # Remaining scalar settings queried by the inherited snapshot.
        return "1"

    resource.write.side_effect = write
    resource.query.side_effect = query
    monkeypatch.setattr(VisaInstrument, "_open_resource", lambda *args: resource)
    instrument = N5234B("test_vna", resource.resource_name, device_clear=False)
    yield instrument, resource
    instrument.close()


def test_trace_shortcuts_follow_reconfigured_measurements(vna, caplog):
    instrument, _ = vna
    original_trace = instrument.trace.instrument

    for sparams in (["S21", "S11"], ["S12"]):
        instrument.configure_active_s_parameters(sparams)

        assert instrument.trace() == sparams[0]
        assert instrument.trace.instrument is not original_trace
        assert instrument.run_sweep.__self__ is instrument.trace.instrument
        assert instrument.format.instrument is instrument.trace.instrument
        snapshot = instrument.snapshot(update=True)
        assert snapshot["parameters"]["trace"]["value"] == sparams[0]

    assert "Could not update parameter" not in caplog.text


def test_s_parameter_snapshot_does_not_acquire_or_create_traces(vna):
    instrument, resource = vna
    instrument.configure_active_s_parameters(["S21"])
    resource.reset_mock()

    instrument.s21_magnitude.snapshot(update=True)

    resource.write.assert_not_called()
    resource.query.assert_not_called()


def test_s_parameter_snapshot_keeps_last_measured_value(vna):
    instrument, resource = vna
    np.testing.assert_array_equal(instrument.s21_magnitude(), [-10, -20, -30])
    resource.reset_mock()

    snapshot = instrument.s21_magnitude.snapshot(update=True)

    np.testing.assert_array_equal(snapshot["value"], [-10, -20, -30])
    resource.write.assert_not_called()
    resource.query.assert_not_called()


def test_empty_trace_configuration_preserves_existing_traces(vna):
    instrument, resource = vna
    resource.reset_mock()

    with pytest.raises(ValueError, match="At least one S-parameter"):
        instrument.configure_active_s_parameters([])

    resource.write.assert_not_called()
    assert instrument.trace() == "S11"
