import time
import sys
import msvcrt  # Windowsでのキーボード入力検知用

# --- 必須ライブラリのインポート ---
try:
    from pydobot import Dobot
except ImportError:
    print("エラー: pydobotライブラリが見つかりません。")
    sys.exit(1)

# --- ロボット設定 (元のコードから流用) ---
# ※ ポートは環境に合わせて変更してください (COM3 または COM4)
ROBOT_CONFIG = {
    "port": "COM3", 
    "ready_pos": (234, 15, 70, 0),   # 待機高さ (中くらい)
    "strike_pos": (234, 15, 22, 0)   # 打鍵高さ
}

# --- 安全制限 (元のコードから流用) ---
SAFETY_LIMITS = {
    'x_min': 160.0, 'x_max': 250.0,
    'y_min': -180.0, 'y_max': 180.0,
    'z_min': 0, 'z_max': 130.0,
}

def clamp_position(x, y, z, r):
    """安全範囲内に座標を収める関数"""
    clamped_x = max(SAFETY_LIMITS['x_min'], min(SAFETY_LIMITS['x_max'], x))
    clamped_y = max(SAFETY_LIMITS['y_min'], min(SAFETY_LIMITS['y_max'], y))
    clamped_z = max(SAFETY_LIMITS['z_min'], min(SAFETY_LIMITS['z_max'], z))
    return clamped_x, clamped_y, clamped_z, r

def check_quit():
    """キーボード入力(q)をチェックする"""
    if msvcrt.kbhit():
        key = msvcrt.getch()
        if key.lower() == b'q':
            return True
    return False

def run_simple_loop():
    port = ROBOT_CONFIG["port"]
    print(f"--- [{port}] ロボットに接続中... ---")
    
    try:
        device = Dobot(port=port, verbose=False)
        print("接続成功。")
    except Exception as e:
        print(f"接続エラー: {e}")
        return

    # 座標の準備
    x, y, _, r = ROBOT_CONFIG["strike_pos"]
    z_strike = ROBOT_CONFIG["strike_pos"][2]
    
    # 【大きくゆっくり】用の高さ（Zを高めに設定）
    z_big_up = 90.0
    # 【小さく素早く】用の高さ（Zを低めに設定）
    z_small_up = 40.0

    # 安全チェック
    safe_strike = clamp_position(x, y, z_strike, r)
    safe_big_up = clamp_position(x, y, z_big_up, r)
    safe_small_up = clamp_position(x, y, z_small_up, r)

    print("動作を開始します。「q」キーを押すと終了します。")
    print("------------------------------------------------")

    try:
        loop_count = 1
        while True:
            if check_quit(): break

            print(f"\n[{loop_count}周目] 開始")

            # --- パターン1: 大きくゆっくり (4回) ---
            print("  >> 大きくゆっくりスイング (x4)")
            # 速度と加速度を遅く設定 (Velocity=100, Acceleration=100)
            device.speed(velocity=400, acceleration=400)
            
            for i in range(4):
                if check_quit(): break
                # 1. 大きく振り上げる
                device.move_to(*safe_big_up, wait=True)
                # 2. 振り下ろす
                device.move_to(*safe_strike, wait=True)
            
            if check_quit(): break

            # --- パターン2: 小さく素早く (4回) ---
            print("  >> 小さく素早くスイング (x4)")
            # 速度と加速度を速く設定 (Velocity=400, Acceleration=400)
            device.speed(velocity=1000, acceleration=1000)
            
            for i in range(4):
                if check_quit(): break
                # 1. 小さく振り上げる
                device.move_to(*safe_small_up, wait=True)
                # 2. 振り下ろす
                device.move_to(*safe_strike, wait=True)

            loop_count += 1
            
            # 少し待機（連続動作の区切り）
            time.sleep(0.01)

    except KeyboardInterrupt:
        pass
    except Exception as e:
        print(f"実行中エラー: {e}")
    finally:
        print("\n終了処理中...")
        # 安全な位置に戻って終了
        safe_end_pos = clamp_position(230, 0, 60, 0)
        try:
            device.speed(velocity=200, acceleration=200)
            device.move_to(*safe_end_pos, wait=True)
            device.close()
            print("切断完了。")
        except:
            pass

if __name__ == "__main__":
    run_simple_loop()