# Remote Work Screen Brightness & CPU Profile Control Tool

- `auto_energy_saving_ubuntu.py`

## 📌 Background (Problem Solved)

When Ubuntu's standard setting **Settings > Power > Automatic Screen Blank** is enabled and configured to **3 minutes** or **5 minutes**, the screen becomes dim and the system may automatically lock at the same time.

Once the system is locked, a remote connection is disconnected and it becomes impossible to operate the machine remotely. This can cause a serious problem when the computer is being used for remote access.

This program was developed to completely avoid the **unintended system lock and remote disconnection caused by automatic screen blanking**.

### ⚙️ Technical Design Highlights

* **No dependency on the display server (Wayland / X11)**  
  Traditional screen-control tools often work only in either Wayland or X11 environments. This program is designed to work normally in both environments without requiring the user to care which display server is in use.

* **Safe operation with normal user privileges**  
  Normally, modifying the CPU power-saving profile (EPP) on Linux requires administrator (root) privileges. Running the entire program with `sudo`, however, can create risks for the Python environment. Therefore, this program uses a safer approach: **the program itself continues to run as a normal user, while write permission is granted only to the specific CPU configuration files that need to be modified.**

---

## 🛠️ Initial Setup (First Time Only)

To allow the program to run and apply its settings as a normal user, grant the required permission and stop the conflicting power-management daemon as follows.

### 1. Create the Permission Configuration File

Run the following command to create a configuration file that grants normal users permission to modify the CPU EPP configuration files (`0666`):

```bash
sudo tee /etc/tmpfiles.d/cpu-epp-permissions.conf <<'EOF'
m /sys/devices/system/cpu/cpufreq/policy*/energy_performance_preference 0666 root root - -
EOF
```

### 2. Apply the Configuration Immediately

Apply the newly created configuration to the system immediately without waiting for a reboot:

```bash
sudo systemd-tmpfiles --create /etc/tmpfiles.d/cpu-epp-permissions.conf
```

### 3. Temporarily Stop the Conflicting Standard Daemon

If Ubuntu's standard power-management daemon, `power-profiles-daemon`, is running, it may automatically overwrite the settings made by this program and interfere with its operation. Temporarily stop it:

```bash
sudo systemctl stop power-profiles-daemon.service
```

### 4. Make the Program Executable

Grant execute permission to the script:

```bash
chmod +x auto_energy_saving_ubuntu.py
```

---

## 🚀 How to Run and Use the Options

Choose the appropriate option depending on how you are working: whether you are operating the physical machine directly or connecting to it remotely.

### 🔹 Pattern A: Normal Execution (Local Mode)

Use this mode when you are sitting in front of the physical machine and operating it directly.

```bash
python3 auto_energy_saving_ubuntu.py
```

* **Behavior:** After the specified period of inactivity, the screen automatically becomes dim (or completely black if the minimum brightness is set to 0), and the CPU enters power-saving mode.
* **Recovery behavior:** When keyboard, mouse, or other local interaction (**User active**) is detected, both the screen brightness and CPU profile automatically return to their previous states (such as balanced mode).
* **How to stop:** Press `Ctrl + C` in the terminal to stop the program.

### 🔹 Pattern B: Remote Mode (`-r` / `--remote`)

Use this mode when working through a remote desktop connection such as RDP or VNC.

```bash
python3 auto_energy_saving_ubuntu.py -r
# or
python3 auto_energy_saving_ubuntu.py --remote
```

* **Behavior:** While operating the computer remotely, the brightness of the local (physical) display is not needed, so the local display can remain completely dark (brightness set to zero).
* **Effect on the remote session:** Even while the local display remains dark, the remote PC screen shown on the client side remains bright, allowing you to continue working normally. Unlike automatic screen blanking, the machine is not locked and the remote connection is not disconnected.  
  *(As an additional benefit, this can also help prevent other people in an office or at home from viewing the physical screen.)*
* **How to stop:** When you finish the remote session and want to restore the local display, press `Ctrl + C` in the terminal to stop the program.

---

## 🔄 Restoring the Original Environment (Undoing the Configuration)

If you want to completely stop using this program and return to the OS's standard automatic power-management profile, restart the daemon with the following command. (The same effect can also be achieved by rebooting the PC.)

```bash
sudo systemctl start power-profiles-daemon.service
```

* **Behavior:** The previously stopped standard power-management service is restarted, and control of the CPU and power management is safely handed back to the OS.

> **Note:** The created `/etc/tmpfiles.d/cpu-epp-permissions.conf` can normally be left in place without causing problems during regular operation. If you want to remove it completely, run:
>
> ```bash
> sudo rm /etc/tmpfiles.d/cpu-epp-permissions.conf
> ``
