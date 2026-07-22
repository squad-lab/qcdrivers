from qcodes import (
    VisaInstrument,
    validators as vals,
)
from qcodes.instrument import Instrument
from functools import partial
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap
import matplotlib.colors as colors
import pyvisa
import time

switch = LinearSegmentedColormap.from_list(
    "switch",
    (
        (0.000, (1.000, 1.000, 1.000)),
        (0.500, (1.000, 0.000, 0.020)),
        (1.000, (0.529, 0.910, 0.122)),
    ),
)


divnorm = colors.TwoSlopeNorm(vmin=-1, vcenter=0, vmax=1)


PINS = [i for i in range(1, 99) if i != 49 and i != 50]  # valid input pins on dsub
OUTS = [1, 2, 3, 4]  # 4 output channels
N_PINS = len(PINS)
N_OUTS = len(OUTS)

# Trouble shooting tips:
# clearing device buffers mux.device_clear() after failed communication often fixes the problem


class Muxi(VisaInstrument):  # short for Muximillian
    """

    QCoDes driver for our Arduino based 96 to 4 multiplexer.
    Each connection is represented by a parameter of the form Cxx_yy
    where xx = 01,02,03...47,48,51,52...97,98 is the input channel (Attention : no 49 and 50!)
    and yy = 01,02,03,04 is the output channel


    pins = inputs
    channel/out = outputs

    """

    def __init__(self, name, address, BAUD, **kwargs):

        super().__init__(name, address, terminator="\n", **kwargs)

        # visa communication setup
        self.visa = self.visa_handle
        self.visa_handle.baud_rate = BAUD
        self.visa_handle.read_termination = "\r\n"
        self.visa_handle.write_termination = "\n"
        self.visa_handle.timeout = 20000
        self.connect_message()
        time.sleep(2.0)
        self.flush_input()

        # adding 96*4 parameters for each possible physical connection
        # for PIN in PINS:
        #     for OUT in OUTS:
        #         self.add_parameter(
        #             name="C" + f"{PIN:02d}" + "_" + "0" + str(OUT),
        #             label="",
        #             initial_value=0,  # all connections start off as disconnected
        #             get_cmd="MUX:STATUS? " + f"{PIN:02d}" + "," + "0" + str(OUT),
        #             get_parser=int,
        #             set_cmd=partial(self.switch, PIN, OUT),
        #             vals=vals.Enum(0, 1),  # only 0,1 i.e. off/on allowed values
        #             docstring="Parameter for connection between input {PIN:d} and output {OUT:d}".format(
        #                 PIN=PIN, OUT=OUT
        #             ),
        #         )

        # 4 parameters for each output channel
        for OUT in OUTS:
            self.add_parameter(
                name="output_channel" + "_" + str(OUT),
                label="",
                get_cmd=partial(self.pins_connected_to_channel, OUT),
                set_cmd=partial(
                    self.connect_multiple_pins_to_channel_bit, OUT
                ),  # (dis)-connect PIN(s) to output channel, pass 96 element binary list
                snapshot_get=False,
            )

        # 96 parameters for each input channel
        for PIN in PINS:
            self.add_parameter(
                name="input_channel" + "_" + str(PIN),
                label="",
                get_cmd=partial(self.outputs_connected_to_pin, PIN),
                set_cmd=partial(
                    self.connect_multiple_channels_to_pin, PIN
                ),  # (dis)-connect output channels to input channel, pass 4 element binary list
                snapshot_get=False,
            )

        # DAC and ADC
        self.add_parameter(
            name="DAC",
            label="",
            get_cmd=self.getDAC,
            set_cmd=self.setDAC,
            vals=vals.Numbers(0.55, 2.75),
        )

        self.add_parameter(
            name="ADC",
            label="",
            get_cmd=self.getADC,
        )

    # bug : this reset does not work sometimes, be careful!
    def reset(self):
        self.ask("*RST")

    # turn off all 4 output channels one by one
    def full_reset(self):
        for OUT in OUTS:
            self.clear_output_channel(OUT)

    def switch(self, PIN, OUT, state):
        """
        Parameters
        ----------
        PIN : int
            input pin number, valid values 1-48 and 51-98
        OUT : int
            output channel number, valid values 1-4
        state : int 0/1
            0 : disconnect PIN from OUT
            1 : connect PIN to OUT

        Returns
        -------
            int : 0: switching succesful, 128: invalid pin/out/state, otherwise: faulty I2C commnunication on board

        """
        if state == 0:
            temp = "OFF"
        elif state == 1:
            temp = "ON"
        else:
            return 128

        return int(self.ask("MUX:SWITCH:" + temp + " " + str(PIN) + "," + str(OUT)))

    def status(self, PIN, OUT):
        """

        Parameters
        ----------
        PIN : int
            input pin number, valid values 1-48 and 51-98
        OUT : int
            output channel number, valid values 1-4

        Returns
        -------
            int: status of connection between PIN and OUT 1:connected, 0:disconnected, 128: invalid pin/out, 255: faulty I2C communication on board

        """
        return int(self.ask("MUX:STATUS? " + " " + str(PIN) + "," + str(OUT)))

    def full_status(self, plot=False):
        switchMatrix = np.zeros((N_PINS + 2, N_OUTS))
        switchMatrix[(49 - 1) : (51 - 1), :] = -1
        # invalid connections (PIN = 49,50)

        for OUT in OUTS:
            name = "output_channel_" + str(OUT)
            channel_status = self.parameters[name].get()
            switchMatrix[:48, OUT - 1] = channel_status[0:48]  # first 48 input  pins
            switchMatrix[50:, OUT - 1] = channel_status[48:]  # the other 48 input pins

        if plot:
            fig, ax = plt.subplots()
            ax.imshow(
                np.transpose(switchMatrix),
                cmap=switch,
                norm=divnorm,
                origin="lower",
                extent=(1, 99, 1, 5),
            )
            plt.title("Switch matrix state")
            plt.xlabel("Input Channels")
            plt.ylabel("Output Channels")
            plt.xticks(np.arange(1, 99, 1), rotation=90, fontsize="8")
            plt.yticks([1, 2, 3, 4])
            ax.set_aspect(4)
            fig = plt.gcf()
            fig.set_size_inches([16.55, 3.56])
            plt.tight_layout()
            plt.grid()
            plt.show()
            mngr = plt.get_current_fig_manager()
            mngr.window.setGeometry(177, 196, 1655, 390)

            # idea for future: one can make the matrix interactive and switch on/off by double click etc.

        return switchMatrix

    def pins_connected_to_channel(self, OUT):
        # returns all pins connected to channel OUT
        s = self.ask(f"MUX:FULLSTATUS:OUTPUT? {OUT}")
        tokens = [t.strip() for t in s.split(",") if t.strip() != ""]
        return np.array([int(t) for t in tokens], dtype=int)

    def outputs_connected_to_pin(self, PIN):
        # returns all channels connected to in put PIN
        outputs_string = self.ask(f"MUX:FULLSTATUS:INPUT? {PIN}")
        connected_outputs = outputs_string.split(",")[:-1]
        return connected_outputs

    def connect_multiple_pins_to_channel(self, OUT, input_switch_list):
        # DEPRECATED!!!
        # input switch list should be a 96 entry list
        # eg. [1,1,1,0,0,0,...0] (0 = switch open, 1 = switch closed)
        # connect out to pin 1 2 3  and disconnect from everything else
        if len(input_switch_list) != 96:
            raise ValueError("input_switch_list must have length 96")

        s = ", ".join(
            str(int(x)) for x in input_switch_list
        )  # no trailing comma needed
        cmd = f"MUX:SETFULL:OUTPUT {OUT}, {s}"

        reply = self.ask(cmd).strip()
        if reply != "OK":
            raise RuntimeError(f"Unexpected SETFULL reply: {reply!r}")

    def connect_multiple_pins_to_channel_bit(self, OUT, input_switch_list):
        arr = np.asarray(input_switch_list)

        if arr.shape != (96,):
            raise ValueError("input_switch_list must have length 96")

        if not np.all((arr == 0) | (arr == 1)):
            bad = np.where(~((arr == 0) | (arr == 1)))[0]
            raise ValueError(f"Invalid values at indices {bad.tolist()}")

        bits = "".join("1" if x == 1 else "0" for x in arr)
        cmd = f"MUX:SBIT {OUT},{bits}"

        reply = self.ask(cmd).strip()
        if reply != "OK":
            raise RuntimeError(f"Unexpected SBIT reply: {reply!r}")

    def connect_multiple_channels_to_pin(self, PIN, output_switch_list):
        # output switch list should be a 4 entry list
        # eg. [1,0,0,1] (0 = switch open, 1 = switch closed)
        # connect pin to channel 1 and 4, and disconnect channel 2 and 3
        if len(output_switch_list) == 4:
            output_switch_string = ""
            for switch in output_switch_list:
                output_switch_string += str(switch) + ","

            self.write(f"MUX:SETFULL:INPUT {PIN}," + output_switch_string)
        else:
            print("Invalid output switch list!")

    def clear_output_channel(self, OUT):
        """disconnect everything from given channel 1,2,3,4"""
        self.connect_multiple_pins_to_channel_bit(OUT, np.zeros(96).astype(int))

    def clear_input_channel(self, PIN):
        """disconnect everything from given input channel 1,2,3,4...98"""
        self.connect_multiple_channels_to_pin(PIN, np.zeros(4).astype(int))

    def setDAC(self, voltage):
        self.ask(f"DAC:SETV {voltage}")

    def getDAC(self):
        return float(self.ask("DAC:GETV?"))

    def getADC(self):
        return float(self.ask("ADC:GETV?"))

    def getADCAverage(self, N_samples):
        return float(self.ask(f"ADC:AVERAGE? {N_samples}"))

    def get_idn(self):
        """
        This function gives the identification of he multiplexer

        Returns:
            identification
        """
        vendor = "AG-BLUHM"
        model = "Arduino Multiplexer"
        serial = 1.0
        firmware = 1.0
        return {
            "vendor": vendor,
            "model": model,
            "serial": serial,
            "firmware": firmware,
        }

    def flush_input(self):
        old_timeout = self.visa_handle.timeout
        self.visa_handle.timeout = 50
        try:
            while True:
                self.visa_handle.read()
        except pyvisa.errors.VisaIOError:
            pass
        finally:
            self.visa_handle.timeout = old_timeout


class MuxiPatternController(Instrument):
    def __init__(self, name, mux, patterns, superpatterns=None, **kwargs):
        super().__init__(name, **kwargs)
        self.mux = mux
        self.patterns = self._validate_patterns(patterns)
        self.superpatterns = self._validate_superpatterns(superpatterns)

        n_patterns = len(self.patterns)

        for out in (1, 2, 3, 4):
            self.add_parameter(
                name=f"out_{out}_pattern",
                vals=vals.Ints(0, n_patterns - 1),
                get_cmd=None,
                set_cmd=lambda idx, out=out: self._apply_pattern(out, idx),
                initial_cache_value=0,
                snapshot_get=False,
            )

        if self.superpatterns is not None:
            self.add_parameter(
                name="super_pattern",
                vals=vals.Ints(0, len(self.superpatterns) - 1),
                get_cmd=None,
                set_cmd=self._apply_superpattern,
                initial_cache_value=0,
                snapshot_get=False,
            )

    def _validate_patterns(self, patterns):
        validated = []

        for pattern in patterns:
            arr = np.asarray(pattern)

            if arr.shape != (96,):
                raise ValueError(f"Pattern must have shape (96,), got {arr.shape}")

            if not np.all((arr == 0) | (arr == 1)):
                raise ValueError("Pattern values must be 0 or 1")

            validated.append(arr.astype(int))

        if len(validated) == 0:
            raise ValueError("patterns must not be empty")

        return validated

    def _validate_superpatterns(self, superpatterns):
        if superpatterns is None:
            return None

        validated = []
        n_patterns = len(self.patterns)

        for sp in superpatterns:
            if len(sp) != 4:
                raise ValueError(f"Each superpattern must have length 4, got {sp}")

            parsed = tuple(int(x) for x in sp)

            for idx in parsed:
                if idx < 0 or idx >= n_patterns:
                    raise ValueError(
                        f"Superpattern contains invalid pattern index {idx}"
                    )

            validated.append(parsed)

        return validated

    def _apply_pattern(self, out, idx):
        idx = int(idx)
        pattern = self.patterns[idx]
        getattr(self.mux, f"output_channel_{out}")(pattern)

    def _apply_superpattern(self, idx):
        idx = int(idx)
        sp = self.superpatterns[idx]

        for out, pattern_idx in enumerate(sp, start=1):
            pattern = self.patterns[pattern_idx]
            getattr(self.mux, f"output_channel_{out}")(pattern)

        self.out_1_pattern.cache.set(sp[0])
        self.out_2_pattern.cache.set(sp[1])
        self.out_3_pattern.cache.set(sp[2])
        self.out_4_pattern.cache.set(sp[3])
