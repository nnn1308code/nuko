# 画面輝度・CPUプロファイル連動制御ツール
* auto_power_energy_saving_ubuntu.py<br>
不自然な名前ですが APES の語呂合わせ名です。

> **TLPは使用しません。** 本プロジェクトはTLPなしで動作する構成です。

## 📌 開発の背景（解決する問題）

Ubuntuの標準設定（設定 > 電源管理 > その右側の 省電力）にある「自動画面ブランク」を「3分」や「5分」に設定して有効化すると、画面が暗くなると同時にシステムが自動的にロック（サスペンド状態）されてしまうという問題があります。

システムがロックされると、リモートアクセスが切断され、外部からの操作が一切できなくなるという問題を避けるため、本プログラムではOSの自動画面ブランクとは別に、画面輝度とCPU EPPを制御します。

### ⚙️ 技術的な設計のポイント

* **GNOME/Mutter IdleMonitor を利用したアイドル検知**
  画面の明るさとCPU EPPの制御はLinux sysfsを利用し、アイドル／ユーザー操作の検知にはGNOME Mutter IdleMonitorを利用します。

* **一般ユーザー権限での実行**
  プログラム自体は `sudo` で起動せず、CPU EPP設定ファイルだけに限定した書き込み権限を与える構成にします。

* **TLPを使用しない**
  本プログラムはTLPやauto-cpufreqには依存しません。

---

## 🛠️ 動かす前の事前設定（初回のみ）

### 1. EPP用の専用グループを作成

`chmod u+rw` は「現在ログインしているユーザー」に権限を与える指定ではなく、「ファイル所有者」にread/write権限を与える指定です。

sysfsのEPPファイルは通常 `root` 所有なので、`chmod u+rw` だけでは一般ユーザーが書き込めません。

そこで、一般ユーザーだけがEPPを変更できるように専用グループを作成します。

```bash
sudo groupadd --system cpu-epp
sudo usermod -aG cpu-epp "$USER"
```

### 2. EPP設定ファイルの権限を設定

以下の設定では、所有者を `root`、グループを `cpu-epp`、権限を `0660` にします。
`0666` のように全ユーザーへ書き込み権限を与えません。

```bash
sudo tee /etc/tmpfiles.d/cpu-epp-permissions.conf <<'EOF'
m /sys/devices/system/cpu/cpufreq/policy*/energy_performance_preference 0660 root cpu-epp - -
EOF
```

設定を今すぐ反映します。

```bash
sudo systemd-tmpfiles --create /etc/tmpfiles.d/cpu-epp-permissions.conf
```

**重要:** `usermod -aG` の反映には、いったんログアウトして再ログインする必要があります。

### 3. WIFIの自動省エネモードを無効化（接続断防止）

Wi-Fiの自動省エネモードを防ぐため、以下の対処が必要です。この設定は再起動後も維持されます。

```bash
sudo tee /etc/NetworkManager/conf.d/default-wifi-powersave-on.conf <<'EOF'
[connection]
# Disable Wi-Fi power saving to prevent disconnections
wifi.powersave = 2
EOF

sudo systemctl restart NetworkManager
```

### 4. 競合する標準デーモンを一時停止

`power-profiles-daemon` がEPP設定を上書きする場合があるため、このスクリプトを使用する間は停止します。

```bash
sudo systemctl stop power-profiles-daemon.service
```

### 5. プログラムを実行可能にする

```bash
chmod +x auto_power_energy_saving_ubuntu.py
```

---

## 🚀 実行方法とオプションの挙動

### 🔹 パターンA：通常実行（ローカルモード）

```bash
python3 auto_power_energy_saving_ubuntu.py
```

* **Stage 1:** 60秒アイドル → CPU EPP `power`、画面10%
* **Stage 2:** 10分アイドル → CPU EPP `power`、画面0%
* **復帰:** キーボードやマウスなどのUser activeを検知 → CPU EPP `balance_performance`、画面輝度を保存値へ復元
* **停止:** `Ctrl + C`

### 🔹 パターンB：リモートモード（`-r` / `--remote`）

```bash
python3 auto_power_energy_saving_ubuntu.py -r
```

または

```bash
python3 auto_power_energy_saving_ubuntu.py --remote
```

リモートモードでは、User activeを検知してもローカル画面輝度の保存値への復元を行いません。リモート作業終了後に `Ctrl + C` で停止すると、保存していた輝度へ戻します。

---

## 🔄 元の環境に戻す場合

```bash
sudo systemctl start power-profiles-daemon.service
```

作成した権限設定を完全に削除する場合：

```bash
sudo rm /etc/tmpfiles.d/cpu-epp-permissions.conf
sudo groupdel cpu-epp
```

※ `groupdel` の前に、そのグループを他の用途で使用していないことを確認してください。

---

## ⚠️ 注意

* このプログラムはGNOME/Mutter IdleMonitorに依存します。
* CPU EPPのsysfsパスとIntelバックライトのパスを使用するため、すべてのハードウェアでそのまま動作するとは限りません。
* `0666` のように全ユーザーへEPP書き込み権限を与える設定は使用しません。
* `chmod u+rw` はファイル所有者への権限追加であり、一般ユーザーへの権限付与を意味しません。
* 本プログラムはサスペンドや画面ロックを実行しません。
