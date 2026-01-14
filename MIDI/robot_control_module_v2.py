# robot_control_module.py (同調制御ロジック統合版)

import time
import threading
import math
from PyQt6.QtCore import QObject, pyqtSignal, QThread

try:
    from pydobot import Dobot
    PYDOBOT_AVAILABLE = True
except ImportError:
    PYDOBOT_AVAILABLE = False

# --- ロボット設定 ---
ROBOT1_CONFIG = {
    "port": "COM3",
    "ready_pos": (234, 15, 60, 0),
    "strike_pos": (222, 11, -5, 0),
}
ROBOT2_CONFIG = {
    "port": "COM4",
    "ready_pos": (234, 15, 60, 0),
    "strike_pos": (222, 11, -5, 0),
}

# --- 動作パラメータ ---
COMMUNICATION_LATENCY_S = 0.050  # PCからロボットへの通信遅延
AVERAGE_SPEED_MM_PER_S = 158.85     # ロボットの平均速度(mm/秒)。要調整！

# 振り上げる高さの計算パラメータ
MAX_BACKSWING_HEIGHT = 40.0
MIN_BACKSWING_HEIGHT = 5.0
TIME_TO_HEIGHT_NORMALIZATION_S = 0.5

class RobotController(QObject):
    log_message = pyqtSignal(str)
    finished = pyqtSignal()
    
    def _calculate_move_duration(self, pos1, pos2):
        """2点間の直線距離から、移動に要する時間を推定する"""
        distance = math.sqrt(
            (pos2[0] - pos1[0])**2 + 
            (pos2[1] - pos1[1])**2 + 
            (pos2[2] - pos1[2])**2
        )
        if AVERAGE_SPEED_MM_PER_S <= 0:
            return 0.0
        return distance / AVERAGE_SPEED_MM_PER_S
    
    # ★★★ 変更点1: __init__ に track_name と controller を追加 ★★★
    def __init__(self, config, note_items, bpm, loop_duration, start_event, stop_event, device_list, track_name, controller):
        super().__init__()
        self.config = config
        self.note_items = note_items
        self.bpm = bpm
        self.loop_duration = loop_duration
        self.start_event = start_event
        self.stop_event = stop_event
        self.device_list = device_list
        self.track_name = track_name      # 'top'か'bottom'か
        self.controller = controller      # 同調制御コントローラー
        
        self.motion_plan = self._create_motion_plan()

    def _create_motion_plan(self):
        """
        演奏開始前に楽譜を分析し、実行すべき全モーションのリストを作成する。
        各モーションは {target_time: 時刻(秒), position: 座標} の形式。
        この時点での target_time は「理想的な」タイミング。
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

            self.log_message.emit(f"ロボット [{port}] キャリブレーションを初期化・再設定します...")
            
            device.speed(velocity=2000, acceleration=2000)
            
            # --- ### 変更点 START ### ---

            # 1. ニュートラルな待機位置へ移動して待つ
            device.move_to(*self.config["ready_pos"], wait=True)
            self.log_message.emit(f"ロボット [{port}] 準備完了、Goサイン待機中...")
            
            # 2. 最初の音を叩くための準備位置への移動」を削除
            #    Goサイン後の最初の動きがストロークになるようにするため。

            # Goサインが出るまでここで待機
            self.start_event.wait()
            if self.stop_event.is_set(): return

            master_start_time = time.time()
            loop_count = 0
            
            # 3. 現在位置を `ready_pos` で初期化
            current_pos = self.config["ready_pos"]
            
            # --- ### 変更点 END ### ---

            while not self.stop_event.is_set():
                current_loop_start_time = master_start_time + (loop_count * self.loop_duration)
                
                # 1ループ目かどうかで、始点となる現在位置(current_pos)の扱いを変える必要はない。
                # なぜなら、2ループ目の開始時のcurrent_posは、1ループ目の最後の位置が
                # 引き継がれているため、動的計算ロジックが正しく機能する。
                # このループ構造で、始動と周回の両方に対応できる。
                
                for motion in self.motion_plan:
                    if self.stop_event.is_set(): break

                    ideal_time_ms = motion["target_time"] * 1000
                    guided_time_ms = self.controller.get_guided_timing(self.track_name, ideal_time_ms)
                    guided_time_s_in_loop = guided_time_ms / 1000.0
                    target_time = current_loop_start_time + guided_time_s_in_loop
                    
                    target_pos = motion["position"]
                    move_duration = self._calculate_move_duration(current_pos, target_pos)

                    send_command_time = target_time - move_duration - COMMUNICATION_LATENCY_S

                    while time.time() < send_command_time:
                        if self.stop_event.is_set(): break
                        time.sleep(0.001)
                    if self.stop_event.is_set(): break
                    
                    if not self.stop_event.is_set():
                        device.move_to(*motion["position"], wait=False)
                        # 次の計算のために、コマンド送信後の位置を現在位置として更新
                        current_pos = motion["position"]

                if self.stop_event.is_set(): break
                loop_count += 1
        
        except Exception as e:
            self.log_message.emit(f"ロボット [{port}] エラー: {e}")
        finally:
            # ... (finallyブロックは変更なし) ...
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

    def get_first_move_preparation_time(self, score_data):
        """
        最初の打撃に必要な準備時間（移動時間＋通信遅延）を事前に計算して返す。
        """
        try:
            # 最初の音は左手(top)の楽譜で決まると仮定
            top_score = score_data.get("top", {})
            if not top_score.get("items"):
                return 0.2 # 楽譜がない場合は安全マージンを返す

            top_bpm = top_score.get("bpm", 120)
            top_items = top_score.get("items", [])
            loop_duration_sec = top_score.get("total_beats", 8) * (60.0 / top_bpm)

            # ダミーのコントローラーを作成
            class DummyController:
                def get_guided_timing(self, _, ideal_time_ms): return ideal_time_ms
            
            # 一時的なRobotControllerを作成して、モーションプランと計算メソッドを利用
            temp_rc = RobotController(
                config=ROBOT1_CONFIG, note_items=top_items, bpm=top_bpm,
                loop_duration=loop_duration_sec, start_event=None,
                stop_event=None, device_list=[],
                track_name='top', controller=DummyController()
            )

            if not temp_rc.motion_plan:
                return 0.2 # モーションがなければ安全マージンを返す

            ready_pos = ROBOT1_CONFIG["ready_pos"]
            first_strike_pos = temp_rc.motion_plan[0]["position"]
            
            # 移動時間と通信遅延を足したものが、必要な準備時間
            move_duration = temp_rc._calculate_move_duration(ready_pos, first_strike_pos)
            preparation_time = move_duration + COMMUNICATION_LATENCY_S
            
            return preparation_time
        except Exception:
            # 計算に失敗した場合の安全なデフォルト値
            return 0.2
        
    def __init__(self, parent=None):
        super().__init__(parent)
        self.threads = []
        self.workers = []
        self.start_event = threading.Event()
        self.stop_event = threading.Event()
        self.active_devices = []

    # ★★★ 変更点3: start_control が active_controller を受け取る ★★★
    def start_control(self, score_data, active_controller):
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
        
        # track_nameを渡すためにタプルの内容を更新
        configs = [
            (ROBOT1_CONFIG, top_items, top_bpm, 'top'), 
            (ROBOT2_CONFIG, bottom_items, bottom_bpm, 'bottom')
        ]

        self.log_message.emit("🎼 楽譜分析とモーションプランニング開始...")
        
        for config, items, bpm, track_name in configs:
            thread = QThread()
            # ★★★ 変更点4: RobotController に track_name と active_controller を渡す ★★★
            worker = RobotController(config, items, bpm, loop_duration_sec, self.start_event, self.stop_event, self.active_devices, track_name, active_controller)
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