import pydobot
from pydobot.message import Message
from serial.tools import list_ports
import time

# 利用可能なCOMポートを探す
available_ports = list_ports.comports()
print(f"利用可能なCOMポート:")
for port in available_ports:
    print(port.device)

# Dobot Magicianが接続されているCOMポートを指定
port = 'COM3'  # ご自身の環境に合わせて変更してください

# Dobotに接続
try:
    device = pydobot.Dobot(port=port, verbose=False)
except Exception as e:
    print(f"エラー: {port} への接続に失敗しました。")
    print(e)
    exit()

print("Dobot Magicianに接続しました。")

# --- ★★★ 修正点 ★★★ ---
# 接続直後に短い待機時間を設けて通信を安定させます
print("通信が安定するまで1秒待機します...")
time.sleep(1)
# -------------------------

print("キャリブレーション（ホーミング）を開始します。")

# ホーミングコマンド(ID:31)を直接メッセージとして送信
msg = Message()
msg.id = 31
msg.ctrl = 3
device._send_command(msg, wait=True)

print("ホーミングが完了しました。")

# 現在の位置情報を取得して表示
pos = device.pose()
print(f"現在の座標 (x, y, z, r): {pos}")

# Dobotとの接続を閉じる
device.close()

print("Dobot Magicianとの接続を終了しました。")