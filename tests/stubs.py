"""
Stand-ins for objects QCDrivers is handed by its callers.

The buffered nodes are handed sweep objects by QCUtils. Depending on QCUtils
here would invert the dependency -- QCUtils depends on QCDrivers -- so the
suite carries its own stub matching the ``SweepLike`` protocol the nodes are
written against.

"""

from typing import Sequence

import numpy as np

__all__ = ["Sweep"]


class Sweep:
    """Stand-in for ``qcutils.sweep.Sweep``, satisfying ``SweepLike``."""

    def __init__(
        self,
        parameter,
        start: int | float,
        stop: int | float,
        num: int = 0,
        delay: float = 0.0,
        start_delay: float = 0.0,
    ) -> None:
        self.parameter = (
            list(parameter) if isinstance(parameter, Sequence) else [parameter]
        )
        self.start = start
        self.stop = stop
        self.num = num
        self.delay = delay
        self.start_delay = start_delay
        self.values = np.linspace(start, stop, num) if num else np.array([])
