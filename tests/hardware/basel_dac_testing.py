# %%

import time

import numpy as np
from qcodes.instrument import Instrument

from qcdrivers.basel.dacs import BaselDac2

# %%

Instrument.close_all()

dac = BaselDac2(name="dac", address="TCPIP0::192.168.0.108::23::SOCKET")

# %%

dac.set_bandwidth_safely([1, 2, 3, 4, 5], high_bw=True)
dac.activate_dac_channels([1, 2, 3, 4, 5])


# %% awg example


gate_channel = 1
n_points = 10
dt = 30 * 1e-3
v_start = 0
v_stop = 1

# Waveform
vg = np.linspace(v_start, v_stop, n_points)

# Gate vorbereiten
gate = dac.all[gate_channel - 1]
gate.enable(True)
gate.high_bandwidth(True)
gate.voltage(v_start)


# define awg config

awg = dac.awga
awg.enable(False)

awg.write_awg_config(
    {
        "channel": gate_channel,
        "cycles": 1,
        "sampling_rate": dt,
        "waveform": vg,
    }
)

# Basel-AWG trigger
awg.trigger("start only")

# %% start the awg just so without any triggering - test with oscilloscope, choose single and correct trigger

awg.trigger("disable")
awg.enable(True)


# %%

# Langsame, gut sichtbare Rampe
waveform = np.linspace(-1.0, 1.0, 20)

# Ausgangskanal vorbereiten
dac.ch1.enable(True)
dac.ch1.high_bandwidth(True)

dac.ch13.enable(True)
dac.ch13.high_bandwidth(True)

# AWG konfigurieren

for awg in [dac.awga, dac.awgc]:
    awg.enable(False)

dac.awga.channel(1)
dac.awgc.channel(13)

dac.awga.trigger("disable")
dac.awgc.trigger("start only")

for awg in [dac.awga, dac.awgc]:
    awg.cycles(1)
    awg.sampling_rate(0.3 * 1e-3)
    awg.length(len(waveform))
    awg.waveform(waveform)

# %%

# Kurz warten, dann starten
time.sleep(1)
dac.awga.enable(True)


# %%

# --------------------------------------------------
# Einstellungen
# --------------------------------------------------
n_steps = 10
step_time = 30e-3  # 10 ms pro eigentlichem Messpunkt
sample_time = step_time / 2

ramp = np.linspace(-1.0, 1.0, n_steps)

# Jeder Spannungswert wird für zwei AWG-Samples gehalten
ramp_waveform = np.repeat(ramp, 2)

# Eine steigende Flanke pro Rampenpunkt
trigger_waveform = np.tile([0.0, 0.5], n_steps)


# --------------------------------------------------
# Ausgangskanäle einschalten
# --------------------------------------------------
dac.ch1.enable(True)  # Rampe
dac.ch13.enable(True)  # Trigger-Ausgang


# --------------------------------------------------
# AWG A: Spannungsrampe auf Kanal 1
# --------------------------------------------------
ramp_awg = dac.awga

ramp_awg.enable(False)
ramp_awg.channel(1)
ramp_awg.cycles(1)
ramp_awg.trigger("disable")
ramp_awg.sampling_rate(sample_time)
ramp_awg.length(len(ramp_waveform))
ramp_awg.waveform(ramp_waveform)


# --------------------------------------------------
# AWG C: Triggerpulse auf Kanal 13
# --------------------------------------------------
trigger_awg = dac.awgc

trigger_awg.enable(False)
trigger_awg.channel(13)
trigger_awg.cycles(1)
trigger_awg.trigger("disable")
trigger_awg.sampling_rate(sample_time)
trigger_awg.length(len(trigger_waveform))
trigger_awg.waveform(trigger_waveform)

# %%

time.sleep(0.2)

trigger_awg.enable(True)
ramp_awg.enable(True)


# %%

Instrument.close_all()


# %%
