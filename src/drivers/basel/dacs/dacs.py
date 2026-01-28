# ----------------------------------------------------------------------------------------------------------------------------------------------
# LNHR DAC II QCoDeS driver
# v0.2.0
# Copyright (c) Basel Precision Instruments GmbH (2025)
#
# This program is free software: you can redistribute it and/or modify it under the terms of the GNU General Public License as published by the
# Free Software Foundation, either version 3 of the License, or any later version. This program is distributed in the hope that it will be
# useful, but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU
# General Public License for more details. You should have received a copy of the GNU General Public License along with this program.
# If not, see <https://www.gnu.org/licenses/>.
# ----------------------------------------------------------------------------------------------------------------------------------------------

# imports --------------------------------------------------------------

from drivers.basel.dacs.dacs_controller import BaselDac2Controller

from qcodes.station import Station
from qcodes.instrument import (
    VisaInstrument,
    InstrumentChannel,
    ChannelList,
    InstrumentModule,
)
from qcodes.parameters import ParameterWithSetpoints, create_on_off_val_mapping
import qcodes.validators as validate

from numpy import ndarray, array, linspace
from functools import partial
from dataclasses import dataclass
from time import sleep

# logging --------------------------------------------------------------

import logging

log = logging.getLogger(__name__)

# class ----------------------------------------------------------------


class BaspiLnhrdac2LockingValidator(validate.Validator):
    def __init__(self, submodule: any):
        """
        This class implements a validator that can be used to lock any submodule of the main instrument.
        The validator checks the locked-attribute inside the submodule. If True, the validator raises an error.

        Parameters:
        submodule: reference of submodule the locked-attribute is a part of

        Raises:
        ValueError: the submodule this parameter is a part of is locked
        """
        self.submodule = submodule

    def validate(self, value: any, context="BaspiLnhrdac2LockingValidator") -> None:
        """
        Validates if the locked-attribute is False.
        """

        if self.submodule.locked:
            raise ValueError(
                f"Submodule {self.submodule} has been locked and is currently not accessible."
            )


# class ----------------------------------------------------------------


class BaspiLnhrdac2Channel(InstrumentChannel):
    def __init__(
        self,
        parent: VisaInstrument,
        name: str,
        channel: int,
        controller: BaselDac2Controller,
    ):
        """
        Class that defines a channel of the LNHR DAC II with all its QCoDeS-parameters.

        Channel-Parameters:
        voltage (-10.0 V ... +10.0 V)
        high_bandwidth (ON/True: 100 kHz, OFF/False: 100 Hz)
        enable (ON/True: channel on, OFF/False: channel off)

        Parameters:
        parent: instrument this channel is a part of
        name: name of the channel
        channel: channel numnber
        controller: the controller the instrument uses for its communication
        """

        super().__init__(parent, name)

        self.voltage = self.add_parameter(
            name="voltage",
            unit="V",
            get_cmd=partial(controller.get_channel_dacvalue, channel),
            set_cmd=partial(controller.set_channel_dacvalue, channel),
            get_parser=BaselDac2Controller.dacval_to_vval,
            set_parser=BaselDac2Controller.vval_to_dacval,
            vals=validate.Numbers(min_value=-10.0, max_value=10.0),
            initial_value=0.0,
        )

        self.high_bandwidth = self.add_parameter(
            name="high_bandwidth",
            get_cmd=partial(controller.get_channel_bandwidth, channel),
            set_cmd=partial(controller.set_channel_bandwidth, channel),
            val_mapping=create_on_off_val_mapping(on_val="HBW", off_val="LBW"),
            initial_value=False,
        )

        self.enable = self.add_parameter(
            name="enable",
            get_cmd=partial(controller.get_channel_status, channel),
            set_cmd=partial(controller.set_channel_status, channel),
            val_mapping=create_on_off_val_mapping(on_val="ON", off_val="OFF"),
            initial_value=False,
        )


# class ----------------------------------------------------------------


class BaspiLnhrdac2AWG(InstrumentModule):
    def __init__(
        self,
        parent: VisaInstrument,
        name: str,
        awg: str,
        controller: BaselDac2Controller,
    ):
        """
        Class which defines an AWG (Arbitrary Waveform Generator) of the LNHR DAC II with all its QCoDeS-parameters.

        AWG-Parameters:
        channel (1 ... 12 or 13 ... 24, selecting AWG output)
        cycles (0 ... 4 000 000 000, amount of times the waveform is repeated)
        sampling_rate (0.000 01 s ... 4 000 s)
        length (0 ... 34 000, amount of data points)
        time_axis (gets automatically created, depending on AWG settings)
        waveform (-10.000000 V ... +10.000000 V)
        trigger (disable: no external trigger, start only: external trigger starts AWG waveform,
                start stop: AWG is started by a positive signal edge and stopped by a negative signal edge,
                single step: positive signal edge triggers every point of the waveform)
        enable (ON/True: start AWG, OFF/False: stop AWG)

        Parameters:
        parent: instrument this channel is a part of
        name: name of the channel
        awg: AWG designator
        controller: the controller the instrument uses for its communication
        """

        super().__init__(parent, name)
        self.__controller = controller

        self.locked = False

        if awg.lower() == "a" or awg.lower() == "b":
            board = "ab"
        elif awg.lower() == "c" or awg.lower() == "d":
            board = "cd"

        self.channel = self.add_parameter(
            name="channel",
            get_cmd=partial(controller.get_awg_channel, awg),
            set_cmd=partial(controller.set_awg_channel, awg),
            vals=validate.MultiTypeAnd(
                validate.Ints(min_value=1, max_value=24),
                BaspiLnhrdac2LockingValidator(self),
            ),
        )

        self.cycles = self.add_parameter(
            name="cycles",
            get_cmd=partial(controller.get_awg_cycles, awg),
            set_cmd=partial(controller.set_awg_cycles, awg),
            vals=validate.MultiTypeAnd(
                validate.Ints(min_value=0, max_value=4000000000),
                BaspiLnhrdac2LockingValidator(self),
            ),
            initial_value=0,
        )

        self.sampling_rate = self.add_parameter(
            name="sampling_rate",
            unit="s",
            get_cmd=partial(controller.get_awg_clock_period, board),
            set_cmd=partial(controller.set_awg_clock_period, board),
            get_parser=self.__get_parser_awg_sampling_rate,
            set_parser=self.__set_parser_awg_sampling_rate,
            vals=validate.MultiTypeAnd(
                validate.Numbers(min_value=0.00001, max_value=4000.0),
                BaspiLnhrdac2LockingValidator(self),
            ),
        )

        self.length = self.add_parameter(
            # Qcodes only value, not saved on device
            # must be set whenever self.waveform is set
            name="length",
            get_cmd=None,
            set_cmd=None,
            initial_value=0,
            vals=validate.MultiTypeAnd(
                validate.Ints(min_value=0, max_value=34000),
                BaspiLnhrdac2LockingValidator(self),
            ),
        )

        self.time_axis = self.add_parameter(
            name="time_axis",
            label="time",
            unit="s",
            get_cmd=partial(self.__get_awg_time_axis, awg),
            get_parser=partial(array, dtype=float),
            vals=validate.Arrays(shape=(self.length,)),
        )

        self.waveform = self.add_parameter(
            name="waveform",
            label=f"waveform AWG {awg.upper()}",
            unit="V",
            parameter_class=ParameterWithSetpoints,
            get_cmd=partial(self.__get_awg_waveform, awg),
            set_cmd=partial(self.__set_awg_waveform, awg),
            get_parser=partial(array, dtype=float),
            set_parser=list,
            setpoints=(self.time_axis,),
            vals=validate.Arrays(shape=(self.length,), min_value=-10.0, max_value=10.0),
        )

        self.trigger = self.add_parameter(
            name="trigger",
            get_cmd=partial(controller.get_awg_trigger_mode, awg),
            set_cmd=partial(controller.set_awg_trigger_mode, awg),
            val_mapping={
                "disable": 0,
                "start only": 1,
                "start stop": 2,
                "single step": 3,
            },
            vals=BaspiLnhrdac2LockingValidator(self),
            initial_value="disable",
        )

        self.enable = self.add_parameter(
            name="enable",
            get_cmd=partial(controller.get_awg_run_state, awg),
            set_cmd=partial(controller.set_awg_start_stop, awg),
            get_parser=BaspiLnhrdac2AWG.__get_parser_awg_enable,
            val_mapping=create_on_off_val_mapping(on_val="START", off_val="STOP"),
            vals=BaspiLnhrdac2LockingValidator(self),
            initial_value=False,
        )

        board = None

    # -------------------------------------------------

    @staticmethod
    def __get_parser_awg_sampling_rate(val: int) -> float:
        """
        Parsing method to convert the AWG sampling rate from us (micro seconds) to s (seconds).
        """

        return round(val / 1000000, 6)

    # -------------------------------------------------

    @staticmethod
    def __set_parser_awg_sampling_rate(val: float) -> int:
        """
        Parsing method to convert the AWG sampling rate from s (seconds) to us (micro seconds).
        """

        return int(val * 1000000)

    # -------------------------------------------------

    def __get_awg_time_axis(self, awg: str) -> list[float]:
        """
        Automatically creates the time axis for the saved waveform.

        Parameters:
        awg: selected AWG

        returns:
        list: list of time values for each voltage saved in the AWG waveform in s
        """

        board = {"a": "ab", "b": "ab", "c": "cd", "d": "cd"}
        memory_size = self.__controller.get_wav_memory_size(awg)
        clock_period = self.__controller.get_awg_clock_period(board[awg])

        increment = clock_period / 1000000
        time_axis = []
        for index in range(0, memory_size):
            time_axis.append(round(index * increment, 6))

        return time_axis

    # -------------------------------------------------

    def __get_awg_waveform(self, awg: str) -> list[float]:
        """
        Read the AWG waveform from device memory.

        Parameters:
        awg: selected AWG

        Returns:
        list: AWG waveform values in V (Volt)
        """

        memory = []
        block_size = 1000  # number of points read by get_wav_memory_block()
        memory_size = self.__controller.get_wav_memory_size(awg)
        adress_range_limit = memory_size // block_size
        if memory_size % block_size != 0:
            adress_range_limit += 1

        # read memory blocks (1000 points) instead of single adresses for faster reading
        for address in range(0, adress_range_limit):
            data = self.__controller.get_wav_memory_block(awg, address * block_size)
            last_value = data.pop()
            while last_value == "NaN":
                last_value = data.pop()
            data.append(last_value)
            memory.extend(data)

        if len(memory) != memory_size:
            raise MemoryError("Error occured while reading the devices memory.")

        return memory

    # -------------------------------------------------

    def __set_awg_waveform(self, awg: str, waveform: list[float]) -> None:
        """
        Write an AWG waveform into device memory. Memory is cleared before writing.

        Parameters:
        awg: selected AWG
        waveform: list of voltages (+/- 10.000000 V)
        """

        # check for lock
        validator = BaspiLnhrdac2LockingValidator(self)
        validator.validate(waveform)

        # check clock period
        dac_board = {"a": "ab", "b": "ab", "c": "cd", "d": "cd"}
        clock_period = self.__controller.get_awg_clock_period(dac_board[awg])

        self.__controller.clear_wav_memory(awg)

        for address in range(0, len(waveform)):
            self.__controller.set_wav_memory_value(
                awg, address, float(waveform[address])
            )

        sleep(0.2)  # sleep bc bad firmware
        memory_size = self.__controller.get_wav_memory_size(awg)

        if len(waveform) != memory_size:
            raise MemoryError("Error occured while writing to the devices memory.")

        self.__controller.write_wav_to_awg(awg)
        while self.__controller.get_wav_memory_busy(awg):
            pass

        # reset clock period bc gets changed by a ghost while write_wav_to_awg()
        if self.__controller.get_awg_clock_period(dac_board[awg]) != clock_period:
            self.__controller.set_awg_clock_period(dac_board[awg], clock_period)

    # -------------------------------------------------

    @staticmethod
    def __get_parser_awg_enable(val: bool) -> str:
        """
        Parsing method for the parameter "enable". Ensures correct function of val_mapping = create_on_off_val_mapping().
        Output of enable.get() has to be a valid input of enable.set().
        """

        if val:
            return "START"
        else:
            return "STOP"


# class ----------------------------------------------------------------


@dataclass
class BaspiLnhrdac2SWGConfig:
    """
    Dataclass to pass a configuration of the LNHR DAC II SWG module.

    Properties:
    shape: "sine", "cosine, "triangle", "sawtooth", "ramp", "rectangle", "pulse", "fixed noise", "random noise" or "DC"
    frequency: signal frequency in Hz (0.001 Hz - 10000 Hz)
    amplitude: signal amplitude in V (+/- 10.000 V)
    offset: signal DC-offset (+/- 10.000 V)
    phase: signal phaseshift in ° (deg) (+/- 360.000°)
    dutycycle: signal dutycycle in % (0.0 - 100.0), only applicable with shape "pulse"
    """

    shape: str
    frequency: float
    amplitude: float
    offset: float
    phase: float
    dutycycle: float

    # -------------------------------------------------

    def __post_init__(self):
        """default values for unspecified values"""
        if isinstance(self.shape, property):
            self.shape = "sine"
        if isinstance(self.frequency, property):
            self.frequency = 100.0
        if isinstance(self.amplitude, property):
            self.amplitude = 1.0
        if isinstance(self.offset, property):
            self.offset = 0.0
        if isinstance(self.phase, property):
            self.phase = 0.0
        if isinstance(self.dutycycle, property):
            self.dutycycle = 0.0

    # -------------------------------------------------

    def __check_min_max(
        self, val: int | float, min: int | float, max: int | float, prop: str
    ) -> None:
        """check validity of properties"""
        if isinstance(val, property):
            # do nothing if value is not specified
            return

        if not isinstance(val, (int, float)):
            raise ValueError(f"Configuration value {prop} is of not the correct type.")
        if val < min:
            raise ValueError(
                f"Configuration value {prop} is too small. Increase {prop} to {min}."
            )
        if val > max:
            raise ValueError(
                f"Configuration value {prop} is too big. Decrease {prop} to {max}."
            )

    # -------------------------------------------------

    @property
    def frequency(self) -> float:
        return self._frequency

    @frequency.setter
    def frequency(self, val: float) -> None:
        self.__check_min_max(val, min=0.001, max=10_000.0, prop="frequency")
        self._frequency = val

    @property
    def amplitude(self) -> float:
        return self._amplitude

    @amplitude.setter
    def amplitude(self, val: float) -> None:
        self.__check_min_max(val, min=-50.0, max=50.0, prop="amplitude")
        self._amplitude = val

    @property
    def offset(self) -> float:
        return self._offset

    @offset.setter
    def offset(self, val: float) -> None:
        self.__check_min_max(val, min=-10.0, max=10.0, prop="offset")
        self._offset = val

    @property
    def phase(self) -> float:
        return self._phase

    @phase.setter
    def phase(self, val: float) -> None:
        self.__check_min_max(val, min=-360.0, max=360.0, prop="phase")
        self._phase = val

    @property
    def dutycycle(self) -> float:
        return self._dutycycle

    @dutycycle.setter
    def dutycycle(self, val: float) -> None:
        self.__check_min_max(val, min=0.0, max=100.0, prop="dutycycle")
        self._dutycycle = val


# class ----------------------------------------------------------------


class BaspiLnhrdac2SWG(InstrumentModule):
    def __init__(
        self, parent: VisaInstrument, name: str, controller: BaselDac2Controller
    ):
        """
        Class defining the Standard Waveform Generator (SWG) module of the LNHR DAC II with all its Qcodes Parameters.
        The SWG can be used to create a waveform, which is then outputted by an AWG.

        SWG-Parameters:
        configuration (object of type BaspiLnhrdac2SWGConfig, to configure the SWG)
        apply (A, B, C or D, applies the configured waveform and saves it to the AWG A, B, C or D)

        Parameters:
        parent: instrument this channel is a part of
        name: name of the module
        controller: the controller the instrument uses for its communication
        """

        super().__init__(parent, name)
        self.__controller = controller

        self.configuration = self.add_parameter(
            name="configuration", get_cmd=None, set_cmd=self.__set_swg_configuration
        )

    # -------------------------------------------------

    def __set_swg_configuration(self, config: BaspiLnhrdac2SWGConfig) -> None:
        """
        Create a waveform using the standard waveform generator. The resulting waveform is automatically written into the waveform memory.

        config-Attributes:
        shape: "sine", "cosine, "triangle", "sawtooth", "ramp", "rectangle", "pulse", "fixed noise", "random noise" or "DC"
        frequency: signal frequency in Hz (0.001 Hz - 10000 Hz)
        amplitude: signal amplitude in V (+/- 10.000 V)
        offset: signal DC-offset (+/- 10.000 V)
        phase: signal phaseshift in ° (deg) (+/- 360.000°)
        dutycycle: signal dutycycle in % (0.0 - 100.0), only applicable with shape "pulse"

        Parameters:
        awg: selected AWG
        config: object containing SWG configuration
        """

        self.__controller.set_swg_new(True)

        # always use "adapt clock" here, clock gets checked again in swg.apply
        self.__controller.set_swg_adapt_clock(True)

        awg_shapes = {
            "sine": 0,
            "cosine": 0,
            "triangle": 1,
            "sawtooth": 2,
            "ramp": 3,
            "rectangle": 4,
            "pulse": 4,
            "fixed noise": 5,
            "random noise": 6,
            "DC": 7,
        }

        if config.shape not in awg_shapes:
            raise ValueError(
                f"Value '{config.shape}' is invalid. Valid values are: {list(awg_shapes.keys())}."
            )

        # specify waveform
        self.__controller.set_swg_shape(awg_shapes[config.shape])
        self.__controller.set_swg_desired_frequency(config.frequency)
        self.__controller.set_swg_amplitude(config.amplitude)
        self.__controller.set_swg_offset(config.offset)

        if config.shape == "cosine":
            self.__controller.set_swg_phase(config.phase + 90.0)
        else:
            self.__controller.set_swg_phase(config.phase)
        if config.shape == "rectangle":
            self.__controller.set_swg_dutycycle(50.0)
        elif config.shape == "pulse":
            self.__controller.set_swg_dutycycle(config.dutycycle)

    # -------------------------------------------------

    def apply(self, awg: str) -> None:
        """
        Apply the SWG configuration to an AWG waveform.

        Parameters:
        awg: selected AWG
        """

        awg = awg.lower()

        # set awgX.length parameter, also checks if AWG is locked
        wav_memory_size = self.__controller.get_wav_memory_size(awg)
        if awg == "a":
            self.parent.awga.length.set(wav_memory_size)
        elif awg == "b":
            self.parent.awgb.length.set(wav_memory_size)
        elif awg == "c":
            self.parent.awgc.length.set(wav_memory_size)
        elif awg == "d":
            self.parent.awgd.length.set(wav_memory_size)

        self.__controller.set_swg_wav_memory(awg)

        # decide on keep or adapt clock period
        other_awg = {"a": "b", "b": "a", "c": "d", "d": "c"}
        other_awg_size = self.__controller.get_awg_memory_size(other_awg[awg])
        if other_awg_size > 2:
            self.__controller.set_swg_adapt_clock(False)
        else:
            self.__controller.set_swg_adapt_clock(True)

        desired_frequency = self.__controller.get_swg_desired_frequency()
        nearest_frequency = self.__controller.get_swg_nearest_frequency()
        if nearest_frequency != desired_frequency:
            print(
                f"Frequency of {desired_frequency} Hz cannot be reached with the current settings. "
                + f"A frequency of {nearest_frequency} Hz is used instead. "
                + f"Changing AWG or clearing unused AWG waveforms might resolve this issue."
            )

        # apply SWG configuration to AWG waveform
        self.__controller.apply_swg_operation()
        self.__controller.write_wav_to_awg(awg)
        while self.__controller.get_wav_memory_busy(awg):
            pass

        awg_memory_size = self.__controller.get_awg_memory_size(awg)
        if awg_memory_size != wav_memory_size:
            if awg == "a":
                self.parent.awga.length.set(awg_memory_size)
            elif awg == "b":
                self.parent.awgb.length.set(awg_memory_size)
            elif awg == "c":
                self.parent.awgc.length.set(awg_memory_size)
            elif awg == "d":
                self.parent.awgd.length.set(awg_memory_size)


# class ----------------------------------------------------------------


@dataclass
class BaspiLnhrdac2Fast2dConfig:
    """
    Dataclass to pass a configuration of the LNHR DAC II Fast Scan 2D module.

    Properties:
    x_channel: channel of the x-axis (1 - 12)
    x_start_voltage: starting voltage of the x-axis in V (+/- 10.000000 V)
    x_stop_voltage: ending voltage of the x-axis in V (+/- 10.000000 V)
    x_steps: number of steps the x-axis voltage is incremented
    y_channel: channel of the y-axis (1 - 12)
    y_start_voltage: starting voltage of the x-axis in V (+/- 10.000000 V)
    y_stop_voltage: ending voltage of the x-axis in V (+/- 10.000000 V)
    y_steps: number of steps the y-axis voltage is incremented
    acquisition_delay: time for which each voltage step is outputted in s
    adaptive_shift: voltage shift in V which is applied to the x-axis, after every y-axis sweep (+/- 10.000000 V)
    """

    x_channel: int
    x_start_voltage: float
    x_stop_voltage: float
    x_steps: int
    y_channel: int
    y_start_voltage: float
    y_stop_voltage: float
    y_steps: int
    acquisition_delay: float
    adaptive_shift: float

    # -------------------------------------------------

    def __post_init__(self):
        """default values for unspecified values"""
        if isinstance(self.x_channel, property):
            self.x_channel = 1
        if isinstance(self.x_start_voltage, property):
            self.x_start_voltage = 0.0
        if isinstance(self.x_stop_voltage, property):
            self.x_stop_voltage = 1.0
        if isinstance(self.x_steps, property):
            self.x_steps = 10
        if isinstance(self.y_channel, property):
            self.y_channel = 2
        if isinstance(self.y_start_voltage, property):
            self.y_start_voltage = 0.0
        if isinstance(self.y_stop_voltage, property):
            self.y_stop_voltage = 1.0
        if isinstance(self.y_steps, property):
            self.y_steps = 10
        if isinstance(self.acquisition_delay, property):
            self.acquisition_delay = 0.0
        if isinstance(self.adaptive_shift, property):
            self.adaptive_shift = 0.0

    # -------------------------------------------------

    def __check_min_max(
        self, val: int | float, min: int | float, max: int | float, prop: str
    ) -> None:
        """check validity of properties"""
        if isinstance(val, property):
            # default values are not checked!
            return

        if not isinstance(val, (int, float)):
            raise ValueError(f"Configuration value {prop} is of not the correct type.")
        if val < min:
            raise ValueError(
                f"Configuration value {prop} is too small. Increase {prop} to {min}."
            )
        if val > max:
            raise ValueError(
                f"Configuration value {prop} is too big. Decrease {prop} to {max}."
            )

    # -------------------------------------------------

    @property
    def x_channel(self) -> int:
        return self._x_channel

    @x_channel.setter
    def x_channel(self, val: int) -> None:
        self.__check_min_max(val, min=1, max=12, prop="x_channel")
        self._x_channel = val

    @property
    def x_start_voltage(self) -> float:
        return self._x_start_voltage

    @x_start_voltage.setter
    def x_start_voltage(self, val: float) -> None:
        self.__check_min_max(val, min=-10.0, max=10.0, prop="x_start_voltage")
        self._x_start_voltage = val

    @property
    def x_stop_voltage(self) -> float:
        return self._x_stop_voltage

    @x_stop_voltage.setter
    def x_stop_voltage(self, val: float) -> None:
        self.__check_min_max(val, min=-10.0, max=10.0, prop="x_stop_voltage")
        self._x_stop_voltage = val

    @property
    def x_steps(self) -> int:
        return self._x_steps

    @x_steps.setter
    def x_steps(self, val: int) -> None:
        self.__check_min_max(val, min=10, max=16_777_216, prop="x_steps")
        self._x_steps = val

    @property
    def y_channel(self) -> int:
        return self._y_channel

    @y_channel.setter
    def y_channel(self, val: int) -> None:
        self.__check_min_max(val, min=1, max=12, prop="y_channel")
        self._y_channel = val

    @property
    def y_start_voltage(self) -> float:
        return self._y_start_voltage

    @y_start_voltage.setter
    def y_start_voltage(self, val: float) -> None:
        self.__check_min_max(val, min=-10.0, max=10.0, prop="y_start_voltage")
        self._y_start_voltage = val

    @property
    def y_stop_voltage(self) -> float:
        return self._y_stop_voltage

    @y_stop_voltage.setter
    def y_stop_voltage(self, val: float) -> None:
        self.__check_min_max(val, min=-10.0, max=10.0, prop="y_stop_voltage")
        self._y_stop_voltage = val

    @property
    def y_steps(self) -> int:
        return self._y_steps

    @y_steps.setter
    def y_steps(self, val: int) -> None:
        self.__check_min_max(val, min=1, max=16_777_216, prop="y_steps")
        self._y_steps = val

    @property
    def acquisition_delay(self) -> float:
        return self._acquisition_delay

    @acquisition_delay.setter
    def acquisition_delay(self, val: float) -> None:
        self.__check_min_max(val, min=0.00001, max=4000.0, prop="acquisition_delay")
        self._acquisition_delay = val

    @property
    def adaptive_shift(self) -> float:
        return self._adaptive_shift

    @adaptive_shift.setter
    def adaptive_shift(self, val: float) -> None:
        self.__check_min_max(val, min=-10.0, max=10.0, prop="adaptive_shift")
        self._adaptive_shift = val


# class ----------------------------------------------------------------


class BaspiLnhrdac2Fast2d(InstrumentModule):
    def __init__(
        self, parent: VisaInstrument, name: str, controller: BaselDac2Controller
    ):
        """
        Class which defines an adaptive fast 2D-scan of the LNHR DAC II with all its QCoDeS-parameters.

        2D-scan-Parameters:
        configuration (object of type BaspiLnhrdac2Fast2dConfig, to configure the fast 2D-scan)
        trigger_channel (13 ... 24, selecting a channel if the point out mode is used)
        trigger (disable: no trigger/ scan as fast as possible, line in: external trigger starts every x-axis sweep,
                line out: trigger is set with every x-axis sweep, point out: trigger is set with every x-axis step)
        x_axis (voltages in V of x-axis sweep, only gettable)
        y_axis (voltages in V of y-axis sweep, only gettable)
        enable (ON/True: start fast 2D-scan, OFF/False: stop fast 2D-scan)

        Parameters:
        parent: instrument this channel is a part of
        name: name of the channel
        controller: the controller the instrument uses for its communication
        """

        super().__init__(parent, name)
        self.__controller = controller
        self.__awg_trig = None
        self.__awg_xy = None
        self.__current_config = None

        self.configuration = self.add_parameter(
            name="configuration", get_cmd=None, set_cmd=self.__set_2d_configuration
        )

        self.trigger_channel = self.add_parameter(
            name="trigger_channel",
            get_cmd=self.__get_2d_trigger_channel,
            set_cmd=self.__set_2d_trigger_channel,
            vals=validate.Ints(min_value=13, max_value=24),
        )

        self.trigger = self.add_parameter(
            name="trigger", get_cmd=None, set_cmd=self.__set_2d_trigger
        )

        self.x_axis = self.add_parameter(
            name="x_axis", unit="V", get_cmd=self.__get_2d_x_axis, set_cmd=None
        )

        self.y_axis = self.add_parameter(
            name="y_axis", unit="V", get_cmd=self.__get_2d_y_axis, set_cmd=None
        )

        self.enable = self.add_parameter(
            name="enable",
            get_cmd=None,
            set_cmd=self.__set_2d_enable,
            val_mapping=create_on_off_val_mapping(on_val=True, off_val=False),
            initial_value=False,
        )

    # -------------------------------------------------

    def __set_2d_configuration(self, config: BaspiLnhrdac2Fast2dConfig) -> None:
        """
        Create an adaptive fast 2D-scan.

        config-Attributes:
        x_channel: channel of the x-axis (1 - 12)
        x_start_voltage: starting voltage of the x-axis in V (+/- 10.000000 V)
        x_stop_voltage: ending voltage of the x-axis in V (+/- 10.000000 V)
        x_steps: number of steps the x-axis voltage is incremented
        y_channel: channel of the y-axis (1 - 12)
        y_start_voltage: starting voltage of the x-axis in V (+/- 10.000000 V)
        y_stop_voltage: ending voltage of the x-axis in V (+/- 10.000000 V)
        y_steps: number of steps the y-axis voltage is incremented
        acquisition_delay: time for which each voltage step is outputted in s
        adaptive_shift: voltage shift in V which is applied to the x-axis, after every y-axis sweep (+/- 10.000000 V)

        Parameters:
        config: object containing 2D scan configuration
        """

        print(
            "Starting to configure fast adaptive 2D scan. AWG A will be repurposed. AWG A and AWG B connot be used while the 2D scan is running."
        )

        # check if AWG can be used
        if (
            not self.__controller.get_awg_run_state("a")
            and self.__controller.get_ramp_state("a") == 0
            and not self.__controller.get_awg_run_state("b")
            and self.__controller.get_ramp_state("b") == 0
        ):
            self.__awg_xy = "a"
        else:
            raise SystemError(
                f"During the setup of the fast adaptive 2D scan, AWG A and B must not run."
            )

        if self.__awg_xy == "a":
            self.parent.awga.locked = False

        # self.__controller.set_awg_channel(self.__awg_xy, config.y_channel)
        self.parent.awga.channel.set(config.y_channel)
        if not self.__controller.get_awg_channel_availability(self.__awg_xy):
            raise SystemError(
                f"The chosen y-axis output (channel {config.y_channel}) is not available."
            )

        self.__controller.set_ramp_channel(self.__awg_xy, config.x_channel)
        if not self.__controller.get_ramp_channel_availability(self.__awg_xy):
            raise SystemError(
                f"The chosen x-axis output (channel {config.y_channel}) is not available."
            )

        # calculate internal values, check for limits
        x_ramp_time = 0.005 * (config.x_steps + 1)
        y_step_size = (config.y_stop_voltage - config.y_start_voltage) / config.y_steps
        y_period = config.y_steps * config.acquisition_delay
        if y_period < 0.006:
            raise SystemError(
                f"The configured y-axis sweep is too short ({y_period:.3f} s). Minimal sweep time is 0.006 s. Increase number of steps or acquisition delay."
            )

        # set up x-axis
        self.__controller.set_ramp_starting_voltage(
            self.__awg_xy, config.x_start_voltage
        )
        self.__controller.set_ramp_peak_voltage(self.__awg_xy, config.x_stop_voltage)
        self.__controller.set_ramp_duration(self.__awg_xy, x_ramp_time)
        self.__controller.set_ramp_shape(self.__awg_xy, 0)
        self.__controller.set_ramp_cycles(self.__awg_xy, 1)
        self.__controller.select_ramp_step(self.__awg_xy, 1)

        # set up y-axis
        y_axis_waveform = []
        for step in range(0, config.y_steps + 1):
            y_axis_waveform.append(step * y_step_size)
        y_axis_waveform.append(config.y_start_voltage)
        y_axis_waveform = array(y_axis_waveform)

        self.parent.awga.trigger.set("disable")
        self.parent.awga.cycles.set(1)
        self.parent.awga.sampling_rate.set(config.acquisition_delay)
        self.parent.awga.length.set(len(y_axis_waveform))
        self.parent.awga.waveform.set(y_axis_waveform)

        # set up adaptive shift
        adaptive_scan = 1 if config.adaptive_shift != 0.0 else 0
        self.__controller.set_awg_start_mode(self.__awg_xy, 1)
        self.__controller.set_awg_reload_mode(self.__awg_xy, adaptive_scan)
        self.__controller.set_apply_polynomial(self.__awg_xy, adaptive_scan)

        # lock AWG to prevent User from manipulating/ breaking stuff
        self.parent.awga.locked = True
        self.parent.awgb.locked = True

        self.__current_config = config

        print("Fast adaptive 2D scan sucessfully configured. Ready to start.")

    # -------------------------------------------------

    def __get_2d_trigger_channel(self) -> int:
        """
        Gets the channel on which the point to point trigger is outputted.
        Only works for trigger mode "point out", for other modes use outputs on the back of the DAC.

        Returns:
        int: "point out" trigger output (13 ... 24)
        """

        if self.__awg_trig == "c":
            self.parent.awgc.locked = False
            channel = self.parent.awgc.channel.get()
            self.parent.awgc.locked = True
        else:
            channel = self.parent.awgc.channel.get()

        return channel

    # -------------------------------------------------

    def __set_2d_trigger_channel(self, channel: int) -> None:
        """
        Select the channel on which the point to point trigger is outputted.
        Only works for trigger mode "point out", for other modes use outputs on the back of the DAC.

        Parameters:
        channel: select "point out" trigger output (13 ... 24)
        """

        if self.__awg_trig == "c":
            self.parent.awgc.locked = False
            self.parent.awgc.channel.set(channel)
            self.parent.awgc.locked = True
        else:
            self.parent.awgc.channel.set(channel)

    # -------------------------------------------------

    def __set_2d_trigger(self, mode: str) -> None:
        """
        Set the trigger mode of fast 2D-scan.

        Parameters:
        mode: "disable": no trigger/ scan as fast as possible, "line in": external trigger starts every x-axis sweep,
                "line out": trigger is set with every x-axis sweep, "point out": trigger is set with every x-axis step

        """

        print(
            "Starting to configure fast 2D scan trigger. AWG C might be repurposed. AWG C and AWG D connot be used while the point to point trigger output is running."
        )

        fast2d_triggers = ("disable", "line in", "line out", "point out")

        if mode not in fast2d_triggers:
            raise ValueError(
                f"Value '{mode}' is invalid. Valid values are: {fast2d_triggers}."
            )

        if self.__current_config == None:
            raise SystemError(
                f"No fast 2D scan configuration available. Set configuration parameter first."
            )

        if (
            self.__controller.get_awg_run_state("a")
            or self.__controller.get_ramp_state("a") == 1
            or self.__controller.get_awg_run_state("b")
            or self.__controller.get_ramp_state("b") == 1
        ):
            raise SystemError(
                f"During the setup of the fast adaptive 2D scan trigger, all AWGs must not run."
            )

        self.parent.awga.locked = False
        self.parent.awgc.locked = False
        self.parent.awgd.locked = False
        if mode == "disable":
            self.__awg_trig = None
            self.parent.awga.trigger.set("disable")
            self.__controller.set_awg_start_mode(self.__awg_xy, 1)
            print(f"Fast 2D scan trigger now set to '{mode}'.")
            if self.__awg_xy == "a":
                self.parent.awga.locked = True
        elif mode == "line in":
            self.__awg_trig = None
            self.parent.awga.trigger.set("start only")
            self.__controller.set_awg_start_mode(self.__awg_xy, 0)
            print(
                f"Trigger mode '{mode}' cannot access channel {self.parent.fast2d.trigger_channel.get()}. Use 'Trig In AWG A' instead."
            )
            self.parent.awga.locked = True
        elif mode == "line out":
            self.__awg_trig = None
            self.parent.awga.trigger.set("disable")
            self.__controller.set_awg_start_mode(self.__awg_xy, 1)
            print(
                f"Trigger mode '{mode}' cannot access channel {self.parent.fast2d.trigger_channel.get()}. Use 'Sync Out AWG A' instead."
            )
            if self.__awg_xy == "a":
                self.parent.awga.locked = True
        elif mode == "point out":
            # choosing AWG for trigger
            if not self.__controller.get_awg_run_state(
                "c"
            ) and not self.__controller.get_awg_run_state("d"):
                self.__awg_trig = "c"
            else:
                raise SystemError(
                    f"During the setup of the fast 2D scan point by point trigger output, AWG C and D must not run."
                )

            # trigger signal must have 1/2 of sweeping frequency
            trig_config = BaspiLnhrdac2SWGConfig(
                shape="rectangle",
                frequency=float(1.0 / self.__current_config.acquisition_delay),
                amplitude=2.5,
                offset=2.5,
            )

            self.parent.swg.configuration.set(trig_config)
            self.parent.swg.apply("C")
            self.parent.awgc.cycles.set(self.__current_config.y_steps)
            self.parent.awgc.trigger.set("start only")
            if self.__awg_xy == "a":
                self.parent.awga.locked = True
            self.parent.awgc.locked = True
            self.parent.awgd.locked = True

            print(
                f"Trigger mode '{mode}' requires a physical connection inbetween the devices 'Sync Out AWG A' and 'Trig In AWG C' outputs."
            )
            print(
                f"Fast 2D scan trigger now set to '{mode}', using DAC channel {self.parent.fast2d.trigger_channel.get()}."
            )

    # -------------------------------------------------

    def __get_2d_x_axis(self) -> ndarray:
        """
        Get the x-axis voltage steps which are outputted in a x-axis sweep.

        Returns:
        ndarray: numpy array with voltage steps in V (+/- 10.000000 V)
        """

        if self.__awg_xy == "a":
            step_size = self.__controller.get_ramp_step_size(self.__awg_xy)
            number_steps = self.__controller.get_ramp_cycle_steps(self.__awg_xy)
            start_voltage = self.__controller.get_ramp_starting_voltage(self.__awg_xy)

            waveform = []
            for step in range(0, number_steps):
                waveform.append(round(start_voltage + (step * step_size), 6))

            return array(waveform, dtype=float)
        else:
            return array([], dtype=float)

    # -------------------------------------------------

    def __get_2d_y_axis(self) -> ndarray:
        """
        Get the y-axis voltage steps which are outputted in a y-axis sweep.

        Returns:
        ndarray: numpy array with voltage steps in V (+/- 10.000000 V)
        """

        if self.__awg_xy == "a":
            self.parent.awga.locked = False
            waveform = self.parent.awga.waveform.get()
            self.parent.awga.locked = True

            # delete last element (returns to starting value)
            waveform = list(waveform)
            waveform.pop()
            return array(waveform)
        else:
            return array([], dtype=float)

    # -------------------------------------------------

    def __set_2d_enable(self, enable: bool) -> None:
        """
        Start or stop the fast 2D-scan by software.

        Parameters:
        enable: start or stop 2D-scan
        """

        if enable:
            if self.__awg_xy == "a":
                self.parent.awga.locked = False
                self.parent.awga.enable.set(True)
                self.parent.awga.locked = True
                self.parent.awgb.locked = True
                print(
                    f"Fast adaptive 2D scan started with configuration {self.__current_config}."
                )
        elif self.__awg_xy == "a":
            self.__awg_xy = None
            self.__current_config = None
            self.parent.awga.locked = False
            self.parent.awgb.locked = False
            print(
                f"Fast adaptive 2D scan stopped. All AWGs can be used normally again."
            )


# class ----------------------------------------------------------------


class BaselDac2(VisaInstrument):
    def __init__(self, name: str, address: str):
        """
        Main class for integrating the Basel Precision Instruments
        LNHR DAC II into QCoDeS as an instrument.

        Parameters:
        name: name of the instrument
        address: VISA address of the instrument
        """

        super().__init__(name, address)

        # "library" of all DAC commands
        # not to be used outside of this class definition
        # to only have a single interface to the device
        self.__controller = BaselDac2Controller(self)

        # visa properties for communication
        self.visa_handle.write_termination = "\r\n"
        self.visa_handle.read_termination = "\r\n"

        # get number of physicallly available channels
        # for correct further initialization
        channel_modes = self.__controller.get_all_mode()
        self.number_channels = len(channel_modes)
        if self.number_channels != 12 and self.number_channels != 24:
            raise SystemError(
                "Physically available number of channels is not 12 or 24. Please check device."
            )

        # create channels and add to instrument
        # save references for later grouping
        channels = {}
        for channel_number in range(1, self.number_channels + 1):
            name = f"ch{channel_number}"
            channel = BaspiLnhrdac2Channel(
                self, name, channel_number, self.__controller
            )
            channels.update({name: channel})
            self.add_submodule(name, channel)

        # grouping channels to simplify simoultaneous access
        all_channels = ChannelList(self, "all channels", BaspiLnhrdac2Channel)
        for channel_number in range(1, self.number_channels + 1):
            channel = channels[f"ch{channel_number}"]
            all_channels.append(channel)

        self.add_submodule("all", all_channels)

        if self.number_channels == 24:
            lower_board = ChannelList(self, "lower board", BaspiLnhrdac2Channel)
            for channel_number in range(1, 12 + 1):
                channel = channels[f"ch{channel_number}"]
                lower_board.append(channel)

            self.add_submodule("lower_board", lower_board)

            higher_board = ChannelList(self, "higher board", BaspiLnhrdac2Channel)
            for channel_number in range(13, 24 + 1):
                channel = channels[f"ch{channel_number}"]
                higher_board.append(channel)

            self.add_submodule("higher board", higher_board)

        # AWGs dependent on 12/24 channel version
        if self.number_channels == 12:
            awgs = ("a", "b")
        elif self.number_channels == 24:
            awgs = ("a", "b", "c", "d")

        for awg_designator in awgs:
            name = f"awg{awg_designator}"
            awg = BaspiLnhrdac2AWG(self, name, awg_designator, self.__controller)
            self.add_submodule(name, awg)

        # only one SWG module available
        name = "swg"
        swg = BaspiLnhrdac2SWG(self, name, self.__controller)
        self.add_submodule(name, swg)

        #  only one 2D scan module available
        name = "fast2d"
        fast2d = BaspiLnhrdac2Fast2d(self, name, self.__controller)
        self.add_submodule(name, fast2d)

        # display some information after instanciation/ initial connection
        print("")
        self.connect_message()
        print(
            "All channels have been turned off (1 MOhm Pull-Down to AGND) upon initialization "
            + "and are pre-set to 0.0 V if turned on without setting a voltage beforehand."
        )
        print("")

    # -------------------------------------------------

    def get_idn(self) -> dict:
        """
        Get the identification information of the device.

        Returns:
        dict: contains all QCodes required IDN fields
        """
        vendor = "Basel Precision Instruments GmbH (BASPI)"
        model = f"LNHR DAC II (SP1060) - {self.number_channels} channel version"

        hardware_info = self.__controller.get_serial()
        serial = hardware_info[37:51]
        software_info = self.__controller.get_firmware()
        firmware = software_info[18:33]

        idn = {"vendor": vendor, "model": model, "serial": serial, "firmware": firmware}

        return idn

    def ask_basel_controller(self, cmd: str):
        """
        This method sends a command directly to the Basel DAC II  and receives multiple answer lines.
        It is to slow for measurement acquisitions, since it relies on a timeout to determine the end of the answer.

        Parameters:
        command: command as per programmers manual of the device

        Returns:
        string: answer of the device for a query
        """

        answer = self.__controller.ask_multi_line(cmd)

        return answer

    def activate_dac_channels(
        self,
        channel_number_list: list[int] = linspace(1, 24, 24, dtype=int),
        high_bw=False,
    ):
        """Activate all DAC channels in the list with specified bandwidth setting and sets them to zero voltage.

        Args:
            dac_chan_numbers (list[int]): List of DAC channel numbers to activate.
            high_bandwidth (bool): Whether to set channels to high bandwidth mode.
        """

        all_channels = self.all

        for chan_number in channel_number_list:
            chan = all_channels[chan_number - 1]  # ChannelList is zero-indexed

            chan.high_bandwidth.set(high_bw)
            sleep(0.1)

            if chan.enable.get():
                continue
            else:
                sleep(0.1)
                chan.enable.set(True)
                sleep(0.1)
                chan.voltage.set(0.0)

    get_help_commands = lambda self: self.__controller.get_help_commands()
    get_help_control = lambda self: self.__controller.get_help_control()
    get_firmware = lambda self: self.__controller.get_firmware()
    get_serial = lambda self: self.__controller.get_serial()
    get_health = lambda self: self.__controller.get_health()
    get_ip = lambda self: self.__controller.get_ip()


# main -----------------------------------------------------------------

if __name__ == "__main__":
    # a little example on how to use this driver

    station = Station()
    dac = BaselDac2("dac", "TCPIP0::192.168.0.108::23::SOCKET")
    station.add_component(dac)
