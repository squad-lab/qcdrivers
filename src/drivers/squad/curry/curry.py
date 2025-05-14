from qcodes import Instrument
from qcodes.parameters import Parameter


class VCCS(Instrument):
    def __init__(
        self,
        name: str,
    ) -> None:
        super().__init__(name)
        self._value = 1

        self.add_parameter(
            name="value",
            label="VCCS Amplification",
            get_cmd=self.get_value,
            set_cmd=self.set_value,
        )

    def set_value(self, val) -> None:
        self._value = val

    def get_value(self) -> float:
        return self._value


class VoltageDivider(Instrument):
    def __init__(
        self,
        name: str,
    ) -> None:
        super().__init__(name)
        self._value = 1

        self.add_parameter(
            name="value",
            label="Voltage Divider",
            get_cmd=self.get_value,
            set_cmd=self.set_value,
        )

    def set_value(self, val) -> None:
        self._value = val

    def get_value(self) -> float:
        return self._value


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
            "norm_value",
            label=f"Normalized Conductance {name}",
            get_parser=float,
            get_cmd=self.get_conductance,
            unit="G0",
        )

        self.add_parameter(
            "value",
            label=f"Conductance {name}",
            get_parser=float,
            get_cmd=self.get_raw_conductance,
            unit="S",
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

    def get_raw_conductance(self):
        return 1 / self.get_resistance()

    def get_idn(self) -> dict:
        idn_dict = {
            "vendor": "Differential Conductance Wrapper",
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
        self.remove_parameter("norm_value")
        self.add_parameter(
            "value",
            label="R",
            get_parser=float,
            get_cmd=super().get_resistance,
            unit="Ohm",
        )

    def get_idn(self) -> dict:
        idn_dict = {
            "vendor": "Differential Resistance Wrapper",
            "model": "1.0",
            "serial": "1.0",
            "firmware": 1,
        }
        return idn_dict


class Current(Instrument):
    def __init__(
        self,
        name: str,
        curr_setter: Parameter = None,
        curr_getter: Parameter = None,
        vccs: VCCS = None,
        curr_ampl: Parameter = None,
        curr_offset: float = 0,
    ) -> None:
        """
        Current instrument class for setting and getting the current

        Args:
            name: name of the qcodes instrument
            curr_setter: parameter supposed to be settig current
            curr_getter: parameter supposed to be getting current
            vccs: voltage controlled current source
            curr_ampl: IV converter amplification parameter
            curr_offset: Constant DC current offset for a given amplifier gain
        """
        super().__init__(name)
        self.curr_setter = curr_setter
        self.curr_getter = curr_getter
        self.curr_offset = curr_offset

        if vccs:
            self.vccs_ampl = vccs.value()
        else:
            self.vccs_ampl = 1

        if curr_ampl:
            self.curr_ampl = curr_ampl()
        else:
            self.curr_ampl = 1
        self.curr_setter = curr_setter
        self.curr_getter = curr_getter
        self.curr_offset = curr_offset

        if vccs:
            self.vccs_ampl = vccs.value()
        else:
            self.vccs_ampl = 1

        if curr_ampl:
            self.curr_ampl = curr_ampl()
        else:
            self.curr_ampl = 1

        self.add_parameter(
            "value",
            label="Current",
            get_cmd=self.get_current,
            get_parser=float,
            set_cmd=self.set_current,
            unit="A",
        )

    def set_current(self, i: float) -> None:
        self.curr_setter(i * self.vccs_ampl)
        self.curr_setter(i * self.vccs_ampl)

    def get_current(self) -> float:
        return (self.curr_getter() / self.curr_ampl) - self.curr_offset


class Voltage(Instrument):
    def __init__(
        self,
        name: str,
        volt_setter: Parameter = None,
        volt_getter: Parameter = None,
        volt_divider: VoltageDivider = None,
        volt_ampl: Parameter = None,
        volt_offset: float = 0,
    ) -> None:
        """
        Voltage instrument class for setting and getting the voltage

        Args:
            name: name of the qcodes instrument
            volt_setter: parameter supposed to be setting voltage
            volt_getter: parameter supposed to be measuring voltage
            volt_divider: voltage divider
            volt_ampl: differential voltage amplification parameter
            volt_offset: offset on the voltage measured
        """
        super().__init__(name)
        self.volt_setter = volt_setter
        self.volt_getter = volt_getter
        self.volt_offset = volt_offset

        if volt_divider:
            self.volt_divider = volt_divider.value()
        else:
            self.volt_divider = 1
        if volt_ampl:
            self.volt_ampl = volt_ampl()
            self.volt_ampl = volt_ampl()
        else:
            self.volt_ampl = 1

        self.add_parameter(
            "value",
            label="Voltage",
            get_cmd=self.get_voltage,
            get_parser=float,
            set_cmd=self.set_voltage,
            unit="V",
        )

    def set_voltage(self, v: float) -> None:
        self.volt_setter(v / self.volt_divider)

    def get_voltage(self) -> float:
        return (self.volt_getter() - self.volt_offset) / self.volt_ampl
