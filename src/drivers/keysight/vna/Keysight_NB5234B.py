
# %%

import pyvisa as visa
import time
import warnings
import subprocess
import numpy as np

import bisect


# Current adress: 'TCPIP0::K-N5234B-52048.local::inst0::INSTR'

#%% helpers

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
        raise ValueError(f"Probing frequency lies outside of frequency range ({np.min(frequncy)} to {np.max(frequncy)} Hz)")
    
    i = bisect.bisect_left(frequncy, f_probe) - 1

    x0, x1 = frequncy[i], frequncy[i + 1]
    y0, y1 = s_trace[i], s_trace[i + 1]

    s_probe = y0 + (f_probe - x0) * (y1 - y0) / (x1 - x0)

    return float(s_probe)


# %%

###     Device parameter and limits
freq_lower_limit = float(10e6)
freq_upper_limit = float(43.5e9)


class KeysightN5234B:
    """Class for the communication and basic functions of a Keysight N5234B PNA

    Raises:
        ValueError: The delay must be a postive number
        ValueError: The state for continuous sweep must be either "ON" or "OFF"
        ValueError: The frequency must be over the device minimum frequency
        ValueError: The frequency must be under the device maximum frequency

    Returns:
        float: Returns the delay
    """

    # TODO : implement reading/setting calibration and instrument state
    # TODO : implement saving data on local client (not just V)

    device_type = "PNA"

    def __init__(self, address: str, delay: float = 0):
        """Initializes the opject

        Args:
            address (str): The IP address of the device
            delay (float, optional): An artifical delay for sending commands. Defaults to 0.
        """

        self.address = address
        self.delay = delay

    @property
    def delay(self):
        """Property decorator

        Returns:
            float: Returns delay as private variable
        """
        return self._delay

    @delay.setter
    def delay(self, value):
        """Setter method for delay function

        Args:
            value (float): Intermediate variable for checking condictions

        Raises:
            ValueError: The delay must be a postive number
        """
        value = float(value)
        if value < 0:
            raise ValueError("Delay must be positive!")
        if value > 10:
            warnings.warn("The delay was set quite high. This might take a while.")

        self._delay = value

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

    def __enter__(self):
        """Creates a session with the device

        Returns:
            self: Returns its own object
        """
        self.rm = visa.ResourceManager()
        self.session = self.rm.open_resource(self.address)

        print("Connected to Keysight NB5234B.")

        return self

    def __exit__(self, exc_type, exc_value, traceback):
        """Closes the connection

        Args:
            exc_type (_type_): Just here so it works
            exc_value (_type_): Just here so it works
            traceback (_type_): Just here so it works
        """
        self.session.close()
        self.rm.close()
        print("Connection to Keysight NB5234B closed.")


    def save(self, folder: str, filename: str, format: str):
        """Saves the displayed data in a .csv file

        Args:
            folder (str): Path where the file should be saved to
            filename (str): Name of the file
            format (str): The format in which data is saved. Choose from: "Displayed" - the format is the same as that in which it is displayed on the VNA screen. "RI" - Real / Imaginary "MA" - Magnitude / Angle "DB" - LogMag / Degrees
        """
        self.write(f':MMEM:MDIR "{folder}"')
        #save_command = f':MMEM:STOR:DATA "{folder}{filename}","CSV Formatted Data","Displayed","RI",{-1}'

        save_command = f':MMEM:STOR:DATA "{folder}{filename}","CSV Formatted Data","Displayed","{format}",{-1}'  # RI for real imaginari instead of LOGM (magnitude and phase)

        #print(f"Data saved in {folder}")
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
        #print(f"Data transfer from {folder}")
        return self.query(transfer_command)

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
        if plt_start < freq_lower_limit or plt_stop < freq_lower_limit:
            raise ValueError(
                "Frequency is too low! Must be over " + str(freq_lower_limit) + " GHz."
            )
        if plt_start > freq_upper_limit or plt_stop > freq_upper_limit:
            raise ValueError(
                "Frequency is too high! Must be under "
                + str(freq_upper_limit)
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

        print(f"Start_f: {plt_start_def} Hz, Stop_f: {plt_stop_def} Hz, bandwidth: {plt_bw_def} Hz")

        return delay, plt_start_def, plt_stop_def, plt_bw_def

    def set_power(self, src_pow=-60):
        self.write(f"SOURCE:POWER:LEVEL {src_pow}")
        #print(f"Power set to: {src_pow} dB")
        return self.get_power()

    def get_power(self):
        pow = self.query(f"SOURCE:POWER:LEVEL?")
        return pow

    def configure_averaging(self, avg_count: int = 3):
        self.write(f"SENSE:AVERAGE:STATE ON")
        self.write(f"SENSE:AVERAGE:COUNT {avg_count}")

    def get_averaging(self):
        avg = self.query("SENSE:AVERAGE:COUNt?")
        print(f"Averaging set to factor {avg}")
        return avg

    def reset(self, name: str):
        """Resets the device to factory settings.

        Args:
            name (str): Name of the device

        Raises:
            ValueError: The S-parameters have to be combinations of 1,2,3,4
        """
        name = str(name)

        # self.write('*RST')
        self.write("INIT:CONT ON")
        if float(self.query(f"SWE:TIME?")) <= 10.0e-2:
            print(name + " reset to default settings successful")
        else:
            warnings.warn(name + " reset to default settings NOT successful!")

    

    def configure_active_s_parameters(self, sparams: list[str]):
        """
        Activates s parater channel always on trace 1
        """
        allowed = {"S11", "S12", "S21", "S22"}
        for s in sparams:
            if s not in allowed:
                raise ValueError(f"{s} not a valid s parameter.")

  
        self.write("DISP:WIND1:TRAC:DEL:ALL")   # delete old traces and parameters
        self.write("CALC:PAR:DEL:ALL")

        self.write("DISP:WIND1:STATE ON") #open window


        for i, sp in enumerate(sparams):
            trace_name = f"{sp}_measurement"
            # create/define parameter (extended form)
            self.write(f'CALCulate:PARameter:DEFine:EXT "{trace_name}",{sp}')

            # select parameter to make it active (important)
            self.write(f'CALC:PAR:SEL "{trace_name}"')

            # feed to Trace i+1 (Trace indices start at 1)
            trace_index = i + 1
            self.write(f'DISPlay:WIND1:TRACe{trace_index}:FEED "{trace_name}"')



    def s_parameter(self, s_parameter: str, measurement_name: str = "MyMeas"):
        """Method for S-parameter measurement

        Args:
            measurement_name (str, optional): Name for measurement. Will be shown as title. Defaults to 'MyMeas'.
            s_parameter (str, optional): Decides which S-parameter are measured. Defaults to 'S21'.
        """
        allowed_parameter = (
            "S11",
            "S12",
            "S21",
            "S22",
        )

        if s_parameter not in allowed_parameter:
            raise ValueError("The S-parameter is not allowed")

        #self.write("SYST:FPReset")

        self.write("DISPlay:WINDow1:STATE ON")
        self.write(f'CALCulate:PARameter:DEFine:EXT "{measurement_name}",{s_parameter}')
        self.write(f'DISPlay:WINDow1:TRACe1:FEED "{measurement_name}"')

    def two_port_s_params(self):
        self.write("SYST:FPReset")  # potentially dangerous
        S_parameters = ["S11", "S12", "S21", "S22"]
        S_parameters = ["S21"]  # quick hack for resonator transmission
        self.write("DISPlay:WINDow1:STATE ON")
        for s in S_parameters:
            self.write(f'CALCulate:PARameter:DEFine:EXT "{s}_measurement",{s}')
        for i in range(len(S_parameters)):
            self.write(
                f'DISPlay:WINDow1:TRACe{i+1}:FEED "{S_parameters[i]}_measurement"'
            )


def discoverIP(mac: str):
    """Method to discover the IP address with a given MAC address.
    Works only if the IP is already in "arp" table.

    Args:
        mac (str): MAC address of the device

    Returns:
        address: Returns the IP addressv
    """
    mac = str(mac)
    cmd = f'arp -a | findstr "{mac}" '
    returned_output = subprocess.check_output(
        (cmd), shell=True, stderr=subprocess.STDOUT
    )
    parse = str(returned_output).split(" ", 1)
    ip = parse[1].split(" ")
    address = ip[1]
    print(ip[1])
    return address





#%%

from qcodes.instrument import Instrument, VisaInstrument, Parameter
import numpy as np
import io
import pandas as pd



class QCodesKeysightN5234B(VisaInstrument):
    def __init__(self, name: str, address: str, **kwargs):
        super().__init__(name, address, **kwargs)
        
    
        self.vna = KeysightN5234B(address)
        self.vna.__enter__()

        # Magnitude of S11
        self.add_parameter(
            "s11_magnitude",
            label="mag(S11)",
            unit="dB",
            get_cmd=self._get_s_parameter("S11", "mag"),
            set_cmd=False,
        )

        # Phase of S11
        self.add_parameter(
            "s11_phase",
            label="arg(S11)",
            unit="deg",
            get_cmd=self._get_s_parameter("S11", "phase"),
            set_cmd=False,
        )

        # Magnitude of S12
        self.add_parameter(
            "s12_magnitude",
            label="mag(S12)",
            unit="dB",
            get_cmd=self._get_s_parameter("S12", "mag"),
            set_cmd=False,
        )

        # Phase of S12
        self.add_parameter(
            "s12_phase",
            label="arg(S12)",
            unit="deg",
            get_cmd=self._get_s_parameter("S12", "phase"),
            set_cmd=False,
        )

        # Magnitude of S21
        self.add_parameter(
            "s21_magnitude",
            label="mag(S21)",
            unit="dB",
            get_cmd=self._get_s_parameter("S21", "mag"),
            set_cmd=False,
        )

        # Phase of S21
        self.add_parameter(
            "s21_phase",
            label="arg(S21)",
            unit="deg",
            get_cmd=self._get_s_parameter("S21", "phase"),
            set_cmd=False,
        )

        # Magnitude of S22
        self.add_parameter(
            "s22_magnitude",
            label="mag(S22)",
            unit="dB",
            get_cmd=self._get_s_parameter("S22", "mag"),
            set_cmd=False,
        )

        # Phase of S22
        self.add_parameter(
            "s22_phase",
            label="arg(S22)",
            unit="deg",
            get_cmd=self._get_s_parameter("S22", "phase"),
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

        # probe frequency
        self.f_probe = None

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


    #################

    def activate_s_parameter_channels(self, s_parameter_list: list[str]):
        self.vna.configure_active_s_parameters(s_parameter_list)
        print(f"Channel {s_parameter_list} opened.")

    def _set_window(self, f_start, f_stop, f_points):
        self.vna.bandwidth(plt_start=f_start, plt_stop=f_stop, plt_points=f_points)

    def _set_probe_frequency(self, freq: float):
        """
        method to set probe frequency: if you want to monitor full trace set it to None (default), if you want single value of S (mag or phase) type in probe frequency
        """
        self.f_probe = freq
    
    def _set_averaging(self, avg_count: int):
        self.vna.configure_averaging(avg_count)

    def _set_power(self, power):
        self.vna.set_power(src_pow=power)
    



    def _get_vna_data(self):
        """The data is localli saved on the integrated vna windows system and then transfered to the local pc"""
        # save & transfer
        folder = "D:\\Samples\\vna_readout_folder\\"
        filename = "temp.csv"

        self.vna.save(folder, filename, format="DB")
        csv_text = self.vna.data_transfer(folder, filename)

        df = pd.read_csv(io.StringIO(csv_text), skiprows=6, skipfooter=3, engine="python")
        return df

    ### getter method for S-parameters

    def _get_s_parameter(self, s_parameter: str, component: str):
        #choose an parameter from the list and the component (mag or phase)
        #probe frequency is boolean, if you 

        allowed_parameter = ("S11","S12","S21","S22")
        allowed_component = ("mag", "phase")

        if s_parameter not in allowed_parameter:
            raise ValueError(f"The S-parameter is not allowed. Choose from: {allowed_parameter}")
        if component not in allowed_component:
            raise ValueError(f"The component is not allowed. Choose from: {allowed_component}")

        #build the key (e.g. "S11(DB)") from input
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

                s_param_value = vna_probe(f_array, s_array, self.f_probe)

                return s_param_value
        
        return getter

    ###


    def _get_frequency(self):
        df = self._get_vna_data()
        f = df["Freq(Hz)"].to_numpy()
        return f
    

    def _get_power(self):
        return float(self.vna.get_power().strip())
  
    
    def _get_averaging(self):
        return float(self.vna.get_averaging().strip())


    def close(self):
        self.vna.__exit__(None, None, None)
        super().close()


# %%

