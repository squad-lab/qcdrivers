# %%

from drivers.keysight.vna.N52xx import N5234B
from qcodes.instrument import Instrument

import numpy as np

# %%

Instrument.close_all()

vna = N5234B(
    "vna", "TCPIP0::K-N5234B-52048.local::inst0::INSTR", data_format="DB"
)  # vna base driver: https://microsoft.github.io/Qcodes/_modules/qcodes/instrument_drivers/Keysight/N52xx.html

# %%

vna.frequency([100 * 1e6])

# %%

vna.frequency(np.linspace(100e6, 200e6, 201))


# %%

vna.close()

# %%
