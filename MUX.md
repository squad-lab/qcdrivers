# Arduino Based Multiplexer
Forked over from course materials: [Research techniques](https://git.rwth-aachen.de/lino.visser/research-techniques-wiring-mux). Go through the examples there for a fuller explanation of the multiplexer and its use.

## The Multiplexer itself
A complete description of the multiplexer (Mux) is given in an excerpt of the master thesis of Harsh Bhardwaj which can be found [here](docs/Bhardwaj_Master_just_mux.pdf). There also the specifications are characterized and listed. A short summary is given here.
The multiplexer is essentially a switch matrix allowing to map four (BNC) output channels to 96 input channels (in a 100 pin D-Sub). The inner shield of the mux is thereby composed of 12 (16:2) multiplexing chips connected to a Arduino Due controlling the individual switches. The multiplexing shield (which is attached to the Arduino board) is depicted in the following. The 100 pin D-Sub is located in the middle of the board with the Mux chips located around it.
<img src="/docs/Mux_shield.JPG" alt="drawing" width="700"/>

The complete device in its housing then looks like this:<br />
<img src="/docs/Mux_total.JPG" alt="drawing" width="700"/><br />
Where the inputs are located at the top while the outputs and serial interface are on the side.

Additionally, the inbuild ADC and DAC modules of the Arduino can be used to read and supply a (low resolution) voltage. These are denoted by i,o in the following. The configuration of the output channels and serial connection can be seen here:<br />
<img src="/docs/Mux_side_view.JPG" alt="drawing" width="700"/><br />

In total this makes up for a switch matrix following this schematic indicating that every output can be indidvidually connected to every input:<br />
<img src="/docs/Mux_functional.JPG" alt="drawing" width="700"/><br />

## Adapters

Since the Mux only has a 96 pin D-Sub as input channels, various adapters have been designed to achieve greater compatibility with the remaining measurement environment in our group. However, the routing of the PCBs does not necessarily yield the same input pin mapping for every adapter. To compensate this transfer matrices can be used (for example for a [chainer PCB](util/mux_chainer_map.py) with which two multiplexers can be connected, doubling the number of output channels). Further matrices should be included in the same way. <br />
<img src="/docs/Mux_chainer.JPG" alt="drawing" width="700"/><br />
Image of the Mux chainer PCB with an alternative input pin mapping.

## Working with SCPI

The SCPI interface can be used entirely to control the Arduino Due board in python. This includes a single line command to check for (defective) dc lines. A complete list of commands (for both the SCPI and QCoDeS control can be found [here](commands.md)).

## Working with QCoDeS

A fully functional QCoDeS driver is included ([mux_qcodes_driver.py](Qcodes driver/mux_qcodes_driver.py)) allowing to fully integrate the multiplexer in complex experiments in which many (swept and measured) parameters from various instruments are included. To use this, a version of QCoDeS is required. The full documentation (and an installation guide) can be found at https://qcodes.github.io/Qcodes/. For the simple measurements, using pip should be sufficient. Plottr is suggested for viewing the database of later measurements. The mux driver must then be imported and (as before) the corresponding COM port must be determined.

## Line checking

For checking dc lines and their resistance (for example when building a setup or repairing), a repetitive measurement can be conducted to determine which lines are connected properly or shorted. For this, the firmware and QCoDeS driver contain single line commands to either use the SCPI or the wrapper to quickly find problems. Exeplary code is given in which this is continuously updated both for the [QCoDes](Examples/LineProbe.py) and the [SCPI](Examples/LineProbe.py) version.

## Measuring gate leakage

Inter-gate leakage is a common phenomenon in not ideal qubit devices which can significantly hinder experimental progress. Measuring the leakage between gate pairs in complex devices (~30 individually controllable gates) is tedious. For this reason we can use the mux as a switch matrix to perform this automatically. Since small currents are often measured, a source-measure-unit (SMU) is mostly used to apply a voltage at one gate and measure the current flowing in while a second gate is grounded and the rest is floated internally. Alternatively, this can be done by a voltage source (e.g. DAC) and a sensing unit (e.g. digital-multi-meter, DMM). This is all handled within the given programm. The QCoDeS semantic is used to create an experiment and store the results in the respective database (see 15 minutes to QCoDeS) due to the added complexity with additional instruments. 

## Muliplying the number of available lines

Arbirary waveform generator (AWG) sources are expensive (per channel) and often not required at all gates at a time. For this reason we can use the multiplexer (in combination with a resistive voltage adder (to maintain a voltage bias)) to electrically swich them to different gates during an experiment. An example (which will not be covered further but should outline the possibilities) is given in instruments.py



## Contributors 
The software for line checking and the leakage matrix in QCoDeS as well as the QCoDeS driver were written by Harsh Bhardwaj in his master thesis (see extract in materials). The ''real world'' example stems from current qubit experiements carried out in our group. 

