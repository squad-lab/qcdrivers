# AD75019 
The AD75019 is a versatile and high-speed analog switch array containing 256 switches in a 16 × 16 matrix. This matrix allows any X pin to be connected to any Y pin. 

Data is programmed into the AD75019 via a serial interface using the SIN (Serial Input) and SCLK (Serial Clock) pins, and then latched into place using the PCLK (Parallel Clock) pin. The shift register is dynamic, requiring a minimum clock rate of 20 kHz and a maximum up to 5 MHz. This high-speed operation allows for rapid configuration of the switch array, with loading times as short as 52 μs. For more information on timing, please see[1].

The data to control the switches is input serially through the SIN pin. The first bit input controls the switch at the intersection of row Y15 and column X15. Subsequent bits control the remaining columns of row Y15, followed by the rows Y14 down to Y0.

For 24*24 switching array
Four AD75019 chips are daisy chained with the SOUT output the end of the shift register, directly connected to the SIN input of the next AD75019. Each chip has a disabled range in X12-X15 and Y12-Y15, those inputs and outputs are physically grounded and the connection are prevented for user in the qcode drive. 

Features of this driver include:
1. Switch functionality allows the user to add a route and flush the configuration to the AD75019
2. Status query allows the user to check the state of a specific connection 
3. Print configuration displays the current configuration of AD75019 
4. Full Status visualization generates a matrix showing the current status of all switches 
5. Identification query  returns identification information for the device
7. Reset method resets the AD75019 switch to its default state (0)

# Usage 
For a detailed description on how QCoDeS drivers work, please look at their documentation. There are a lot of good examples to look at on the QCoDeS website.

The AD75019Controller class is initialized with a few parameters that need to be set:

1. name: The name for the AD75019 chip, sed by QCoDeS to identify the fridge
2. address: The VISA address of the instrument, which tells the system where to find and communicate with the device.
3. baud_rate: Sets the baud rate for serial communication
4. **kwargs: Any additional keyword arguments that need to be passed to the parent VisaInstrument class.

For example usages please check AD75019_test

# QCoDeS Parameters Description 
1. x_pins_{index}: index refers to the valid X pin (input pin) in the range [0-31], excluding the disabled pins {12, 13, 14, 15, 28, 29, 30, 31}.
2. y_pins_{index}: index refers to the valid Y pin (input pin) in the range [0-31], excluding the disabled pins {12, 13, 14, 15, 28, 29, 30, 31}. 
3. switch(x, y): This method allows you to create a connection between an X pin and a Y pin. It is equivalent to adding a route and flushing the configuration.
4. status(PIN, OUT): This parameter checks the current state of the connection between a specified X pin (PIN) and Y pin (OUT).


# Reference 
[1] Analog Devices.(2018) 16*16 Crosspoint
Switch Array: AD75019. https://www.analog.com/media/en/technical-documentation/data-sheets/ad75019.pdf [Accessed 14th June 2024]

