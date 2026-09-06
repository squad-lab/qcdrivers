"""Base class for buffered sweep nodes."""

from typing import Sequence

from qcodes.instrument import Instrument
from qcodes.parameters import Parameter

from qcdrivers.buffered._typing import SweepLike

__all__ = ["BufferedNodeBase"]


class BufferedNodeBase:
    def __init__(self, inst: Instrument) -> None:
        """
        Initialize a buffered-tree node around an instrument.

        A node may drive sweeps, acquire dependents, or do both. Concrete node
        classes implement the operations their hardware supports.

        Args:
            inst (Instrument): QCoDeS instrument controlled by this node.

        """
        self.buffered = True
        self.toplevel = False
        self._processed_sweeps = False
        self._processed_dependents = False
        self.core = inst

        self.endnode = True
        self.sweepnode = True

    def _process_sweeps(self, sweep: SweepLike | Sequence[SweepLike]) -> None:
        """
        Normalize and validate the sweeps assigned to this node.

        Args:
            sweep (SweepLike | Sequence[SweepLike]): One or two sweeps belonging to the
                same instrument and using the same delay.

        Raises:
            AssertionError: If the sweeps use different instruments or delays,
                or more than two dimensions are supplied.

        """
        if not isinstance(sweep, Sequence):
            self.sweeps = [sweep]
        else:
            self.sweeps = sweep

        instruments = [
            param.underlying_instrument for sw in self.sweeps for param in sw.parameter
        ]
        assert len(set(instruments)) == 1, (
            "All sweeps of the buffered node must be from the same instrument"
        )

        delays = [sw.delay for sw in self.sweeps]
        assert len(set(delays)) == 1, (
            "All sweeps of the buffered node must have the same delay"
        )

        assert len(self.sweeps) <= 2, "Maximum 2D sweep supported"

        self.delay = delays[0]
        self.num = 1
        for sw in self.sweeps:
            self.num *= sw.num
        self.num_tup = [sw.num for sw in self.sweeps]
        self.start_delay = [sw.start_delay for sw in self.sweeps]
        self.endnode = False
        self.dims = len(self.sweeps)

    def _process_dependents(self, dependent: Parameter | Sequence[Parameter]) -> None:
        """
        Normalize one or more dependent parameters to a sequence.

        Args:
            dependent (Parameter | Sequence[Parameter]): Parameters acquired by
                this node.

        """
        if not isinstance(dependent, Sequence):
            self.dependents = [dependent]
        else:
            self.dependents = dependent

    def abort(self) -> None:
        """Provide a no-op cleanup hook for nodes without active resources."""
