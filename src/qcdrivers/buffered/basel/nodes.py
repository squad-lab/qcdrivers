"""Buffered sweep nodes for Basel Precision Instruments instruments."""

from typing import Sequence

import numpy as np
from qcodes.instrument import Instrument
from qcodes.parameters import Parameter

from qcdrivers.buffered._typing import SweepLike
from qcdrivers.buffered.base import BufferedNodeBase

__all__ = ["NodeBaselDAC"]


class NodeBaselDAC(BufferedNodeBase):
    """Basel LNHR DAC node for one- or two-dimensional AWG sweeps."""

    def __init__(
        self,
        inst: Instrument,
        *args,
        **kwargs,
    ) -> None:
        """
        Initialize a node around a Basel LNHR DAC.

        Args:
            inst (Instrument): Basel LNHR DAC QCoDeS instrument.
            *args: Additional arguments passed to :class:`BufferedNodeBase`.
            **kwargs: Additional keyword arguments passed to
                :class:`BufferedNodeBase`.

        """
        super().__init__(inst=inst, *args, **kwargs)
        self.contacts = {}

    def register_sweep(
        self,
        sweep: SweepLike | Sequence[SweepLike],
        input_trigger: int | None = None,
        output_trigger: int | None = None,
        trigger_type: str | None = None,
        trigger_width: float | None = None,
    ) -> tuple[str | None, int, float]:
        """
        Configure a one- or two-dimensional DAC AWG sweep.

        Args:
            sweep (SweepLike | Sequence[SweepLike]): One or two channel sweeps.
            input_trigger (int | None): Accepted for the common node interface
                and ignored.
            output_trigger (int | None): Accepted for the common node interface
                and ignored.
            trigger_type (str | None): Trigger label returned to the tree.
            trigger_width (float | None): Accepted for the common node interface
                and ignored.

        Returns:
            tuple[str | None, int, float]: Trigger label, total point count, and
                innermost step time.

        Raises:
            ValueError: If the delay is shorter than 20 microseconds, or a 2D
                sweep does not place its channels on different AWGs.
            NotImplementedError: If more than two sweeps are supplied.

        """

        # The DAC requires at least 20 microseconds between ramp steps.
        minimum_delay = 20 * 1e-6  # 20 us

        self._process_sweeps(sweep)

        inner_sampling_rate = self.delay

        if self.delay < minimum_delay:
            raise ValueError(f"Delay is too small, use at least {minimum_delay} s")

        if len(self.sweeps) == 2:
            num_points = self.num

            inner_sweep = sweep[1]
            outer_sweep = sweep[0]

            inner_voltages = inner_sweep.values
            outer_voltages = outer_sweep.values

            self.contacts = {
                inner_sweep.parameter[0].name: inner_sweep.parameter[
                    0
                ].instrument._channum,
                outer_sweep.parameter[0].name: outer_sweep.parameter[
                    0
                ].instrument._channum,
            }

            inner_channel = self.contacts[inner_sweep.parameter[0].name]
            outer_channel = self.contacts[outer_sweep.parameter[0].name]

            if inner_channel < 13 and outer_channel > 12:
                inner_awg = self.core.awga
                outer_awg = self.core.awgc
            elif inner_channel > 12 and outer_channel < 13:
                inner_awg = self.core.awgc
                outer_awg = self.core.awga
            else:
                raise ValueError(
                    "Inner and outer channels must be on different AWGs (1-12 on AWG A, 13-24 on AWG C)"
                )

            # Configure both AWGs explicitly for the nested sweep.
            inner_awg.enable(False)
            outer_awg.enable(False)

            inner_awg.write_awg_config(
                {
                    "channel": inner_channel,
                    "cycles": len(outer_voltages),
                    "sampling_rate": inner_sampling_rate,
                    "waveform": inner_voltages,
                }
            )

            outer_awg.write_awg_config(
                {
                    "channel": outer_channel,
                    "cycles": 1,
                    "sampling_rate": inner_sampling_rate * len(inner_voltages),
                    "waveform": outer_voltages,
                }
            )

            inner_awg.trigger("disable")
            outer_awg.trigger("single step")

            self._BaselDAC_sweep_start = lambda: self.core.run_awg_sweep(
                [inner_awg, outer_awg]
            )

            return trigger_type, num_points, self.delay

        elif len(self.sweeps) == 1:
            num_points = self.num
            sweep = self.sweeps[0]

            self.contacts = {}
            if isinstance(sweep.parameter, Sequence):
                assert len(sweep.parameter) == 1, (
                    "Only one parameter supported for 1D sweeps"
                )
                for param in sweep.parameter:
                    self.contacts[param.name] = param.instrument._channum
            else:
                self.contacts[sweep.parameter.name] = (
                    sweep.parameter.instrument._channum
                )

            channel_number = self.contacts[list(self.contacts.keys())[0]]

            if channel_number < 13:
                awg = self.core.awga
            else:
                awg = self.core.awgc

            awg.enable(False)

            awg.write_awg_config(
                {
                    "channel": channel_number,
                    "cycles": 1,
                    "sampling_rate": inner_sampling_rate,
                    "waveform": sweep.values,
                }
            )

            awg.trigger("disable")

            self._BaselDAC_sweep_start = lambda: self.core.run_awg_sweep([awg])

            return trigger_type, num_points, self.delay
        else:
            raise NotImplementedError("Only 1D and 2D sweeps are supported")

    def run_sweep(self):
        """Start the configured Basel DAC AWG sweep."""
        self._BaselDAC_sweep_start()

    def register_dependent(
        self,
        dependent: Parameter | Sequence[Parameter],
        num: int | Sequence[int],
        delay: int | float,
        input_trigger: int | None = None,
    ) -> None:
        """
        Register parameters to read after the Basel DAC sweep.

        Args:
            dependent (Parameter | Sequence[Parameter]): Parameter or parameters
                read by :meth:`fetch`.
            num (int | Sequence[int]): Expected point geometry.
            delay (int | float): Step time supplied by the tree.
            input_trigger (int | None): Accepted for the common node interface
                and ignored.

        """
        self._process_dependents(dependent)
        self.num = num

    def fetch(self) -> list[np.ndarray]:
        """
        Fetch dependent data.

        Returns:
            list[np.ndarray]: One array per dependent.
        """
        return [dep() for dep in self.dependents]
