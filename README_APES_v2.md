# APES — Automatic Power & Energy Saving

`auto_power_energy_saving_tlp_ubuntu_v2.py`

APES automatically changes CPU EPP and screen brightness toward lower-power settings according to the user's idle time in a GNOME environment on Ubuntu.

## Important Change in This Version

This version no longer assumes that APES itself should define the normal CPU EPP as:

```text
AC      → balance_performance
Battery → balance_power
```

Instead, **APES reads and remembers the actual power state and CPU EPP that already exist when APES starts.**

APES then changes CPU EPP to `power` only while the machine is idle.

### At startup

APES remembers:

```text
Power source
  ├─ AC
  └─ Battery

CPU EPP
  └─ The actual EPP value present at startup
```

The preferred power-source check is:

```text
/sys/class/power_supply/AC/online
```

where:

```text
1 = AC
0 = Battery
```

If that path is unavailable, APES searches for a power-supply device whose `type` is `Mains`.

---

## With and Without TLP

APES always saves the actual CPU EPP values present when it starts.

During idle time, APES temporarily changes CPU EPP to `power`. When user activity is detected or APES exits, it restores the exact EPP values saved at startup.

This behavior is the same whether TLP is active or not.

### When TLP is active

TLP continues running normally. APES does not stop or restart TLP and does not run `tlp ac` or `tlp bat`. APES simply restores the EPP values saved at startup when it releases its temporary idle-time override.

If the AC/Battery state changes **after APES has restored the startup state**, TLP can then apply its own normal policy in response to that power-source event.

### When TLP is not active

APES restores the exact EPP values saved at startup. APES does not assume that the normal value must be `balance_performance` or `balance_power`.

---

# Operation

The current downloaded version uses test timings:

```text
Stage 1 : 20 seconds
Stage 2 : 40 seconds
```

### Stage 1

```text
CPU EPP        : power
Screen         : 10%
```

### Stage 2

```text
CPU EPP        : power
Screen         : 0%
```

When user activity is detected:

```text
Restore the exact EPP values saved at APES startup
```

Screen brightness is restored to the saved value in normal mode.

---

# Running

```bash
python3 auto_power_energy_saving_tlp_ubuntu_v2.py
```

Remote mode:

```bash
python3 auto_power_energy_saving_tlp_ubuntu_v2.py -r
```

or:

```bash
python3 auto_power_energy_saving_tlp_ubuntu_v2.py --remote
```

Stop with:

```text
Ctrl + C
```

---

# ⚠️ Recommended Usage

Before starting APES, first select the power state in which you intend to use it: **AC power or battery power**. Allow the normal power-management policy to settle, and then start APES.

APES saves the CPU EPP values that exist **at the moment APES starts**. It later restores those exact values when user activity is detected or APES exits.

For this reason, avoid switching between AC and battery while APES is running.

For example:

```text
AC connected
    ↓
TLP: balance_performance
    ↓
Start APES
    ↓
APES saves balance_performance
    ↓
Idle → APES uses power
    ↓
Activity → APES restores balance_performance
```

If AC is disconnected while APES is still running, TLP may change the EPP to its battery policy. However, when APES later exits or restores its startup state, APES will restore the value it saved when it started. Therefore, the restored value may not match the normal EPP expected for the new power state.

This is an intentional consequence of APES's startup-state restoration design. **It is not an error or a bug.**

Recommended sequence:

```text
1. Select AC or Battery
2. Let the normal power policy settle
3. Start APES
4. Keep the same power state while APES is running
5. Stop APES when finished
```

---

# `sudo`

APES itself does not need to be run with `sudo`.

Run it as a regular user:

```bash
python3 auto_power_energy_saving_tlp_ubuntu_v2.py
```

Only the necessary permissions for writing the CPU EPP sysfs files should be configured.

---

# TLP Detection

This version does not consider the mere presence of the `tlp` command sufficient evidence that TLP is controlling the system.

APES checks:

```text
tlp command exists
        +
tlp.service is active
        ↓
TLP active
```

Therefore, if TLP is installed but its service is stopped, APES treats TLP as inactive and restores the EPP saved at startup.

---

# Design Philosophy

The roles are intentionally separated:

```text
TLP
 ↓
Normal system-wide power management

APES
 ↓
Temporary idle-time power saving
```

APES does not decide what the normal CPU EPP should be.

Therefore the same APES program can be used with:

```text
TLP installed and active
```

or:

```text
TLP not installed / not active
```

---

# GNOME / Wayland

User activity detection uses:

```text
org.gnome.Mutter.IdleMonitor
```

The current implementation is therefore primarily intended for GNOME environments.

---

# Difference from Screen Blanking

APES does not use Ubuntu's screen-blanking mechanism.

It controls:

```text
CPU EPP
Screen brightness
```

It does not:

```text
Lock the computer
Suspend the computer
```

The purpose is to reduce power consumption while avoiding the loss of remote access such as RDP.

---

# Testing

The program has been tested on a Dell Latitude 5300 running Ubuntu 26.04.1 with GNOME and Wayland, using both AC and battery power.

The previous TLP-compatible version confirmed:

```text
AC:
balance_performance → power → balance_performance

Battery:
balance_power → power → balance_power
```

This version changes the design so that APES does not hard-code those `balance_*` values. Instead, it saves the actual EPP present at startup. The `balance_*` values seen in these tests are the startup values restored by APES; they are not values hard-coded into APES.

---

# Notes

- APES depends on GNOME/Mutter IdleMonitor.
- CPU EPP sysfs paths can vary by hardware and kernel.
- Screen brightness control is hardware-dependent.
- APES always restores the exact EPP values saved at startup.
- TLP remains active independently and may change EPP when its own power-management events occur, such as an AC/Battery transition.
- The downloaded version currently uses Stage 1 = 20 seconds and Stage 2 = 40 seconds for testing. Change these values before normal long-term use if desired.


# 🔊 Audio Output and Multiple Monitors

APES **does not control audio output**.

The script controls CPU EPP and screen brightness only. Therefore, when APES enters its power-saving stages during idle time, it does not change the volume or the audio output device.

Screen brightness is also limited to the **local PC's main screen (`intel_backlight`)** in the current implementation.

If you use a dual-monitor or multi-monitor setup:

- Local PC screen → APES may adjust its brightness
- Second/external monitor → APES does not adjust its brightness

In other words, APES is not designed to control the brightness of external monitors.


## License

See the repository's LICENSE file.
