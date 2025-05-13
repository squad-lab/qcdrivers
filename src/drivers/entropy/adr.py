"""
Author: Lino Visser
Affiliation: Forschungszentrum Jülich GmbH
Updated: 13-05-2025
"""


from typing import Any

from qcodes import Instrument
import socket

from qcodes.validators import Numbers

class ADR(Instrument):

    def __init__(self, name: str, address: str, port: int, **kwargs: Any) -> None:
        """Qcodes driver for Entropy m-type ADR controlling temperature sweeps via PID.
        Control via TCP/IP commands provided by entropy manual.
        Allows temperature and resistance readings of all three sensors (4K, GGG, FAA).

        Args:
            name: name of the qcodes instrument
            address: the server's hostname or IP address 
            port: the port used by the server
        """
        super().__init__(name, **kwargs)
        self.HOST = address  # The server's hostname or IP address
        self.PORT = port  # The port used by the server

        self.s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.s.connect((self.HOST, self.PORT))
        data = self.s.recv(4096).decode('utf-8').strip('b').replace(',', '').replace('\\r\\n', '')
        print(str(data))
        # establish connection 
        self.s.send(b'DEVSEL ADR\r\n')
        data = self.s.recv(4096)

        def ask(cmd:str):
          return self.cmd        
        self.add_parameter('t4K',
                           label = '4K Stage',
                           get_cmd = f'QKELVIN 4k Stage\r\n',
                           get_parser = float,
                           unit = 'K',
                           vals = Numbers(min_value=0, max_value=350))
    	
        self.add_parameter('R4K',
                           label = 'R4K',
                           get_cmd = f'QOHM 4K Stage\r\n',
                           get_parser=float,
                           unit='Ohm',
                           vals=Numbers(min_value=0, max_value=10))
        
        self.add_parameter('GGG',
                           label = 'GGG',
                           get_cmd = f'QKELVIN GGG\r\n',
                           get_parser=float,
                           unit='K',
                           vals=Numbers(min_value=0, max_value=350)
        )

        self.add_parameter('RGGG',
                           label = 'RGGG',
                           get_cmd = f'QOHM GGG\r\n',
                           get_parser=float,
                           unit='Ohm',
                           vals=Numbers(min_value=0, max_value=350)
        )

        self.add_parameter('FAA',
                                label = 'FAA',
                                get_cmd = f'QKELVIN FAA\r\n',
                                get_parser=float,
                                unit='K',
                                vals=Numbers(min_value=0, max_value=350)
                )
        
        self.add_parameter('RFAA',
                        label = 'RFAA',
                        get_cmd = f'QOHM FAA\r\n',
                        get_parser=float,
                        unit='Ohm',
                        vals=Numbers(min_value=0, max_value=350)
        )

        self.add_parameter('compressor',
                                label = 'compressor',
                                get_cmd = f'QCOMPRESSOR\r\n',
                                get_parser=float,
                                unit='',
                                vals=Numbers(min_value=0, max_value=1)
                )

        self.add_parameter('magnetsense',
                                        label = 'magnetsense',
                                        get_cmd = f'QMAGNETSENSE\r\n',
                                        get_parser=float,
                                        unit='V',
                                        vals=Numbers(min_value=0, max_value=1)
                        )
        
        self.add_parameter('supplycurrent',
                                        label = 'supplycurrent',
                                        get_cmd = f'QSUPPLYCURRENT\r\n',
                                        get_parser=float,
                                        unit='A',
                                        vals=Numbers(min_value=0, max_value=1)
                        )
        
        self.add_parameter('supplyvoltage',
                                        label = 'supplyvoltage',
                                        get_cmd = f'QSUPPLYVOLTAGE\r\n',
                                        get_parser=float,
                                        unit='V',
                                        vals=Numbers(min_value=0, max_value=10)
                        )

        self.add_parameter('pressure',
                                        label = 'pressure',
                                        get_cmd = f'QVACUUM\r\n',
                                        get_parser=float,
                                        unit='mbar',
                                        vals=Numbers(min_value=0, max_value=1100)
                        )
        
    def ask_raw(self, cmd: str) -> str:
        self.s.send(bytes(cmd, 'utf-8'))
        data = float(self.s.recv(4096).decode('utf-8').strip('b').replace(',', '').replace('\r\n', '').split(' ')[0])
        return data

    def send_raw(self, cmd: str):
        self.s.send(bytes(cmd, 'utf-8'))
        self.s.send(bytes(f'\r\n', 'utf-8')) #has to send an empty return for the ADR socket to recieve again
        return 

    def tempreg(self, enable:bool = 0, temperature:float = 0.045, rate:float = None): # base value set to approx base T of adr cryostat
        """ PID control of magnet vs FAA stage temperature sensor, PID values can be changed in entropy GUI for specific ranges
        Args: 
        enable: turn PID loop on/off
        temperature: desired temperature
        rate: desired temperature ramp rate of PID loop
        """
        if rate:
            self.send_raw(f'XTEMPREG {enable} {temperature} {rate} \r\n')
        else: 
            self.send_raw(f'XTEMPREG {enable} {temperature} \r\n')

    def voltreg(self, enable:bool = 0, voltage:float = 0):
        """ PID control of magnet voltage
        Args: 
        enable: turn PID loop on/off
        voltage: desired magnet voltage
        """
        self.send_raw(f'XVOLTREG {enable} {voltage} \r\n')

    def startcompressor(self):
        """Starts pulse tube compressor
        """
        self.send_raw(f'STOPCOMPRESSOR  \r\n') # switched due to wrongly soldered relay

    def stopcompressor(self):
        """Stops pulse tube compressor
        """
        self.send_raw(f'STARTCOMPRESSOR \r\n')
       


# %%
