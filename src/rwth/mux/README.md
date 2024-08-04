# Hash's Multiplexer
QCoDeS and Python implementation of control for a multiplexer. The device is comprised of a PCA9544ADWR connecting to twelve MAX14661 (slave) ICs. It is controlled and interfaced via Arduino Due. This package allows for full control of the multiplexer through the VISA interface.

Features of this driver include:

1. Reset all the connections to 0 (all switches are open)
2. Setting and monitoring connections between multiple inputs and outputs
3. Querying and setting DAC and ADC values, including average value for ADC

# Installation
This pip package has only been tested with 'python>=3.7'. Please make sure to update your Python installation before proceeding with the installation. It is also always a good idea to keep 'pip' and 'setuptools' updated to prevent arbitrary installation issues. For the full list of app dependencies, check 'requirements.txt'. A separate 'venv' testing environment is suggested while the package is in production, and the tests are being built. Once the project is out of development and is pushed onto 'qcodes_contrib_drivers', this installation will not be needed.

Installation is supported using the GitLab instance of the project.
```
pip install git+ssh://git@gitlab.com/squad-lab/muxiutils.git
```

## Usage
For a detailed description on how QCoDeS drivers work, please look at their documentation. There are a lot of good examples to look at on the [QCoDeS](https://qcodes.github.io/Qcodes/examples/index.html) website.

We provide a description of how to use our driver. The Muxi class is initialized with a few parameters that need to be set:

1. name: A name for the multiplexer. This is used by QCoDeS to identify the device.
2. address: The address of the device.
3. BAUD: Baud rate for communication.

example usages are shown in mux_test.ipynb

QCoDeS Parameters Description

    
1. C{pin}_{output}: Connection between a specific input pin and an output channel. Values can be 0  (disconnected) or 1 (connected).
    
2. output_channel_{n}: Where n is the output channel number. Returns the list of input pins connected to that output.
    
3. input_channel_{n}: Where n is the input pin number. Returns the list of output channels connected to that input.
    
4. DAC: DAC voltage. Can be set within a specified range.
    
5. ADC: ADC voltage. Read-only.
    
6. getADCAverage(N_samples): Returns the average value of ADC over a specified number of samples.

