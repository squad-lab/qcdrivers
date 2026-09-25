import types
from collections.abc import Sequence

import numpy as np
from qcodes.instrument import Instrument
from zhinst.qcodes import UHFLI as ZIUHFLI

# helper functions


def dbm_to_vpk(power_dbm: float, out_impedance: float = 50) -> float:
    power_w = 1e-3 * 10 ** (power_dbm / 10)
    vrms = np.sqrt(power_w * out_impedance)

    return float(np.sqrt(2) * vrms)


def vpk_to_dbm(vpk: float, out_impedance: float = 50) -> float:
    if vpk == 0:
        return -np.inf

    power_w = vpk**2 / (2 * out_impedance)

    return float(10 * np.log10(power_w / 1e-3))


class UHFLI(Instrument):
    """
    Wrapper for a Zurich Instruments UHFLI.
    """

    def __init__(
        self,
        name: str,
        address: str,
        serial: str,
        demod_channels: Sequence[int] = (0,),
        *args,
        **kwargs,
    ) -> None:
        super().__init__(f"wrapper_{name}")

        self.core = ZIUHFLI(
            name=f"{name}_core",
            host=address,
            interface="1GbE",
            serial=serial,
            *args,
            **kwargs,
        )

        self.snapshot = self.core.snapshot

        # set input trigger impedance to 1 kOhm !
        for i in [0, 1, 2, 3]:
            self.core.triggers.in_[i].imp50(0)

        self.in1_ac = self.core.sigins[0].ac
        self.in2_ac = self.core.sigins[1].ac

        self.in1_imp50 = self.core.sigins[0].imp50
        self.in2_imp50 = self.core.sigins[1].imp50

        self.on1 = self.core.sigouts[0].on
        self.on2 = self.core.sigouts[1].on

        self.autosigout1 = self.core.sigouts[0].autorange
        self.autosigout2 = self.core.sigouts[1].autorange

        self.out1_imp50 = self.core.sigouts[0].imp50
        self.out2_imp50 = self.core.sigouts[1].imp50

        self.offset_out1 = self.core.sigouts[0].offset
        self.offset_out2 = self.core.sigouts[1].offset

        # Disable all demodulators first, then only enable the ones specified in demod_channels
        for demod in range(len(self.core.demods)):
            self.core.demods[demod].enable(False)

        for demod in demod_channels:
            # Add parameters for frequency, R, and P for each for each of the eight demodulators/osscilators that are input

            self.core.demods[demod].enable(True)

            self.core.add_parameter(
                f"frequency{demod + 1}",
                label=f"{name} Frequency{demod + 1}",
                get_parser=float,
                get_cmd=lambda d=demod: self.core.oscs[d].freq(),
                set_cmd=lambda val, d=demod: self.core.oscs[d].freq(val),
                unit="Hz",
            )

            # zi-nodes for frequencies
            getattr(
                self.core,
                f"frequency{demod + 1}",
            ).zi_node = f"/OSCS/{demod}/FREQ"

            # sample rate
            self.core.add_parameter(
                f"sample_rate{demod + 1}",
                label=f"{name} Sample Rate {demod + 1}",
                get_parser=float,
                get_cmd=lambda d=demod: self.core.demods[d].rate(),
                set_cmd=lambda val, d=demod: self.core.demods[d].rate(val),
                unit="Sa/s",
            )

            self.core.add_parameter(
                f"R{demod + 1}",
                label=f"{name} R{demod + 1}",
                get_parser=float,
                get_cmd=lambda d=demod: self.r_val(d),
                unit=f"{self.get_r_unit(demod)}",
            )

            self.core.add_parameter(
                f"P{demod + 1}",
                label=f"{name} P{demod + 1}",
                get_parser=float,
                get_cmd=lambda d=demod: self.p_val(d),
                unit="deg",
            )

            # add zi-nodes
            getattr(self.core, f"R{demod + 1}").zi_node = f"/DEMODS/{demod}/SAMPLE.R"
            getattr(
                self.core, f"P{demod + 1}"
            ).zi_node = f"/DEMODS/{demod}/SAMPLE.THETA"

            # phaseshift
            self.core.add_parameter(
                f"phase{demod + 1}",
                label=f"{name} Phase{demod + 1}",
                get_parser=float,
                get_cmd=self.core.demods[demod].phaseshift,
                set_cmd=lambda val, d=demod: self.core.demods[d].phaseshift(val),
                unit="deg",
            )

            # timeconstant
            setattr(self, f"tc{demod + 1}", self.core.demods[demod].timeconstant)

            # filter order
            setattr(self, f"order{demod + 1}", self.core.demods[demod].order)

            for out in range(2):
                self.core.add_parameter(
                    f"out{out + 1}_amplitude{demod + 1}",
                    label=f"{name} out{out + 1} amplitude {demod + 1}",
                    get_parser=float,
                    get_cmd=lambda o=out, d=demod: (
                        self.core.sigouts[o].amplitudes[d].value()
                    ),
                    set_cmd=lambda val, o=out, d=demod: (
                        self.core.sigouts[o].amplitudes[d].value(val)
                    ),
                    unit="V",
                )

                # dbm power - attention: when setting dbm power,the 50Ohm out is automatiacally activated.
                def _get_power_dbm(o=out, d=demod):
                    vpk = self.core.sigouts[o].amplitudes[d].value()
                    return vpk_to_dbm(vpk)

                def _set_power_dbm(val, o=out, d=demod):
                    # Enable 50 Ohm output termination
                    self.core.sigouts[o].imp50(1)

                    # Convert dBm -> Vpk and set amplitude
                    vpk = dbm_to_vpk(val)
                    self.core.sigouts[o].amplitudes[d].value(vpk)

                self.core.add_parameter(
                    f"out{out + 1}_power{demod + 1}_dbm",
                    label=f"{name} out{out + 1} power {demod + 1} dBm",
                    get_cmd=_get_power_dbm,
                    set_cmd=_set_power_dbm,
                    get_parser=float,
                    unit="dBm",
                )

                # zi-nodes for output amplitudes
                getattr(
                    self.core,
                    f"out{out + 1}_amplitude{demod + 1}",
                ).zi_node = f"/SIGOUTS/{out}/AMPLITUDES/{demod}"

                self.core.add_parameter(
                    f"out{out + 1}_amplitude{demod + 1}_enable",
                    label=f"{name} out{out + 1} amplitude {demod + 1} enable",
                    get_parser=bool,
                    get_cmd=lambda o=out, d=demod: (
                        self.core.sigouts[o].enables[d].value()
                    ),
                    set_cmd=lambda val, o=out, d=demod: (
                        self.core.sigouts[o].enables[d].value(val)
                    ),
                )

            _adc_param = self.core.demods[demod].adcselect
            _original_set_raw = _adc_param.set_raw

            def _new_set_raw(this, val):
                _original_set_raw(val)
                if val == 0:
                    getattr(self.core, f"R{demod + 1}").unit = "V"
                elif val == 1:
                    getattr(self.core, f"R{demod + 1}").unit = "A"

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
