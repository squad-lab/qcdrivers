"""
Shared fixtures for the QCDrivers test suite.

Nothing here talks to hardware. Tests that need a real QCoDeS ``Parameter`` --
one with a unit, a label and a root instrument -- get a ``DummyInstrument``.

QCoDeS keeps a process-wide instrument registry keyed by name, so an instrument
left open makes the next test asking for that name fail with a duplicate-name
error. ``instrument`` closes everything it created.

Stand-ins for objects QCDrivers is handed by its callers live in :mod:`stubs`;
pytest puts ``tests/`` on ``sys.path``, so test modules import them directly.

"""

from itertools import count

import pytest
from qcodes.instrument_drivers.mock_instruments import (
    DummyChannelInstrument,
    DummyInstrument,
)

_NAMES = count()


@pytest.fixture
def instrument():
    """
    Factory for throwaway QCoDeS instruments.

    Yields:
        Callable[..., DummyInstrument]: Called as ``instrument("x", "y")`` to
            build a gated instrument, or ``instrument(channels=True)`` for a
            channelled one. Names are unique per call.

    """
    created = []

    def _make(*gates: str, channels: bool = False):
        name = f"qcdrivers_test_{next(_NAMES)}"
        if channels:
            inst = DummyChannelInstrument(name)
        else:
            inst = DummyInstrument(name, gates=list(gates) or ["ch1"])
        created.append(inst)
        return inst

    yield _make

    for inst in created:
        inst.close()


@pytest.fixture
def gates(instrument):
    """
    A two-gate instrument, both gates parked at zero.

    Returns:
        DummyInstrument: Instrument exposing ``x`` and ``y``.

    """
    inst = instrument("x", "y")
    inst.x(0.0)
    inst.y(0.0)
    return inst
