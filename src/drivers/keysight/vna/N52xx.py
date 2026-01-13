from __future__ import annotations

from typing import TYPE_CHECKING, Optional

import numpy as np
from qcodes.instrument_drivers.Keysight import N52xx

if TYPE_CHECKING:
    from qcodes.instrument.visa import VisaInstrumentKWArgs
    from typing_extensions import Unpack


class PNABase(N52xx.KeysightPNABase):
    """
    Driver for Keysight PNA N52xx.
    """

    def __init__(
        self,
        name: str,
        address: str,
        min_freq: float,
        max_freq: float,
        min_power: float,
        max_power: float,
        nports: int,
        data_format: str = "DB",
        **kwargs: "Unpack[VisaInstrumentKWArgs]",
    ) -> None:
        super().__init__(
            name,
            address,
            min_freq=min_freq,
            max_freq=max_freq,
            min_power=min_power,
            max_power=max_power,
            nports=nports,
            **kwargs,
        )

        # DEFAULTS
        self.averages_enabled(False)
        self.output(False)
        self.sweep_type("LIN")
        self.sweep_mode("CONT")

        allowed_formats = {"DB", "RI", "MA"}
        if data_format not in allowed_formats:
            raise ValueError(f"{data_format} not a valid data format.")
        self.data_format = data_format

        self.sparams_list = [
            f"S{i + 1}{j + 1}" for i in range(nports) for j in range(nports)
        ]

        # Ensure we can safely query numeric ASCII quickly
        try:
            self.write("FORMat:DATA ASCii,0")
        except Exception:
            # some firmwares accept only "FORM:DATA ASCII"
            try:
                self.write("FORMat:DATA ASCii")
            except Exception:
                pass

        # Create parameters for each sparam + component
        for sparam in self.sparams_list:
            if self.data_format == "DB":
                components_with_unit = [
                    ("mag", "dB"),
                    ("phase", "deg"),
                    ("unwrapped_phase", "deg"),
                ]
                name_map = {
                    "mag": "magnitude",
                    "phase": "phase",
                    "unwrapped_phase": "unwrapped_phase",
                }
                label_map = {
                    "mag": "mag",
                    "phase": "arg",
                    "unwrapped_phase": "arg_unwrapped",
                }
            elif self.data_format == "RI":
                components_with_unit = [("real", ""), ("imag", "")]
                name_map = {"real": "real", "imag": "imag"}
                label_map = {"real": "Re", "imag": "Im"}
            elif self.data_format == "MA":
                components_with_unit = [
                    ("mag", ""),
                    ("phase", "deg"),
                    ("unwrapped_phase", "deg"),
                ]
                name_map = {
                    "mag": "magnitude",
                    "phase": "phase",
                    "unwrapped_phase": "unwrapped_phase",
                }
                label_map = {
                    "mag": "mag",
                    "phase": "arg",
                    "unwrapped_phase": "arg_unwrapped",
                }

            for comp, unit in components_with_unit:
                name = f"{sparam.lower()}_{name_map[comp]}"
                label = f"{label_map[comp]}({sparam})"

                self.add_parameter(
                    name,
                    label=label,
                    unit=unit,
                    get_cmd=self._get_s_parameter(sparam, comp),
                    set_cmd=False,
                )
                self.parameters[name]._sparam = sparam
                self.parameters[name]._component = comp

        # IF bandwidth
        self.if_bandwidth.get_cmd = self._get_ifbw
        self.if_bandwidth.set_cmd = self._set_ifbw
        self.if_bandwidth.vals = None

        # Frequency
        self.add_parameter(
            "frequency",
            label="Frequency",
            unit="Hz",
            get_cmd=self._get_frequency,
            set_cmd=self._set_frequency,
        )

        # Segmented sweep table
        self.add_parameter(
            "segment_table",
            label="Segmented Sweep Table",
            unit=None,
            get_cmd=self._get_segment_table,
            set_cmd=self._set_segment_table,
        )

    def _query_ascii_floats(self, cmd: str) -> np.ndarray:
        resp = self.ask(cmd).strip()
        if not resp:
            return np.array([], dtype=float)
        return np.fromstring(resp, sep=",", dtype=float)

    def _trace_name(self, sparam: str, component: str) -> str:
        """
        Unique CALC parameter name per (sparam, dependent, data_format),
        so the PNA can keep each dependent in its own trace.
        """
        # Example: "S21_DB_mag" or "S11_RI_real"
        return f"{sparam}_{self.data_format}_{component}"

    def _calc_form_for(self, component: str) -> str:
        """
        Map our 'component' and selected data_format to a CALC:FORM code.
        We then query FDAT for that trace.
        """
        if self.data_format == "DB":
            if component == "mag":
                return "MLOG"
            if component == "phase":
                # wrapped phase
                return "PHAS"
            if component == "unwrapped_phase":
                # unwrapped phase
                return "UPH"
        elif self.data_format == "MA":
            if component == "mag":
                return "MLIN"
            if component == "phase":
                # wrapped phase
                return "PHAS"
            if component == "unwrapped_phase":
                # unwrapped phase
                return "UPH"
        elif self.data_format == "RI":
            if component == "real":
                return "REAL"
            if component == "imag":
                return "IMAG"

        raise ValueError(
            f"Unsupported component '{component}' for format '{self.data_format}'"
        )

    def _ensure_trace_for(self, sparam: str, component: str) -> str:
        """
        Ensure a CALC parameter exists for (sparam, component) and has the correct format.
        Then select it and return its name.

        This is the piece that respects: "different dependents are stored in different traces".
        """
        tname = self._trace_name(sparam, component)
        form = self._calc_form_for(component)

        # Define the parameter if needed.
        # Many PNAs will error if it already exists; we ignore that.
        try:
            self.write(f'CALCulate:PARameter:DEFine:EXT "{tname}",{sparam}')
        except Exception:
            pass

        # Select and apply the trace format (usually stored per-parameter/trace)
        self.write(f'CALCulate:PARameter:SELect "{tname}"')
        self.write(f"CALCulate:FORMat {form}")

        return tname

    def _get_s_parameter(self, s_parameter: str, component: str):
        allowed_parameter = tuple(self.sparams_list)
        allowed_component = ("mag", "phase", "unwrapped_phase", "real", "imag")

        if s_parameter not in allowed_parameter:
            raise ValueError(
                f"The S-parameter is not allowed. Choose from: {allowed_parameter}"
            )
        if component not in allowed_component:
            raise ValueError(
                f"The component is not allowed. Choose from: {allowed_component}"
            )

        def getter():
            # Ensure the correct dependent is tied to its own trace and selected
            self._ensure_trace_for(s_parameter, component)

            # Query formatted data (FDAT) for the selected trace
            # This returns:
            # - DB/mag: dB values
            # - MA/mag: linear magnitude
            # - phase: degrees
            # - RI: real or imag
            data = self._query_ascii_floats("CALCulate:DATA? FDAT")

            return data

        return getter

    def _set_frequency(self, freq: list) -> None:
        self.freq = np.asarray(freq, dtype=float)
        difference = np.diff(self.freq)

        if self.freq.ndim != 1:
            raise ValueError("freq must be a 1D array")

        if np.any(difference <= 0):
            raise ValueError("freq must be strictly increasing.")

        if np.allclose(difference, difference[0]):
            self.start(freq[0])
            self.stop(freq[-1])
            self.points(len(freq))
        else:
            segments = []
            start_idx = 0

            for i in range(1, len(difference)):
                if not np.isclose(difference[i], difference[i - 1], rtol=1e-6):
                    segments.append(self._make_segment(freq, start_idx, i))
                    start_idx = i

            segments.append(
                self._make_segment(self.freq, start_idx, len(self.freq) - 1)
            )
            self._set_segment_table(segments)

    def _get_frequency(self) -> np.ndarray:
        # Best: ask the actual stimulus point list (covers LIN and SEGM)
        try:
            f = self._query_ascii_floats("SENSe:FREQuency:DATA?")
            if f.size > 0:
                return f
        except Exception:
            pass

        # Fallbacks
        if self.sweep_type() == "LIN":
            f_start = self.start()
            f_stop = self.stop()
            points = self.points()
            return np.linspace(f_start, f_stop, points)

        if self.sweep_type() == "SEGM":
            segments = self._get_segment_table()
            freq_list = []
            for seg in segments:
                f_start = seg["start"]
                f_stop = seg["stop"]
                points = seg["points"]
                freq_list.append(np.linspace(f_start, f_stop, points))
            return np.concatenate(freq_list)

        raise ValueError("Unknown sweep type. Only LIN and SEGM are supported.")

    def _make_segment(self, freq, i0, i1, ifbw=None) -> dict:
        if ifbw is None:
            ifbw = self.if_bandwidth()
        f_start = freq[i0]
        f_stop = freq[i1]
        points = i1 - i0 + 1

        return {
            "start": f_start,
            "stop": f_stop,
            "points": points,
            "ifbw": ifbw,
        }

    def _set_segment_table(self, segments: list[dict]) -> None:
        self.write("SENS:SEGM:DEL:ALL")
        self.write("SENS:SWE:TYPE SEGM")

        self.write("SENS:SEGM:BWID:PORT:CONT OFF")
        self.write("SENS:SEGM:BWID:CONT ON")
        self.write("SENS:SEGM:ARB ON")
        self.write("SENS:SEGM:X:SPAC OBAS")

        for i, seg in enumerate(segments, start=1):
            self.write(f"SENS:SEGM{i}:ADD")
            self.write(f"SENS:SEGM{i}:FREQ:STAR {seg['start']}")
            self.write(f"SENS:SEGM{i}:FREQ:STOP {seg['stop']}")
            self.write(f"SENS:SEGM{i}:SWE:POIN {seg['points']}")
            self.write(f"SENS:SEGM{i}:BWID {seg['ifbw']}")
            self.write(f"SENS:SEGM{i}:STAT ON")

        self.write("SENS:SWE:TYPE SEGM")

    def _get_segment_table(self) -> Optional[list[dict]]:
        sweep_type = self.ask("SENS:SWE:TYPE?").strip()

        if sweep_type == "LIN":
            # No segment table in linear mode
            return None

        if sweep_type == "SEGM":
            seg_count = int(self.ask("SENS:SEGM:COUN?"))
            segments = []

            for i in range(1, seg_count + 1):
                seg = {
                    "index": i,
                    "state": bool(int(self.ask(f"SENS:SEGM{i}:STAT?"))),
                    # Use your original keys for set/get compatibility:
                    "start": float(self.ask(f"SENS:SEGM{i}:FREQ:STAR?")),
                    "stop": float(self.ask(f"SENS:SEGM{i}:FREQ:STOP?")),
                    "points": int(self.ask(f"SENS:SEGM{i}:SWE:POIN?")),
                    # Some firmwares use BWID or BAND:RES; keep yours:
                    "ifbw": float(self.ask(f"SENS:SEGM{i}:BAND:RES?")),
                }
                segments.append(seg)

            return segments

        raise ValueError("Unknown sweep type. Only LIN and SEGM are supported.")

    def _set_ifbw(self, ifbw) -> None:
        sweep_type = self.ask("SENS:SWE:TYPE?").strip()

        if sweep_type == "LIN":
            if not (1 <= ifbw <= 15e6):
                raise ValueError("IFBW must be between 1 Hz and 15 MHz")
            self.write(f"SENS:BAND:RES {ifbw}")
            return

        if sweep_type == "SEGM":
            seg_count = int(self.ask("SENS:SEGM:COUN?"))
            if len(ifbw) != seg_count:
                raise ValueError("Length of ifbw list must match number of segments.")

            for i, bw in enumerate(ifbw, start=1):
                if not (1 <= bw <= 15e6):
                    raise ValueError(
                        f"IFBW must be between 1 Hz and 15 MHz. Got {bw} for segment {i}."
                    )
                self.write(f"SENS:SEGM{i}:BWID {bw}")
            return

        raise ValueError("Unknown sweep type. Only LIN and SEGM are supported.")

    def _get_ifbw(self) -> float | list[float]:
        sweep_type = self.ask("SENS:SWE:TYPE?").strip()

        if sweep_type == "SEGM":
            segments = self._get_segment_table() or []
            return [seg["ifbw"] for seg in segments]

        if sweep_type == "LIN":
            ifbw = self.ask("SENS:BAND:RES?")
            return float(ifbw.strip())

        raise ValueError("Unknown sweep type. Only LIN and SEGM are supported.")

    def configure_active_s_parameters(self, sparams: list[str]):
        """
        Activates s parameter channel always on trace 1 (display use-case).
        NOTE: Your internal getters do not rely on this display setup anymore.
        """
        allowed = self.sparams_list
        for s in sparams:
            if s not in allowed:
                raise ValueError(f"{s} not a valid s parameter.")

        self.write("DISP:WIND1:TRAC:DEL:ALL")
        self.write("CALC:PAR:DEL:ALL")
        self.write("DISP:WIND1:STATE ON")

        for i, sp in enumerate(sparams):
            trace_name = f"{sp}_measurement"
            self.write(f'CALCulate:PARameter:DEFine:EXT "{trace_name}",{sp}')
            self.write(f'CALC:PAR:SEL "{trace_name}"')
            trace_index = i + 1
            self.write(f'DISPlay:WIND1:TRACe{trace_index}:FEED "{trace_name}"')


class N5222B(PNABase):
    def __init__(
        self,
        name: str,
        address: str,
        data_format: str = "DB",
        **kwargs,
    ) -> None:
        """Driver for Keysight PNA N5222B."""
        super().__init__(
            name,
            address,
            min_freq=10e6,
            max_freq=26.5e9,
            min_power=-30,
            max_power=13,
            nports=4,
            data_format=data_format,
            **kwargs,
        )

        attenuators_options = {"217", "219", "220", "417", "419", "420"}
        options = set(self.get_options())
        if attenuators_options.intersection(options):
            self._set_power_limits(min_power=-95, max_power=13)


class N5234B(PNABase):
    def __init__(
        self, 
        name: str, 
        address: str,
        data_format: str = "DB",
        **kwargs: "Unpack[VisaInstrumentKWArgs]"
    ) -> None:
        """Driver for Keysight PNA N5234B."""
        super().__init__(
            name,
            address,
            min_freq=10e6,
            max_freq=43.5e9,
            min_power=-120,
            max_power=10,
            nports=2,
            data_format=data_format,
            **kwargs,
        )
