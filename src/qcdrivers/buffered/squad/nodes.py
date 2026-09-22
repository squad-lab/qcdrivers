"""Buffered sweep nodes for SQUAD instruments."""

from time import sleep
from typing import Sequence
import numpy as np

from qcodes.instrument import Instrument
from qcodes.parameters import Parameter

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


class NodeDummyAcquisition(BufferedNodeBase):
    """
    Buffered dummy acquisition node.

    Mimics something like NodeMFLI:
        register_dependent(...)
        fetch() -> list[np.ndarray]
    """

    def __init__(
        self,
        inst: Instrument,
        *,
        noise: float = 0.01,
        seed: int | None = 42,
    ):
        super().__init__(inst=inst)

        self.noise = noise
        self.rng = np.random.default_rng(seed)

        self.num = 0
        self.delay = 0.0
        self.frame = 0

    def register_dependent(
        self,
        dependent: Parameter | Sequence[Parameter],
        num: int | Sequence[int],
        delay: float,
        **kwargs,
    ) -> None:
        """
        Qanary calls this while arming the buffered tree.
        """

        self._process_dependents(dependent)

        if isinstance(num, Sequence) and not isinstance(num, (str, bytes)):
            self.num = int(np.prod(num))
        else:
            self.num = int(num)

        self.delay = float(delay)

    def fetch(self) -> list[np.ndarray]:
        """
        Return one flattened array for every registered dependent.
        """

        n = self.num

        # Synthetic time coordinate for producing nice dummy data.
        t = np.arange(n) * self.delay

        # Slowly change the signal from frame to frame so that you
        # can actually see LiveTuning refreshing in Qimchi.
        frame_phase = self.frame * 0.3

        r_data = (
            1.0
            + 0.25 * np.sin(2 * np.pi * 0.5 * t + frame_phase)
            + self.noise * self.rng.standard_normal(n)
        )

        p_data = (
            30.0
            * np.sin(2 * np.pi * 0.2 * t + frame_phase)
            + self.noise * 10 * self.rng.standard_normal(n)
        )

        arrays = []

        for dependent in self.dependents:
            if dependent.name.lower() in {"r", "dummy_r"}:
                arrays.append(r_data)

            elif dependent.name.lower() in {"p", "dummy_p"}:
                arrays.append(p_data)

            else:
                # Generic fallback for additional dummy dependents.
                arrays.append(
                    self.rng.standard_normal(n)
                )

        self.frame += 1

        return arrays
