"""Buffered sweep nodes for SQUAD instruments."""

from math import isclose, prod
from time import sleep
from typing import Sequence

import numpy as np
from qcodes.instrument import Instrument
from qcodes.parameters import Parameter

from qcdrivers.buffered._typing import SweepLike
from qcdrivers.buffered.base import BufferedNodeBase

__all__ = ["NodeDummySweeper", "NodeDummyAcquisition"]


class NodeDummySweeper(BufferedNodeBase):
    """
    Virtual sweep node for buffered 1D and 2D sweeps.

    The node does not actively step physical hardware. It defines the sweep
    shape and point spacing for a downstream buffered acquisition node.

    Supported:
        1D: (n,)
        2D: (n_outer, n_inner)

    More than two sweep dimensions are rejected.
    """

    def __init__(self, inst: Instrument, *args, **kwargs):
        super().__init__(inst=inst, *args, **kwargs)

        self.shape: tuple[int, ...] = ()
        self.num: int | tuple[int, int] = 0
        self.total_num: int = 0
        self.delay: float = 0.0

    def register_sweep(
        self,
        sweep: SweepLike | Sequence[SweepLike],
        input_trigger: int | None = None,
        output_trigger: int | None = None,
        trigger_type: str | None = None,
        trigger_width: float | None = None,
        **kwargs,
    ) -> tuple[
        None,
        int | tuple[int, int],
        float,
    ]:
        """
        Register a virtual buffered 1D or 2D sweep.

        Args:
            sweep:
                One sweep or a sequence containing one or two sweeps.

                For two sweeps the ordering is preserved:

                    sweep[0] -> outer dimension
                    sweep[1] -> inner dimension

            input_trigger:
                Accepted for compatibility and ignored.

            output_trigger:
                Accepted for compatibility and ignored.

            trigger_type:
                Accepted for compatibility and ignored.

            trigger_width:
                Accepted for compatibility and ignored.

            **kwargs:
                Ignored compatibility options.

        Returns:
            tuple:
                ``(None, num, delay)``

                For 1D:
                    ``num`` is an int.

                For 2D:
                    ``num`` is ``(n_outer, n_inner)``.

                ``delay`` is the common sampling interval.

        Raises:
            ValueError:
                If zero sweeps, more than two sweeps, or different delays
                for the two dimensions are supplied.
        """
        self._process_sweeps(sweep)

        ndim = len(self.sweeps)

        if ndim == 0:
            raise ValueError("NodeDummySweeper requires at least one sweep.")

        if ndim > 2:
            raise ValueError("NodeDummySweeper supports at most 2D buffered sweeps.")

        # Preserve the sweep order:
        #
        #   sweeps[0] -> outer dimension
        #   sweeps[1] -> inner dimension
        self.shape = tuple(int(sw.num) for sw in self.sweeps)

        self.total_num = prod(self.shape)

        delays = tuple(float(sw.delay) for sw in self.sweeps)

        if ndim == 2 and not isclose(
            delays[0],
            delays[1],
            rel_tol=0.0,
            abs_tol=1e-15,
        ):
            raise ValueError(
                "NodeDummySweeper requires the same delay for both "
                "dimensions of a 2D buffered sweep. "
                f"Received {delays[0]} s and {delays[1]} s."
            )

        self.delay = delays[0]

        # Keep the old 1D interface backwards compatible.
        if ndim == 1:
            self.num = self.shape[0]
        else:
            self.num = (
                self.shape[0],
                self.shape[1],
            )

        return None, self.num, self.delay

    def run_sweep(self) -> None:
        """
        Wait for the complete acquisition window when this node is the
        root of the buffered tree.

        For 2D the sweep is treated as one flattened acquisition buffer:

            total_num = n_outer * n_inner
        """
        if not self.toplevel:
            return

        if self.total_num <= 0:
            raise RuntimeError("No sweep has been registered on NodeDummySweeper.")

        sleep((self.total_num + 1) * self.delay)


class NodeDummyAcquisition(BufferedNodeBase):
    """
    Buffered dummy acquisition node.

    Mimics something like NodeMFLI:
        register_dependent(...)
        fetch() -> list[np.ndarray]
    """

    def _get_optional_parameter(self, name: str) -> float | None:
        param = getattr(self.core, name, None)

        if param is None:
            return None

        return float(param())

    def __init__(
        self,
        inst: Instrument,
        *,
        noise: float = 0.01,
        seed: int | None = 42,
    ):
        super().__init__(inst=inst)

        self.shape = ()

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
            self.shape = tuple(int(n) for n in num)
            self.num = int(np.prod(num))
        else:
            self.shape = (int(num),)
            self.num = int(num)

        self.delay = float(delay)

    def fetch(self) -> list[np.ndarray]:
        """
        Return one flattened array for every registered dependent.

        If control parameters are present on the dummy instrument, generate
        deterministic data controlled by those parameters. Otherwise return
        random data.
        """
        param_x = self._get_optional_parameter("param_x")
        param_y = self._get_optional_parameter("param_y")

        # No control parameters -> plain random dummy data
        if param_x is None and param_y is None:
            arrays = [
                self.rng.standard_normal(self.num)
                for _ in self.dependents
            ]

            self.frame += 1
            return arrays

        # One control parameter -> 1D Gaussian
        if param_x is not None and param_y is None:
            x = np.linspace(-1.0, 1.0, self.num)

            sigma = 0.15
            data = np.exp(-(x - param_x) ** 2 / (2 * sigma**2))

        # Two control parameters -> 2D Gaussian
        else:
            if len(self.shape) != 2:
                raise RuntimeError(
                    "Two dummy control parameters require a 2D sweep."
                )

            ny, nx = self.shape

            x = np.linspace(-1.0, 1.0, nx)
            y = np.linspace(-1.0, 1.0, ny)

            X, Y = np.meshgrid(x, y, indexing="xy")

            sigma = 0.15

            data = np.exp(
                -(
                    (X - param_x) ** 2
                    + (Y - param_y) ** 2
                )
                / (2 * sigma**2)
            )

        if self.noise > 0:
            data = data + self.noise * self.rng.standard_normal(data.shape)

        arrays = []

        for dependent in self.dependents:
            arrays.append(np.asarray(data).ravel())

        self.frame += 1

        return arrays
