# robot_control_module.py (1打目の遅延修正版)

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
    "ready_pos": (279, -25, 50, 0),
    "strike_pos": (264, -23, 11, 0),
}
ROBOT2_CONFIG = {
    "port": "COM4", 
    "ready_pos": (279, -25, 50, 0),
    "strike_pos": (264, -23, 11, 0),
}

# --- 動作パラメータ ---
LATENCY_COMPENSATION_S = 0.050

# 振り上げる高さの計算パラメータ
MAX_BACKSWING_HEIGHT = 40.0
MIN_BACKSWING_HEIGHT = 5.0
TIME_TO_HEIGHT_NORMALIZATION_S = 0.5 

class RobotController(QObject):
    log_message = pyqtSignal(str)
    finished = pyqtSignal()
    
    def __init__(self, config, note_items, bpm, loop_duration, start_event, stop_event, device_list):
        super().__init__()
        self.config = config
        self.note_items = note_items # noteとrestを含む完全なリスト
        self.bpm = bpm
        self.loop_duration = loop_duration
        self.start_event = start_event
        self.stop_event = stop_event
        self.device_list = device_list
        
        self.motion_plan = self._create_motion_plan()

    def _create_motion_plan(self):
        """
        演奏開始前に楽譜を分析し、実行すべき全モーションのリストを作成する。
        各モーションは {target_time: 時刻, position: 座標} の形式。
        """
        notes_only = sorted([item for item in self.note_items if item.get("class") == "note"], key=lambda x: x['beat'])
        if not notes_only:
            return []

        motion_plan = []
        seconds_per_beat = 60.0 / self.bpm
        
        for i, current_note in enumerate(notes_only):
            is_last_note = (i == len(notes_only) - 1)
            next_note = notes_only[0] if is_last_note else notes_only[i + 1]
            
            current_strike_time = current_note.get("beat", 0) * seconds_per_beat
            
            interval = 0
            if is_last_note:
                interval = self.loop_duration - current_strike_time + (next_note.get("beat", 0) * seconds_per_beat)
            else:
                interval = (next_note.get("beat", 0) - current_note.get("beat", 0)) * seconds_per_beat
            
            if interval <= 0.02: continue

            upstroke_duration = interval / 2.0
            upstroke_target_time = current_strike_time + upstroke_duration

            height_ratio = min(upstroke_duration / TIME_TO_HEIGHT_NORMALIZATION_S, 1.0)
            backswing_z = MIN_BACKSWING_HEIGHT + (MAX_BACKSWING_HEIGHT - MIN_BACKSWING_HEIGHT) * height_ratio
            
            ready_x, ready_y, _, ready_r = self.config["ready_pos"]
            backswing_pos = (ready_x, ready_y, backswing_z, ready_r)
            
            motion_plan.append({"target_time": current_strike_time, "position": self.config["strike_pos"]})
            motion_plan.append({"target_time": upstroke_target_time, "position": backswing_pos})

        return sorted(motion_plan, key=lambda x: x['target_time'])

    def run(self):
        device = None
        port = self.config["port"]
        try:
            if not PYDOBOT_AVAILABLE: raise ImportError("pydobotライブラリが見つかりません。")

            device = Dobot(port=port, verbose=False)
            self.device_list.append(device)
            self.log_message.emit(f"ロボット [{port}] 接続完了")
            
            device.speed(velocity=2000, acceleration=2000)
            
            device.move_to(*self.config["ready_pos"], wait=True)
            self.log_message.emit(f"ロボット [{port}] 準備完了")

            # --- ★★★ ここからが修正点 ★★★ ---
            # カウントダウン中に、最初の音符を叩くための構えの位置へ移動する
            if self.motion_plan:
                # 最初の振り上げ動作（モーションプランの2番目の要素）の位置を取得
                initial_backswing_pos = self.motion_plan[1]["position"]
                device.move_to(*initial_backswing_pos, wait=True)
                self.log_message.emit(f"ロボット [{port}] 最初の打撃準備完了")
            # --- ★★★ ここまでが修正点 ★★★ ---

            # GUIのカウントダウン終了を待つ
            self.start_event.wait()
            if self.stop_event.is_set(): return

            master_start_time = time.time()
            loop_count = 0
            
            while not self.stop_event.is_set():
                current_loop_start_time = master_start_time + (loop_count * self.loop_duration)
                
                # 最初の振り上げ動作は準備で済ませたので、プランの最初（打撃）から開始
                start_index = 0
                # ループの初回のみ、最初の打撃から開始。2周目以降は全てのプランを実行
                if loop_count == 0:
                    start_index = 0
                
                for motion in self.motion_plan[start_index:]:
                    if self.stop_event.is_set(): break

                    target_time = current_loop_start_time + motion["target_time"]
                    send_command_time = target_time - LATENCY_COMPENSATION_S

                    while time.time() < send_command_time:
                        if self.stop_event.is_set(): break
                        time.sleep(0.001)
                    if self.stop_event.is_set(): break
                    
                    if not self.stop_event.is_set():
                        device.move_to(*motion["position"], wait=False)

                if self.stop_event.is_set(): break
                loop_count += 1

        except Exception as e:
            self.log_message.emit(f"ロボット [{port}] エラー: {e}")
        finally:
            if device:
                try:
                    if device in self.device_list: self.device_list.remove(device)
                    device.move_to(250, 0, 80, 0, wait=True)
                except: pass
                try: device.close()
                except: pass
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

        top_score = score_data.get("top", {}); bottom_score = score_data.get("bottom", {})
        top_bpm = top_score.get("bpm", 120); bottom_bpm = bottom_score.get("bpm", 120)
        
        top_items = top_score.get("items", [])
        bottom_items = bottom_score.get("items", [])
        
        top_beats = top_score.get("total_beats", 8); bottom_beats = bottom_score.get("total_beats", 8)
        top_duration = top_beats * (60.0 / top_bpm)
        bottom_duration = bottom_beats * (60.0 / bottom_bpm)
        loop_duration_sec = max(top_duration, bottom_duration)
        
        configs = [(ROBOT1_CONFIG, top_items, top_bpm), (ROBOT2_CONFIG, bottom_items, bottom_bpm)]

        self.log_message.emit("🎼 楽譜分析とモーションプランニング開始...")
        
        for config, items, bpm in configs:
            thread = QThread()
            worker = RobotController(config, items, bpm, loop_duration_sec, self.start_event, self.stop_event, self.active_devices)
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
        self.stop_event.set()
        self.start_event.set()

    def trigger_start(self):
        self.log_message.emit("🎬 演奏開始！")
        self.start_event.set()

    def _on_thread_finished(self, thread_obj, worker_obj):
        if thread_obj in self.threads: self.threads.remove(thread_obj)
        if worker_obj in self.workers: self.workers.remove(worker_obj)