import pydobot
from serial.tools import list_ports
import time

# --- 1. Dobotの接続設定 ---
available_ports = list_ports.comports()
if not available_ports:
    print("エラー: 利用可能なシリアルポートが見つかりません。")
    print("DobotがPCに接続され、電源が入っているか確認してください。")
    exit()

print("利用可能なシリアルポート:")
for i, port in enumerate(available_ports):
    print(f"  {i}: {port.device}")

while True:
    try:
        port_index_str = input("Dobotが接続されているポートの番号を入力してください: ")
        port_index = int(port_index_str)
        if 0 <= port_index < len(available_ports):
            port = available_ports[port_index].device
            break
        else:
            print(f"エラー: 0 から {len(available_ports) - 1} の間の番号を入力してください。")
    except ValueError:
        print("エラー: ポート名ではなく、左側に表示されている「番号」を半角数字で入力してください。")

try:
    print(f"{port}に接続しています...")
    device = pydobot.Dobot(port=port, verbose=False)
    print("接続に成功しました。")
    
    # ↓↓↓ エラーの原因だった以下の行を削除しました ↓↓↓
    # device.set_led(r=0, g=255, b=0, on=True)
    # time.sleep(1)
    # device.set_led(on=False)
    # ↑↑↑ ここまで ↑↑↑

except Exception as e:
    print(f"接続に失敗しました: {e}")
    exit()


# --- 2. メイン処理 ---
try:
    print("\n--- 座標取得プログラム ---")
    print("準備が完了しました。")

    while True:
        user_input = input("Enterキーを押して現在の座標を取得 ('q'で終了): ")

        if user_input.lower() == 'q':
            print("プログラムを終了します。")
            break
        
        pose = device.pose()
        
        print(f"✅ 現在の座標: X={pose[0]:.2f}, Y={pose[1]:.2f}, Z={pose[2]:.2f}, R={pose[3]:.2f}\n")

finally:
    # --- 3. 終了処理 ---
    print("Dobotとの接続を終了します。")
    device.close()