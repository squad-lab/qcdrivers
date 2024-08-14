from qcodes import VisaInstrument
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap
import matplotlib.colors as colors
import time

# Creating a colourmap with name 'switch'
# Color points: white, red, green
switch_cmap = LinearSegmentedColormap.from_list(
    "switch",
    [
        (0.0, (1.0, 1.0, 1.0)),  # White
        (0.5, (1.0, 0.0, 0.02)),  # Red
        (1.0, (0.529, 0.910, 0.122)),  # Green
    ],
)

divnorm = colors.TwoSlopeNorm(vmin=-1, vcenter=0, vmax=1)

x_pins = [i for i in range(32) if i not in {12, 13, 14, 15, 28, 29, 30, 31}]
y_pins = [j for j in range(32) if j not in {12, 13, 14, 15, 28, 29, 30, 31}]
N_x = len(x_pins)
N_y = len(y_pins)


class AD75019Controller(VisaInstrument):
    """
    The AD75019Controller class is used to control an AD75019 crosspoint switch
    using a serial interface via pyVISA and QCoDeS. This class provides methods for 
    configuring the switch, switching connections, querying connection statuses, 
    and visualizing the switch matrix status.
    """

    def __init__(self, name, address, baud_rate=9600, **kwargs):
        """
        Initialize the AD75019Controller instance.

        Args:
            name (str): name of the instrument.
            address (str): VISA address of the instrument.
            baud_rate (int): baud rate for serial communication (9600).
            **kwargs: Additional keyword arguments passed to the parent VisaInstrument class.

        Returns:
            None
        """
        super().__init__(name, address, **kwargs)
        self.visa_handle.baud_rate = baud_rate
        self.visa_handle.read_termination = "\r\n"
        self.visa_handle.write_termination = "\n"
        self.visa_handle.timeout = 20000  # 20000 milliseconds

        self.connect_message()
        self.visa_handle.clear()

        self.switch_matrix = np.zeros((32, 32), dtype=int)

        # Define the valid X and Y pins (excluding the disabled range)
        self.x_pins = [i for i in range(32) if i not in {12, 13, 14, 15, 28, 29, 30, 31}]
        self.y_pins = [j for j in range(32) if j not in {12, 13, 14, 15, 28, 29, 30, 31}]

    def configure_pins(self, pclk_pin, sclk_pin, sin_pin):
        """
        Configure the control pins for the AD75019 switch on Arduino.

        Args:
            pclk_pin (int): The pin number for the PCLK signal.
            sclk_pin (int): The pin number for the SCLK signal.
            sin_pin (int): The pin number for the SIN signal.

        Returns:
            None
        """
        self.pclk_pin = pclk_pin
        self.sclk_pin = sclk_pin
        self.sin_pin = sin_pin

    def send_command(self, command):
        """
        Send a command to the AD75019 switch via the VISA interface.

        Args:
            command (str): The command to send.

        Returns:
            None
        """
        self.visa_handle.write(command)

    def switch(self, x, y):
        """
        equivalent to add a route and flush the configuration.

        Args:
            x (int): X coordinate (input pin).
            y (int): Y coordinate (output pin).

        Returns:
            Response from the device after the route is added and configuration is flushed.
        """
        # Check if the route is within the disabled range
        if (12 <= x < 16) or (12 <= y < 16) or (28 <= x < 32) or (28 <= y < 32):
            print(f"Skipping route for x={x}, y={y} as it is in the disabled range.")
            return "Route skipped: disabled range"

        # Construct the command to add the route
        command = f'SWITCH {x},{y}'
        self.send_command(command)

        # Flush the configuration to apply the changes
        response = self.send_command('FLUSH')

        return response

    def status(self, PIN, OUT):
        """
        Checking the state of connections.

        Args:
            PIN (int): input pin number.
            OUT (int): output pin number.

        Returns:
            State of the connection. 1 for on, 0 for off, None if no response.
        """
        command = f"MUX:STATUS? {PIN},{OUT}"
        response = self.send_command(command)
        return int(response) if response else None
    '''
    def check_status(self):
        """
        Check and update the status of all valid connections.

        This function iterates over all valid PIN and OUT combinations
        and checks their current state using the status command.
        
        Args:
            None

        Returns:
            None
        """
        for PIN in self.x_pins:
            for OUT in self.y_pins:
                state = self.status(PIN, OUT)
                if state is not None:
                    self.switch_matrix[PIN, OUT] = state
    '''
    def reset(self):
        """
        Reset the AD75019 switch to its default state.

        Args:
            None

        Returns:
            None
        """
        time.sleep(0.1)
        self.send_command("*RST")
        # Optionally read response or delay if needed

    def printconfig(self):
        """
        Print the current configuration of the AD75019 switch.

        Args:
            None

        Returns:
            configuration matrix
        """
        self.send_command('PRINT')
        response = self.visa_handle.read()
        return response

    def full_status(self, plot=False):
        """
        Show the status of all the switches.

        This function demonstrates the state of switches in a matrix and a colourmap
        with specific ranges set as invalid (-1 in the matrix, white in plot).

        Args:
            plot (bool): Whether to plot the status matrix.

        Returns:
            switchMatrix, which shows the status of all the switches.
        """
        switchMatrix = np.zeros((N_x + 8, N_y + 8))

        # Set invalid ranges
        switchMatrix[12:16, :] = -1
        switchMatrix[:, 12:16] = -1
        switchMatrix[28:32, :] = -1
        switchMatrix[:, 28:32] = -1

        for i in range(N_x):
            for j in range(N_y):
                if (i, j) not in switchMatrix:
                    switchMatrix[i, j] = 1  # Example logic; replace with actual switch status check

        if plot:
            fig, ax = plt.subplots()
            ax.imshow(
                np.transpose(switchMatrix),
                cmap=switch_cmap,
                norm=divnorm,
                origin="lower",
                extent=(0, 32, 0, 32),
            )
            plt.title("Switch Matrix State")
            plt.xlabel("X Pins")
            plt.ylabel("Y Pins")
            plt.xticks(np.arange(0, 32, 1), rotation=90, fontsize="9.5")
            plt.yticks(np.arange(0, 32, 1), rotation=0, fontsize="9.5")
            ax.set_aspect(4)
            fig = plt.gcf()
            fig.set_size_inches([15, 15])
            plt.tight_layout()
            plt.grid()
            plt.show()

        return switchMatrix
    
    '''
    def clear(self):
        """
        Clear the configuration buffer on the AD75019 switch.

        Args:
            None

        Returns:
            None
        """
        self.send_command('CLEAR')
    '''
    def close(self):
        """
        Close the VISA handle for the instrument.

        Args:
            None

        Returns:
            None
        """
        self.visa_handle.close()

    def get_idn(self):
        """
        Get the identification information for the AD75019 switch.

        Args:
            None

        Returns:
            A dictionary containing information of vendor, model, serial, and firmware.
        """
        vendor = "AG-BLUHM"
        model = "Arduino AD75019 Switch"
        serial = 1.0
        firmware = 1.0
        return {
            "vendor": vendor,
            "model": model,
            "serial": serial,
            "firmware": firmware,
        }
