import types

import numpy as np
from qcodes.instrument import Instrument
from zhinst.qcodes import MFLI as ZIMFLI


class MFLI(Instrument):
    """
    Wrapper for a Zurich Instruments MFLI.
    """

    def __init__(
        self,
        name: str,
        address: str,
        serial: str,
        *args,
        **kwargs,
    ) -> None:
        super().__init__(f"wrapper_{name}")

        self.core = ZIMFLI(
            name=name,
            host=address,
            interface="1GbE",
            serial=serial,
            *args,
            **kwargs,
        )

        self.frequency = self.core.oscs[0].freq
        self.amplitude = self.core.sigouts[0].amplitudes[1].value
        self.on = self.core.sigouts[0].on

        self.select_input = self.core.demods[
            0
        ].adcselect  # call 0 for voltage (Sig In 1) and 1 for current (Curr In 1)

        self.add = self.core.sigouts[0].add
        self.diff = self.core.sigouts[0].diff

        # sample rate
        self.sample_rate = self.core.demods[0].rate

        self.sinc = self.core.demods[0].sinc
        self.harmonic = self.core.demods[0].harmonic

        self.ac = self.core.sigins[0].ac
        self.tc = self.core.demods[0].timeconstant
        self.order = self.core.demods[0].order

        self.dc_offset = self.core.sigouts[0].offset
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

    def r_val(self, demod=0) -> float:
        sample = self.core.demods[demod].sample()

        x = sample["x"][0]
        y = sample["y"][0]

        return float(np.abs(x + 1j * y))

    def p_val(self, demod=0) -> float:
        sample = self.core.demods[demod].sample()

        x = sample["x"][0]
        y = sample["y"][0]

        return float(np.rad2deg(np.arctan2(y, x)))

    def get_r_unit(self, demods=0) -> str:
        match self.core.demods[demods].adcselect():
            case 0:
                unit = "V"
            case 1:
                unit = "A"

        return unit

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
