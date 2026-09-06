"""Buffered sweep nodes for Keysight instruments."""

from time import sleep
from typing import Sequence

import numpy as np
from pyvisa.constants import StatusCode
from pyvisa.errors import VisaIOError
from qcodes.instrument import Instrument
from qcodes.parameters import Parameter

from qcdrivers.buffered._typing import SweepLike
from qcdrivers.buffered.base import BufferedNodeBase

__all__ = ["NodeKeysightDMM", "NodeKeysightVNA"]


class NodeKeysightDMM(BufferedNodeBase):
    """
    Keysight 344xxA DMM node using externally triggered reading memory.

    One-dimensional step-triggered acquisition is implemented. A
    two-dimensional point shape is accepted by the shared interface, but its
    DMM count configuration still requires hardware validation. The upstream
    sweep node must provide a trigger pulse at least one millisecond wide.

    """

    def __init__(self, inst: Instrument, *args, **kwargs) -> None:
        super().__init__(inst=inst, *args, **kwargs)
        self.core.trigger.source("IMM")
        self.core.reset()

    def register_dependent(
        self,
        dependent: Parameter | Sequence[Parameter] | None,
        num: int | Sequence[int],
        delay: int | float,
        input_trigger: int = 1,
        trigger_type: str = "step",
    ) -> None:
        """
        Configure a buffered, externally triggered DMM acquisition.

        Args:
            dependent (Parameter | Sequence[Parameter] | None): Parameters
                associated with the DMM readings.
            num (int | Sequence[int]): Point count. A two-dimensional shape is
                interpreted as ``(trigger events, points per trigger)`` but is
                not fully configured yet.
            delay (int | float): Step time used to select trigger delay and
                integration time.
            input_trigger (int): External trigger selector. Only 1 is supported.
            trigger_type (str): Triggering mode. Only ``"step"`` is supported.

        Raises:
            NotImplementedError: If the trigger input, trigger type, or DMM
                model is unsupported.

        """
        self._process_dependents(dependent)
        self.num = num
        self.delay = delay
        self.trigger_type = trigger_type
        if input_trigger == 1:
            self.core.trigger.source("EXT")
        else:
            raise NotImplementedError(
                "Only input_trigger=1 (EXT) is supported for Keysight DMM"
            )
        self.core.trigger.slope("POS")
        self.core.autorange("OFF")
        self.core.autozero("OFF")

        if isinstance(num, Sequence) and not isinstance(num, (str, bytes)):
            # TODO: Configure the 2D counts after validating them on the DMM.
            rows, cols = int(num[0]), int(num[1])  # noqa: F841
        else:
            if self.trigger_type == "step":
                self.core.sample.count(1)
                self.core.trigger.count(self.num)

                if self.core.model == "34410A":
                    self.core.trigger.delay(0.1 * self.delay)
                elif self.core.model == "34461A":
                    self.core.trigger.delay(0.2 * self.delay)
                else:
                    raise NotImplementedError(
                        f"Trigger type 'step' not implemented for {self.core.model}"
                    )

            else:
                raise NotImplementedError(
                    f"Trigger type '{self.trigger_type}' not implemented for Keysight DMM"
                )

        trigger_delay = 0.2 * self.delay
        self.core.trigger.delay(trigger_delay)

        available = 0.8 * (self.delay - trigger_delay)

        for nplc in reversed(self.core.NPLC_list):
            if nplc / self.core.line_frequency() < available:
                self.core.NPLC(nplc)
                break

        self.core.init_measurement()
        sleep(0.1)

    def fetch(self) -> list[np.ndarray]:
        """
        Fetch buffered measurements from the Keysight DMM.

        Returns:
            list[np.ndarray]: List containing a single flattened array of
            measured values.

        Raises:
            VisaIOError: If the instrument read fails or times out.

        """
        if isinstance(self.num, Sequence) and not isinstance(self.num, (str, bytes)):
            num = int(self.num[0]) * int(self.num[1])
        else:
            num = int(self.num)

        try:
            with self.core.timeout.set_to(max(5, num * self.delay + 2)):
                data = self.core.fetch()
        except VisaIOError as exc:
            if exc.error_code != StatusCode.error_timeout:
                raise

            raise
        finally:
            self.abort()

        return [np.asarray(data).flatten()]

    def abort(self) -> None:
        """Abort acquisition and restore settings for ordinary scalar reads."""
        self.core.device_clear()
        self.core.abort_measurement()
        self.core.sample.count(1)
        self.core.trigger.count(1)
        self.core.trigger.source("IMM")


class NodeKeysightVNA(BufferedNodeBase):
    """Keysight VNA node for buffered frequency sweeps."""

    def __init__(self, inst: Instrument, *args, **kwargs):
        super().__init__(inst=inst, *args, **kwargs)

    def register_sweep(
        self,
        sweep: SweepLike | Sequence[SweepLike],
        input_trigger: int | None = None,
        output_trigger: int | None = None,
        trigger_type: str | None = None,
        trigger_width: float | None = None,
    ) -> tuple[None, int, None]:
        """
        Configure a one-dimensional buffered frequency sweep.

        Args:
            sweep (SweepLike | Sequence[SweepLike]): One frequency sweep.
            input_trigger (int | None): Accepted for the common node interface
                and ignored.
            output_trigger (int | None): Accepted for the common node interface
                and ignored.
            trigger_type (str | None): Accepted for the common node interface
                and ignored.
            trigger_width (float | None): Accepted for the common node interface
                and ignored.

        Returns:
            tuple[None, int, None]: No trigger type, point count, and no fixed
                step time.

        Raises:
            NotImplementedError: If more than one sweep is supplied.

        """
        self._process_sweeps(sweep)

        if len(self.sweeps) != 1:
            raise NotImplementedError("Only one sweep supported")

        num_points = self.num
        sw = self.sweeps[0]
        self.core.frequency(sw.values)
        return None, num_points, None

    def register_dependent(
        self,
        dependent: Parameter | Sequence[Parameter],
        num: int | Sequence[int],
        delay: int | float,
        input_trigger: int | None = None,
    ) -> None:
        """
        Register S-parameter dependents to be measured by the VNA.

        Args:
            dependent (Parameter | Sequence[Parameter]): VNA parameters
                exposing an ``_sparam`` attribute.
            num (int | Sequence[int]): Expected point geometry.
            delay (int | float): Accepted for the common node interface and
                ignored.
            input_trigger (int | None): Accepted for the common node interface
                and ignored.

        """
        self._process_dependents(dependent)
        self.num = num

        self.core.configure_active_s_parameters(
            [dep._sparam for dep in self.dependents]
        )

    def run_sweep(self):
        """Run the configured VNA sweep."""
        self.core.traces[0].run_sweep()

    def fetch(self) -> list[np.ndarray]:
        """
        Fetch dependent data.

        Returns:
            list[np.ndarray]: One array per dependent.

        """
        return [dep() for dep in self.dependents]
