from qcodes import Instrument
from qcodes.parameters import Parameter

from typing import Any, Mapping
from time import sleep


class Conductance(Instrument):
    def __init__(
        self,
        name,
        current: Parameter,
        voltage: Parameter,
        curr_ampl: Instrument,
        volt_ampl: Instrument,
        volt_divider=1.0,
        delay=0.1,
        resistance=0.0,
    ):
        """Conductance instrument class for calculating the conductance from a current and voltage parameter

        Args:
            name: name of the qcodes instrument
            current: current parameter or float
            voltage: voltage parameter or float
            curr_ampl: current amplifier
            volt_ampl: voltage amplifier
            volt_divider: voltage divider
            delay: delay at each measurement
            resistance: resistance of the line
        """

        super().__init__(name)

        from scipy.constants import physical_constants

        self.cond_quantum = physical_constants["conductance quantum"][0]
        self.line_resistance = resistance
        self.delay = delay
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
        sleep(self.delay)
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


class Resistance(Conductance):
    def __init__(
        self,
        name,
        current,
        voltage,
        curr_ampl,
        volt_ampl,
        volt_divider=1,
        delay=0.1,
        resistance=0,
    ):
        super().__init__(
            name,
            current,
            voltage,
            curr_ampl,
            volt_ampl,
            volt_divider,
            delay,
            resistance,
        )

        self.add_parameter(
            "value",
            label="R",
            get_parser=float,
            get_cmd=super().get_resistance,
            unit="Ohm",
        )


class CurrentSource(Instrument):
    def __init__(self, name) -> None:
        super().__init__(name)
