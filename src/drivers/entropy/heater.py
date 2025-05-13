
"""
Author: Lino Visser
Affiliation: Forschungszentrum Jülich GmbH
Updated: 13-05-2025
"""

import time
from typing import Any
from qcodes.validators import Numbers
import numpy as np 

from qcodes.instrument import Instrument


class Heater(Instrument):
    
    def __init__(self, name: str, current_source: Instrument, adr: Instrument, **kwargs: Any) -> None:
        """QCodes instrument to control the heater inside an entropy ADR cryostat. Uses ADR temperature sensors for PID and (Keithley) SMU as power output on heater. 

        Args:
            name: name of the qcodes instrument
            current_source: qcodes instrument which allows for a constant power output settable by current (curr) with a gettable voltage (volt)
            adr: qcodes instrument resembling ADR
        """

        super().__init__(name, **kwargs)

        self.current_source = current_source  
        self.adr = adr 
        self.current_arr = np.array([0,0.032,0.06,0.1,0.15,0.2,0.25,0.3,0.35,0.4]) #experimentally determined current and temperature array for current estimates in our specific adr
        self.temp_arr = np.array([3.2,3.5,4.2,5.8,9,12.7,17.3,23.1,29.2,35.7])
        self.kp = 0.3 # Proportional gain
        self.ki = 0.01 # Integral gain
        self.kd = 0 # Derivative gain

        def ask(cmd:str):
          return self.cmd      
          	
        self.add_parameter('current',
                           label = 'Heater Current',
                           get_cmd = f'current_source.curr()',
                           get_parser=float,
                           unit='A',
                           vals=Numbers(min_value=0, max_value=0.5))
        
        self.add_parameter('voltage',
                           label = 'Heater Voltage',
                           get_cmd = f'current_source.volt()',
                           get_parser=float,
                           unit='V',
                           vals=Numbers(min_value=0, max_value=21))
        
        self.add_parameter('t4K',
                                label = 'ADR Temperature',
                                get_cmd = f'adr.t4K()',
                                get_parser=float,
                                unit='K',
                                vals=Numbers(min_value=0, max_value=350)
                )

    def read_temperature(self):

        """
        Reads temperature on 4K plate of adr instrument
        """

        return self.adr.t4K()
        
    def read_voltage(self):
        """
        Reads voltage to determine power output of SMU
        """
        return self.current_source.volt() 
    
    def set_current(self, current = 0, curr_limit = 0.3):
        """
        Sets current on SMU
        Args: 
        current: current applied in amps
        curr_limit: current limit for PID loop
        """

        if current<=curr_limit and current >= 0:
            print(f"Setting current to: {current:.3f}")
            self.current_source.curr(current)
        else: 
            self.current_source.curr(curr_limit)
            print('Im at my limit')


    def ask_raw(self, cmd: str) -> str:
        self.s.send(bytes(cmd, 'utf-8'))
        data = float(self.s.recv(4096).decode('utf-8').strip('b').replace(',', '').replace('\r\n', '').split(' ')[0])
        return data

    def send_raw(self, cmd: str):
        self.s.send(bytes(cmd, 'utf-8'))
        self.s.send(bytes(f'\r\n', 'utf-8')) 
        return 

    def set_T(self, temperature:float = 4, duration:float = None, turnoff:bool = True):
        self.current_estimate = np.interp(temperature,self.temp_arr,self.current_arr)
        self.current_limit = self.current_estimate*1.5
        integral = 0.0
        last_error = 0.0
        self.start_time = time.time()
        self.last_time = time.time()


        
        try: 
            while True:
                current_time = time.time()
                dt = current_time - self.last_time
                if dt <= 0.0:
                    dt = 1e-16  # Prevent division by zero

                # Read sensors
                current_temperature = self.read_temperature()
                voltage = self.read_voltage()  # You can use this for monitoring or as an additional parameter
                
                # Calculate error between desired setpoint and measured temperature
                error = temperature - current_temperature
                
                # Proportional term
                P_out = self.kp * error
                
                # Integral term: accumulate the error over time
                integral += error * dt
                I_out = self.ki * integral
                
                # Derivative term: calculate the rate of change of error
                derivative = (error - last_error) / dt
                D_out = self.kd * derivative
                
                # Total PID output: this value can be interpreted as the adjustment to the current source
                output = self.current_estimate + P_out + I_out + D_out

                output = max(0, output)
                
                # Apply the computed output to your current source controlling the heater
                self.set_current(current = output, curr_limit=self.current_limit)
                
                # Debug/monitoring: print current values (optional)
                print(f"Temperature: {current_temperature:.3f}K, Voltage: {voltage:.3f}V, Error: {error:.3f}, PID Output: {keithley.curr():.3f}")
                
                # Update variables for next iteration
                last_error = error
                
                # Wait before next control cycle (this sleep interval can be adjusted as needed, this is required to be larger when multiple temperature sensors are currently turned on)
                time.sleep(1)

                start_time = time.time()
                if duration:
                    if time.time()-start_time<duration:
                        if not turnoff: 
                            print('Setting current to estimate.')
                            self.set_current(self.current_estimate)
                        elif turnoff:
                            print('Turning off heater.')
                            self.set_current(self.current_estimate)
                        break

        except KeyboardInterrupt:
            print("PID loop interrupted by user.") 
            if not turnoff: 
                print('Setting current to estimate.')
                self.set_current(self.current_estimate)
            elif turnoff:
                print('Turning off heater.')
                self.set_current(self.current_estimate)


