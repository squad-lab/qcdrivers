"""Tests for the hardware-independent Harvard DecaDAC utilities."""

import pytest

from qcdrivers.harvard.dacs.dacs import DACException, DacReader


@pytest.mark.parametrize(
    ("response", "parsed"),
    [("A123!", "123"), (" B7!\r\n", "7"), ("C-4!", "-4")],
)
def test_dac_response_parser_removes_command_and_terminator(response, parsed):
    assert DacReader._dac_parse(response) == parsed


def test_dac_response_parser_rejects_an_invalid_terminator():
    with pytest.raises(DACException, match="Unexpected terminator"):
        DacReader._dac_parse("A123?")


@pytest.fixture
def reader():
    dac = DacReader()
    dac.min_val = -5.0
    dac.max_val = 5.0
    return dac


@pytest.mark.parametrize(
    ("voltage", "code"),
    [(-5.0, 0), (0.0, 32_768), (4.0, 58_982)],
)
def test_voltage_to_code_conversion(reader, voltage, code):
    assert reader._dac_v_to_code(voltage) == code


@pytest.mark.parametrize("voltage", [-5.1, 5.0, 6.0])
def test_voltage_to_code_conversion_rejects_out_of_range_values(reader, voltage):
    with pytest.raises(ValueError, match="value out of range"):
        reader._dac_v_to_code(voltage)


@pytest.mark.parametrize("code", [0, 1, 32_768, 65_535])
def test_harvard_dac_conversion_round_trip(reader, code):
    voltage = reader._dac_code_to_v(code)

    assert reader._dac_v_to_code(voltage) == code
