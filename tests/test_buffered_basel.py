"""Hardware-free tests for the buffered Basel DAC node."""

from types import SimpleNamespace

import numpy as np
import pytest
from stubs import Sweep

from qcdrivers.buffered import NodeBaselDAC


class RecordingValue:
    """A callable setting that records every value written to it."""

    def __init__(self):
        self.calls = []

    def __call__(self, value):
        self.calls.append(value)


class FakeAWG:
    """The subset of a Basel AWG used by ``NodeBaselDAC``."""

    def __init__(self):
        self.enable = RecordingValue()
        self.trigger = RecordingValue()
        self.configs = []

    def write_awg_config(self, config):
        self.configs.append(config)


class FakeBaselDAC:
    """A Basel DAC stand-in with the two AWGs used for buffered sweeps."""

    def __init__(self):
        self.awga = FakeAWG()
        self.awgc = FakeAWG()
        self.run_calls = []

    def run_awg_sweep(self, awgs):
        self.run_calls.append(awgs)


def channel_parameter(name, channel, root):
    """Create the parameter attributes read by the Basel node."""
    return SimpleNamespace(
        name=name,
        full_name=name,
        instrument=SimpleNamespace(_channum=channel),
        underlying_instrument=root,
    )


@pytest.fixture
def basel():
    core = FakeBaselDAC()
    return NodeBaselDAC(inst=core), core


@pytest.mark.parametrize(
    ("channel", "awg_name"),
    [(3, "awga"), (17, "awgc")],
)
def test_one_dimensional_sweep_configures_the_awg_for_its_channel(
    basel, channel, awg_name
):
    node, core = basel
    root = object()
    gate = channel_parameter("gate", channel, root)
    sweep = Sweep(gate, -0.2, 0.3, num=6, delay=40e-6)

    result = node.register_sweep(sweep, trigger_type="step")

    awg = getattr(core, awg_name)
    assert result == ("step", 6, 40e-6)
    assert node.contacts == {"gate": channel}
    assert awg.enable.calls == [False]
    assert awg.trigger.calls == ["disable"]
    assert awg.configs[0]["channel"] == channel
    assert awg.configs[0]["cycles"] == 1
    assert awg.configs[0]["sampling_rate"] == 40e-6
    np.testing.assert_allclose(awg.configs[0]["waveform"], sweep.values)

    node.run_sweep()

    assert core.run_calls == [[awg]]


def test_a_sweep_rejects_delays_below_the_dac_minimum(basel):
    node, _ = basel
    gate = channel_parameter("gate", 1, object())

    with pytest.raises(ValueError, match="Delay is too small"):
        node.register_sweep(Sweep(gate, 0, 1, num=5, delay=19e-6))


@pytest.mark.parametrize(
    ("outer_channel", "inner_channel", "outer_awg_name", "inner_awg_name"),
    [(3, 17, "awga", "awgc"), (17, 3, "awgc", "awga")],
)
def test_two_dimensional_sweep_coordinates_different_awgs(
    basel, outer_channel, inner_channel, outer_awg_name, inner_awg_name
):
    node, core = basel
    root = object()
    outer = Sweep(
        channel_parameter("outer", outer_channel, root),
        -1,
        1,
        num=4,
        delay=50e-6,
    )
    inner = Sweep(
        channel_parameter("inner", inner_channel, root),
        0,
        0.5,
        num=5,
        delay=50e-6,
    )

    result = node.register_sweep([outer, inner], trigger_type="ramp")

    outer_awg = getattr(core, outer_awg_name)
    inner_awg = getattr(core, inner_awg_name)
    assert result == ("ramp", 20, 50e-6)
    assert node.contacts == {"inner": inner_channel, "outer": outer_channel}
    assert inner_awg.enable.calls == [False]
    assert outer_awg.enable.calls == [False]
    assert inner_awg.trigger.calls == ["disable"]
    assert outer_awg.trigger.calls == ["single step"]
    assert inner_awg.configs[0]["cycles"] == 4
    assert inner_awg.configs[0]["sampling_rate"] == 50e-6
    np.testing.assert_allclose(inner_awg.configs[0]["waveform"], inner.values)
    assert outer_awg.configs[0]["cycles"] == 1
    assert outer_awg.configs[0]["sampling_rate"] == pytest.approx(250e-6)
    np.testing.assert_allclose(outer_awg.configs[0]["waveform"], outer.values)

    node.run_sweep()

    assert core.run_calls == [[inner_awg, outer_awg]]


def test_two_dimensional_sweep_requires_channels_on_different_awgs(basel):
    node, _ = basel
    root = object()
    outer = Sweep(channel_parameter("outer", 2, root), 0, 1, 4, 50e-6)
    inner = Sweep(channel_parameter("inner", 8, root), 0, 1, 5, 50e-6)

    with pytest.raises(ValueError, match="different AWGs"):
        node.register_sweep([outer, inner])


def test_one_dimensional_sweep_accepts_only_one_parameter(basel):
    node, _ = basel
    root = object()
    gates = [
        channel_parameter("left", 1, root),
        channel_parameter("right", 2, root),
    ]

    with pytest.raises(AssertionError, match="Only one parameter"):
        node.register_sweep(Sweep(gates, 0, 1, 5, 50e-6))


def test_dependents_are_read_in_registration_order(basel):
    node, _ = basel

    def first():
        return np.array([1.0, 2.0])

    def second():
        return np.array([3.0, 4.0])

    node.register_dependent([first, second], num=(2, 2), delay=0.1)
    result = node.fetch()

    assert node.num == (2, 2)
    np.testing.assert_allclose(result[0], [1.0, 2.0])
    np.testing.assert_allclose(result[1], [3.0, 4.0])
