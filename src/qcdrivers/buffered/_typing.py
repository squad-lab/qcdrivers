"""
Structural types shared by the buffered nodes.

Buffered nodes are handed sweep objects by QCUtils. Naming the concrete
``qcutils.sweep.Sweep`` here would make QCDrivers depend on QCUtils, which
depends on QCDrivers in turn. The nodes only ever read attributes off those
objects -- they never construct one, subclass one, or isinstance-check one --
so a structural type is both sufficient and more accurate: ``CircularSweep``
and ``SegmentedSweep`` satisfy it too, and neither subclasses ``Sweep``.

"""

from typing import Protocol, Sequence

import numpy as np
from qcodes.parameters import Parameter

__all__ = ["SweepLike"]


class SweepLike(Protocol):
    """Any QCUtils sweep: ``Sweep``, ``CircularSweep`` or ``SegmentedSweep``."""

    parameter: Sequence[Parameter]
    values: np.ndarray
    start: int | float
    stop: int | float
    num: int | float
    delay: float
    start_delay: float
