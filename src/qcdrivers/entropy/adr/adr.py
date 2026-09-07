"""
Author: Lino Visser
Affiliation: Forschungszentrum Jülich GmbH
Updated: 13-05-2025
"""

import socket
import threading
import warnings
from typing import Any

from qcodes.instrument import Instrument
from qcodes.validators import Numbers


class ADR(Instrument):
    def __init__(
        self, name: str, address: str, port: int, timeout: float = 10.0, **kwargs: Any
    ) -> None:
        """
        Qcodes driver for Entropy m-type ADR controlling temperature sweeps via PID.
        Control via TCP/IP commands provided by entropy manual.
        Allows temperature and resistance readings of all three sensors (4K, GGG, FAA).

        Args:
            name: name of the qcodes instrument
            address: the server's hostname or IP address
            port: the port used by the server
        """
        super().__init__(name, **kwargs)

        self.HOST = address
        self.PORT = port

        # Prevent simultaneous socket accesses, e.g. from threaded measurements
        self._io_lock = threading.Lock()

        self.s = socket.create_connection(
            (self.HOST, self.PORT),
            timeout=timeout,
        )

        self.s.settimeout(timeout)

        # Startup message
        startup = self.s.recv(4096).decode("utf-8").strip()
        self.log.info("ADR startup message: %s", startup)
        print(startup)

        # Select ADR device
        self.s.sendall(b"DEVSEL ADR\r\n")

        response = self.s.recv(4096).decode("utf-8").strip()
        self.log.debug("DEVSEL response: %s", response)

        # ---------------------------------------------------------
        # Parameters
        # ---------------------------------------------------------

        # Reads 4K plate temperature
        self.add_parameter(
            "t4K",
            label="4K Stage",
            get_cmd="QKELVIN 4k Stage",
            get_parser=self._parse_numeric_response,
            unit="K",
            vals=Numbers(min_value=0, max_value=350),
        )

        # Reads GGG stage temperature
        self.add_parameter(
            "GGG",
            label="GGG",
            get_cmd="QKELVIN GGG",
            get_parser=self._parse_numeric_response,
            unit="K",
            vals=Numbers(min_value=0, max_value=350),
        )

        # Reads GGG stage temperature sensor resistance
        self.add_parameter(
            "RGGG",
            label="RGGG",
            get_cmd="QOHM GGG",
            get_parser=self._parse_numeric_response,
            unit="Ohm",
            vals=Numbers(min_value=0, max_value=350),
        )

        # Reads FAA stage temperature
        self.add_parameter(
            "FAA",
            label="FAA",
            get_cmd="QKELVIN FAA",
            get_parser=self._parse_numeric_response,
            unit="K",
            vals=Numbers(min_value=0, max_value=350),
        )

        # Reads FAA stage temperature sensor resistance
        self.add_parameter(
            "RFAA",
            label="RFAA",
            get_cmd="QOHM FAA",
            get_parser=self._parse_numeric_response,
            unit="Ohm",
            vals=Numbers(min_value=0, max_value=350),
        )

        # Parameter to query compressor status (on/off)
        self.add_parameter(
            "compressor",
            label="compressor",
            get_cmd="QCOMPRESSOR",
            set_cmd=self._set_compressor,
            get_parser=self._parse_numeric_response,
            unit="",
            vals=Numbers(min_value=0, max_value=1),
            snapshot_get=False,
        )

        # Parameter to query magnet sense voltage
        self.add_parameter(
            "magnetsense",
            label="magnetsense",
            get_cmd="QMAGNETSENSE",
            get_parser=self._parse_numeric_response,
            unit="V",
            vals=Numbers(min_value=0, max_value=1),
        )

        # Parameter to query magnet supply current
        self.add_parameter(
            "supplycurrent",
            label="supplycurrent",
            get_cmd="QSUPPLYCURRENT",
            get_parser=self._parse_numeric_response,
            unit="A",
            vals=Numbers(min_value=0, max_value=1),
        )

        # Parameter to query magnet supply voltage
        self.add_parameter(
            "supplyvoltage",
            label="supplyvoltage",
            get_cmd="QSUPPLYVOLTAGE",
            get_parser=self._parse_numeric_response,
            unit="V",
            vals=Numbers(min_value=0, max_value=10),
        )

        # Parameter to query OVC pressure - not supported by ADR currently, problem could not be fixed by Entropy
        self.add_parameter(
            "pressure",
            label="pressure",
            get_cmd="QVACUUM",
            get_parser=self._parse_numeric_response,
            unit="mbar",
            vals=Numbers(min_value=0, max_value=1100),
            snapshot_get=False,
        )

    @staticmethod
    def _terminate(cmd: str) -> str:
        """
        Ensure that a command ends with exactly one CRLF.
        """
        return cmd.rstrip("\r\n") + "\r\n"

    @staticmethod
    def _parse_numeric_response(response: str) -> float:
        """
        Convert an ADR response such as

            '0.045 K'
            '0.045, K'
            '123.4 Ohm'

        to a float.
        """

        response = response.strip()

        if not response:
            warnings.warn(
                "ADR returned an empty response",
                RuntimeWarning,
                stacklevel=2,
            )
            return None

        token = response.split(maxsplit=1)[0].rstrip(",")

        try:
            return float(token)
        except ValueError:
            warnings.warn(
                f"Could not parse numeric ADR response: {response!r}. ",
                RuntimeWarning,
                stacklevel=2,
            )
            return None

    def ask_raw(self, cmd: str) -> str:
        """
        Send a query command to the ADR and return the numeric value from the response.

        The ADR typically returns a string where the first token is the numeric
        value of interest, followed by an optional unit or status message.
        Example: '0.045 K\\r\\n' -> 0.045

        Args:
            cmd: Command string without terminating newline.

        Returns:
            Parsed numeric value (first whitespace-separated token as float).
        """

        command = self._terminate(cmd)

        with self._io_lock:
            self.s.sendall(command.encode("utf-8"))

            data = self.s.recv(4096)

        if not data:
            raise ConnectionError(f"ADR closed connection while executing {cmd!r}")

        response = data.decode("utf-8").strip()

        if not response:
            raise ValueError(f"ADR returned an empty response for command {cmd!r}")

        return response

    def write_raw(self, cmd: str) -> None:
        """
        Send a non-query command to the ADR.

        The ADR expects a command terminated by CRLF, followed by an empty
        CRLF to allow subsequent communication.

        Args:
            cmd: Command string (without or with newline; CRLF will be ensured).
        """
        command = cmd.rstrip("\r\n") + "\r\n\r\n"

        with self._io_lock:
            self.s.sendall(command.encode("utf-8"))

    def tempreg(
        self, enable: bool = 0, temperature: float = 0.045, rate: float = None
    ):  # base value set to approx base T of adr cryostat (40-45mK)
        """
        PID control of magnet vs FAA stage temperature sensor, PID values can be changed in entropy GUI for specific ranges
        Args:
        enable: turn PID loop on/off
        temperature: desired temperature (K)
        rate: desired temperature ramp rate of PID loop (K/min)
        """

        if rate:
            self.write(f"XTEMPREG {enable} {temperature} {rate}")
        else:
            self.write(f"XTEMPREG {enable} {temperature}")

    def voltreg(self, enable: bool = 0, voltage: float = 0):
        """
        PID control of magnet voltage
        Args:
        enable: turn PID loop on/off
        voltage: desired magnet voltage
        """
        self.write(f"XVOLTREG {enable} {voltage}")

    # Start and stop pulse tube compressor
    def _set_compressor(self, value: float) -> None:
        """
        Set pulse tube compressor state.

        Args:
            value:
                1 = compressor ON
                0 = compressor OFF

        Note:
            Commands are intentionally reversed because of the
            incorrectly wired relay.
        """
        if value == 1:
            self.write("STOPCOMPRESSOR")
        elif value == 0:
            self.write("STARTCOMPRESSOR")
        else:
            raise ValueError(f"Invalid compressor state {value!r}. Expected 0 or 1.")

    def get_idn(self):
        """Return the instrument ID string."""
        return {"vendor": "Entropy", "model": "ADR", "serial": "", "firmware": ""}

    def close(self) -> None:
        """
        Close TCP socket and deregister the QCoDeS instrument.
        """

        sock = getattr(self, "s", None)

        if sock is not None:
            try:
                sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass

            try:
                sock.close()
            except OSError:
                pass

        super().close()
