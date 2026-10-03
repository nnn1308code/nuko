# APES — 自動電力・省エネルギー制御

`auto_power_energy_saving_tlp_ubuntu_v2.py`

UbuntuのGNOME環境で、ユーザーのアイドル時間に応じてCPU EPPと画面輝度を自動的に省電力側へ変更するプログラムです。

## 今回の重要な変更

今回のバージョンでは、APES自身が

```text
AC  → balance_performance
Battery → balance_power
```

と決めつける方式をやめました。

**APES起動時に、現在の電源状態と現在のCPU EPPを読み取り、その状態を記憶します。**

その後、アイドル時だけCPU EPPを `power` に変更します。

### 起動時

APESは次を記憶します。

```text
電源状態
  ├─ AC
  └─ Battery

CPU EPP
  └─ 起動時に実際に設定されていた値
```

電源状態の判定には、まず次を使用します。

```text
/sys/class/power_supply/AC/online
```

```text
1 = AC
0 = Battery
```

このパスが存在しない場合は、`type` が `Mains` の電源デバイスを探します。

---

## TLPがある場合とない場合

APESは、**起動した時点で実際に設定されているCPU EPPを保存します。**

アイドル時にはCPU EPPを一時的に `power` へ変更し、ユーザー操作を検出したとき、またはAPESを終了したときに、起動時に保存したEPPをそのまま復元します。

この動作は、TLPがactiveの場合でも、TLPがactiveでない場合でも同じです。

### TLPが動作している場合

TLPは通常どおり動作を続けます。APESはTLPを停止・再起動せず、`tlp ac` や `tlp bat` も実行しません。APESは一時的な省電力制御を解除するときに、起動時に保存したEPPを復元します。

APESが起動時の状態を復元した**後**にAC/Batteryが切り替わった場合は、その電源状態の変化に応じてTLPが通常のポリシーを適用できます。

### TLPが動作していない場合

APESは起動時に保存したEPPをそのまま復元します。APESは通常値を `balance_performance` や `balance_power` と決めつけません。

---

# 動作

現在のテスト設定では、

```text
Stage 1 : 20秒
Stage 2 : 40秒
```

です。

### Stage 1

```text
CPU EPP     : power
画面輝度    : 10%
```

### Stage 2

```text
CPU EPP     : power
画面輝度    : 0%
```

ユーザー操作を検出すると、CPU EPPについては、

```text
APES起動時に保存したEPPをそのまま復元
```

となります。

画面輝度は、通常モードでは保存していた値へ復元します。

---

# 実行

```bash
python3 auto_power_energy_saving_tlp_ubuntu_v2.py
```

リモートモード：

```bash
python3 auto_power_energy_saving_tlp_ubuntu_v2.py -r
```

または：

```bash
python3 auto_power_energy_saving_tlp_ubuntu_v2.py --remote
```

終了：

```text
Ctrl + C
```

---

# ⚠️ APESの推奨使用方法

APESを起動する前に、まず使用する電源状態を決めてください。**AC電源で使用するのか、バッテリーで使用するのかを先に決めます。** その状態で通常の電源管理ポリシーが落ち着いてから、APESを起動します。

APESは、**起動した瞬間に設定されているCPU EPPを保存**します。そして、ユーザー操作を検出したとき、またはAPESを終了したときに、その保存値をそのまま復元します。

そのため、APES動作中はAC電源とバッテリーを切り替えないことを推奨します。

例えば、

```text
AC接続
    ↓
TLP: balance_performance
    ↓
APES起動
    ↓
APESが balance_performance を保存
    ↓
アイドル → APES: power
    ↓
操作 → APESが balance_performance を復元
```

APES動作中にACを抜くと、TLPがバッテリー用のEPPへ変更する場合があります。しかし、その後APESを終了したり起動時の状態へ復元したりすると、APESは**起動時に保存したEPP**へ戻します。そのため、復元されたEPPが、新しい電源状態で通常期待されるEPPと一致しない場合があります。

これはAPESが「起動時の状態を保存して復元する」という設計から生じる仕様です。**エラーやバグではありません。**

推奨する手順は次のとおりです。

```text
1. ACまたはBatteryを選択する
2. 通常の電源管理ポリシーが落ち着くまで待つ
3. APESを起動する
4. APES動作中は電源状態を維持する
5. 終了するときにAPESを停止する
```

---

# `sudo` について

APES全体を `sudo` で実行する必要はありません。

```bash
python3 auto_power_energy_saving_tlp_ubuntu_v2.py
```

として一般ユーザーで実行します。

CPU EPPのsysfsを書き込めるように、必要な権限だけを設定してください。

---

# TLPの検出

このバージョンでは、単に `tlp` コマンドが存在するだけでは「TLPが動作中」とは判断しません。

```text
tlp コマンドが存在
        +
tlp.service が active
        ↓
TLP active
```

という判定です。

したがって、TLPがインストールされていても停止している場合は、APESはTLPに制御を任せず、起動時に保存したEPPを復元します。

---

# 設計思想

今回のAPESでは、役割を次のように分離します。

```text
TLP
 ↓
通常時のシステム電源管理

APES
 ↓
アイドル時の一時的な省電力化
```

APESは通常時のCPU EPPを勝手に決定しません。

そのため、

```text
TLPあり
```

でも、

```text
TLPなし
```

でも同じAPESプログラムを使用できます。

---

# GNOME / Wayland

ユーザーのアイドル状態の検出には、

```text
org.gnome.Mutter.IdleMonitor
```

を使用しています。

したがって、現在の実装はGNOME環境を主な対象としています。

---

# 画面ブランクとの違い

APESはUbuntuの画面ブランク機能を使用しません。

APESが変更するのは、

```text
CPU EPP
画面輝度
```

です。

PCを、

```text
ロック
サスペンド
```

させるプログラムではありません。

そのため、画面を暗くして省電力化しながら、RDPなどのリモートアクセスを維持することを目的としています。

---

# 動作確認

Dell Latitude 5300 / Ubuntu 26.04.1 / GNOME / Wayland環境で、AC電源およびバッテリーの両方についてテストしています。

以前のTLP併用版では、

```text
AC:
balance_performance → power → balance_performance

Battery:
balance_power → power → balance_power
```

を確認しました。

今回の版では、このような `balance_*` の値をAPESが固定的に決めるのではなく、**起動時の実際のEPPを保存する方式**へ変更しています。テストで確認された `balance_*` は、APESが固定値として設定したものではなく、起動時に保存して復元した値です。

---

# 注意

- GNOME/Mutter IdleMonitorに依存します。
- CPU EPPのsysfsパスはハードウェアやカーネルによって異なる場合があります。
- 画面輝度制御もハードウェア依存です。
- APESは起動時に保存したEPPを、ユーザー操作時または終了時にそのまま復元します。
- TLPはAPESとは独立して動作し、AC/Batteryの切り替えなど、自身の電源管理イベントに応じてEPPを変更する場合があります。
- 現在のダウンロード版はテスト用にStage 1 = 20秒、Stage 2 = 40秒です。正式運用時は必要に応じて変更してください。


# 🔊 音声出力とマルチモニターについて

APESは、**音声出力の制御を行いません。**

このスクリプトが制御するのは、CPU EPPと画面輝度です。したがって、アイドル時にAPESが省電力動作へ移行しても、音量や音声出力デバイスを変更することはありません。

また、画面輝度については、現在の実装では**ローカルPCのメインスクリーン（`intel_backlight`）のみ**を対象としています。

デュアルモニターなど、外部モニターを接続して使用している場合：

- ローカルPC本体のスクリーン → APESが輝度を変更する場合があります
- セカンドモニター（外部モニター） → APESは輝度を変更しません

つまり、APESは外部モニターの明るさを制御するプログラムではありません。


## License

リポジトリのLICENSEファイルを参照してください。
