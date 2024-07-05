from qcodes import Instrument
from qcodes.parameters import Parameter

from typing import Any, Mapping
from time import sleep


class DiffConductance(Instrument):
    def __init__(
        self,
        name: str,
        current: Parameter,
        voltage: Parameter,
        curr_ampl: Instrument,
        volt_ampl: Instrument,
        volt_divider: float = 1.0,
        resistance: float = 0.0,
    ) -> None:
        """Conductance instrument class for calculating the conductance from a current and voltage parameter

        Args:
            name: name of the qcodes instrument
            current: parameter supposed to be measuring current
            voltage: parameter supposed to be measuring voltage
            curr_ampl: iv converter
            volt_ampl: differential voltage amplifier
            volt_divider: voltage divider
            resistance: resistance of the line
        """

        super().__init__(name)

        from scipy.constants import physical_constants

        self.cond_quantum = physical_constants["conductance quantum"][0]
        self.line_resistance = resistance
        self.curr_ampl = curr_ampl.gain()
        self.volt_ampl = volt_ampl.gain() / volt_divider

        self.current = current
        self.voltage = voltage

        self.add_parameter(
            "value",
            label="G",
            get_parser=float,
            get_cmd=self.get_conductance,
            unit="G0",
        )

    def get_current(self):
        if type(self.current) == float or type(self.current) == int:
            return self.current / self.curr_ampl
        else:
            return self.current() / self.curr_ampl

    def get_voltage(self):
        if type(self.voltage) == float or type(self.voltage) == int:
            return self.voltage / self.volt_ampl
        else:
            return self.voltage() / self.volt_ampl

    def get_resistance(self):
        return (self.get_voltage() / self.get_current()) - self.line_resistance

    def get_conductance(self):
        return (1 / self.get_resistance()) * (1 / self.cond_quantum)

    def get_idn(self) -> dict:
        idn_dict = {
            "vendor": "Conductance Wrapper",
            "model": "1.0",
            "serial": "1.0",
            "firmware": 1,
        }
        return idn_dict


class DiffResistance(DiffConductance):
    def __init__(
        self,
        name: str,
        current: Parameter,
        voltage: Parameter,
        curr_ampl: Instrument,
        volt_ampl: Instrument,
        volt_divider: float = 1.0,
        resistance: float = 0.0,
    ) -> None:
        """Resistance instrument class for calculating the conductance from a current and voltage parameter

        Args:
            name: name of the qcodes instrument
            current: parameter supposed to be measuring current
            voltage: parameter supposed to be measuring voltage
            curr_ampl: iv converter
            volt_ampl: differential voltage amplifier
            volt_divider: voltage divider
            resistance: resistance of the line
        """
        super().__init__(
            name,
            current,
            voltage,
            curr_ampl,
            volt_ampl,
            volt_divider,
            resistance,
        )

        self.add_parameter(
            "value",
            label="R",
            get_parser=float,
            get_cmd=super().get_resistance,
            unit="Ohm",
        )


class Current(Instrument):
    def __init__(
        self,
        name: str,
        current: Parameter,
        dac: Parameter,
        vccs_ampl: float,
        curr_ampl: Instrument,
    ) -> None:
        """Current instrument class for setting and getting the current

        Args:
            name: name of the qcodes instrument
            current: parameter supposed to be measuring current
            dac: dac parameter supposed to be setting the current
            vccs_ampl: vccs amplification
            curr_ampl: current amplifier
        """
        super().__init__(name)
        self.curr = current
        self.vccs_ampl = vccs_ampl
        self.curr_ampl = curr_ampl.gain()
        self.dac_ch = dac

        self.add_parameter(
            "value",
            label="Current",
            get_cmd=self._get_current,
            get_parser=float,
            set_cmd=self._set_current,
            unit="A",
        )

    def _set_current(self, dac_v: float) -> None:
        self.dac_ch(dac_v * self.vccs_ampl)

    def _get_current(self) -> float:
        return self.curr() / self.curr_ampl


class Voltage(Instrument):
    def __init__(
        self,
        name: str,
        voltage: Parameter,
        volt_ampl: Instrument,
        volt_divider: float = 1.0,
    ) -> None:
        """Voltage instrument class for setting and getting the current

        Args:
            name: name of the qcodes instrument
            voltage: parameter supposed to be measuring current
            volt_ampl: differential voltage amplifier
            volt_divider: voltage divider
        """
        super().__init__(name)
        self.volt = voltage
        self.volt_ampl = volt_ampl.gain()
        self.volt_divider = volt_divider

        self.add_parameter(
            "value",
            label="Voltage",
            get_cmd=self._get_voltage,
            get_parser=float,
            set_cmd=self._set_voltage,
            unit="V",
        )

    def _set_voltage(self, dac_v: float) -> None:
        self.volt(dac_v) / self.volt_divider

    def _get_voltage(self) -> float:
        return self.volt() / self.volt_ampl
