import pydobot
from pydobot import Dobot
import time

# --- 設定 -----------------------------------------------------------------
# 自分のDobotが接続されているCOMポート名
DOBOT_PORT = "COM3"

# 動作テスト用の座標 (x, y, z, r)
POINT_A = (200, -100, 50, 0)
POINT_B = (200, 100, 50, 0)
# 安全な初期位置
HOME_POSITION = (250, 0, 50, 0)
# -------------------------------------------------------------------------


def test_movement(velocity, acceleration):
    """指定された速度と加速度でDobotを動かし、最後に初期位置へ戻す"""
    device = None
    try:
        device = Dobot(port=DOBOT_PORT, verbose=False)
        print("\n--- テスト中 ---")
        print(f"速度: {velocity}, 加速度: {acceleration} に設定します。")
        
        # 速度と加速度を設定
        device.speed(velocity, acceleration)
        
        # 動作開始
        print("動作開始... A -> B -> A")
        device.move_to(*POINT_A, wait=True)
        device.move_to(*POINT_B, wait=True)
        device.move_to(*POINT_A, wait=True)
        
        print("初期位置に戻ります...")
        device.speed(100, 100) # 適度な速度に戻す
        device.move_to(*HOME_POSITION, wait=True)
        print("動作完了。")

    except Exception as e:
        print(f"❌ エラーが発生しました: {e}")
    finally:
        if device:
            device.close()
            print("🔌 接続を解除しました。")


if __name__ == "__main__":
    print("Dobot Speed Tester - 速度・加速度の最大値を探します。")
    print("終了するには 'q' と入力してください。")

    while True:
        try:
            vel_input = input("\n> 速度の値を入力してください (推奨: 50-200): ")
            if vel_input.lower() == 'q':
                break
            
            acc_input = input("> 加速度の値を入力してください (推奨: 50-200): ")
            if acc_input.lower() == 'q':
                break

            v = int(vel_input)
            a = int(acc_input)
            
            test_movement(v, a)

        except ValueError:
            print("⚠️ 半角数字で入力してください。")
        except KeyboardInterrupt:
            break

    print("\nテストを終了します。")