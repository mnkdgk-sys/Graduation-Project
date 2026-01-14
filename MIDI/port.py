import serial.tools.list_ports

def list_ports():
    print("--- 利用可能なシリアルポート一覧 ---")
    
    # PC上のポートを全て取得
    ports = serial.tools.list_ports.comports()

    if not ports:
        print("利用可能なポートは見つかりませんでした。")
        print("・USBケーブルが正しく接続されているか確認してください。")
        print("・ドライバがインストールされているか確認してください。")
        return

    # 見やすく整形して表示
    # ヘッダー
    print(f"{'Port':<10} | {'Description (デバイス名)':<40} | {'Hardware ID'}")
    print("-" * 80)

    for port in ports:
        device = port.device             # ポート番号 (例: COM3)
        desc = port.description          # デバイスの説明 (例: Silicon Labs CP210x...)
        hwid = port.hwid                 # ハードウェアID

        print(f"{device:<10} | {desc:<40} | {hwid}")

    print("-" * 80)

if __name__ == "__main__":
    list_ports()