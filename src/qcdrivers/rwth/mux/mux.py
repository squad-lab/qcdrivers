"""
Author: Harsh Bhardwaj, Xingyue Luo
Affiliation: Forschungszentrum Julich GmbH, Imperial College London
Updated: 24-07-2024
"""

import time
from functools import partial

import matplotlib.colors as colors
import matplotlib.pyplot as plt
import numpy as np
import pyvisa
from matplotlib.colors import LinearSegmentedColormap
from qcodes import validators as vals
from qcodes.instrument import VisaInstrument

"""
Creating a colourmap with name 'switch'
color poits: white, red, green 
"""
switch = LinearSegmentedColormap.from_list(
    "switch",
    (
        (0.000, (1.000, 1.000, 1.000)),
        (0.500, (1.000, 0.000, 0.020)),
        (1.000, (0.529, 0.910, 0.122)),
    ),
)

divnorm = colors.TwoSlopeNorm(vmin=-1, vcenter=0, vmax=1)

"""
Define list of valid pins, (49 and 50 are not in use)
number of input pins and output channels
"""
PINS = [i for i in range(1, 99) if i != 49 and i != 50]  # valid input pins on dsub

OUTS = [1, 2, 3, 4]  # 4 output channels
N_PINS = len(PINS)
N_OUTS = len(OUTS)


class Muxi(VisaInstrument):
    """
    Class to control a multiplexer via VISA

    The Muxi class controls and monitor the state of connections of multiplexer
    which has 96 inputs and 4 outputs
    """

    def __init__(self, name, address, BAUD, **kwargs):
        """
        Initialise the multiplexer

        This function set the initial settings for communication with the multiplexer

        Args:when PIN and OUT are
            name (str): name of OUT in OUTS, PIN in PINS, and  physical connections
            address (str): the address of the multiplexer read by computer
            BAUD (int): the rate of transmission of command to the multiplexer
        """
        super().__init__(name, address, terminator="\n", **kwargs)
        self.visa_handle.baud_rate = BAUD
        self.visa_handle.read_termination = "\r\n"
        self.visa_handle.write_termination = "\n"
        self.visa_handle.timeout = 20000  # 20000 milliseconds

        self.connect_message()

        self.visa_handle.clear()

        # adding 96*4 parameters for each possible physical connection
        for PIN in PINS:
            for OUT in OUTS:
                self.add_parameter(
                    name="C" + f"{PIN:02d}" + "_" + "0" + str(OUT),
                    label="",
                    initial_value=0,  # all connections start off as disconnected
                    get_cmd="MUX:STATUS? "
                    + f"{PIN:02d}"
                    + ","
                    + "0"
                    + str(OUT),  # used to query the current state of conections
                    get_parser=int,
                    set_cmd=partial(self.switch, PIN, OUT),  # change the connections
                    vals=vals.Enum(0, 1),  # only 0,1 i.e. off/on allowed values
                    docstring="Parameter for connection between input {PIN:d} and output {OUT:d}".format(
                        PIN=PIN, OUT=OUT
                    ),
                )

        # 4 parameters for each output channel
        for OUT in OUTS:
            self.add_parameter(
                name="output_channel" + "_" + str(OUT),
                label="",
                get_cmd=partial(self.pins_connected_to_channel, OUT),
                set_cmd=partial(
                    self.connect_multiple_pins_to_channel, OUT
                ),  # (dis)-connect PIN(s) to output channel, pass 96 element binary list
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
            )

        # add parametr or DAC and ADC with their respective get and set command
        self.add_parameter(
            name="DAC",
            label="",
            get_cmd=self.getDAC,
            set_cmd=self.setDAC,
            vals=vals.Numbers(0.55, 2.75),  # confine the value
        )

        self.add_parameter(
            name="ADC",
            label="",
            get_cmd=self.getADC,
        )

    def send_command(self, command):
        """
        Send command to multiplexer with proper timing

        This function clear the VISA handle's input and output buffers,
        then it send a command and return the response from multiplexer
        delay used to receive the response from muliplexer

        Args:
            command (str): command to be send

        Returns:
            the response from the multiplexer

        """
        try:
            response = self.visa_handle.query(command)
        except pyvisa.VisaIOError:
            self.visa.handle.clear()
            time.sleep(0.1)
            response = self.visa_handle.query(command)

        return response

    def switch(self, PIN, OUT, state):
        """
        Method to switch the state of connection

        This function constructs the command of switch
        i.e. MUX:SWITCH:ON 10, 2 (connecting input 10 to output 2)

        Args:
            PIN (int): input
            OUT (int): output
            state (int): connections (0 = switching successful, 128 = invalid pin/out/state,
                                      otherwise: faulty I2C communication)

        Return:
            state of the connection (if the response is not empty)

        Raises:
            None
        """
        if state == 0:
            temp = "OFF"
        elif state == 1:
            temp = "ON"
        else:
            return 128

        command = "MUX:SWITCH:" + temp + " " + str(PIN) + "," + str(OUT)
        response = self.send_command(command)
        return int(response) if response else None

    def reset(self):
        """
        Set all the connections to 0
        """
        response = self.send_command("*RST")
        time.sleep(0.1)
        return response

    def status(self, PIN, OUT):
        """
        Checking the state of connections

        This function send the query about the state of connection and receive response from multiplexer
        i.e. MUX:STATUS? 10, 2

        Args:
            PIN (int): input
            OUT (int): output

        Returns:
            response of connection state from multiplexer
        """
        command = "MUX:STATUS? " + str(PIN) + "," + str(OUT)
        response = self.send_command(command)
        return int(response) if response else None

    def full_status(self, plot=False):
        """
        Show the status of all the switches

        This function demonstrates the state of switches in a matrix and a colourmap
        with input 49 ad 50 not in use (-1 in the matix, white in plot)

        Args:
            plot (bool): colourmap

        Returns:
            switchMatrix
        """
        switchMatrix = np.zeros((N_PINS + 2, N_OUTS))
        switchMatrix[(49 - 1) : (51 - 1), :] = -1

        for OUT in OUTS:
            name = "output_channel_" + str(OUT)
            channel_status = self.parameters[name].get()
            switchMatrix[:48, OUT - 1] = channel_status[0:48]
            switchMatrix[50:, OUT - 1] = channel_status[48:]

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

        return switchMatrix

    def pins_connected_to_channel(self, OUT):
        """
        Gets the list of input pins connected to that output

        This funciton send command,
        i.e., MUX:FULLSTATUS:OUTPUT? 2
        to obtain the status of connection of each input pin to that output

        Args:
            OUT (int): output

        Returns:
            states of connections of all pins to that output
        """
        command = f"MUX:FULLSTATUS:OUTPUT? {OUT}"
        response = self.send_command(command)
        connected_pins = response.split(", ")[:-1] if response else []
        return connected_pins

    def outputs_connected_to_pin(self, PIN):
        """
        Gets the list of output channels connected to that output

        This funciton send command,
        i.e., MUX:FULLSTATUS:INPUT? 2
        to obtain the status of connection of each output to that input

        Args:
            PIN (int): input

        Returns:
            states of connections of all outputs to that input
        """
        command = f"MUX:FULLSTATUS:INPUT? {PIN}"
        response = self.send_command(command)
        connected_outputs = response.split(", ")[:-1] if response else []
        return connected_outputs

    def connect_multiple_pins_to_channel(self, OUT, input_switch_list):
        """
        An output connecting to multiple inputs

        Args:
            OUT (int): output
            input_switch_list (list of int): inputs that connected to that output

        Raise:
            ValueError("Invalid input switch list!")
        """
        if len(input_switch_list) == 96:
            input_switch_string = ",".join(map(str, input_switch_list)) + ","
            command = f"MUX:SETFULL:OUTPUT {OUT}, " + input_switch_string
            self.send_command(command)
        else:
            raise ValueError("Invalid input switch list!")

    def connect_multiple_channels_to_pin(self, PIN, output_switch_list):
        """
        An input connecting to multiple outputs

        Args:
            PIN (int): input
            output_switch_list (list of int): outputs that connected to that input

        Raise:
            ValueError("Invalid output switch list!")
        """
        if len(output_switch_list) == 4:
            output_switch_string = ",".join(map(str, output_switch_list)) + ","
            command = f"MUX:SETFULL:INPUT {PIN}," + output_switch_string
            self.send_command(command)
        else:
            raise ValueError("Invalid output switch list!")

    def setDAC(self, voltage):
        """
        Construct a command string to set the DAC's voltage

        Args:
            voltage (float): applied voltage
        """
        command = f"DAC:SETV {voltage}"
        self.send_command(command)

    def getDAC(self):
        """
        Get the DAC

        This function sending a command 'DAC:GETV?' to ask a response on DAC from multiplexer

        Returns:
            DAC
        """
        command = "DAC:GETV?"
        response = self.send_command(command)
        return float(response) if response else None

    def getADC(self):
        """
        Get the ADC

        This function sending a command 'ADC:GETV?' to ask a response on ADC from multiplexer

        Returns:
            ADC
        """
        command = "ADC:GETV?"
        response = self.send_command(command)
        return float(response) if response else None

    def getADCAverage(self, N_samples):
        """
        Get the average value of ADC

        This function sending a command 'ADC:AVERAGE?' to ask a response on average value of DAC
        over N samples from multiplexer

        Arg:
            N_samples (int): number of samples used in calculating mean

        Returns:
            DAC
        """
        command = f"ADC:AVERAGE? {N_samples}"
        response = self.send_command(command)
        return float(response) if response else None

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
