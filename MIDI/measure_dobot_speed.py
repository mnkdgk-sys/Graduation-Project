# measure_dobot_speed.py
#Magicianの速度パラメータと実際の速度を紐づけるプログラム
import time
import math
from pydobot import Dobot

# --- ユーザー設定項目 ---

# 1. Dobotが接続されているCOMポートを指定
PORT = "COM4" 

# 2. 移動の始点と終点を指定 (X, Y, Z)
#    - ある程度距離が離れている方が計測精度が上がります。
#    - 必ずロボットの可動域内で、安全な座標を指定してください。
POS_A = (215, 19, -90, 0)
POS_B = (181, 11, 115, 0)

# 3. テストしたい速度と加速度の組み合わせをリストで定義
#    - (velocity, acceleration) のタプルの形式で追加します。
#    - pydobotのデフォルトは (100, 100) です。
SPEED_PROFILES_TO_TEST = [
    (50, 50),       # 低速
    (100, 100),     # 中速 (デフォルト)
    (200, 200),     # 高速
    (500, 500),     # かなり高速
    (1000, 1000),   # 非常に高速
    (2000, 2000),   # drum_analyzerで設定されていた値
]

# -------------------------

def calculate_distance(p1, p2):
    """3次元座標の2点間の直線距離を計算する"""
    return math.sqrt((p2[0] - p1[0])**2 + (p2[1] - p1[1])**2 + (p2[2] - p1[2])**2)

def measure_move_time(device: Dobot, start_pos, end_pos):
    """指定された2点間の移動時間を計測する"""
    # 1. まず始点に移動し、完了するまで待つ
    device.move_to(start_pos[0], start_pos[1], start_pos[2], 0, wait=True)
    time.sleep(1) # 動きが完全に安定するまで少し待つ

    # 2. 時間計測を開始
    start_time = time.time()

    # 3. 終点に移動し、完了するまで待つ (これが計測対象の動き)
    device.move_to(end_pos[0], end_pos[1], end_pos[2], 0, wait=True)

    # 4. 時間計測を終了
    end_time = time.time()

    # 5. かかった時間を返す
    duration = end_time - start_time
    return duration

if __name__ == '__main__':
    device = None
    try:
        # Dobotに接続
        print(f"🔩 ポート '{PORT}' でDobotに接続中...")
        device = Dobot(port=PORT, verbose=False)
        print("✅ 接続完了。")

        # A-B間の距離を計算 (これは常に一定)
        distance_mm = calculate_distance(POS_A, POS_B)
        print(f"📏 計測距離: {distance_mm:.2f} mm")
        print("-" * 30)

        results = {}

        # 定義された各速度プロファイルで計測を実行
        for v, a in SPEED_PROFILES_TO_TEST:
            print(f"🚀 パラメータ (v={v}, a={a}) で計測開始...")
            
            # Dobotに速度・加速度を設定
            device.speed(velocity=v, acceleration=a)
            
            # A→Bの移動時間を計測
            duration_ab = measure_move_time(device, POS_A, POS_B)
            # B→Aの移動時間を計測 (往復で精度を確認)
            duration_ba = measure_move_time(device, POS_B, POS_A)
            
            # 平均時間を計算
            avg_duration = (duration_ab + duration_ba) / 2
            
            # 平均速度を計算 (mm/s)
            avg_speed = distance_mm / avg_duration if avg_duration > 0 else 0
            
            print(f"   ⏱️  往復平均時間: {avg_duration:.4f} 秒")
            print(f"   ⚡️  実測平均速度: {avg_speed:.2f} mm/s")
            print("-" * 30)
            
            results[(v, a)] = avg_speed

        print("\n\n--- ✨ 計測結果まとめ ✨ ---")
        for params, speed in results.items():
            print(f"パラメータ (v={params[0]}, a={params[1]}): \t {speed:.2f} mm/s")
        print("\nこれらの値を参考に `AVERAGE_SPEED_MM_PER_S` を設定してください。")

    except Exception as e:
        print(f"❌ エラーが発生しました: {e}")
    finally:
        if device:
            # 安全な位置に退避させてから接続を解除
            print("\n🔧 安全な位置に移動して接続を解除します...")
            device.move_to(250, 0, 50, 0, wait=True)
            device.close()
            print("🔌 接続を解除しました。")