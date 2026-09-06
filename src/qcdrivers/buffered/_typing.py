"""
Structural types shared by the buffered nodes.

Buffered nodes are handed sweep objects by Qanary. The nodes only ever read
attributes off those objects.

"""

from typing import Protocol, Sequence

import numpy as np
from qcodes.parameters import Parameter

__all__ = ["SweepLike"]


class SweepLike(Protocol):
    """Any Qanary sweep: ``Sweep``, ``CircularSweep`` or ``SegmentedSweep``."""

    parameter: Sequence[Parameter]
    values: np.ndarray
    start: int | float
    stop: int | float
    num: int | float
    delay: float
    start_delay: float
