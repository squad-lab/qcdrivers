# BlueFors Utilities
QCoDeS and python implemenetation of control for BlueFors refrigerators. This package is similar to functionality provided by the `BlueFors` driver at the [contrib drivers](https://github.com/QCoDeS/Qcodes_contrib_drivers/tree/main/qcodes_contrib_drivers/drivers/BlueFors) repository, but is more up to date and exposes the control API of the fridge through python. The previous driver used just the logs created by the fridge, and did not allow for control. This driver uses the REST API provided by the BlueFors to control the fridge.

New features of this driver include:
1. Support for temperature control of the FSE, along with the standard BFTC
2. Support for setting, and changing heater settings through the BFTC
3. Support for setting temperatures with the PID controller provided by the BFTC
4. Support for setting the parameters of the PID controller

## Usage
For a detailed description on how QCoDeS drivers work, please look at their documentation. There are a lot of good examples to look at on the [QCoDeS](https://qcodes.github.io/Qcodes/examples/index.html) website.

What we provide is a description of how to use our driver. The `BlueFors` class is initialized with a few parameters that need to be set:
1. `name`: A name for the fridge. This is used by QCoDeS to identify the fridge
2. `log_location`: Location of the BlueFors log files
3. `bftc_ip`: IP Address of the BFTC as a string
4. `bftc_port`: Port of the BFTC as an integer
5. `fse_ip`: IP Address of the FSE as a string
6. `fse_port`: Port of the FSE as an integer
7. `bftc_channels`: A dictionary of the BFTC channels. The keys are the channel numbers, and the values are the names of the channels. The names are used to identify the channels in the QCoDeS parameters. An example is given below
```python
{1: "50k", 2: "4k", 3: "magnet", 5: "still", 6: "mxc"}
```
8. `heater_channels`: A dictionary of the heater channels. The keys are the channel numbers, and the values are the names of the channels. The names are used to identify the channels in the QCoDeS parameters. It is important that the heater names match the correspointing temperature sensor names in the `bftc_channels` dictionary. This determines whether or not a temperature parameter can be settable. An example is given below
```python
{3: "still", 4: "mxc"}
```
9. `fse_heater_channels`: A dictionary of the FSE heater channels. The keys are the channel numbers, and the values are the names of the channels. The names are used to identify the channels in the QCoDeS parameters
```python
{4: "fse"}
```
10. `timeout`: Timeout for the REST API calls to the BFTC and the FSE
11. `controller_timeout`: Timeout for the controller hardware


## QCoDeS Parameters Description
1. `p_{n}`: Where n is the index of the pressure sensor starting from 1. Returns the pressure in mbar.
2. `t_{name}`: Where n is the name of the temperature sensor according to the `bftc_channels` dictionary, it is just `t_fse` when you do have a FSE. Returns the temperature in Kelvin. If the same key exists in both the `bftc_channels` and the `heater_channels` dictionary, we assume that the temperature of that stage can be set through the REST API, using the PID controller. The setpoint can also be set through this parameter.
3. `pressure`: Returns a dictionary of all the pressures in the fridge.
4. `temperature`: Returns a dictionary of all the temperatures in the fridge.
5. `h_{name}`: Where n is the name of the heater according to the `heater_channels` dictionary. Returns the heater power in watt. The setpoint can also be set through this parameter.
6. `pid_{name}`: Where n is the name of the heater according to the `heater_channels` dictionary. Returns a dictionary of the PID parameters for the heater. The values for P, I, D can also be set through this parameter.
