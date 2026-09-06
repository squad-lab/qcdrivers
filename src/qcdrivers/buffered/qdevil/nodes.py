"""Buffered sweep nodes for QDevil instruments."""

from time import sleep
from typing import Sequence

import numpy as np
from qcodes.instrument import Instrument
from qcodes.parameters import Parameter

from qcdrivers.buffered._typing import SweepLike
from qcdrivers.buffered.base import BufferedNodeBase

__all__ = ["NodeQDAC2"]


class NodeQDAC2(BufferedNodeBase):
    """QDevil QDAC-II sweep and current-acquisition node."""

    def __init__(
        self,
        inst: Instrument,
        *args,
        **kwargs,
    ) -> None:
        """
        Initialize a node around a QDAC-II instrument.

        Args:
            inst (Instrument): QDAC-II QCoDeS instrument.
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
        trigger_type: str = "ramp",
        trigger_width: float = 1e-4,
    ) -> tuple[str, int | list[int], float]:
        """
        Configure a one- or two-dimensional QDAC-II virtual sweep.

        Args:
            sweep (SweepLike | Sequence[SweepLike]): One or two QDAC-II channel sweeps.
            input_trigger (int | None): Optional external start-trigger number.
            output_trigger (int | None): Optional trigger-output number.
            trigger_type (str): ``"ramp"`` for an output trigger per inner
                ramp or ``"step"`` for one per inner point. One-dimensional
                sweeps support only ``"step"``.
            trigger_width (float): Output-trigger width in seconds. Defaults to
                0.0001.

        Returns:
            tuple[str, int | list[int], float]: Trigger type, point geometry,
                and innermost step time.

        Raises:
            ValueError: If the step delay is shorter than the trigger width or
                *trigger_type* is invalid.
            NotImplementedError: If the requested dimensionality or a
                one-dimensional ramp trigger is unsupported.

        """
        self._process_sweeps(sweep)
        self._trigger_width = trigger_width

        if self.delay < self._trigger_width:
            raise ValueError(
                f"Delay {self.delay} s is less than trigger width {self._trigger_width} s"
            )

        self.core.free_all_triggers()
        if trigger_type not in ["ramp", "step"]:
            raise ValueError('trigger_type must be either "ramp" or "step"')

        if len(self.sweeps) == 2:
            inner_sweep = sweep[1]
            outer_sweep = sweep[0]

            inner_voltages = inner_sweep.values
            outer_voltages = outer_sweep.values

            self.input_trigger = (
                {f"trigin_{input_trigger}": input_trigger} if input_trigger else None
            )
            self.output_trigger = (
                {f"trigout_{output_trigger}": output_trigger}
                if output_trigger
                else None
            )
            self.input_trigger_key = (
                f"trigin_{input_trigger}" if input_trigger else None
            )
            self.output_trigger_key = (
                f"trigout_{output_trigger}" if output_trigger else None
            )

            self.contacts = {
                inner_sweep.parameter[0].name: inner_sweep.parameter[
                    0
                ].instrument._channum,
                outer_sweep.parameter[0].name: outer_sweep.parameter[
                    0
                ].instrument._channum,
            }
            self.arrangement = self.core.arrange(
                contacts=self.contacts,
                output_triggers=self.output_trigger,
            )

            for trig in self.core.external_triggers:
                trig.width_s(self._trigger_width)

            if trigger_type == "ramp":
                num_points = self.num_tup
                self._qdac_sweep = self.arrangement.virtual_sweep2d(
                    inner_contact=inner_sweep.parameter[0].name,
                    outer_contact=outer_sweep.parameter[0].name,
                    inner_voltages=inner_voltages,
                    outer_voltages=outer_voltages,
                    start_sweep_trigger=self.input_trigger_key,
                    inner_step_time_s=self.delay,
                    outer_step_trigger=self.output_trigger_key,
                )
            else:
                num_points = self.num
                self._qdac_sweep = self.arrangement.virtual_sweep2d(
                    inner_contact=inner_sweep.parameter[0].name,
                    outer_contact=outer_sweep.parameter[0].name,
                    inner_voltages=inner_voltages,
                    outer_voltages=outer_voltages,
                    start_sweep_trigger=self.input_trigger_key,
                    inner_step_time_s=self.delay,
                    inner_step_trigger=self.output_trigger_key,
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

            self.input_trigger = (
                {f"trigin_{input_trigger}": input_trigger} if input_trigger else None
            )
            self.output_trigger = (
                {f"trigout_{output_trigger}": output_trigger}
                if output_trigger
                else None
            )
            self.input_trigger_key = (
                f"trigin_{input_trigger}" if input_trigger else None
            )
            self.output_trigger_key = (
                f"trigout_{output_trigger}" if output_trigger else None
            )

            self.arrangement = self.core.arrange(
                contacts=self.contacts,
                output_triggers=self.output_trigger,
            )

            for trig in self.core.external_triggers:
                trig.width_s(self._trigger_width)

            if trigger_type == "ramp":
                raise NotImplementedError(
                    "trigger_type 'ramp' not implemented for 1D sweeps"
                )

            self._qdac_sweep = self.arrangement.virtual_sweep(
                contact=list(self.contacts.keys())[0],
                voltages=self.sweeps[0].values,
                start_sweep_trigger=self.input_trigger_key,
                step_time_s=self.delay,
                step_trigger=self.output_trigger_key,
            )

            return trigger_type, num_points, self.delay
        else:
            raise NotImplementedError("Only 1D and 2D sweeps are supported")

    def run_sweep(self):
        """Start the configured QDAC-II sweep and wait when this is the root."""
        self._sweep_active = True
        self._qdac_sweep.start()
        try:
            if self.toplevel:
                sleep((self.num + 1) * self.delay)
        finally:
            if self.toplevel:
                self.abort()

    def abort(self) -> None:
        """Stop the active QDAC list sweep and release its trigger routing."""
        if getattr(self, "_sweep_active", False):
            self._qdac_sweep.close()
            self._sweep_active = False

    def register_dependent(
        self,
        dependent: Parameter | Sequence[Parameter],
        num: int | Sequence[int],
        delay: float,
        input_trigger: int = 1,
    ) -> None:
        """
        Configure QDAC-II current measurements for the buffered sweep.

        Args:
            dependent (Parameter | Sequence[Parameter]): Current parameters to
                acquire.
            num (int | Sequence[int]): Point geometry supplied by the tree.
            delay (float): Measurement aperture in seconds.
            input_trigger (int): Accepted for the common node interface and
                ignored.

        Raises:
            NotImplementedError: If the QDAC-II is used only as an acquisition
                end node.

        """
        self._process_dependents(dependent)

        # TODO: Check that dependent is read_current_A, make it robust against parameter renames

        # A combined sweep/acquisition node uses its configured internal trigger.
        # Acquisition-only operation would require an external-trigger setup.
        if self.sweepnode:
            for dependent in self.dependents:
                dependent.instrument.clear_measurements()
                meas = dependent.instrument.measurement(aperture_s=delay)
                meas.start_on(
                    self.arrangement.get_trigger_by_name(self.output_trigger_key)
                )
        elif self.endnode:
            raise NotImplementedError("End node not implemented for QDAC2")

    def fetch(self) -> list[np.ndarray]:
        """
        Fetch buffered current readings from the QDAC-II.

        Returns:
            list[np.ndarray]: One flattened current array per dependent.

        """
        results = []
        for dependent in self.dependents:
            data = dependent.instrument.fetch_current_A()
            results.append(np.array(data).flatten())
        return results
