# Screen Brightness & CPU Profile Sync Tool
* auto_energy_saving_ubuntu.py

## 📌 Background (Problem Solved)
In Ubuntu's default settings (Settings > Power > Power Saving), if "Automatic Screen Blank" is enabled and set to "3 minutes" or "5 minutes", a problem occurs where the system is automatically locked (enters suspend state) as soon as the screen dims.

When the system is locked, **remote access is disconnected, and all external control is lost**, leading to critical operational failure.

This program was developed to completely avoid this "unintended system lock and remote disconnection caused by automatic screen blanking."

### ⚙️ Technical Design Points
* **Elimination of dependency on display servers (Wayland / X11)**
  While conventional screen control tools often only work in either Wayland or X11 environments, this program is designed to operate normally in either environment without the user needing to be aware of the difference.
* **Safe execution with general user privileges**
  Writing to the CPU energy performance preference (EPP) files on Linux usually requires administrator (root) privileges. However, running the entire program with `sudo` carries the risk of corrupting the Python environment. Therefore, we have adopted a safe approach: **"Run the program itself with general user privileges and grant write permissions only to the specific CPU setting files."**

---

## 🛠️ Pre-configuration (First-time only)

To allow the program to be executed and applied with general user privileges, follow these steps to grant permissions and stop conflicting daemons.

### 1. Create the permission configuration file
Execute the following command to create a configuration file that grants write permissions (`0666`) to the CPU EPP setting files for general users.
```bash
sudo tee /etc/tmpfiles.d/cpu-epp-permissions.conf <<'EOF'
m /sys/devices/system/cpu/cpufreq/policy*/energy_performance_preference 0666 root root - -
EOF
```

### 2. Apply settings to the system immediately
Apply the created configuration file to the system immediately without waiting for a reboot.
```bash
sudo systemd-tmpfiles --create /etc/tmpfiles.d/cpu-epp-permissions.conf
```

### 3. Disable Wi-Fi automatic power saving (Prevent disconnection)
To prevent Wi-Fi automatic power saving mode, the following action is required. This setting persists after rebooting.
```bash
sudo tee /etc/NetworkManager/conf.d/default-wifi-powersave-on.conf << 'EOF'
[connection]
# Disable Wi-Fi power saving to prevent disconnections (Default is 3)
wifi.powersave = 2
EOF

sudo systemctl restart NetworkManager  # Restart NetworkManager after configuration
```

### 4. Temporarily stop conflicting standard daemons
If the standard power management daemon (`power-profiles-daemon`) running in Ubuntu etc. is active, it may automatically overwrite and interfere with the settings made by this program. Therefore, stop it temporarily.
```bash
sudo systemctl stop power-profiles-daemon.service
```

### 5. Make the program executable
Grant execution permissions to the script.
```bash
chmod +x auto_energy_saving_ubuntu.py
```

---

## 🚀 How to Run and Option Behaviors

Depending on the environment you are working in (operating the physical machine directly or operating via remote connection), use the options accordingly.

### 🔹 Pattern A: Normal Execution (Local Mode)
Use this when sitting in front of the physical machine and operating it directly.
```bash
python3 auto_energy_saving_ubuntu.py
```
* **Behavior:** After a period of inactivity, the screen will automatically dim (if minimum brightness is set to 0, it will be completely dark), and the CPU will enter power-saving mode.
* **Recovery Behavior:** When user activity (such as keyboard or mouse operation) is detected on the physical machine, **both the screen brightness and the CPU profile will automatically return to their original state (e.g., balanced).**
* **How to Stop:** To exit, press **`Ctrl + C`** in the terminal to stop the program.

### 🔹 Pattern B: Remote Mode Execution (`-r` / `--remote`)
Use this when working via screen sharing using RDP or VNC etc. from a remote location.
```bash
python3 auto_energy_saving_ubuntu.py -r
# or
python3 auto_energy_saving_ubuntu.py --remote
```
* **Behavior:** While operating remotely, **since the screen of the physical machine is not needed, it can be kept completely dark (brightness zero).**
* **Impact on Remote Side:** Even if the local screen is dark, **the remote PC screen (the display on the client side) remains bright**, allowing for comfortable operation without any impact. Unlike automatic screen blanking, the machine will not lock and the remote connection will not be cut. (As a result, this also prevents third parties from peeking at the physical machine screen left in the office or home).
* **How to Stop:** To end remote work and restore the local screen brightness, press **`Ctrl + C`** in the terminal to stop the program.

---

## 🔄 Returning to Original Environment (Removing Settings)

To completely stop using this program and return to the OS standard automatic power management profiles, execute the following command to restart the daemon. (Rebooting the PC has the same effect.)

```bash
sudo systemctl start power-profiles-daemon.service
```
* **Behavior:** The stopped standard power management service restarts, and control of the CPU and power is safely handed back to the OS.

*(※ The created `/etc/tmpfiles.d/cpu-epp-permissions.conf` does not harm normal operation if left as is, but if you wish to delete it completely, run `sudo rm /etc/tmpfiles.d/cpu-epp-permissions.conf`)*
