import time
import threading
from PyQt6.QtCore import QObject, pyqtSignal, QThread

try:
    from pydobot import Dobot
    PYDOBOT_AVAILABLE = True
except ImportError:
    PYDOBOT_AVAILABLE = False

# --- ロボット設定 ---
ROBOT1_CONFIG = {"port": "COM3", "ready_pos": (279, -25, 50, 0), "tap_pos": (264, -23, 11, 0), "short_ready_pos": (270, -24, 20, 0)}
ROBOT2_CONFIG = {"port": "COM4", "ready_pos": (279, -25, 50, 0), "tap_pos": (264, -23, 11, 0), "short_ready_pos": (270, -24, 20, 0)}
LATENCY_COMPENSATION_S = 0.090 # 90ミリ秒の遅延補正値（秒単位）
QUICK_TAP_THRESHOLD = 0.7

class RobotController(QObject):
    log_message = pyqtSignal(str)
    finished = pyqtSignal()
   
    def __init__(self, config, note_items, bpm, loop_duration, start_event, stop_event, device_list):
        super().__init__()
        self.config = config
        self.note_items = note_items
        self.bpm = bpm
        self.loop_duration = loop_duration
        self.start_event = start_event
        self.stop_event = stop_event
        self.device_list = device_list

    def run(self):
        device = None
        port = self.config["port"]
        try:
            if not PYDOBOT_AVAILABLE:
                raise ImportError("pydobotライブラリが見つかりません。")

            ready_pos = self.config["ready_pos"]
            tap_pos = self.config["tap_pos"]
            short_ready_pos = self.config["short_ready_pos"]
            seconds_per_beat = 60.0 / self.bpm

            device = Dobot(port=port, verbose=False)
            self.device_list.append(device)
            self.log_message.emit(f"ロボット [{port}] 接続完了 (BPM: {self.bpm})")
           
            device.speed(1000, 1000)
            device.move_to(*ready_pos, wait=True)
            self.log_message.emit(f"ロボット [{port}] 準備完了")

            self.start_event.wait()
            if self.stop_event.is_set(): return

            master_start_time = time.time()
            loop_count = 0
           
            while not self.stop_event.is_set():
                current_loop_start_time = master_start_time + (loop_count * self.loop_duration)
               
                for i, current_note in enumerate(self.note_items):
                    if self.stop_event.is_set(): break
                   
                    current_beat = current_note.get("beat", 0)
                   
                    # --- ↓↓↓ ここからが修正点 ↓↓↓ ---
                    # 1. 本来の目標時刻を計算
                    target_time = current_loop_start_time + (current_beat * seconds_per_beat)
                   
                    # 2. 遅延補正を適用した「コマンド送信時刻」を計算
                    send_command_time = target_time - LATENCY_COMPENSATION_S

                    # 3. 精度を上げるため、スリープ時間を短くして待機
                    while time.time() < send_command_time:
                        if self.stop_event.is_set(): break
                        time.sleep(0.001) # スリープ時間を短縮して精度向上
                   
                    if self.stop_event.is_set(): break
                   
                    # --- ↑↑↑ ここまでが修正点 ↑↑↑ ---

                    time_to_next = 0
                    if i + 1 < len(self.note_items):
                        time_to_next = (self.note_items[i+1].get("beat", 0) - current_beat) * seconds_per_beat
                    else:
                        next_loop_sync_time = current_loop_start_time + self.loop_duration
                        next_tap_time = next_loop_sync_time + (self.note_items[0].get("beat", 0) * seconds_per_beat)
                        time_to_next = next_tap_time - time.time()

                    return_pos = short_ready_pos if time_to_next < QUICK_TAP_THRESHOLD else ready_pos
                   
                    if not self.stop_event.is_set(): device.move_to(*tap_pos, wait=False)
                    if not self.stop_event.is_set(): device.move_to(*return_pos, wait=False)

                if self.stop_event.is_set(): break

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
        top_notes = [item for item in top_score.get("items", []) if item.get("class") == "note"]
        bottom_notes = [item for item in bottom_score.get("items", []) if item.get("class") == "note"]
        top_beats = top_score.get("total_beats", 8); bottom_beats = bottom_score.get("total_beats", 8)
        top_duration = top_beats * (60.0 / top_bpm)
        bottom_duration = bottom_beats * (60.0 / bottom_bpm)
        loop_duration_sec = max(top_duration, bottom_duration)
       
        configs = [(ROBOT1_CONFIG, top_notes, top_bpm), (ROBOT2_CONFIG, bottom_notes, bottom_bpm)]

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
        self.stop_event.set()
        self.start_event.set()

    def trigger_start(self):
        self.start_event.set()

    def _on_thread_finished(self, thread_obj, worker_obj):
        if thread_obj in self.threads: self.threads.remove(thread_obj)
        if worker_obj in self.workers: self.workers.remove(worker_obj)