#!/usr/bin/env python3

import os
import signal
import sys
import glob
import time
from datetime import datetime
from gi.repository import Gio, GLib

# ============================================================
# Configuration & Arguments Check
# ============================================================
ACTIVE_CPU_PROFILE = "balance_performance"

# --- [Stage 1] 60 seconds idle ---
#IDLE_STAGE1_SECONDS = 15
IDLE_STAGE1_SECONDS = 60
IDLE_STAGE1_CPU_PROFILE = "power"
IDLE_STAGE1_BRIGHTNESS_PERCENT = 10

# --- [Stage 2] 10 minutes idle (600 seconds) ---
IDLE_STAGE2_SECONDS = 10 * 60
#IDLE_STAGE2_SECONDS = 90
IDLE_STAGE2_CPU_PROFILE = "power"
IDLE_STAGE2_BRIGHTNESS_PERCENT = 0  # 0%指定（完全消灯） 0 is screen off, try 1 or 400 or 12000 ...etc

IS_REMOTE_MODE = "-r" in sys.argv or "--remote" in sys.argv

# ============================================================
# Hardware Paths
# ============================================================
INTEL_BRIGHTNESS_PATH = "/sys/class/backlight/intel_backlight/brightness"
INTEL_MAX_BRIGHTNESS_PATH = "/sys/class/backlight/intel_backlight/max_brightness"

MUTTER_BUS = "org.gnome.Mutter.IdleMonitor"
MUTTER_PATH = "/org/gnome/Mutter/IdleMonitor/Core"
MUTTER_IFACE = "org.gnome.Mutter.IdleMonitor"

bus = None
idle_watch_id_stage1 = None
idle_watch_id_stage2 = None
active_watch_id = None
current_cpu_profile = None
saved_brightness_raw = None

def current_time():
    return datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S")

def get_current_brightness_raw():
    if os.path.exists(INTEL_BRIGHTNESS_PATH):
        try:
            with open(INTEL_BRIGHTNESS_PATH, "r") as f:
                return int(f.read().strip())
        except Exception:
            pass
    return None

def set_brightness_percent(percent):
    if not os.path.exists(INTEL_BRIGHTNESS_PATH) or not os.path.exists(INTEL_MAX_BRIGHTNESS_PATH):
        return
    try:
        with open(INTEL_MAX_BRIGHTNESS_PATH, "r") as f:
            max_val = int(f.read().strip())
        
        # ガードを「0」に修正（これにより0%のときに完全に「0」が書き込まれます）
        target_val = max(0, int(max_val * (percent / 100.0)))
        
        with open(INTEL_BRIGHTNESS_PATH, "w") as f:
            f.write(str(target_val))
    except Exception as e:
        print(f"[error] Failed to set backlight: {e}", file=sys.stderr, flush=True)

def set_brightness_raw(raw_value):
    if os.path.exists(INTEL_BRIGHTNESS_PATH) and raw_value is not None:
        try:
            with open(INTEL_BRIGHTNESS_PATH, "w") as f:
                f.write(str(raw_value))
        except Exception as e:
            print(f"[error] Failed to restore backlight: {e}", file=sys.stderr, flush=True)

def set_cpu_profile(profile):
    global current_cpu_profile
    if current_cpu_profile == profile:
        return
    targets = glob.glob("/sys/devices/system/cpu/cpufreq/policy*/energy_performance_preference")
    if not targets:
        return
    try:
        for path in targets:
            with open(path, "w") as f:
                f.write(profile)
        current_cpu_profile = profile
    except Exception as e:
        print(f"[error] Failed to set CPU profile: {e}", file=sys.stderr, flush=True)

def remove_watch(watch_id):
    if watch_id is None:
        return
    try:
        bus.call_sync(MUTTER_BUS, MUTTER_PATH, MUTTER_IFACE, "RemoveWatch", GLib.Variant("(u)", (watch_id,)), None, Gio.DBusCallFlags.NONE, -1, None)
    except Exception:
        pass

def add_all_idle_watches():
    global idle_watch_id_stage1, idle_watch_id_stage2
    if idle_watch_id_stage1 is not None: remove_watch(idle_watch_id_stage1)
    if idle_watch_id_stage2 is not None: remove_watch(idle_watch_id_stage2)

    result1 = bus.call_sync(MUTTER_BUS, MUTTER_PATH, MUTTER_IFACE, "AddIdleWatch", GLib.Variant("(t)", (IDLE_STAGE1_SECONDS * 1000,)), GLib.VariantType("(u)"), Gio.DBusCallFlags.NONE, -1, None)
    idle_watch_id_stage1 = result1.unpack()

    result2 = bus.call_sync(MUTTER_BUS, MUTTER_PATH, MUTTER_IFACE, "AddIdleWatch", GLib.Variant("(t)", (IDLE_STAGE2_SECONDS * 1000,)), GLib.VariantType("(u)"), Gio.DBusCallFlags.NONE, -1, None)
    idle_watch_id_stage2 = result2.unpack()

    print(f"[idle] filters set -> Stage1: {IDLE_STAGE1_SECONDS}s | Stage2: {IDLE_STAGE2_SECONDS}s", flush=True)

def add_active_watch():
    global active_watch_id
    if active_watch_id is not None:
        remove_watch(active_watch_id)
        active_watch_id = None
    result = bus.call_sync(MUTTER_BUS, MUTTER_PATH, MUTTER_IFACE, "AddUserActiveWatch", GLib.Variant("()", ()), GLib.VariantType("(u)"), Gio.DBusCallFlags.NONE, -1, None)
    active_watch_id = result.unpack()
    print(f"[active] waiting for user activity", flush=True)

def on_watch_fired(connection, sender_name, object_path, interface_name, signal_name, parameters):
    global idle_watch_id_stage1, idle_watch_id_stage2, active_watch_id, saved_brightness_raw
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
            print(f"[{now}] [power] Stage 1 -> CPU: {IDLE_STAGE1_CPU_PROFILE} | Screen: {IDLE_STAGE1_BRIGHTNESS_PERCENT}%", flush=True)
            if active_watch_id is None: add_active_watch()

        elif fired_id == idle_watch_id_stage2:
            now = current_time()
            idle_watch_id_stage2 = None
            set_cpu_profile(IDLE_STAGE2_CPU_PROFILE)
            set_brightness_percent(IDLE_STAGE2_BRIGHTNESS_PERCENT)
            print(f"[{now}] [power] Stage 2 -> CPU: {IDLE_STAGE2_CPU_PROFILE} | Screen: {IDLE_STAGE2_BRIGHTNESS_PERCENT}%", flush=True)
            if active_watch_id is None: add_active_watch()

        elif fired_id == active_watch_id:
            now = current_time()
            active_watch_id = None
            set_cpu_profile(ACTIVE_CPU_PROFILE)
            
            if IS_REMOTE_MODE:
                restore_msg = "skipped (Remote Mode active)"
            else:
                if saved_brightness_raw is not None:
                    set_brightness_raw(saved_brightness_raw)
                    restore_msg = "restored"
                else:
                    restore_msg = "skipped"
                    
            print(f"[{now}] [power] User active -> CPU: {ACTIVE_CPU_PROFILE} | Screen: {restore_msg}", flush=True)
            if not IS_REMOTE_MODE:
                saved_brightness_raw = None
                
            time.sleep(1.0)
            add_all_idle_watches()
            
    except Exception as e:
        print(f"\n[error in event loop] {e}", file=sys.stderr, flush=True)
        shutdown()

def shutdown(*args):
    global idle_watch_id_stage1, idle_watch_id_stage2, active_watch_id
    print(f"\n[{current_time()}] [shutdown] stopping script...", flush=True)
    try:
        if idle_watch_id_stage1 is not None: remove_watch(idle_watch_id_stage1)
        if idle_watch_id_stage2 is not None: remove_watch(idle_watch_id_stage2)
        if active_watch_id is not None: remove_watch(active_watch_id)
    except Exception: pass
    try:
        set_cpu_profile(ACTIVE_CPU_PROFILE)
        if saved_brightness_raw is not None: set_brightness_raw(saved_brightness_raw)
        else: set_brightness_percent(80)
    except Exception: pass
    print("\n" + "="*46 + "\n [NOTICE] Please run the following command\n          to restore the original power daemon:\n" + "="*46 + "\n sudo systemctl start power-profiles-daemon.service\n" + "="*46 + "\n")
    loop.quit()

if not os.path.exists(INTEL_BRIGHTNESS_PATH):
    print(f"[fatal] Intel backlight device not found at {INTEL_BRIGHTNESS_PATH}", file=sys.stderr)
    sys.exit(1)
try:
    bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
except Exception as e:
    print(f"[fatal] cannot connect to session D-Bus: {e}", file=sys.stderr)
    sys.exit(1)

bus.signal_subscribe(MUTTER_BUS, MUTTER_IFACE, "WatchFired", MUTTER_PATH, None, Gio.DBusSignalFlags.NONE, on_watch_fired)
signal.signal(signal.SIGINT, shutdown)
signal.signal(signal.SIGTERM, shutdown)

set_cpu_profile(ACTIVE_CPU_PROFILE)
add_all_idle_watches()

print(f"\n" + "="*46 + "\n Automatic 2-Stage Power Controller\n" + "="*46 + f"\n Active CPU : {ACTIVE_CPU_PROFILE}\n Remote Mode: {IS_REMOTE_MODE}\n Stage1 Idle: {IDLE_STAGE1_SECONDS}s -> Screen {IDLE_STAGE1_BRIGHTNESS_PERCENT}%\n Stage2 Idle: {IDLE_STAGE2_SECONDS}s -> Screen {IDLE_STAGE2_BRIGHTNESS_PERCENT}%\n" + "="*46 + "\n")

loop = GLib.MainLoop()
try:
    loop.run()
except KeyboardInterrupt:
    shutdown()
