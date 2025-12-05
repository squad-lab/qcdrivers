"""
Author: Simon Schreibing
Affiliation: Forschungszentrum Jülich GmbH
Updated: 05-12-2025
"""


import pyvisa as visa
from qcodes.instrument import VisaInstrument

import time
import warnings

import numpy as np
import pandas as pd

import bisect
import io


# Current adress: "TCPIP0::134.94.110.228::inst0::INSTR"




class KeysightN5234B(VisaInstrument):
    
    def __init__(self, name: str, address: str, data_format: str = "DB", delay: float = 0, **kwargs):
        """QCodes driver for the communication and basic functions of a Keysight N5234B vector network analyzer.
        You can set th measurement window, RF power, averaging and read the four different S-parameters. The standarad data format is magnitude in dB and phase in degrees.

        Args:
            name: name of the qcodes instrument (e.g. 'vna')
            address: the server's hostname or IP address
            data_format (str, optional): The format in which data is saved. Choose from: "DB" - LogMag / Degrees "RI" - Real / Imaginary "MA" - Magnitude / Angle. Defaults to "DB".
            delay (float, optional): An artifical delay for sending commands. Defaults to 0.
        """
        super().__init__(name, address, **kwargs)

        # probe frequency (to be set)
        self.f_probe = None

        # default data format
        allowed_formats = {"DB", "RI", "MA"}
        if data_format not in allowed_formats:
            raise ValueError(f"{data_format} not a valid data format.")

        self.data_format = data_format

        self.delay = delay

        #Device parameter and limits
        self.freq_lower_limit = float(10e6)
        self.freq_upper_limit = float(43.5e9)


        self.address = address


        # create session with the device
        self.rm = visa.ResourceManager()
        self.session = self.rm.open_resource(self.address)
        print("Connected to Keysight NB5234B.")


        # add s parameters
        for sparam in ["S11", "S12", "S21", "S22"]:

            if self.data_format == "DB":
                components_with_unit = [("mag", "dB"), ("phase", "deg")]
                name_map = {"mag": "magnitude", "phase": "phase"}
                label_map = {"mag": "mag", "phase": "arg"}
            elif self.data_format == "RI":
                components_with_unit = [("real", ""), ("imag", "")]
                name_map = {"real": "real", "imag": "imag"}
                label_map = {"real": "Re", "imag": "Im"}
            elif self.data_format == "MA":
                components_with_unit = [("mag", ""), ("phase", "deg")]
                name_map = {"mag": "magnitude", "phase": "phase"}
                label_map = {"mag": "mag", "phase": "arg"}

            for comp, unit in components_with_unit:
                name = f"{sparam.lower()}_{name_map[comp]}"
                label = f"{label_map[comp]}({sparam})"

                self.add_parameter(
                    name,
                    label=label,
                    unit=unit,
                    get_cmd=self._get_s_parameter(sparam, comp),
                    set_cmd=False,
                )


        # frequency
        self.add_parameter(
            "frequency",
            label="f",
            unit="Hz",
            get_cmd=self._get_frequency,
            set_cmd=False,
        )

        # power
        self.add_parameter(
            "power",
            label="P",
            unit="dB",
            get_cmd=self._get_power,
            set_cmd=self._set_power,
        )

        # averaging
        self.add_parameter(
            "averaging",
            label="Avg",
            unit=None,
            get_cmd=self._get_averaging,
            set_cmd=self._set_averaging,
        )




    # -------------------------
    # static helper functions
    # -------------------------


    @staticmethod
    def vna_probe(frequncy: list, s_trace: list, f_probe: float):
        """
        method to get s paramter at certain probe frequency

        Args:
            frequency (list): list of frequency belonging to the measurement
            s_trace (list): measured s parameter trace [can be mag or phase]
            f_probe (float): frequency you would like to probe at in Hz

        Returns:
            s_value (float): fixed s value [can be mag or phase] at given probe frequency
        """

        if f_probe > np.max(frequncy) or f_probe < np.min(frequncy):
            raise ValueError(
                f"Probing frequency lies outside of frequency range ({np.min(frequncy)} to {np.max(frequncy)} Hz)"
            )

        i = bisect.bisect_left(frequncy, f_probe) - 1

        x0, x1 = frequncy[i], frequncy[i + 1]
        y0, y1 = s_trace[i], s_trace[i + 1]

        s_probe = y0 + (f_probe - x0) * (y1 - y0) / (x1 - x0)

        return float(s_probe)
    


    # -------------------------
    # SCPI I/O commands
    # -------------------------

    def read(self, msg: str):
        """Method to retrieve a status or message from the device

        Args:
            msg (str): Message or command send to the device

        Returns:
            str: Resturns the status or message the device returned
        """
        out = self.session.read(msg)
        # print(out.rstrip('\n'))
        time.sleep(self.delay)
        return out


    def query(self, msg: str):
        """Method to execute a command and retrieve its response from the device

        Args:
            msg (str): Message or command send to the device

        Returns:
            str: Resturns the status or message the device returned
        """
        out = self.session.query(msg)
        # print(out.rstrip('\n'))
        time.sleep(self.delay)
        return out


    def write(self, msg: str):
        """Method to execute a command

        Args:
            msg (str): Message or command send to the device
        """
        self.session.write(msg)
        # I am assuming you want ot sleep after writing?
        time.sleep(self.delay)




    # -------------------------
    # Data saving and transfer on the device
    # -------------------------

    def save(self, folder: str, filename: str, format: str):
        """Saves the displayed data in a .csv file

        Args:
            folder (str): Path where the file should be saved to
            filename (str): Name of the file
            format (str): The format in which data is saved. Choose from: "Displayed" - the format is the same as that in which it is displayed on the VNA screen. "RI" - Real / Imaginary "MA" - Magnitude / Angle "DB" - LogMag / Degrees
        """
        self.write(f':MMEM:MDIR "{folder}"')
        # save_command = f':MMEM:STOR:DATA "{folder}{filename}","CSV Formatted Data","Displayed","RI",{-1}'

        save_command = f':MMEM:STOR:DATA "{folder}{filename}","CSV Formatted Data","Displayed","{format}",{-1}'  # RI for real imaginari instead of LOGM (magnitude and phase)

        self.write(save_command)

    def data_transfer(self, folder: str, filename: str, delay=0):
        """_summary_

        Args:
            folder (str): Path where the file should be saved to
            filename (str): Name of the file
            delay (int, optional): An artifical delay for sending commands. Defaults to 0.

        Returns:
            Array: Retruns an array of the saved data

        Notes: Transfers only the first ca. 1000 entries, because of bandwidth limitions
        """
        transfer_command = f'MMEMory:TRANsfer? "{folder}{filename}"'
        
        return self.query(transfer_command)

    def _get_vna_data(self):
        """The data is locally saved on the integrated vna windows system and then transfered to the local pc"""
        # save & transfer
        folder = "D:\\Samples\\vna_readout_folder\\"
        filename = "temp.csv"

        self.save(folder, filename, format=self.data_format)
        csv_text = self.data_transfer(folder, filename)

        df = pd.read_csv(
            io.StringIO(csv_text), skiprows=6, skipfooter=3, engine="python"
        )
        return df


    # -------------------------
    # VNA window configuration
    # -------------------------

    def bandwidth(
        self,
        plt_start: int = 100e6,
        plt_stop: int = 1e9,
        plt_bw: int = 3.0e6,
        state: str = "ON",
        plt_points: int = 201,
    ):
        """Modifies the measured bandwidth and resolution

        Args:
            plt_start (int, optional): Start of the bandwidth. Defaults to 100e6.
            plt_stop (int, optional): End of the bandwidth. Defaults to 1e9.
            plt_bw (int, optional): Spe size of the measurement. Defaults to 3.0e6.
            state (str, optional): Toggles the continuous measurement on or off. Defaults to "ON".
            plt_points (int, optional): Number of data point for the measurement. Defaults to 201.

        Raises:
            ValueError: The state for continuous sweep must be either "ON" or "OFF"
            ValueError: The frequency must be over the device minimum frequency
            ValueError: The frequency must be under the device maximum frequency

        Returns:
            float: Returns the actual measurement parameters
        """
        plt_start = int(plt_start)
        plt_stop = int(plt_stop)
        plt_bw = int(plt_bw)
        state = str(state)
        plt_points = int(plt_points)

        if state == "on" or state == "oN" or state == "On":
            warnings.warn(
                'Input for bandwidth must be "ON" in capitals...but we changed it for you'
            )
            state = "ON"
        if state == "off" or state == "oFf" or state == "ofF" or state == "Off":
            warnings.warn(
                'Input for bandwidth must be "OFF" in capitals...but we changed it for you'
            )
            state = "OFF"
        if state != "ON" and state != "OFF":
            raise ValueError("Wrong input! The input for bandwidth must be ON or OFF!")

        # Check for input values
        if plt_start < self.freq_lower_limit or plt_stop < self.freq_lower_limit:
            raise ValueError(
                "Frequency is too low! Must be over " + str(self.freq_lower_limit) + " GHz."
            )
        if plt_start > self.freq_upper_limit or plt_stop > self.freq_upper_limit:
            raise ValueError(
                "Frequency is too high! Must be under "
                + str(self.freq_upper_limit)
                + " GHz."
            )

        self.write(f"SENS1:FREQ:STAR {plt_start}")
        self.write(f"SENS1:FREQ:STOP {plt_stop}")
        self.write(f"SENS1:BAND:RES {plt_bw}")
        self.write(f"SENS1:SWEep:POINts {plt_points}")
        self.write(f"INIT:CONT {state}")

        delay = self.query(f"SENS:SWE:TIME?")[:-1]
        plt_start_def = self.query("SENS1:FREQ:STAR?")[:-1]
        plt_stop_def = self.query("SENS1:FREQ:STOP?")[:-1]
        plt_bw_def = self.query("SENS1:BAND:RES?")[:-1]

        delay = float(delay)
        plt_start_def = float(plt_start_def)
        plt_stop_def = float(plt_stop_def)
        plt_bw_def = float(plt_bw_def)

        print(
            f"Start_f: {plt_start_def} Hz, Stop_f: {plt_stop_def} Hz, bandwidth: {plt_bw_def} Hz"
        )

        return delay, plt_start_def, plt_stop_def, plt_bw_def

    # -------------------------
    # getter and setter methods
    # -------------------------

    def _set_window(self, f_start, f_stop, f_points):
        self.bandwidth(plt_start=f_start, plt_stop=f_stop, plt_points=f_points)

    def _set_probe_frequency(self, freq: float):
        """
        method to set probe frequency: if you want to monitor full trace set it to None (default), if you want single value of S (mag or phase) type in probe frequency
        """
        self.f_probe = freq


    def _get_frequency(self):
        df = self._get_vna_data()
        f = df["Freq(Hz)"].to_numpy()
        return f

    def _set_power(self, src_pow=-60):
        self.write(f"SOURCE:POWER:LEVEL {src_pow}")
        # print(f"Power set to: {src_pow} dB")
        return self.get_power()

    def _get_power(self):
        pow = self.query(f"SOURCE:POWER:LEVEL?")
        return pow

    def _set_averaging(self, avg_count: int = 3):
        self.write(f"SENSE:AVERAGE:STATE ON")
        self.write(f"SENSE:AVERAGE:COUNT {avg_count}")

    def _get_averaging(self):
        avg = self.query("SENSE:AVERAGE:COUNt?")
        print(f"Averaging set to factor {avg}")
        return avg


    # -------------------------
    # s parameter configuration
    # -------------------------

    def configure_active_s_parameters(self, sparams: list[str]):
        """
        Activates s parater channel always on trace 1

        Args:
            sparams (list[str]): list of s parameters to be activated e.g. ["S11","S21"]
        """
        allowed = {"S11", "S12", "S21", "S22"}
        for s in sparams:
            if s not in allowed:
                raise ValueError(f"{s} not a valid s parameter.")

        self.write("DISP:WIND1:TRAC:DEL:ALL")  # delete old traces and parameters
        self.write("CALC:PAR:DEL:ALL")

        self.write("DISP:WIND1:STATE ON")  # open window

        for i, sp in enumerate(sparams):
            trace_name = f"{sp}_measurement"
            # create/define parameter (extended form)
            self.write(f'CALCulate:PARameter:DEFine:EXT "{trace_name}",{sp}')

            # select parameter to make it active (important)
            self.write(f'CALC:PAR:SEL "{trace_name}"')

            # feed to Trace i+1 (Trace indices start at 1)
            trace_index = i + 1
            self.write(f'DISPlay:WIND1:TRACe{trace_index}:FEED "{trace_name}"')


    def _get_s_parameter(self, s_parameter: str, component: str):
        # choose an parameter from the list and the component (mag or phase)
        # probe frequency is boolean, if you

        allowed_parameter = ("S11", "S12", "S21", "S22")
        allowed_component = ("mag", "phase")

        if s_parameter not in allowed_parameter:
            raise ValueError(
                f"The S-parameter is not allowed. Choose from: {allowed_parameter}"
            )
        if component not in allowed_component:
            raise ValueError(
                f"The component is not allowed. Choose from: {allowed_component}"
            )

        # build the key (e.g. "S11(DB)") from input
        if component == "mag":
            column_key = f"{s_parameter}(DB)"
        else:
            column_key = f"{s_parameter}(DEG)"

        def getter():
            df = self._get_vna_data()

            if column_key not in df.columns:
                raise KeyError(f"{column_key} not in VNA data trace.")

            # without probing -> full array back
            if self.f_probe is None:
                return df[column_key].to_numpy()

            else:
                # with probing -> single interpolated value back
                f_array = df["Freq(Hz)"].to_numpy()
                s_array = df[column_key].to_numpy()

                s_param_value = self.vna_probe(f_array, s_array, self.f_probe)

                return s_param_value

        return getter


    # -------------------------
    # close the device connection
    # -------------------------

    def close(self, exc_type = None, exc_value = None, traceback = None):
        """Closes the connection

        Args:
            exc_type (_type_): Just here so it works
            exc_value (_type_): Just here so it works
            traceback (_type_): Just here so it works
        """
        self.session.close()
        self.rm.close()
        print("Connection to Keysight NB5234B closed.")

        super().close()

