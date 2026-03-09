import types
from time import sleep
from typing import Any, Optional

import numpy as np
from qcodes import Instrument
from qcodes import validators as vals


class ShellInstrument(Instrument):
    def __init__(self, name: str, parameters: dict, **kwargs) -> None:
        """Shell instrument class for defining qcodes parameters from instruments with oddly behaving parameters, or to define new instruments with custom parameters

        Args:
            name: name of the qcodes instrument
            parameters (dict): dictionary of parameters to be added to the instrument, kwargs to qcodes.Instrument.add_parameter()
        """

        super().__init__(name, **kwargs)

        for key, parameter in parameters.items():
            self.add_parameter(key, **parameter)


class Lockin(Instrument):
    """Wrapper class for lockin amplifiers, currently only supports SR830 and MFLI

    Args:
        name: name of the qcodes instrument
        address: address of the lockin amplifier (localhost or GPIB address)
        device: device type
        serial: serial number of the lockin amplifier, only required for MFLI
    """

    def __init__(
        self, name, address, device="MFLI", serial=None, demod_channels: list=[0], *args, **kwargs
    ) -> None:
        super().__init__(f"wrapper_{name}", **kwargs)
        if serial:
            try:
                pass
            except ImportError:
                raise ImportError(f"Please install zhinst-qcodes to use the {device}")

            if device == "MFLI":
                from zhinst.qcodes import MFLI

                self.core = MFLI(
                    name=name,
                    host=address,
                    interface="1GbE",
                    serial=serial,
                    *args,
                    **kwargs,
                )
                self.frequency = self.core.oscs[0].freq
                self.amplitude = self.core.sigouts[0].amplitudes[1].value
                self.on = self.sigouts[0].on

                self.select_input = (
                    self.core.demods[0].adcselect
                )  # call 0 for voltage (Sig In 1) and 1 for current (Curr In 1)

                self.add = self.core.sigouts[0].add
                self.diff = self.core.sigouts[0].diff

                self.sinc = self.core.demods[0].sinc
                self.harmonic = self.core.demods[0].harmonic

                self.ac = self.core.sigins[0].ac
                self.tc = self.core.demods[0].timeconstant
                self.order = self.core.demods[0].order

                self.enable_amplitude = self.core.sigouts[0].enables[1].value

                self.autosigout = self.core.sigouts[0].autorange
                self.sigout_range = self.core.sigouts[
                    0
                ].range  # available: 10mV, 100mV, 1V, 10V

                self.autovoltin = self.core.sigins[0].autorange
                self.voltin_range = self.core.sigins[0].range

                self.autocurrin = self.core.currins[0].autorange
                self.currin_range = self.core.currins[0].range

                self.snapshot = self.core.snapshot
                self.core.add_parameter(
                    "R",
                    label=f"{name} R",
                    get_parser=float,
                    get_cmd=self.r_val,
                    unit=self.get_r_unit(),
                )

                self.core.add_parameter(
                    "P",
                    label=f"{name} P",
                    get_parser=float,
                    get_cmd=self.p_val,
                    unit="deg",
                )

                self.core.R.zi_node = "/DEMODS/0/SAMPLE.R"
                self.core.P.zi_node = "/DEMODS/0/SAMPLE.THETA"

                _adc_param = self.core.demods[0].adcselect
                _original_set_raw = _adc_param.set_raw

                def _new_set_raw(this, val):
                    _original_set_raw(val)
                    if val == 0:
                        self.core.R.unit = "V"
                    elif val == 1:
                        self.core.R.unit = "A"

                _adc_param.set_raw = types.MethodType(_new_set_raw, _adc_param)

            elif device == "UHFLI":
                # Still have to add all of the parameters here
                from zhinst.qcodes import UHFLI

                self.core = UHFLI(
                    name=f"{name}_core",
                    host=address,
                    interface="1GbE",
                    serial=serial,
                    *args,
                    **kwargs,
                )

                self.snapshot = self.core.snapshot

                self.on1 = self.sigouts[0].on
                self.on2 = self.sigouts[1].on

                self.autosigout1 = self.core.sigouts[0].autorange
                self.autosigout2 = self.core.sigouts[1].autorange

                self.offset_out1 = self.core.sigouts[0].offset
                self.offset_out2 = self.core.sigouts[1].offset

                # Disable all demodulators first, then only enable the ones specified in demod_channels
                for demod in range(len(self.core.demods)):
                    self.core.demods[demod].enable(False)

                for demod in demod_channels:
                    # Add parameters for frequency, R, and P for each for each of the eight demodulators/osscilators that are input

                    self.core.demods[demod].enable(True)

                    self.core.add_parameter(
                        f"frequency{demod+1}",
                        label=f"{name} Frequency{demod+1}",
                        get_parser=float,
                        get_cmd=lambda d=demod: self.core.oscs[d].freq(),
                        set_cmd=lambda val, d=demod: self.core.oscs[d].freq(val),
                        unit="Hz",
                    )

                    self.core.add_parameter(
                        f"R{demod+1}",
                        label=f"{name} R{demod+1}",
                        get_parser=float,
                        get_cmd=lambda d=demod: self.r_val(d),
                        unit=f"{self.get_r_unit(demod)}",
                    )

                    self.core.add_parameter(
                        f"P{demod+1}",
                        label=f"{name} P{demod+1}",
                        get_parser=float,
                        get_cmd=lambda d=demod: self.p_val(d),
                        unit="deg",
                    )

                    for out in range(2):
                        self.core.add_parameter(
                            f"out{out+1}_amplitude{demod+1}",
                            label=f"{name} out{out+1} amplitude {demod+1}",
                            get_parser=float,
                            get_cmd=lambda o=out, d=demod: self.core.sigouts[o].amplitudes[d].value(),
                            set_cmd=lambda val, o=out, d=demod: self.core.sigouts[o].amplitudes[d].value(val),
                            unit="V",
                        )

                        self.core.add_parameter(
                            f"out{out+1}_amplitude{demod+1}_enable",
                            label=f"{name} out{out+1} amplitude {demod+1} enable",
                            get_parser=bool,
                            get_cmd=lambda o=out, d=demod: self.core.sigouts[o].enables[d].value(),
                            set_cmd=lambda val, o=out, d=demod: self.core.sigouts[o].enables[d].value(val),
                        )


                    _adc_param = self.core.demods[demod].adcselect
                    _original_set_raw = _adc_param.set_raw

                    def _new_set_raw(this, val):
                        _original_set_raw(val)
                        if val == 0:
                            getattr(self.core, f"R{demod+1}").unit = "V"
                        elif val == 1:
                            getattr(self.core, f"R{demod+1}").unit = "A"

                    _adc_param.set_raw = types.MethodType(_new_set_raw, _adc_param)

        else:
            # Still have to add all the parameters here
            from qcodes.instrument_drivers.stanford_research import SR830

            device = "SR830"
            self.core = SR830(f"{name}_core", address, *args, **kwargs)

            self.snapshot = self.core.snapshot

            self.sinc = self.core.sync_filter
            self.tc = self.core.time_constant
            self.order = self.filter_slope
            self.core.R.label = f"{name} R"
            self.core.P.label = f"{name} P"

    def delay(self, order, tc) -> float:
        filter_settling = {
            1: 3 * tc,
            2: 4.7 * tc,
            3: 6.3 * tc,
            4: 7.8 * tc,
            5: 9.2 * tc,
            6: 11 * tc,
            7: 12 * tc,
            8: 13 * tc,
        }
        return filter_settling[int(order)]

    def r_val(self, demods=0) -> float:
        return abs(
            self.core.demods[demods].sample()["x"][0]
            + 1j * self.core.demods[demods].sample()["y"][0]
        )

    def p_val(self, demods=0) -> float:
        return np.rad2deg(
            np.arctan2(
                self.core.demods[demods].sample()["y"][0],
                self.core.demods[demods].sample()["x"][0],
            )
        )

    def get_r_unit(self, demods=0) -> str:
        match self.core.demods[demods].adcselect():
            case 0:
                unit = "V"
            case 1:
                unit = "A"

        return unit

    def get_idn(self) -> dict:
        return self.core.get_idn()

    def __getattr__(self, name):
        # Avoid recursion for attributes that truly don't exist yet
        if name == "core":
            raise AttributeError("'Lockin' object has no attribute 'core'")
        try:
            return super().__getattribute__(name)
        except AttributeError:
            core = self.__dict__.get("core", None)
            if core is not None and hasattr(core, name):
                return getattr(core, name)
            raise


class Delay(Instrument):
    def __init__(self, name, delay=0.1):
        super().__init__(name)

        self.num_time = 0
        self.delay = delay

        self.add_parameter(
            "time",
            label="Time Delay",
            set_cmd=self.set_delay,
            unit=f"x ({delay}s)",
        )

    def set_delay(self, number):
        self.num_time += 1
        sleep(self.delay)


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
