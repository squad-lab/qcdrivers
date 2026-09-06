"""
Dummy Basel preamplifier instruments.

Software stand-ins for the Basel SP1004a and SP983a preamplifiers, for wiring
up a measurement without the hardware present. Moved here from
``qcdrivers.squad.helpers.helpers`` so that Basel instruments live under the
Basel manufacturer package.

"""

from typing import Any, Optional

from qcodes import validators as vals
from qcodes.instrument import Instrument

__all__ = ["DummyBaselSP1004a", "DummyBaselSP983a"]


class DummyBaselSP1004a(Instrument):
    """
    A driver for Dummy Basel Diffamp's (SP1004a) Remote Instrument - Model SP1004a.

    Args:
        name: name for your instrument driver instance
        address: address of the connected remote controller of basel preamp
    """

    def __init__(
        self,
        name: str,
        **kwargs: Any,
    ) -> None:
        super().__init__(name, **kwargs)
        self.gain_value = None
        self.filter_value = None

        self.add_parameter(
            "gain",
            label="Gain",
            unit="",
            set_cmd=self._set_gain,
            get_cmd=self._get_gain,
            vals=vals.Enum(1e2, 1e3, 1e4),
        )
        self.add_parameter(
            "fcut",
            unit="Hz",
            label="Filter Cut-Off Frequency",
            get_cmd=self._get_filter,
            set_cmd=self._set_filter,
            vals=vals.Enum(100, 300, 1000, 3000, 10e3, 30e3, 100e3, 300e3, 1e6),
        )

    def get_idn(self) -> dict[str, Optional[str]]:
        vendor = "SQUAD Lab"
        model = "Dummy SP 1004A"
        serial = None
        firmware = None
        return {
            "vendor": vendor,
            "model": model,
            "serial": serial,
            "firmware": firmware,
        }

    def _set_gain(self, value: float) -> None:
        self.gain_value = value

    def _get_gain(self) -> float:
        return self.gain_value

    def _set_filter(self, value: str) -> None:
        self.filter_value = value

    def _get_filter(self) -> str:
        return self.filter_value


class DummyBaselSP983a(Instrument):
    """
    A driver for a Dummy Basel I/V Converter (SP983a) Remote Instrument - Model SP983a.

    Args:
        name: name for your instrument driver instance
        address: address of the connected remote controller of basel preamp
    """

    def __init__(
        self,
        name: str,
        **kwargs: Any,
    ) -> None:
        super().__init__(name, **kwargs)
        self.gain_value = None
        self.filter_value = None

        self.add_parameter(
            "gain",
            label="Gain",
            unit="",
            set_cmd=self._set_gain,
            get_cmd=self._get_gain,
            vals=vals.Enum(1e5, 1e6, 1e7, 1e8, 1e9),
        )
        self.add_parameter(
            "fcut",
            unit="Hz",
            label="Filter Cut-Off Frequency",
            get_cmd=self._get_filter,
            set_cmd=self._set_filter,
            vals=vals.Enum(30, 100, 300, 1000, 3000, 10e3, 30e3, 100e3, 1e6),
        )

    def get_idn(self) -> dict[str, Optional[str]]:
        vendor = "SQUAD Lab"
        model = "Dummy SP 983a"
        serial = None
        firmware = None
        return {
            "vendor": vendor,
            "model": model,
            "serial": serial,
            "firmware": firmware,
        }

    def _set_gain(self, value: float) -> None:
        self.gain_value = value

    def _get_gain(self) -> float:
        return self.gain_value

    def _set_filter(self, value: str) -> None:
        self.filter_value = value

    def _get_filter(self) -> str:
        return self.filter_value
