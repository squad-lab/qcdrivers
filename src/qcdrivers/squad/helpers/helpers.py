
from qcodes.instrument import Instrument


class ShellInstrument(Instrument):
    def __init__(self, name: str, parameters: dict, **kwargs) -> None:
        """
        Shell instrument class for defining qcodes parameters from instruments with oddly behaving parameters, or to define new instruments with custom parameters

        Args:
            name: name of the qcodes instrument
            parameters (dict): dictionary of parameters to be added to the instrument, kwargs to qcodes.Instrument.add_parameter()
        """

        super().__init__(name, **kwargs)

        for key, parameter in parameters.items():
            self.add_parameter(key, **parameter)

    def get_idn(self) -> dict[str, str | None]:
        return {
            "vendor": "SQUAD Lab",
            "model": "Shell Instrument",
            "serial": None,
            "firmware": None,
        }


class Delay(Instrument):
    def __init__(self, name):
        super().__init__(name)

        self.num_time = 0

        # for sweep use: Sweep(time, point_delay, n_samples*point_delay, n_samples, start_delay=point_delay, delay=point_delay)
        self.add_parameter(
            "time",
            label="Time",
            get_cmd=self.get_time,
            set_cmd=self.set_time,
            unit="s",
        )

    # delay comes from Sweep and is handled in stepper
    def set_time(self, number):
        self.num_time += 1

    # lets you add time to your station and make snapshot possible (getter is needed)
    def get_time(self):
        return None

    def get_idn(self) -> dict[str, str | None]:
        return {
            "vendor": "SQUAD Lab",
            "model": "Delay",
            "serial": None,
            "firmware": None,
        }
