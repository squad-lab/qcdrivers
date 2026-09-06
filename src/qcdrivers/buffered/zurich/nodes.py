"""Buffered sweep nodes for Zurich Instruments instruments."""

from time import sleep, time
from typing import Sequence

import numpy as np
from qcodes.instrument import Instrument
from qcodes.parameters import Parameter

from qcdrivers.buffered._typing import SweepLike
from qcdrivers.buffered.base import BufferedNodeBase

__all__ = ["NodeMFLI", "NodeUHFLI"]


class NodeMFLI(BufferedNodeBase):
    """
    Zurich Instruments MFLI acquisition node using the LabOne DAQ module.

    The node uses hardware-trigger mode. For two-dimensional geometry, rows are
    trigger events and columns are points recorded per trigger. The upstream
    sweep node must provide a trigger pulse at least 100 microseconds wide.

    """

    def __init__(self, inst: Instrument, *args, **kwargs) -> None:
        super().__init__(inst=inst, *args, **kwargs)

        self.core = self.core.core
        self.serial = self.core.serial
        self.daq = self.core.session.daq_server

        self.daq_module = self.daq.dataAcquisitionModule()
        self.daq_module.set("device", self.serial)
        self.daq_module.set("type", 6)

        self._subs: list[str] = []

    def register_dependent(
        self,
        dependent: Parameter | Sequence[Parameter],
        num: int | Sequence[int],
        delay: float,
        input_trigger: int = 1,
        *,
        force_trigger: bool = False,
        trigger_delay: float = 0.0,
        trigger_level: float = 0.5,
        tc_factor: float = 1.0,
        grid_mode: str = "linear",
        edge: str = "rising",
        endless: bool = False,
        count: int = 1,
    ) -> None:
        """
        Configure and start a hardware-triggered DAQ acquisition.

        Args:
            dependent (Parameter | Sequence[Parameter]): Parameters exposing a
                Zurich Instruments ``zi_node`` path.
            num (int | Sequence[int]): Point count, or ``(rows, columns)`` for a
                two-dimensional acquisition.
            delay (float): Innermost step time in seconds.
            input_trigger (int): Trigger input number. Defaults to 1.
            force_trigger (bool): Force a trigger after arming. Defaults to
                False.
            trigger_delay (float): Additional delay before the first sample.
                Defaults to 0.
            trigger_level (float): Trigger threshold. Defaults to 0.5.
            tc_factor (float): Set the demodulator time constant to
                ``delay / tc_factor``. Defaults to 1.
            grid_mode (str): ``"nearest"``, ``"linear"``, or ``"exact"``.
                Defaults to ``"linear"``.
            edge (str): ``"rising"``, ``"falling"``, or ``"both"``. Defaults
                to ``"rising"``.
            endless (bool): Enable continuous acquisition. Defaults to False.
            count (int): Grids to acquire when *endless* is false. Defaults to
                1.

        Raises:
            ValueError: If *grid_mode* is unsupported.

        """
        # Normalize the dependent list.
        if isinstance(dependent, Sequence):
            self.dependents = [dep.zi_node.lower() for dep in dependent]
        else:
            self.dependents = [dependent.zi_node.lower()]

        if grid_mode not in ["nearest", "linear", "exact"]:
            raise ValueError(
                f"Invalid grid_mode: {grid_mode}. Must be nearest, linear or exact."
            )

        # Save whether the module should be triggered after arming.
        self._force_trigger = force_trigger

        # Configure how samples are aligned to the requested grid.
        self.daq_module.set("grid/mode", grid_mode)

        self.daq.setInt(f"/{self.serial}/demods/0/enable", 1)
        self.daq.setDouble(
            f"/{self.serial}/demods/0/timeconstant", float(delay) / tc_factor
        )

        self.daq_module.finish()
        self.daq_module.unsubscribe("*")
        self.daq_module.set("clearhistory", 1)

        self.daq_module.set(
            "triggernode", f"/{self.serial}/demods/0/sample.TrigIn{int(input_trigger)}"
        )

        # Configure the selected trigger input.
        self.daq.setDouble(
            f"/{self.serial}/triggers/in/{int(input_trigger) - 1}/level",
            trigger_level,
        )

        edge_map = {"rising": 1, "falling": 2, "both": 3}
        self.daq_module.set("edge", edge_map.get(edge, 1))

        self.daq_module.set("endless", 1 if endless else 0)
        if not endless:
            self.daq_module.set("count", int(count))

        if isinstance(num, Sequence) and not isinstance(num, (str, bytes)):
            rows, cols = int(num[0]), int(num[1])
        else:
            rows, cols = 1, int(num)

        self.daq_module.set("grid/rows", rows)
        self.daq_module.set("grid/cols", cols)

        if grid_mode != "exact":
            duration = float(delay) * cols
            self.daq_module.set("duration", duration)

        # Sample near the end of each ramp step, adjusted by trigger_delay.
        self.daq_module.set("delay", float(delay) + trigger_delay)

        self.daq_module.set("holdoff/time", max(0.0, float(delay) * (cols - 0.5)))

        self._subs = []
        for dep in self.dependents:
            path = f"/{self.serial}{dep}"
            self.daq_module.subscribe(path)
            self._subs.append(path)

        self.daq_module.execute()

        if self._force_trigger:
            sleep(0.2)  # Allow the DAQ module to finish arming.
            self.daq_module.set("forcetrigger", 1)

    def fetch(self, *, timeout: float = 15.0) -> list[np.ndarray]:
        """
        Wait for DAQ completion and read subscribed values.

        Args:
            timeout (float): Maximum wait before reading available data.
                Defaults to 15 seconds.

        Returns:
            list[np.ndarray]: One flattened array per dependent.

        """
        t0 = time()
        while not self.daq_module.finished():
            sleep(0.05)
            if time() - t0 > timeout:
                break

        result = self.daq_module.read()
        self.daq_module.finish()

        arrays: list[np.ndarray] = []
        for dep in self.dependents:
            dep_split = dep.split("/")
            data = result[self.serial][dep_split[1]][dep_split[2]][dep_split[3]][0][
                "value"
            ]
            arrays.append(np.array(data).flatten())

        return arrays


class NodeUHFLI(BufferedNodeBase):
    """
    Zurich Instruments UHFLI buffered sweep and acquisition node.

    Dependents may use the hardware-triggered DAQ module or the LabOne Sweeper
    module. The upstream sweep node must provide a trigger pulse at least
    100 microseconds wide for DAQ acquisition.

    """

    _shared = {}

    def __init__(self, inst: Instrument, *args, **kwargs):
        super().__init__(inst=inst, *args, **kwargs)

        self.core = self.core.core
        self.serial = self.core.serial
        self.daq = self.core.session.daq_server

        self.daq_module = self.daq.dataAcquisitionModule()
        self.daq_module.set("device", self.serial)
        self.daq_module.set("type", 6)

        # Share one Sweeper module and its subscriptions per physical UHFLI.
        if self.serial not in self._shared:
            sweeper = self.daq.sweep()
            sweeper.set("device", self.serial)

            self._shared[self.serial] = {
                "sweeper_module": sweeper,
                "subs": [],
                "sweeper_fields": [],
            }

        self._ctx = self._shared[self.serial]

        self.sweeper_module = self._ctx["sweeper_module"]

        self._active_acquisition = None

    def register_sweep(
        self,
        sweep: Sequence[SweepLike],
        input_trigger: int | None = None,
        output_trigger: int | None = None,
        trigger_type: str | None = None,
        trigger_width: float | None = None,
        *,
        spacing: str = "lin",
        averaging: int = 1,
        averaging_tc: int = 5,
        sweep_order: int = 3,
        settling_inaccuracy: float = 100 * 1e-6,
        phase_unwrap: bool = False,
        **kwargs,
    ) -> tuple[None, int, None]:
        """
        Configure a one-dimensional LabOne Sweeper Module sweep.

        Args:
            sweep (Sequence[SweepLike]): Sequence containing exactly one sweep of a
                parameter with a ``zi_node`` attribute.
            input_trigger (int | None): Accepted for the common node interface
                and ignored by this acquisition mode.
            output_trigger (int | None): Accepted for the common node interface
                and ignored by this acquisition mode.
            trigger_type (str | None): Accepted for the common node interface
                and ignored by this acquisition mode.
            trigger_width (float | None): Accepted for the common node interface
                and ignored by this acquisition mode.
            spacing (str): ``"lin"`` or ``"log"``. Defaults to ``"lin"``.
            averaging (int): Samples averaged per sweep point. Defaults to 1.
            averaging_tc (int): Time constants allowed per point. Defaults to
                5.
            sweep_order (int): Demodulator filter order. Defaults to 3.
            settling_inaccuracy (float): Target filter-settling inaccuracy.
            phase_unwrap (bool): Unwrap phase across 2-pi boundaries. Defaults
                to False.
            **kwargs: Ignored compatibility options.

        Returns:
            tuple[None, int, None]: No trigger type, point count, and no fixed
                step time.

        Raises:
            ValueError: If more than one sweep is supplied, the parameter has
                no ``zi_node``, or *spacing* is unsupported.

        """

        if len(sweep) > 1:
            raise ValueError(
                "Only 1D sweeps are supported with the Sweeper module, with one parameter being swept."
            )
        else:
            single_sweep = sweep[0]

        self.num = int(single_sweep.num)
        self.delay = float(single_sweep.delay)

        sweep_parameter = single_sweep.parameter[0]

        if not hasattr(sweep_parameter, "zi_node"):
            raise ValueError(
                f"Parameter {sweep_parameter.full_name!r} cannot be swept "
                "with the Zurich Instruments Sweeper because it has no zi_node."
            )

        gridnode = f"/{self.serial}/{sweep_parameter.zi_node.lower().lstrip('/')}"
        self.sweeper_module.set("gridnode", gridnode)

        self.sweeper_module.set("start", float(single_sweep.start))
        self.sweeper_module.set("stop", float(single_sweep.stop))
        self.sweeper_module.set("samplecount", int(self.num))

        if spacing == "lin":
            xmapping = 0
        elif spacing == "log":
            xmapping = 1
        else:
            raise ValueError(f"Invalid spacing: {spacing}. Must be 'lin' or 'log'.")

        self.sweeper_module.set("scan", 0)  # Sequential forward scan.
        self.sweeper_module.set("xmapping", xmapping)

        self.sweeper_module.set("bandwidthcontrol", 2)  # Automatic selection.
        self.sweeper_module.set("bandwidthoverlap", 0)
        self.sweeper_module.set("loopcount", 1)

        self.sweeper_module.set("settling/time", 0)

        self.sweeper_module.set(
            "settling/inaccuracy",
            float(settling_inaccuracy),
        )

        self.sweeper_module.set(
            "averaging/sample",
            int(averaging),
        )

        self.sweeper_module.set(
            "averaging/tc",
            int(averaging_tc),
        )

        self.sweeper_module.set(
            "order",
            int(sweep_order),
        )

        self.sweeper_module.set(
            "phaseunwrap",
            int(phase_unwrap),
        )

        num_points = self.num

        return None, num_points, None

    def run_sweep(self):
        """Start the configured LabOne sweep."""
        self.daq_module.finish()
        self.sweeper_module.execute()
        if self.toplevel:
            sleep((self.num + 1) * self.delay)

    def _register_daq_dependent(
        self,
        dependent: Parameter | Sequence[Parameter],
        num: int | Sequence[int],
        delay: float,
        input_trigger: int = 1,
        *,
        demod_channels: int | Sequence[int] = 0,
        force_trigger: bool = False,
        trigger_delay: float = 0.0,
        trigger_level: float = 0.5,
        tc_factor: float = 1.0,
        grid_mode: str = "linear",
        edge: str = "rising",
        endless: bool = False,
        count: int = 1,
        **kwargs,
    ) -> None:
        """
        Configure and start a hardware-triggered DAQ acquisition.

        Args:
            dependent (Parameter | Sequence[Parameter]): Parameters exposing a
                Zurich Instruments ``zi_node`` path.
            num (int | Sequence[int]): Point count, or ``(rows, columns)`` for a
                two-dimensional acquisition.
            delay (float): Innermost step time in seconds.
            input_trigger (int): Trigger input number. Defaults to 1.
            demod_channels (int | Sequence[int]): Demodulators to enable.
                Defaults to 0.
            force_trigger (bool): Force a trigger after arming. Defaults to
                False.
            trigger_delay (float): Additional delay before the first sample.
                Defaults to 0.
            trigger_level (float): Trigger threshold. Defaults to 0.5.
            tc_factor (float): Set each demodulator time constant to
                ``delay / tc_factor``. Defaults to 1.
            grid_mode (str): ``"nearest"``, ``"linear"``, or ``"exact"``.
                Defaults to ``"linear"``.
            edge (str): ``"rising"``, ``"falling"``, or ``"both"``. Defaults
                to ``"rising"``.
            endless (bool): Enable continuous acquisition. Defaults to False.
            count (int): Grids to acquire when *endless* is false. Defaults to
                1.
            **kwargs: Ignored compatibility options.

        Raises:
            ValueError: If *grid_mode* is unsupported.

        """
        # Normalize the dependent list.
        if isinstance(dependent, Sequence):
            self.dependents = [dep.zi_node.lower() for dep in dependent]
        else:
            self.dependents = [dependent.zi_node.lower()]

        if grid_mode not in ["nearest", "linear", "exact"]:
            raise ValueError(
                f"Invalid grid_mode: {grid_mode}. Must be nearest, linear or exact."
            )

        # Save whether the module should be triggered after arming.
        self._force_trigger = force_trigger

        # Configure how samples are aligned to the requested grid.
        self.daq_module.set("grid/mode", grid_mode)

        for demod in np.atleast_1d(demod_channels):
            self.daq.setInt(f"/{self.serial}/demods/{demod}/enable", 1)
            self.daq.setDouble(
                f"/{self.serial}/demods/{demod}/timeconstant", float(delay) / tc_factor
            )

        self.daq_module.finish()
        self.daq_module.unsubscribe("*")
        self.daq_module.set("clearhistory", 1)

        for demod in np.atleast_1d(demod_channels):
            self.daq_module.set(
                "triggernode",
                f"/{self.serial}/demods/{demod}/sample.TrigIn{int(input_trigger)}",
            )

        # Configure the selected trigger input.
        self.daq.setDouble(
            f"/{self.serial}/triggers/in/{int(input_trigger) - 1}/level",
            trigger_level,
        )

        # Use high-impedance mode for every trigger input.
        for i in [0, 1, 2, 3]:
            self.daq.set(f"/{self.serial}/triggers/in/{i}/imp50", 0)

        edge_map = {"rising": 1, "falling": 2, "both": 3}
        self.daq_module.set("edge", edge_map.get(edge, 1))

        self.daq_module.set("endless", 1 if endless else 0)
        if not endless:
            self.daq_module.set("count", int(count))

        if isinstance(num, Sequence) and not isinstance(num, (str, bytes)):
            rows, cols = int(num[0]), int(num[1])
        else:
            rows, cols = 1, int(num)

        self.daq_module.set("grid/rows", rows)
        self.daq_module.set("grid/cols", cols)

        if grid_mode != "exact":
            duration = float(delay) * cols
            self.daq_module.set("duration", duration)

        # Sample near the end of each ramp step, adjusted by trigger_delay.
        self.daq_module.set("delay", float(delay) + trigger_delay)

        self.daq_module.set("holdoff/time", max(0.0, float(delay) * (cols - 0.5)))

        self._subs = []
        for dep in self.dependents:
            path = f"/{self.serial}{dep}"
            self.daq_module.subscribe(path)
            self._subs.append(path)

        self.daq_module.execute()

        if self._force_trigger:
            sleep(0.2)  # Allow the DAQ module to finish arming.
            self.daq_module.set("forcetrigger", 1)

    def _register_sweeper_dependent(
        self,
        dependent: Parameter | Sequence[Parameter],
        num: int | Sequence[int],
        delay: float,
        input_trigger: int | None = None,
        **kwargs,
    ) -> None:
        """
        Subscribe dependents to the configured LabOne Sweeper Module.

        Args:
            dependent (Parameter | Sequence[Parameter]): Parameters exposing a
                supported ``zi_node`` sample field.
            num (int | Sequence[int]): Accepted for the common node interface.
            delay (float): Accepted for the common node interface.
            input_trigger (int | None): Accepted for the common node interface.
            **kwargs: Ignored compatibility options.

        Raises:
            ValueError: If this is not an acquisition-only end node or a
                dependent uses an unsupported sample field.

        """
        if not self.endnode:
            raise ValueError("Sweeper dependents can only be registered on end nodes.")

        if isinstance(dependent, Sequence):
            dependents = list(dependent)
        else:
            dependents = [dependent]

        self.dependents = dependents

        # Map each QCoDeS dependent to its Sweeper sample field.
        sweeper_fields = []

        # Subscribe to each demodulator sample node only once.
        sample_paths = set()

        for dep in dependents:
            zi_node = dep.zi_node.lower()

            # For example, /demods/0/sample.r maps to /demods/0/sample.
            if zi_node.endswith(".r"):
                sample_path = zi_node.removesuffix(".r")
                field = "r"

            elif zi_node.endswith(".theta"):
                sample_path = zi_node.removesuffix(".theta")
                field = "phase"

            elif zi_node.endswith(".x"):
                sample_path = zi_node.removesuffix(".x")
                field = "x"

            elif zi_node.endswith(".y"):
                sample_path = zi_node.removesuffix(".y")
                field = "y"

            else:
                raise ValueError(f"Unsupported Sweeper dependent: {zi_node!r}")

            full_path = f"/{self.serial}{sample_path}"

            sample_paths.add(full_path)

            sweeper_fields.append(
                {
                    "dependent": dep,
                    "path": full_path,
                    "field": field,
                }
            )

        self._ctx["subs"] = list(sample_paths)
        self._ctx["sweeper_fields"] = sweeper_fields

        self.sweeper_module.unsubscribe("*")

        for path in self._ctx["subs"]:
            self.sweeper_module.subscribe(path)

    def register_dependent(
        self,
        dependent: Parameter | Sequence[Parameter],
        num: int | list[int],
        delay: float,
        *,
        acquisition: str = "daq",
        **kwargs,
    ) -> None:
        """
        Configure dependents for DAQ or Sweeper acquisition.

        Args:
            dependent (Parameter | Sequence[Parameter]): Parameters exposing a
                Zurich Instruments ``zi_node`` path.
            num (int | list[int]): Point count, or two-dimensional geometry.
            delay (float): Innermost step time in seconds.
            acquisition (str): ``"daq"`` or ``"sweeper"``. Defaults to
                ``"daq"``.
            **kwargs: Mode-specific options forwarded to the selected
                acquisition setup.

        Raises:
            ValueError: If *acquisition* is unsupported or a Sweeper dependent
                is registered on a non-end node.

        """
        if acquisition == "daq":
            self._register_daq_dependent(
                dependent=dependent,
                num=num,
                delay=delay,
                **kwargs,
            )

        elif acquisition == "sweeper":
            self._register_sweeper_dependent(
                dependent=dependent,
                num=num,
                delay=delay,
                **kwargs,
            )

        else:
            raise ValueError(
                f"Unknown acquisition mode {acquisition!r}. "
                "Expected 'daq' or 'sweeper'."
            )

        self._active_acquisition = acquisition

    def fetch(self, *, timeout: float = 15.0) -> list[np.ndarray]:
        """
        Fetch the active DAQ or Sweeper acquisition.

        Args:
            timeout (float): DAQ wait limit in seconds. Sweeper acquisition uses
                twice this value as an allowance beyond its estimated duration.
                Defaults to 15.

        Returns:
            list[np.ndarray]: One flattened array per dependent.

        Raises:
            RuntimeError: If no acquisition has been registered.
            TimeoutError: If a Sweeper acquisition exceeds its estimated time
                plus the timeout allowance.

        """
        if self._active_acquisition == "daq":
            return self._fetch_daq(timeout=timeout)

        if self._active_acquisition == "sweeper":
            return self._fetch_sweeper(timeout=2 * timeout)

        raise RuntimeError("No acquisition has been registered.")

    def _fetch_daq(self, *, timeout: float = 15.0) -> list[np.ndarray]:
        """
        Wait for DAQ completion and read subscribed values.

        Args:
            timeout (float): Maximum wait before reading available data.
                Defaults to 15 seconds.

        Returns:
            list[np.ndarray]: One flattened array per dependent.

        """
        t0 = time()
        while not self.daq_module.finished():
            sleep(0.05)
            if time() - t0 > timeout:
                break

        result = self.daq_module.read()
        self.daq_module.finish()

        arrays: list[np.ndarray] = []
        for dep in self.dependents:
            dep_split = dep.split("/")
            data = result[self.serial][dep_split[1]][dep_split[2]][dep_split[3]][0][
                "value"
            ]
            arrays.append(np.array(data).flatten())

        return arrays

    def _fetch_sweeper(self, *, timeout: float = 30.0) -> list[np.ndarray]:
        """
        Wait for Sweeper completion and read the requested sample fields.

        Args:
            timeout (float): Additional allowance beyond the Sweeper's reported
                remaining time. Defaults to 30 seconds.

        Returns:
            list[np.ndarray]: One flattened array per dependent.

        Raises:
            TimeoutError: If acquisition exceeds its reported remaining time
                plus *timeout*.
            KeyError: If a requested field is absent from the returned sample.

        """
        remaining = self.sweeper_module.getDouble("remainingtime")
        while np.isnan(remaining):
            sleep(0.1)
            remaining = self.sweeper_module.getDouble("remainingtime")

        t0 = time()
        real_timeout = remaining + timeout

        while not self.sweeper_module.finished():
            if time() - t0 > real_timeout:
                self.sweeper_module.finish()
                raise TimeoutError(
                    f"Sweeper acquisition timed out after {real_timeout:.1f} s."
                )

            sleep(0.05)

        self.sweeper_module.finish()
        result = self.sweeper_module.read()

        arrays = []

        for spec in self._ctx["sweeper_fields"]:
            path = spec["path"]
            field = spec["field"]

            # Example path: /dev2793/demods/0/sample
            parts = path.strip("/").split("/")

            device = parts[0]  # dev2793
            demod = parts[2]  # 0

            sample = result[device]["demods"][demod]["sample"][0][0]

            if field not in sample:
                raise KeyError(
                    f"Field {field!r} not found in Sweeper sample. "
                    f"Available fields: {list(sample.keys())}"
                )

            arrays.append(np.asarray(sample[field]).flatten())

        self.sweeper_module.unsubscribe("*")

        return arrays
