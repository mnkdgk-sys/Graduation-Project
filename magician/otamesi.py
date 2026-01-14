import pydobot
import keyboard
import time
from collections import defaultdict

# --- 設定項目 ---
# Dobotが接続されているCOMポート
DOBOT_PORT = 'COM3' 
# 移動速度 (mm/s)
MOVE_SPEED = 300.0
# 加速の滑らかさ係数 (0.1に近いほど滑らか、1.0に近いほどキビキビ)
ACCELERATION_FACTOR = 0.1 
# ループ頻度 (Hz) ※高くすると応答性が向上
UPDATE_FREQUENCY = 100
# --- 設定ここまで ---


class SmoothDobotController:
    def __init__(self, port):
        self.bot = None
        self.port = port
        self.running = False
        # 各軸の現在速度の割合 (-1.0 から 1.0)
        self.current_velocity_ratio = defaultdict(float)
        # 前回の位置を記録（連続移動用）
        self.last_position = None
        
    def connect(self):
        """Dobotに接続"""
        print(f"Dobot ({self.port}) に接続しています...")
        self.bot = pydobot.Dobot(port=self.port, verbose=False)
        print("✅ 接続しました。")
        
        # 速度設定（velocity, acceleration）
        self.bot.speed(velocity=100, acceleration=100)
        
        x, y, z, r, *_ = self.bot.pose()
        self.last_position = [x, y, z, r]
        print(f"初期座標: X:{x:.2f} Y:{y:.2f} Z:{z:.2f}")

    def get_key_input(self):
        """キー入力に基づいて目標速度の割合を設定"""
        target_velocity_ratio = defaultdict(float)
        
        # Z軸（上下）
        if keyboard.is_pressed('up'):
            target_velocity_ratio['z'] = 1.0
        elif keyboard.is_pressed('down'):
            target_velocity_ratio['z'] = -1.0
            
        # Y軸（左右）
        if keyboard.is_pressed('left'):
            target_velocity_ratio['y'] = -1.0  # 左方向
        elif keyboard.is_pressed('right'):
            target_velocity_ratio['y'] = 1.0   # 右方向
            
        # X軸（前後）
        if keyboard.is_pressed('w'):
            target_velocity_ratio['x'] = 1.0   # 前方向
        elif keyboard.is_pressed('s'):
            target_velocity_ratio['x'] = -1.0  # 後方向
            
        return target_velocity_ratio
    
    def update_velocity(self, target_velocity_ratio):
        """速度を滑らかに変化させる（加速・減速）"""
        for axis in ['x', 'y', 'z']:
            target = target_velocity_ratio[axis]
            current = self.current_velocity_ratio[axis]
            
            diff = target - current
            self.current_velocity_ratio[axis] += diff * ACCELERATION_FACTOR

    def send_move_command(self):
        """現在の速度に基づいて移動コマンドを送信"""
        if not self.last_position:
            return
            
        # 時間間隔を計算
        dt = 1.0 / UPDATE_FREQUENCY
        
        # 各軸の移動量を計算
        dx = self.current_velocity_ratio['x'] * MOVE_SPEED * dt
        dy = self.current_velocity_ratio['y'] * MOVE_SPEED * dt
        dz = self.current_velocity_ratio['z'] * MOVE_SPEED * dt
        
        # 微小な移動は無視
        if abs(dx) < 0.01 and abs(dy) < 0.01 and abs(dz) < 0.01:
            return
            
        # 新しい目標位置を計算
        new_x = self.last_position[0] + dx
        new_y = self.last_position[1] + dy
        new_z = self.last_position[2] + dz
        new_r = self.last_position[3]  # 回転は変更しない
        
        try:
            # move_to を使用して位置移動（ノンブロッキング）
            self.bot.move_to(new_x, new_y, new_z, new_r, wait=False)
            self.last_position = [new_x, new_y, new_z, new_r]
        except Exception as e:
            print(f"\n移動コマンドエラー: {e}")

    def control_loop(self):
        """メインの制御ループ"""
        print("--- アナログ連続移動モード 操作方法 ---")
        print("↑/↓: 上/下, ←/→: 左/右, W/S: 奥/手前")
        print(f"最大移動速度: {MOVE_SPEED} mm/s")
        print("ESC: プログラム終了")
        print("------------------------------------")
        print("\nキー操作待機中...")
        
        while self.running:
            current_time = time.time()

            if keyboard.is_pressed('esc'):
                print("\nESCキーが押されました。プログラムを終了します。")
                break
            
            target_velocity_ratio = self.get_key_input()
            self.update_velocity(target_velocity_ratio)
            self.send_move_command()

            # デバッグ情報の表示
            vx = self.current_velocity_ratio['x'] * MOVE_SPEED
            vy = self.current_velocity_ratio['y'] * MOVE_SPEED
            vz = self.current_velocity_ratio['z'] * MOVE_SPEED
            if abs(vx) > 0.1 or abs(vy) > 0.1 or abs(vz) > 0.1:
                print(f"\r速度: X:{vx:<6.1f} Y:{vy:<6.1f} Z:{vz:<6.1f}", end="")

            sleep_time = (1.0 / UPDATE_FREQUENCY) - (time.time() - current_time)
            if sleep_time > 0:
                time.sleep(sleep_time)

    def start(self):
        """制御を開始"""
        self.running = True
        self.control_loop()
    
    def stop(self):
        """制御を停止"""
        self.running = False
        if self.bot:
            print("\nアームを停止しています...")
            # 速度を0にリセット
            for axis in ['x', 'y', 'z']:
                self.current_velocity_ratio[axis] = 0.0
            time.sleep(0.1)  # 確実に停止させるため待機
            
    def close(self):
        """接続を閉じる"""
        if self.bot:
            print("接続を閉じます...")
            self.bot.close()
            print(f"✅ Dobot ({self.port}) との接続を閉じました。")

# 追加: pydobot APIの確認用関数
def check_dobot_methods():
    """利用可能なDobotメソッドを確認"""
    try:
        # 一時的にDobotに接続してメソッドを確認
        bot = pydobot.Dobot(port=DOBOT_PORT, verbose=False)
        print("利用可能なメソッド:")
        methods = [method for method in dir(bot) if not method.startswith('_')]
        for method in sorted(methods):
            print(f"  - {method}")
        bot.close()
    except Exception as e:
        print(f"メソッド確認エラー: {e}")

def main():
    controller = SmoothDobotController(DOBOT_PORT)
    
    try:
        controller.connect()
        controller.start()
    except Exception as e:
        print(f"❌ エラーが発生しました: {e}")
        print("\n利用可能なメソッドを確認します...")
        check_dobot_methods()
    finally:
        controller.stop()
        controller.close()

if __name__ == '__main__':
    main()