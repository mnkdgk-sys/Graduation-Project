# robot_control_module.py (キューベース動作制御版)

import time
import threading
from PyQt6.QtCore import QObject, pyqtSignal, QThread

try:
    from pydobot import Dobot
    PYDOBOT_AVAILABLE = True
except ImportError:
    PYDOBOT_AVAILABLE = False

# --- ロボット設定 ---
ROBOT1_CONFIG = {
    "port": "COM3", 
    "ready_pos": (279, -25, 50, 0),     # 基本待機位置
    "strike_pos": (264, -23, 11, 0),    # 実際の打撃位置
}
ROBOT2_CONFIG = {
    "port": "COM4", 
    "ready_pos": (279, -25, 50, 0),
    "strike_pos": (264, -23, 11, 0),
}

# --- 動作パラメータ ---
LATENCY_COMPENSATION_S = 0.050  # PCとロボット間の遅延補正値 (秒)

# 振り上げる高さの計算パラメータ
MAX_BACKSWING_HEIGHT = 90.0   # 振り上げる最大の高さ (mm)
MIN_BACKSWING_HEIGHT = 30.0   # 振り上げる最小の高さ (mm)
TIME_TO_HEIGHT_NORMALIZATION_S = 0.5 

class RobotController(QObject):
    log_message = pyqtSignal(str)
    finished = pyqtSignal()
    
    def __init__(self, config, note_items, bpm, loop_duration, start_event, stop_event, device_list):
        super().__init__()
        self.config = config
        self.note_items = sorted(note_items, key=lambda x: x['beat'])
        self.bpm = bpm
        self.loop_duration = loop_duration
        self.start_event = start_event
        self.stop_event = stop_event
        self.device_list = device_list

    def calculate_motion_plan(self, current_beat, next_beat_interval):
        """動作計画を事前計算"""
        # 時間に応じた振り上げ高さを決定
        height_ratio = min(next_beat_interval / TIME_TO_HEIGHT_NORMALIZATION_S, 1.0)
        max_backswing_z = MIN_BACKSWING_HEIGHT + (MAX_BACKSWING_HEIGHT - MIN_BACKSWING_HEIGHT) * height_ratio
        
        # 振り上げの中間点（振り下ろし転換点）を計算
        # ready_posの高さを中間点として使用
        ready_x, ready_y, ready_z, ready_r = self.config["ready_pos"]
        intermediate_z = ready_z  # 中間点の高さ
        
        # 打撃位置のX,Y座標を基準にした位置計算
        strike_x, strike_y, _, strike_r = self.config["strike_pos"]
        
        # 3段階の動作プラン：打撃→振り上げ途中で転換→振り下ろし
        motion_plan = [
            {"pos": self.config["strike_pos"], "duration": 0.05},     # 1.打撃位置: 50ms
            {"pos": (strike_x, strike_y, intermediate_z, strike_r), "duration": next_beat_interval * 0.475},  # 2.振り上げ途中（中間点）: 47.5%
            {"pos": self.config["strike_pos"], "duration": next_beat_interval * 0.475}   # 3.振り下ろし: 47.5%
        ]
        
        return motion_plan

    def execute_motion_sequence(self, device, start_time, motion_plan):
        """動作シーケンスを時間制御で実行"""
        current_time = start_time
        
        for i, motion in enumerate(motion_plan):
            if self.stop_event.is_set():
                return False
            
            # 動作開始時刻まで高精度待機
            target_time = current_time - LATENCY_COMPENSATION_S
            while time.time() < target_time:
                if self.stop_event.is_set():
                    return False
                time.sleep(0.001)
            
            # 最初の打撃以外は非同期で実行（スムーズな動作のため）
            wait_for_completion = (i == 0)  # 打撃のみ完了を待つ
            
            try:
                device.move_to(*motion["pos"], wait=wait_for_completion)
            except Exception as e:
                self.log_message.emit(f"動作エラー: {e}")
                return False
            
            # 次の動作時刻を更新
            current_time += motion["duration"]
        
        return True

    def run(self):
        device = None
        port = self.config["port"]
        try:
            if not PYDOBOT_AVAILABLE: 
                raise ImportError("pydobotライブラリが見つかりません。")

            seconds_per_beat = 60.0 / self.bpm
            device = Dobot(port=port, verbose=False)
            self.device_list.append(device)
            self.log_message.emit(f"ロボット [{port}] 接続完了")
            
            # 最高速度設定
            device.speed(velocity=3000, acceleration=3000)
            
            # 初期位置に移動
            device.move_to(*self.config["ready_pos"], wait=True)
            self.log_message.emit(f"ロボット [{port}] 準備完了")

            self.start_event.wait()
            if self.stop_event.is_set(): return

            master_start_time = time.time()
            loop_count = 0
            
            while not self.stop_event.is_set():
                current_loop_start_time = master_start_time + (loop_count * self.loop_duration)
                
                for i, current_note in enumerate(self.note_items):
                    if self.stop_event.is_set(): break

                    # 現在の音符の開始時刻を計算
                    current_beat = current_note.get("beat", 0)
                    note_start_time = current_loop_start_time + (current_beat * seconds_per_beat)
                    
                    # 次の音符までの間隔を計算
                    is_last_note = (i == len(self.note_items) - 1)
                    if is_last_note:
                        next_loop_start_time = current_loop_start_time + self.loop_duration
                        next_note = self.note_items[0]
                        next_beat_abs_time = next_loop_start_time + (next_note.get("beat", 0) * seconds_per_beat)
                        beat_interval = next_beat_abs_time - note_start_time
                    else:
                        next_note = self.note_items[i + 1]
                        beat_interval = (next_note.get("beat", 0) - current_beat) * seconds_per_beat
                    
                    # 動作計画を生成
                    motion_plan = self.calculate_motion_plan(current_beat, beat_interval)
                    
                    # 動作シーケンスを実行
                    if not self.execute_motion_sequence(device, note_start_time, motion_plan):
                        break  # エラーまたは停止

                if self.stop_event.is_set(): break

                # 次のループまで同期待機
                next_loop_sync_time = master_start_time + ((loop_count + 1) * self.loop_duration)
                while time.time() < next_loop_sync_time:
                    if self.stop_event.is_set(): break
                    time.sleep(0.01)

                if self.stop_event.is_set(): break
                loop_count += 1

        except Exception as e:
            self.log_message.emit(f"ロボット [{port}] エラー: {e}")
        finally:
            if device:
                try:
                    if device in self.device_list: 
                        self.device_list.remove(device)
                    # 安全な位置に移動
                    device.move_to(250, 0, 80, 0, wait=False)
                    time.sleep(0.1)
                    device.close()
                except Exception:
                    pass
                self.log_message.emit(f"ロボット [{port}] 接続解除")
            self.finished.emit()

class RobotManager(QObject):
    log_message = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.threads = []
        self.workers = []
        self.start_event = threading.Event()
        self.stop_event = threading.Event()
        self.active_devices = []

    def start_control(self, score_data):
        self.stop_control()
        self.stop_event.clear()
        self.start_event.clear()

        top_score = score_data.get("top", {})
        bottom_score = score_data.get("bottom", {})
        top_bpm = top_score.get("bpm", 120)
        bottom_bpm = bottom_score.get("bpm", 120)
        top_notes = [item for item in top_score.get("items", []) if item.get("class") == "note"]
        bottom_notes = [item for item in bottom_score.get("items", []) if item.get("class") == "note"]
        top_beats = top_score.get("total_beats", 8)
        bottom_beats = bottom_score.get("total_beats", 8)
        top_duration = top_beats * (60.0 / top_bpm)
        bottom_duration = bottom_beats * (60.0 / bottom_bpm)
        loop_duration_sec = max(top_duration, bottom_duration)
        
        configs = [(ROBOT1_CONFIG, top_notes, top_bpm), (ROBOT2_CONFIG, bottom_notes, bottom_bpm)]

        self.log_message.emit("🎼 楽譜分析開始...")
        
        for config, notes, bpm in configs:
            if not notes: continue
            thread = QThread()
            worker = RobotController(config, notes, bpm, loop_duration_sec, self.start_event, self.stop_event, self.active_devices)
            worker.moveToThread(thread)
            worker.log_message.connect(self.log_message.emit)
            thread.started.connect(worker.run)
            worker.finished.connect(thread.quit)
            worker.finished.connect(worker.deleteLater)
            thread.finished.connect(thread.deleteLater)
            thread.finished.connect(lambda t=thread, w=worker: self._on_thread_finished(t, w))
            thread.start()
            self.threads.append(thread)
            self.workers.append(worker)

    def stop_control(self):
        if not self.threads: return
        self.log_message.emit("🛑 演奏停止中...")
        
        # 停止シグナルを送信
        self.stop_event.set()
        self.start_event.set()
        
        # 全スレッドの終了を待機
        for thread in self.threads[:]:
            if thread.isRunning():
                thread.quit()
                if not thread.wait(3000):  # 3秒でタイムアウト
                    self.log_message.emit("⚠️ 強制終了中...")
                    thread.terminate()
                    thread.wait(1000)
        
        # リストをクリア
        self.threads.clear()
        self.workers.clear()
        
        # デバイスを強制クローズ
        for device in self.active_devices[:]:
            try:
                if hasattr(device, 'close'):
                    device.close()
            except Exception:
                pass
        self.active_devices.clear()
        
        self.log_message.emit("✅ 全て停止完了")

    def trigger_start(self):
        self.log_message.emit("🎬 演奏開始！")
        self.start_event.set()

    def _on_thread_finished(self, thread_obj, worker_obj):
        if thread_obj in self.threads: 
            self.threads.remove(thread_obj)
        if worker_obj in self.workers: 
            self.workers.remove(worker_obj)