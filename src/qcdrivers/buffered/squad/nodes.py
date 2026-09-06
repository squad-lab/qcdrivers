"""Buffered sweep nodes for SQUAD instruments."""

from time import sleep
from typing import Sequence

from qcodes.instrument import Instrument

from qcdrivers.buffered._typing import SweepLike
from qcdrivers.buffered.base import BufferedNodeBase

__all__ = ["NodeDelay"]


class NodeDelay(BufferedNodeBase):
    """
    Virtual sweep node for buffered time sweeps.

    The node does not actively step anything. It defines the point count and
    spacing for a downstream buffered acquisition such as a Zurich Instruments
    DAQ module.

    """

    def __init__(self, inst: Instrument, *args, **kwargs):
        """
        Initialize a virtual delay node.

        Args:
            inst (Instrument): Placeholder instrument required by the common
                buffered-node interface.
            *args: Additional arguments passed to :class:`BufferedNodeBase`.
            **kwargs: Additional keyword arguments passed to
                :class:`BufferedNodeBase`.

        """
        super().__init__(inst=inst, *args, **kwargs)

    def register_sweep(
        self,
        sweep: SweepLike | Sequence[SweepLike],
        input_trigger: int | None = None,
        output_trigger: int | None = None,
        trigger_type: str | None = None,
        trigger_width: float | None = None,
        **kwargs,
    ) -> tuple[None, int, float]:
        """
        Register one time sweep without configuring physical hardware.

        Args:
            sweep (SweepLike | Sequence[SweepLike]): Sequence containing one sweep.
            input_trigger (int | None): Accepted for the common node interface
                and ignored.
            output_trigger (int | None): Accepted for the common node interface
                and ignored.
            trigger_type (str | None): Accepted for the common node interface
                and ignored.
            trigger_width (float | None): Accepted for the common node interface
                and ignored.
            **kwargs: Ignored compatibility options.

        Returns:
            tuple[None, int, float]: No trigger type, point count, and time
                spacing in seconds.

        Raises:
            ValueError: If more than one sweep is supplied.

        """
        self._process_sweeps(sweep)

        if len(self.sweeps) != 1:
            raise ValueError("NodeDelay only supports 1D time sweeps.")

        sw = self.sweeps[0]

        self.num = int(sw.num)
        self.delay = float(sw.delay)

        return None, self.num, self.delay

    def run_sweep(self):
        """
        Wait for the acquisition window when this delay node is the tree root.

        The downstream acquisition module runs asynchronously, so no physical
        parameter is stepped here.

        """
        if self.toplevel:
            sleep((self.num + 1) * self.delay)
