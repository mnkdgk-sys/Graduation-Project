# 利用可能なシリアルポートをリストアップ
import serial.tools.list_ports
ports = serial.tools.list_ports.comports()

if not ports:
    print("利用可能なシリアルポートが見つかりません。")
else:
    print("利用可能なシリアルポート:")
    for port in ports:
        # ポート名、説明、ハードウェアIDを分かりやすく表示
        print(f"  - {port.device}: {port.description} (VID:{port.vid}, PID:{port.pid})")