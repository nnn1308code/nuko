# Screen Brightness & CPU Profile Control Tool
* `auto_power_energy_saving_ubuntu.py`	<br>
   It's an unnatural name, but it's a wordplay on "APES."

> **TLP is not used.** This project is designed to operate without TLP.

## 📌 Background (The Problem This Tool Solves)

When Ubuntu's standard setting for automatic screen blanking (Settings > Power Management > Screen Power Saving) is enabled and configured to blank the screen after 3 or 5 minutes, the system may automatically lock or enter a suspended state when the screen turns off.

Once the system is locked, remote access may be disconnected, making it impossible to operate the machine remotely. To avoid this problem, this program controls screen brightness and CPU EPP independently of the operating system's automatic screen blanking feature.

### ⚙️ Technical Design Highlights

* **Idle detection using GNOME/Mutter IdleMonitor**
  Linux sysfs is used to control screen brightness and CPU EPP, while GNOME Mutter IdleMonitor is used to detect idle periods and user activity.

* **Runs as a regular user**
  The program itself is not started with `sudo`. Instead, write access is granted only to the CPU EPP configuration files.

* **No TLP**
  This program does not depend on TLP or auto-cpufreq.

---

## 🛠️ Initial Setup (Required Only Once)

### 1. Create a dedicated group for EPP

`chmod u+rw` does not grant permissions to the "currently logged-in user." It adds read/write permissions for the **file owner**.

Since sysfs EPP files are normally owned by `root`, using `chmod u+rw` alone does not allow a regular user to write to them.

Therefore, create a dedicated group so that regular users can change EPP settings.

```bash
sudo groupadd --system cpu-epp
sudo usermod -aG cpu-epp "$USER"
```

### 2. Set permissions for the EPP configuration files

The following configuration sets the owner to `root`, the group to `cpu-epp`, and the permissions to `0660`.

Unlike `0666`, this does not grant write permission to every user.

```bash
sudo tee /etc/tmpfiles.d/cpu-epp-permissions.conf <<'EOF'
m /sys/devices/system/cpu/cpufreq/policy*/energy_performance_preference 0660 root cpu-epp - -
EOF
```

Apply the configuration immediately:

```bash
sudo systemd-tmpfiles --create /etc/tmpfiles.d/cpu-epp-permissions.conf
```

**Important:** You must log out and log back in for the `usermod -aG` change to take effect.

### 3. Disable automatic Wi-Fi power saving (to prevent connection loss)

To prevent automatic Wi-Fi power saving from causing connection problems, apply the following configuration. This setting persists across reboots.

```bash
sudo tee /etc/NetworkManager/conf.d/default-wifi-powersave-on.conf <<'EOF'
[connection]
# Disable Wi-Fi power saving to prevent disconnections
wifi.powersave = 2
EOF

sudo systemctl restart NetworkManager
```

### 4. Temporarily stop the conflicting standard daemon

`power-profiles-daemon` may overwrite the EPP settings. Therefore, stop it while using this script.

```bash
sudo systemctl stop power-profiles-daemon.service
```

### 5. Make the program executable

```bash
chmod +x auto_power_energy_saving_ubuntu.py
```

---

## 🚀 Running the Program and Options

### 🔹 Option A: Normal Mode (Local Mode)

```bash
python3 auto_power_energy_saving_ubuntu.py
```

* **Stage 1:** After 60 seconds of inactivity → CPU EPP `power`, screen brightness 10%
* **Stage 2:** After 10 minutes of inactivity → CPU EPP `power`, screen brightness 0%
* **Resume:** When user activity such as keyboard or mouse input is detected → CPU EPP `balance_performance`, and the screen brightness is restored to the saved value
* **Stop:** Press `Ctrl + C`

### 🔹 Option B: Remote Mode (`-r` / `--remote`)

```bash
python3 auto_power_energy_saving_ubuntu.py -r
```

or

```bash
python3 auto_power_energy_saving_ubuntu.py --remote
```

In Remote Mode, the saved local screen brightness is not restored when user activity is detected. When the remote session is finished, press `Ctrl + C` to stop the program and restore the saved brightness.

---

## 🔄 Restoring the Original Environment

```bash
sudo systemctl start power-profiles-daemon.service
```

To completely remove the permission configuration that was created:

```bash
sudo rm /etc/tmpfiles.d/cpu-epp-permissions.conf
sudo groupdel cpu-epp
```

※ Before running `groupdel`, make sure that the `cpu-epp` group is not being used for any other purpose.

---

## ⚠️ Notes

* This program depends on GNOME/Mutter IdleMonitor.
* It uses a CPU EPP sysfs path and the Intel backlight path, so it may not work as-is on all hardware.
* It does not use a configuration that grants EPP write permission to every user, such as `0666`.
* `chmod u+rw` adds permissions for the file owner; it does not mean "grant read/write access to the current regular user."
* This program does not suspend the system or lock the screen.
