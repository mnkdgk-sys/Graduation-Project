import sys
import pydobot
import time
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QGridLayout, QLabel
)
from PyQt6.QtCore import QThread, pyqtSignal, pyqtSlot, QObject
from PyQt6.QtGui import QFont

# -----------------------------------------------------------
# グローバル設定
# -----------------------------------------------------------
DOBOT_PORT = "COM4"       
MONITOR_FPS = 50          
MONITOR_INTERVAL = 1.0 / MONITOR_FPS 

# -----------------------------------------------------------
# (スレッド1) 座標監視だけを高頻度で行うワーカー (変更なし)
# -----------------------------------------------------------
class PoseMonitorWorker(QObject):
    pose_updated = pyqtSignal(float, float, float, float)
    status_updated = pyqtSignal(str) 

    def __init__(self, device):
        super().__init__()
        self.device = device
        self.running = True

    @pyqtSlot()
    def run(self):
        print(f"[監視スレッド] 開始 (Target FPS: {MONITOR_FPS})")
        while self.running:
            try:
                pose = self.device.pose()
                self.pose_updated.emit(pose[0], pose[1], pose[2], pose[3])
                time.sleep(MONITOR_INTERVAL)
            except Exception as e:
                time.sleep(MONITOR_INTERVAL) 

    def stop(self):
        self.running = False

# -----------------------------------------------------------
# (スレッド2) デモモーション（コマンド発行）だけを行うワーカー
# -----------------------------------------------------------
class DemoRunnerWorker(QObject):
    status_updated = pyqtSignal(str)
    finished = pyqtSignal()

    def __init__(self, device):
        super().__init__()
        self.device = device

    @pyqtSlot()
    def run(self):
        print("[デモスレッド] 開始")
        try:
            self.status_updated.emit("キューをクリアします...")
            self.device._set_queued_cmd_clear()
            self.device._set_queued_cmd_start_exec()
            
            self.status_updated.emit("1. 安全な待機位置へ移動...")
            self.move_to_and_wait(200.0, 0.0, 100.0, 0.0)
            
            self.status_updated.emit("2. 座標 (250, 0, 50) へ...")
            self.move_to_and_wait(250.0, 0.0, 50.0, 0.0)
            
            self.status_updated.emit("3. 座標 (250, 80, 50) へ...")
            self.move_to_and_wait(250.0, 80.0, 50.0, 0.0)
            
            self.status_updated.emit("4. 座標 (200, 80, 100) へ...")
            self.move_to_and_wait(200.0, 80.0, 100.0, 0.0)

            self.status_updated.emit("5. サクションカップON")
            self.suck_and_wait(True) 
            time.sleep(1) 

            self.status_updated.emit("6. サクションカップOFF")
            self.suck_and_wait(False) 
            time.sleep(0.5)

            self.status_updated.emit("7. 待機位置へ戻ります...")
            self.move_to_and_wait(200.0, 0.0, 100.0, 0.0)

            self.status_updated.emit("--- デモモーション終了 ---")
            
        except AttributeError as e:
            error_message = f"デモエラー: ライブラリが低レベル関数をサポートしていません。 ({str(e)})"
            self.status_updated.emit(error_message)
        except Exception as e:
            self.status_updated.emit(f"デモエラー: {e}")
        finally:
            print("[デモスレッド] 終了")
            self.finished.emit()

    def move_to_and_wait(self, x, y, z, r):
        """
        移動をキューに入れ、完了するまでポーリングする。
        """
        current_index = self.device._get_queued_cmd_current_index()
        target_index = current_index + 1

        with self.device.lock:
            # --- 修正点: 'mode' と 'wait' も float に変換 ---
            self.device._set_ptp_cmd(
                float(x), 
                float(y), 
                float(z), 
                float(r), 
                float(0x02), # mode (int 2 -> float 2.0)
                wait=float(0)  # wait (bool False -> int 0 -> float 0.0)
            )

        while current_index < target_index:
            time.sleep(0.05) 
            try:
                current_index = self.device._get_queued_cmd_current_index()
            except Exception:
                pass 

    def suck_and_wait(self, enable):
        """吸引コマンドをキューに入れ、完了するまでポーリングする"""
        
        current_index = self.device._get_queued_cmd_current_index()
        target_index = current_index + 1
        
        # --- 修正点: enable と wait を float に変換 ---
        enable_float = float(1.0 if enable else 0.0)
        
        self.device.suck(
            enable_float, 
            wait=float(0) # wait (bool False -> int 0 -> float 0.0)
        ) 
        
        while current_index < target_index:
            time.sleep(0.05)
            try:
                current_index = self.device._get_queued_cmd_current_index()
            except Exception:
                pass

# -----------------------------------------------------------
# (スレッド3) メインGUIスレッド (変更なし)
# -----------------------------------------------------------
class MainWindow(QMainWindow):
    def __init__(self, device):
        super().__init__()
        self.setWindowTitle("Dobot リアルタイム座標監視 (高FPS v5)")
        self.setGeometry(100, 100, 450, 250)
        self.device = device 

        # --- UIセットアップ (省略なし) ---
        self.title_font = QFont("Arial", 14)
        self.value_font = QFont("Consolas", 16)
        self.value_font.setBold(True)
        self.status_font = QFont("Arial", 10)
        
        main_widget = QWidget()
        main_layout = QVBoxLayout()
        grid_layout = QGridLayout()
        
        self.labels = {}
        self.values = {}
        coords = ["X", "Y", "Z", "R"]
        
        for i, coord in enumerate(coords):
            self.labels[coord] = QLabel(f"{coord}:")
            self.labels[coord].setFont(self.title_font)
            self.values[coord] = QLabel("0.00")
            self.values[coord].setFont(self.value_font)
            self.values[coord].setMinimumWidth(150)
            grid_layout.addWidget(self.labels[coord], i, 0)
            grid_layout.addWidget(self.values[coord], i, 1)

        main_layout.addLayout(grid_layout)
        self.status_label = QLabel("初期化中...")
        self.status_label.setFont(self.status_font)
        main_layout.addStretch()
        main_layout.addWidget(self.status_label)
        main_widget.setLayout(main_layout)
        self.setCentralWidget(main_widget)

        # --- ワーカースレッドのセットアップ (変更なし) ---
        self.monitor_worker = PoseMonitorWorker(self.device)
        self.monitor_thread = QThread()
        self.monitor_worker.moveToThread(self.monitor_thread)
        self.monitor_thread.started.connect(self.monitor_worker.run)
        self.monitor_worker.pose_updated.connect(self.update_pose)
        self.monitor_worker.status_updated.connect(self.update_status)

        self.demo_worker = DemoRunnerWorker(self.device)
        self.demo_thread = QThread()
        self.demo_worker.moveToThread(self.demo_thread)
        self.demo_thread.started.connect(self.demo_worker.run)
        self.demo_worker.status_updated.connect(self.update_status)
        self.demo_worker.finished.connect(self.demo_thread.quit)

        self.monitor_thread.start()
        self.demo_thread.start()

    @pyqtSlot(float, float, float, float)
    def update_pose(self, x, y, z, r):
        self.values["X"].setText(f"{x:8.2f}")
        self.values["Y"].setText(f"{y:8.2f}")
        self.values["Z"].setText(f"{z:8.2f}")
        self.values["R"].setText(f"{r:8.2f}")

    @pyqtSlot(str)
    def update_status(self, message):
        self.status_label.setText(message)
        print(f"[Status] {message}")

    def closeEvent(self, event):
        print("ウィンドウが閉じられました。全スレッドに停止信号を送ります...")
        
        self.monitor_worker.stop()
        self.monitor_thread.quit()
        if not self.monitor_thread.wait(2000): 
            print("警告: 監視スレッドが時間内に終了しませんでした。")
        
        self.demo_thread.quit()
        if not self.demo_thread.wait(2000):
            print("警告: デモスレッドが時間内に終了しませんでした。")
        
        if self.device:
            print("Dobot接続を切断します。")
            try:
                self.device.close()
            except Exception as e:
                print(f"切断時にエラー: {e}")
            
        event.accept()

# -----------------------------------------------------------
# メイン処理 (変更なし)
# -----------------------------------------------------------
if __name__ == "__main__":
    
    dobot_device = None
    try:
        print(f"ポート {DOBOT_PORT} に接続しています...")
        dobot_device = pydobot.Dobot(port=DOBOT_PORT)
        print("Dobot Magicianに接続成功。")
    except Exception as e:
        print(f"致命的エラー: Dobotに接続できませんでした。{e}")
        print("ポート番号が正しいか、ドライバがインストールされているか確認してください。")
        sys.exit(1)

    app = QApplication(sys.argv)
    window = MainWindow(device=dobot_device)
    window.show()
    sys.exit(app.exec())