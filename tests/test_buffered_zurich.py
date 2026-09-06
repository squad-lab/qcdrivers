"""Hardware-free tests for the buffered Zurich Instruments nodes."""

from types import SimpleNamespace

import numpy as np
import pytest
from stubs import Sweep

from qcdrivers.buffered.zurich import NodeMFLI, NodeUHFLI


class FakeLabOneModule:
    """Recording stand-in for LabOne DAQ and Sweeper modules."""

    def __init__(self):
        self.settings = []
        self.subscriptions = []
        self.unsubscribe_calls = []
        self.execute_calls = 0
        self.finish_calls = 0
        self.finished_states = []
        self.read_result = {}
        self.remaining_values = [0.0]

    def set(self, key, value):
        self.settings.append((key, value))

    def subscribe(self, path):
        self.subscriptions.append(path)

    def unsubscribe(self, path):
        self.unsubscribe_calls.append(path)

    def execute(self):
        self.execute_calls += 1

    def finish(self):
        self.finish_calls += 1

    def finished(self):
        if self.finished_states:
            return self.finished_states.pop(0)
        return True

    def read(self):
        return self.read_result

    def getDouble(self, key):
        assert key == "remainingtime"
        if len(self.remaining_values) > 1:
            return self.remaining_values.pop(0)
        return self.remaining_values[0]


class FakeDaqServer:
    """The LabOne server surface used by both Zurich nodes."""

    def __init__(self):
        self.data_modules = []
        self.sweeper = FakeLabOneModule()
        self.sweep_calls = 0
        self.int_settings = []
        self.double_settings = []
        self.settings = []

    def dataAcquisitionModule(self):
        module = FakeLabOneModule()
        self.data_modules.append(module)
        return module

    def sweep(self):
        self.sweep_calls += 1
        return self.sweeper

    def setInt(self, path, value):
        self.int_settings.append((path, value))

    def setDouble(self, path, value):
        self.double_settings.append((path, value))

    def set(self, path, value):
        self.settings.append((path, value))


def zurich_instrument(server, serial="dev1234"):
    """Build the nested wrapper exposed by zhinst-qcodes instruments."""
    core = SimpleNamespace(
        serial=serial,
        session=SimpleNamespace(daq_server=server),
    )
    return SimpleNamespace(core=core)


def zi_parameter(path, name="signal"):
    return SimpleNamespace(zi_node=path, full_name=name)


def last_setting(module, key):
    """Return the last value written to a module setting."""
    return [value for setting, value in module.settings if setting == key][-1]


@pytest.fixture(autouse=True)
def clear_shared_uhfli_modules():
    NodeUHFLI._shared.clear()
    yield
    NodeUHFLI._shared.clear()


@pytest.fixture
def mfli():
    server = FakeDaqServer()
    node = NodeMFLI(zurich_instrument(server))
    return node, server


def test_mfli_initializes_a_hardware_triggered_daq_module(mfli):
    node, _ = mfli

    assert node.serial == "dev1234"
    assert node.daq_module.settings[:2] == [("device", "dev1234"), ("type", 6)]


def test_mfli_configures_a_one_dimensional_acquisition(mfli):
    node, server = mfli
    signal = zi_parameter("/DEMODS/0/SAMPLE.R")

    node.register_dependent(signal, num=6, delay=0.001)

    module = node.daq_module
    assert node.dependents == ["/demods/0/sample.r"]
    assert ("/dev1234/demods/0/enable", 1) in server.int_settings
    assert ("/dev1234/demods/0/timeconstant", 0.001) in server.double_settings
    assert last_setting(module, "grid/mode") == "linear"
    assert last_setting(module, "triggernode") == ("/dev1234/demods/0/sample.TrigIn1")
    assert last_setting(module, "grid/rows") == 1
    assert last_setting(module, "grid/cols") == 6
    assert last_setting(module, "duration") == pytest.approx(0.006)
    assert last_setting(module, "delay") == pytest.approx(0.001)
    assert last_setting(module, "holdoff/time") == pytest.approx(0.0055)
    assert module.unsubscribe_calls == ["*"]
    assert module.subscriptions == ["/dev1234/demods/0/sample.r"]
    assert module.execute_calls == 1


def test_mfli_supports_exact_endless_2d_acquisition_and_force_trigger(
    mfli, monkeypatch
):
    node, server = mfli
    sleeps = []
    monkeypatch.setattr("qcdrivers.buffered.zurich.nodes.sleep", sleeps.append)

    node.register_dependent(
        [zi_parameter("/demods/0/sample.x"), zi_parameter("/demods/0/sample.y")],
        num=(2, 3),
        delay=0.01,
        input_trigger=2,
        force_trigger=True,
        trigger_delay=0.002,
        trigger_level=0.75,
        tc_factor=2,
        grid_mode="exact",
        edge="both",
        endless=True,
    )

    module = node.daq_module
    assert ("/dev1234/demods/0/timeconstant", 0.005) in server.double_settings
    assert ("/dev1234/triggers/in/1/level", 0.75) in server.double_settings
    assert last_setting(module, "edge") == 3
    assert last_setting(module, "endless") == 1
    assert not any(key == "count" for key, _ in module.settings)
    assert last_setting(module, "grid/rows") == 2
    assert last_setting(module, "grid/cols") == 3
    assert not any(key == "duration" for key, _ in module.settings)
    assert last_setting(module, "delay") == pytest.approx(0.012)
    assert last_setting(module, "forcetrigger") == 1
    assert sleeps == [0.2]


def test_mfli_rejects_an_unknown_grid_mode(mfli):
    node, _ = mfli

    with pytest.raises(ValueError, match="Invalid grid_mode"):
        node.register_dependent(
            zi_parameter("/demods/0/sample.r"),
            num=5,
            delay=0.01,
            grid_mode="cubic",
        )


def test_mfli_fetch_flattens_each_subscribed_value(mfli):
    node, _ = mfli
    node.register_dependent(
        [zi_parameter("/demods/0/sample.x"), zi_parameter("/demods/0/sample.y")],
        num=4,
        delay=0.01,
    )
    node.daq_module.read_result = {
        "dev1234": {
            "demods": {
                "0": {
                    "sample.x": [{"value": [[1, 2], [3, 4]]}],
                    "sample.y": [{"value": [[5, 6], [7, 8]]}],
                }
            }
        }
    }

    arrays = node.fetch()

    np.testing.assert_array_equal(arrays[0], [1, 2, 3, 4])
    np.testing.assert_array_equal(arrays[1], [5, 6, 7, 8])
    assert node.daq_module.finish_calls == 2


def test_mfli_fetch_stops_waiting_at_the_timeout(mfli, monkeypatch):
    node, _ = mfli
    node.register_dependent(zi_parameter("/demods/0/sample.r"), num=2, delay=0.01)
    node.daq_module.finished_states = [False]
    node.daq_module.read_result = {
        "dev1234": {"demods": {"0": {"sample.r": [{"value": [[1, 2]]}]}}}
    }
    times = iter([0.0, 1.0])
    monkeypatch.setattr("qcdrivers.buffered.zurich.nodes.time", lambda: next(times))
    monkeypatch.setattr("qcdrivers.buffered.zurich.nodes.sleep", lambda seconds: None)

    arrays = node.fetch(timeout=0.1)

    np.testing.assert_array_equal(arrays[0], [1, 2])


@pytest.fixture
def uhfli():
    server = FakeDaqServer()
    node = NodeUHFLI(zurich_instrument(server))
    return node, server


def test_uhfli_reuses_one_sweeper_per_physical_instrument():
    server = FakeDaqServer()

    first = NodeUHFLI(zurich_instrument(server, "dev5678"))
    second = NodeUHFLI(zurich_instrument(server, "dev5678"))

    assert first.sweeper_module is second.sweeper_module
    assert server.sweep_calls == 1


@pytest.mark.parametrize(("spacing", "mapping"), [("lin", 0), ("log", 1)])
def test_uhfli_configures_linear_and_logarithmic_sweeps(uhfli, spacing, mapping):
    node, _ = uhfli
    frequency = zi_parameter("/oscs/0/freq", "lockin_frequency")
    sweep = Sweep(frequency, 1e3, 1e6, num=11, delay=0.02)

    result = node.register_sweep(
        [sweep],
        spacing=spacing,
        averaging=4,
        averaging_tc=7,
        sweep_order=5,
        settling_inaccuracy=1e-5,
        phase_unwrap=True,
    )

    module = node.sweeper_module
    assert result == (None, 11, None)
    assert last_setting(module, "gridnode") == "/dev1234/oscs/0/freq"
    assert last_setting(module, "start") == 1e3
    assert last_setting(module, "stop") == 1e6
    assert last_setting(module, "samplecount") == 11
    assert last_setting(module, "xmapping") == mapping
    assert last_setting(module, "averaging/sample") == 4
    assert last_setting(module, "averaging/tc") == 7
    assert last_setting(module, "order") == 5
    assert last_setting(module, "settling/inaccuracy") == 1e-5
    assert last_setting(module, "phaseunwrap") == 1


def test_uhfli_sweeper_rejects_invalid_sweep_requests(uhfli):
    node, _ = uhfli
    valid = Sweep(zi_parameter("/oscs/0/freq"), 1, 2, 3, 0.1)

    with pytest.raises(ValueError, match="Only 1D sweeps"):
        node.register_sweep([valid, valid])

    missing_node = Sweep(SimpleNamespace(full_name="gate"), 1, 2, 3, 0.1)
    with pytest.raises(ValueError, match="has no zi_node"):
        node.register_sweep([missing_node])

    with pytest.raises(ValueError, match="Invalid spacing"):
        node.register_sweep([valid], spacing="geometric")


def test_uhfli_runs_the_sweeper_and_waits_only_as_the_root(uhfli, monkeypatch):
    node, _ = uhfli
    node.register_sweep([Sweep(zi_parameter("/oscs/0/freq"), 1, 2, 4, 0.25)])
    sleeps = []
    monkeypatch.setattr("qcdrivers.buffered.zurich.nodes.sleep", sleeps.append)

    node.run_sweep()
    assert sleeps == []

    node.toplevel = True
    node.run_sweep()
    assert sleeps == [pytest.approx(1.25)]
    assert node.sweeper_module.execute_calls == 2
    assert node.daq_module.finish_calls == 2


def test_uhfli_configures_daq_acquisition_for_multiple_demodulators(uhfli):
    node, server = uhfli

    node.register_dependent(
        zi_parameter("/demods/1/sample.r"),
        num=(3, 4),
        delay=0.02,
        acquisition="daq",
        demod_channels=[0, 1],
        edge="falling",
        count=2,
    )

    module = node.daq_module
    assert node._active_acquisition == "daq"
    assert server.int_settings == [
        ("/dev1234/demods/0/enable", 1),
        ("/dev1234/demods/1/enable", 1),
    ]
    assert last_setting(module, "triggernode") == ("/dev1234/demods/1/sample.TrigIn1")
    assert last_setting(module, "edge") == 2
    assert last_setting(module, "count") == 2
    assert last_setting(module, "grid/rows") == 3
    assert last_setting(module, "grid/cols") == 4
    assert server.settings == [
        (f"/dev1234/triggers/in/{index}/imp50", 0) for index in range(4)
    ]


def test_uhfli_supports_exact_endless_daq_and_force_trigger(uhfli, monkeypatch):
    node, _ = uhfli
    sleeps = []
    monkeypatch.setattr("qcdrivers.buffered.zurich.nodes.sleep", sleeps.append)

    node.register_dependent(
        [zi_parameter("/demods/0/sample.x"), zi_parameter("/demods/0/sample.y")],
        num=5,
        delay=0.01,
        acquisition="daq",
        grid_mode="exact",
        endless=True,
        force_trigger=True,
    )

    module = node.daq_module
    assert last_setting(module, "grid/rows") == 1
    assert last_setting(module, "grid/cols") == 5
    assert not any(key == "count" for key, _ in module.settings)
    assert not any(key == "duration" for key, _ in module.settings)
    assert last_setting(module, "forcetrigger") == 1
    assert sleeps == [0.2]


def test_uhfli_daq_rejects_an_unknown_grid_mode(uhfli):
    node, _ = uhfli

    with pytest.raises(ValueError, match="Invalid grid_mode"):
        node.register_dependent(
            zi_parameter("/demods/0/sample.r"),
            num=5,
            delay=0.01,
            acquisition="daq",
            grid_mode="cubic",
        )


def test_uhfli_maps_sweeper_dependents_and_deduplicates_subscriptions(uhfli):
    node, _ = uhfli
    dependents = [
        zi_parameter("/demods/0/sample.r", "magnitude"),
        zi_parameter("/demods/0/sample.theta", "phase"),
        zi_parameter("/demods/1/sample.x", "x"),
        zi_parameter("/demods/1/sample.y", "y"),
    ]

    node.register_dependent(
        dependents,
        num=10,
        delay=0.1,
        acquisition="sweeper",
    )

    assert node._active_acquisition == "sweeper"
    assert set(node.sweeper_module.subscriptions) == {
        "/dev1234/demods/0/sample",
        "/dev1234/demods/1/sample",
    }
    assert [spec["field"] for spec in node._ctx["sweeper_fields"]] == [
        "r",
        "phase",
        "x",
        "y",
    ]


def test_uhfli_rejects_invalid_dependent_modes(uhfli):
    node, _ = uhfli
    signal = zi_parameter("/demods/0/sample.r")

    node.endnode = False
    with pytest.raises(ValueError, match="only be registered on end nodes"):
        node.register_dependent(signal, 5, 0.1, acquisition="sweeper")

    node.endnode = True
    with pytest.raises(ValueError, match="Unsupported Sweeper dependent"):
        node.register_dependent(
            zi_parameter("/demods/0/sample.frequency"),
            5,
            0.1,
            acquisition="sweeper",
        )

    with pytest.raises(ValueError, match="Unknown acquisition mode"):
        node.register_dependent(signal, 5, 0.1, acquisition="stream")


def test_uhfli_fetch_requires_a_registered_acquisition(uhfli):
    node, _ = uhfli

    with pytest.raises(RuntimeError, match="No acquisition"):
        node.fetch()


def test_uhfli_fetches_and_flattens_daq_values(uhfli):
    node, _ = uhfli
    node.register_dependent(
        zi_parameter("/demods/0/sample.r"),
        num=4,
        delay=0.01,
        acquisition="daq",
    )
    node.daq_module.read_result = {
        "dev1234": {"demods": {"0": {"sample.r": [{"value": [[1, 2], [3, 4]]}]}}}
    }

    arrays = node.fetch()

    np.testing.assert_array_equal(arrays[0], [1, 2, 3, 4])


def test_uhfli_fetches_and_flattens_sweeper_fields(uhfli, monkeypatch):
    node, _ = uhfli
    monkeypatch.setattr("qcdrivers.buffered.zurich.nodes.sleep", lambda seconds: None)
    node.register_dependent(
        [
            zi_parameter("/demods/0/sample.r"),
            zi_parameter("/demods/0/sample.theta"),
        ],
        num=3,
        delay=0.1,
        acquisition="sweeper",
    )
    node.sweeper_module.remaining_values = [np.nan, 0.5]
    node.sweeper_module.read_result = {
        "dev1234": {
            "demods": {
                "0": {
                    "sample": [
                        [
                            {
                                "r": [[1.0, 2.0, 3.0]],
                                "phase": [[0.1, 0.2, 0.3]],
                            }
                        ]
                    ]
                }
            }
        }
    }
    node.sweeper_module.finished_states = [False, True]

    arrays = node.fetch(timeout=1.0)

    np.testing.assert_allclose(arrays[0], [1.0, 2.0, 3.0])
    np.testing.assert_allclose(arrays[1], [0.1, 0.2, 0.3])
    assert node.sweeper_module.finish_calls == 1
    assert node.sweeper_module.unsubscribe_calls[-1] == "*"


def test_uhfli_reports_a_missing_sweeper_sample_field(uhfli):
    node, _ = uhfli
    node.register_dependent(
        zi_parameter("/demods/0/sample.r"),
        num=2,
        delay=0.1,
        acquisition="sweeper",
    )
    node.sweeper_module.read_result = {
        "dev1234": {"demods": {"0": {"sample": [[{"x": [[1.0, 2.0]]}]]}}}
    }

    with pytest.raises(KeyError, match="Field 'r' not found"):
        node.fetch()


def test_uhfli_sweeper_timeout_finishes_the_module(uhfli, monkeypatch):
    node, _ = uhfli
    node.register_dependent(
        zi_parameter("/demods/0/sample.r"),
        num=3,
        delay=0.1,
        acquisition="sweeper",
    )
    node.sweeper_module.remaining_values = [0.1]
    node.sweeper_module.finished_states = [False]
    times = iter([0.0, 1.0])
    monkeypatch.setattr("qcdrivers.buffered.zurich.nodes.time", lambda: next(times))
    monkeypatch.setattr("qcdrivers.buffered.zurich.nodes.sleep", lambda seconds: None)

    with pytest.raises(TimeoutError, match="timed out"):
        node._fetch_sweeper(timeout=0.2)

    assert node.sweeper_module.finish_calls == 1
