#dobotの速度・加速度パラメータと、実際の動作速度をチューニングするためのデータを収集するコード
import time
import csv
import math
import itertools
from pydobot import Dobot

# --- 計測パラメータ（ご自身の環境に合わせて調整してください） ---
ROBOT_PORT = "COM4"  # ロボットのCOMポート

# テストする速度(mm/s)と加速度(mm/s^2)のリスト
TEST_VELOCITIES = [100, 200, 300, 400, 500, 600, 700, 800, 900, 1000]
TEST_ACCELERATIONS = [100, 200, 300, 400, 500, 600, 700, 800, 900, 1000]

# 動作の始点と、テストしたい終点のZ座標
START_POS = (230, 0, 50, 0)
TEST_END_Z = [45, 40, 35, 30, 25, 20, 15, 10, 5, 0, -5]

# 1試行あたりの計測回数
SAMPLES_PER_TRIAL = 5

# --- ヘルパー関数 ---
def get_z(device):
    """現在のZ座標を取得"""
    return device.pose()[2]

def get_distance(pos1, pos2):
    """3次元距離（rは無視）"""
    return math.sqrt(
        (pos1[0] - pos2[0])**2 +
        (pos1[1] - pos2[1])**2 +
        (pos1[2] - pos2[2])**2
    )

def measure_move_time(device, start_pos, end_pos, threshold=0.2):
    """
    Dobotが実際に動き始めてから到達するまでの時間を計測する
    """
    device.move_to(*start_pos, wait=True)
    time.sleep(0.2)

    start_z = get_z(device)
    device.move_to(*end_pos, wait=False)

    # 動き始めを検出
    while True:
        z = get_z(device)
        if abs(z - start_z) > threshold:
            t_start = time.perf_counter()
            break
        time.sleep(0.01)

    # 到達を検出
    while True:
        z = get_z(device)
        if abs(z - end_pos[2]) < threshold:
            t_end = time.perf_counter()
            break
        time.sleep(0.01)

    return t_end - t_start


# --- メイン処理 ---
def run_tuning():
    """チューニング測定を実行し、結果をCSVに保存する"""
    try:
        device = Dobot(port=ROBOT_PORT, verbose=False)
        print(f"✅ ロボット [{ROBOT_PORT}] に接続しました。")
    except Exception as e:
        print(f"❌ エラー: ロボットに接続できませんでした。{e}")
        return

    output_filename = 'tuning_data.csv'
    with open(output_filename, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['distance_mm', 'target_velocity', 'target_acceleration', 'avg_duration_s'])

        print(f"📁 測定結果を {output_filename} に保存します。")

        test_combinations = list(itertools.product(TEST_END_Z, TEST_VELOCITIES, TEST_ACCELERATIONS))
        total_tests = len(test_combinations)

        for i, (z, vel, acc) in enumerate(test_combinations):
            end_pos = (START_POS[0], START_POS[1], z, START_POS[3])
            distance = get_distance(START_POS, end_pos)
            durations = []

            print(f"[{i+1}/{total_tests}] 測定中: Z={z:>4} mm, D={distance:>5.1f} mm, V={vel:>4}, A={acc:>4} ... ", end="")

            try:
                # 速度と加速度を設定
                device.speed(velocity=vel, acceleration=acc)

                # 複数回計測して平均化
                for sample_num in range(SAMPLES_PER_TRIAL):
                    duration = measure_move_time(device, START_POS, end_pos)
                    durations.append(duration)
                    # 1往復して安定化
                    measure_move_time(device, end_pos, START_POS)

                avg_duration = sum(durations) / len(durations)
                writer.writerow([distance, vel, acc, avg_duration])
                print(f"完了 ✅ (平均時間: {avg_duration:.4f} s)")

            except Exception as e:
                print(f"⚠️ エラー発生: {e}")
                break

    print("🎯 すべての測定が完了しました。")
    device.move_to(*START_POS, wait=True)
    device.close()


if __name__ == "__main__":
    run_tuning()
