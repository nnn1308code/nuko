#!/usr/bin/env python3

import glob
import os
import shutil
import signal
import subprocess
import sys
import time
from datetime import datetime

from gi.repository import Gio, GLib


# ============================================================
# APES — Automatic Power & Energy Saving
#
# Design:
#   * APES does NOT decide the normal CPU EPP.
#   * At startup, APES saves the EPP that already exists.
#   * AC/battery status is read from /sys/class/power_supply/AC/online
#     (with a generic Mains fallback).
#   * During idle, APES temporarily uses EPP "power".
#   * If TLP is active when APES restores the system, APES does NOT
#     write a balance_* value. TLP remains the owner of power policy.
#   * If TLP is not active, APES restores the exact EPP saved at startup.
#
# This allows the same APES script to work with or without TLP.
# ============================================================

# --- Test/default timings ---
# Change these two values for testing if desired.
IDLE_STAGE1_SECONDS = 20
IDLE_STAGE1_CPU_PROFILE = "power"
IDLE_STAGE1_BRIGHTNESS_PERCENT = 10

IDLE_STAGE2_SECONDS = 40
IDLE_STAGE2_CPU_PROFILE = "power"
IDLE_STAGE2_BRIGHTNESS_PERCENT = 0

IS_REMOTE_MODE = ("-r" in sys.argv) or ("--remote" in sys.argv)

# --- Hardware paths ---
INTEL_BRIGHTNESS_PATH = "/sys/class/backlight/intel_backlight/brightness"
INTEL_MAX_BRIGHTNESS_PATH = "/sys/class/backlight/intel_backlight/max_brightness"

EPP_GLOB = "/sys/devices/system/cpu/cpufreq/policy*/energy_performance_preference"

MUTTER_BUS = "org.gnome.Mutter.IdleMonitor"
MUTTER_PATH = "/org/gnome/Mutter/IdleMonitor/Core"
MUTTER_IFACE = "org.gnome.Mutter.IdleMonitor"

bus = None
loop = None

idle_watch_id_stage1 = None
idle_watch_id_stage2 = None
active_watch_id = None

saved_brightness_raw = None
startup_epp_by_policy = {}
startup_power_source = None
tlp_active_at_start = False


def current_time():
    return datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S")


def get_power_source():
    """
    Return "AC" or "BATTERY".

    Preferred source:
        /sys/class/power_supply/AC/online

    If that path is unavailable, use a generic power-supply entry
    whose type is "Mains".
    """
    ac_online = "/sys/class/power_supply/AC/online"

    if os.path.exists(ac_online):
        try:
            with open(ac_online, "r") as f:
                return "AC" if f.read().strip() == "1" else "BATTERY"
        except OSError:
            pass

    for type_path in glob.glob("/sys/class/power_supply/*/type"):
        try:
            with open(type_path, "r") as f:
                supply_type = f.read().strip()

            if supply_type != "Mains":
                continue

            supply_dir = os.path.dirname(type_path)
            online_path = os.path.join(supply_dir, "online")

            if os.path.exists(online_path):
                with open(online_path, "r") as f:
                    return "AC" if f.read().strip() == "1" else "BATTERY"

        except OSError:
            continue

    return "UNKNOWN"


def read_epp_values():
    """Return {policy_path: epp_value} for all available CPU policies."""
    values = {}

    for path in sorted(glob.glob(EPP_GLOB)):
        try:
            with open(path, "r") as f:
                value = f.read().strip()

            if value:
                values[path] = value

        except OSError:
            pass

    return values


def get_first_epp(values=None):
    if values is None:
        values = read_epp_values()

    for value in values.values():
        return value

    return "unavailable"


def save_startup_state():
    global startup_epp_by_policy
    global startup_power_source
    global tlp_active_at_start

    startup_power_source = get_power_source()
    startup_epp_by_policy = read_epp_values()
    tlp_active_at_start = tlp_is_active()


def tlp_is_active():
    """
    True only when the TLP system service is actually active.

    An installed-but-stopped TLP is treated as "not active", because
    there is no active TLP controller to which APES can hand control.
    """
    if shutil.which("tlp") is None:
        return False

    try:
        result = subprocess.run(
            ["systemctl", "is-active", "--quiet", "tlp.service"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        return result.returncode == 0

    except OSError:
        return False


def set_cpu_profile(profile):
    targets = sorted(glob.glob(EPP_GLOB))

    if not targets:
        print(
            "[warning] No CPU EPP sysfs files were found.",
            file=sys.stderr,
            flush=True,
        )
        return False

    success = True

    for path in targets:
        try:
            with open(path, "w") as f:
                f.write(profile)

        except OSError as e:
            success = False
            print(
                f"[error] Failed to set CPU EPP {path}: {e}",
                file=sys.stderr,
                flush=True,
            )

    return success


def restore_startup_epp():
    """Restore exactly the EPP values that existed before APES changed them."""
    if not startup_epp_by_policy:
        print(
            "[warning] No startup EPP values were saved.",
            file=sys.stderr,
            flush=True,
        )
        return False

    success = True

    for path, value in startup_epp_by_policy.items():
        try:
            with open(path, "w") as f:
                f.write(value)

        except OSError as e:
            success = False
            print(
                f"[error] Failed to restore EPP {path}: {e}",
                file=sys.stderr,
                flush=True,
            )

    return success


def restore_cpu_control():
    """Restore exactly the CPU EPP values saved when APES started.

    APES temporarily overrides CPU EPP with ``power`` during idle time.
    TLP is allowed to manage the normal power policy, but APES must restore
    the state that existed before APES made its temporary change.

    This is important because TLP does not necessarily re-apply its EPP
    immediately when APES exits.
    """
    print(
        "[restore] restoring CPU EPP saved at APES startup",
        flush=True,
    )
    return restore_startup_epp()


def get_current_brightness_raw():
    if os.path.exists(INTEL_BRIGHTNESS_PATH):
        try:
            with open(INTEL_BRIGHTNESS_PATH, "r") as f:
                return int(f.read().strip())
        except OSError:
            pass

    return None


def set_brightness_percent(percent):
    if (
        not os.path.exists(INTEL_BRIGHTNESS_PATH)
        or not os.path.exists(INTEL_MAX_BRIGHTNESS_PATH)
    ):
        return

    try:
        with open(INTEL_MAX_BRIGHTNESS_PATH, "r") as f:
            max_val = int(f.read().strip())

        target_val = max(0, int(max_val * (percent / 100.0)))

        with open(INTEL_BRIGHTNESS_PATH, "w") as f:
            f.write(str(target_val))

    except OSError as e:
        print(
            f"[error] Failed to set backlight: {e}",
            file=sys.stderr,
            flush=True,
        )


def set_brightness_raw(raw_value):
    if not os.path.exists(INTEL_BRIGHTNESS_PATH) or raw_value is None:
        return

    try:
        with open(INTEL_BRIGHTNESS_PATH, "w") as f:
            f.write(str(raw_value))

    except OSError as e:
        print(
            f"[error] Failed to restore backlight: {e}",
            file=sys.stderr,
            flush=True,
        )


def remove_watch(watch_id):
    if watch_id is None:
        return

    try:
        bus.call_sync(
            MUTTER_BUS,
            MUTTER_PATH,
            MUTTER_IFACE,
            "RemoveWatch",
            GLib.Variant("(u)", (watch_id,)),
            None,
            Gio.DBusCallFlags.NONE,
            -1,
            None,
        )
    except Exception:
        pass


def add_all_idle_watches():
    global idle_watch_id_stage1, idle_watch_id_stage2

    if idle_watch_id_stage1 is not None:
        remove_watch(idle_watch_id_stage1)

    if idle_watch_id_stage2 is not None:
        remove_watch(idle_watch_id_stage2)

    result1 = bus.call_sync(
        MUTTER_BUS,
        MUTTER_PATH,
        MUTTER_IFACE,
        "AddIdleWatch",
        GLib.Variant("(t)", (IDLE_STAGE1_SECONDS * 1000,)),
        GLib.VariantType("(u)"),
        Gio.DBusCallFlags.NONE,
        -1,
        None,
    )
    idle_watch_id_stage1 = result1.unpack()

    result2 = bus.call_sync(
        MUTTER_BUS,
        MUTTER_PATH,
        MUTTER_IFACE,
        "AddIdleWatch",
        GLib.Variant("(t)", (IDLE_STAGE2_SECONDS * 1000,)),
        GLib.VariantType("(u)"),
        Gio.DBusCallFlags.NONE,
        -1,
        None,
    )
    idle_watch_id_stage2 = result2.unpack()

    print(
        f"[idle] filters set -> Stage1: {IDLE_STAGE1_SECONDS}s | "
        f"Stage2: {IDLE_STAGE2_SECONDS}s",
        flush=True,
    )


def add_active_watch():
    global active_watch_id

    if active_watch_id is not None:
        remove_watch(active_watch_id)
        active_watch_id = None

    result = bus.call_sync(
        MUTTER_BUS,
        MUTTER_PATH,
        MUTTER_IFACE,
        "AddUserActiveWatch",
        GLib.Variant("()", ()),
        GLib.VariantType("(u)"),
        Gio.DBusCallFlags.NONE,
        -1,
        None,
    )

    active_watch_id = result.unpack()
    print("[active] waiting for user activity", flush=True)


def on_watch_fired(
    connection,
    sender_name,
    object_path,
    interface_name,
    signal_name,
    parameters,
):
    global idle_watch_id_stage1, idle_watch_id_stage2
    global active_watch_id, saved_brightness_raw

    if signal_name != "WatchFired":
        return

    fired_id = parameters.unpack()

    try:
        if fired_id == idle_watch_id_stage1:
            now = current_time()
            idle_watch_id_stage1 = None

            if saved_brightness_raw is None:
                saved_brightness_raw = get_current_brightness_raw()

            set_cpu_profile(IDLE_STAGE1_CPU_PROFILE)
            set_brightness_percent(IDLE_STAGE1_BRIGHTNESS_PERCENT)

            print(
                f"[{now}] [power] Stage 1 -> CPU: "
                f"{IDLE_STAGE1_CPU_PROFILE} | "
                f"Screen: {IDLE_STAGE1_BRIGHTNESS_PERCENT}%",
                flush=True,
            )

            if active_watch_id is None:
                add_active_watch()

        elif fired_id == idle_watch_id_stage2:
            now = current_time()
            idle_watch_id_stage2 = None

            set_cpu_profile(IDLE_STAGE2_CPU_PROFILE)
            set_brightness_percent(IDLE_STAGE2_BRIGHTNESS_PERCENT)

            print(
                f"[{now}] [power] Stage 2 -> CPU: "
                f"{IDLE_STAGE2_CPU_PROFILE} | "
                f"Screen: {IDLE_STAGE2_BRIGHTNESS_PERCENT}%",
                flush=True,
            )

            if active_watch_id is None:
                add_active_watch()

        elif fired_id == active_watch_id:
            now = current_time()
            active_watch_id = None

            restore_cpu_control()

            if IS_REMOTE_MODE:
                restore_msg = "skipped (Remote Mode active)"
            else:
                if saved_brightness_raw is not None:
                    set_brightness_raw(saved_brightness_raw)
                    restore_msg = "restored"
                else:
                    restore_msg = "skipped"

            print(
                f"[{now}] [power] User active -> "
                f"CPU control: startup EPP | "
                f"Screen: {restore_msg}",
                flush=True,
            )

            if not IS_REMOTE_MODE:
                saved_brightness_raw = None

            time.sleep(1.0)
            add_all_idle_watches()

    except Exception as e:
        print(
            f"\n[error in event loop] {e}",
            file=sys.stderr,
            flush=True,
        )
        shutdown()


def shutdown(*args):
    global idle_watch_id_stage1, idle_watch_id_stage2, active_watch_id
    global loop

    print(
        f"\n[{current_time()}] [shutdown] stopping script...",
        flush=True,
    )

    try:
        remove_watch(idle_watch_id_stage1)
        remove_watch(idle_watch_id_stage2)
        remove_watch(active_watch_id)
    except Exception:
        pass

    try:
        restore_cpu_control()

        if saved_brightness_raw is not None:
            set_brightness_raw(saved_brightness_raw)

    except Exception as e:
        print(
            f"[warning] Restore operation failed: {e}",
            file=sys.stderr,
            flush=True,
        )

    notice = (
        "[NOTICE] APES restored the CPU EPP saved at startup.\n"
        "         TLP remains running if it was active."
    )

    print("\n" + "=" * 52)
    print(notice)
    print("=" * 52 + "\n", flush=True)

    if loop is not None:
        try:
            loop.quit()
        except Exception:
            pass


# ============================================================
# Startup
# ============================================================

if not os.path.exists(INTEL_BRIGHTNESS_PATH):
    print(
        f"[fatal] Intel backlight device not found at "
        f"{INTEL_BRIGHTNESS_PATH}",
        file=sys.stderr,
    )
    sys.exit(1)

try:
    bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
except Exception as e:
    print(
        f"[fatal] cannot connect to session D-Bus: {e}",
        file=sys.stderr,
    )
    sys.exit(1)

save_startup_state()

bus.signal_subscribe(
    MUTTER_BUS,
    MUTTER_IFACE,
    "WatchFired",
    MUTTER_PATH,
    None,
    Gio.DBusSignalFlags.NONE,
    on_watch_fired,
)

signal.signal(signal.SIGINT, shutdown)
signal.signal(signal.SIGTERM, shutdown)

add_all_idle_watches()

print(
    "\n"
    + "=" * 52
    + "\n APES — Automatic 2-Stage Power Controller\n"
    + "=" * 52
    + f"\n Power source at startup : {startup_power_source}"
    + f"\n Initial CPU EPP         : {get_first_epp(startup_epp_by_policy)}"
    + f"\n TLP active at startup  : {tlp_active_at_start}"
    + f"\n Remote Mode             : {IS_REMOTE_MODE}"
    + f"\n Stage1 Idle             : {IDLE_STAGE1_SECONDS}s"
    + f" -> CPU {IDLE_STAGE1_CPU_PROFILE}"
    + f" / Screen {IDLE_STAGE1_BRIGHTNESS_PERCENT}%"
    + f"\n Stage2 Idle             : {IDLE_STAGE2_SECONDS}s"
    + f" -> CPU {IDLE_STAGE2_CPU_PROFILE}"
    + f" / Screen {IDLE_STAGE2_BRIGHTNESS_PERCENT}%"
    + "\n"
    + "=" * 52
    + "\n",
    flush=True,
)

loop = GLib.MainLoop()

try:
    loop.run()
except KeyboardInterrupt:
    shutdown()
