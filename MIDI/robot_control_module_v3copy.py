import time
import threading
import math
import os
from PyQt6.QtCore import QObject, pyqtSignal, QThread

# --- 必須ライブラリのインポート ---
try:
    from pydobot import Dobot
    PYDOBOT_AVAILABLE = True
except ImportError:
    PYDOBOT_AVAILABLE = False

try:
    import pandas as pd
    import numpy as np
    from scipy.spatial import cKDTree
    PANDAS_SCIPY_AVAILABLE = True
except ImportError:
    PANDAS_SCIPY_AVAILABLE = False

# --- ロボット設定 ---
ROBOT1_CONFIG = { "port": "COM3", "ready_pos": (234, 15, 70, 0), "strike_pos": (234, 15, 22, 0) }
ROBOT2_CONFIG = { "port": "COM4", "ready_pos": (234, 15, 70, 0), "strike_pos": (234, 15, 22, 0) }

# --- 動作パラメータ ---
COMMUNICATION_LATENCY_S = 0.05
TUNING_DATA_CSV_PATH = 'tuning_data.csv'

# ★★★ 修正: このグローバル変数は使わずに動的に設定する ★★★
# MOTOR_REVERSAL_PAUSE_S = 0.40 

# 一打目の遅延を強制的に補正する値 (秒)
FIRST_HIT_COMPENSATION_S = 0.350

# --- 表現力パラメータ ---
MAX_EXPECTED_INTERVAL_S = 2.0
MIN_EXPECTED_INTERVAL_S = 0.1
MIN_VELOCITY = 100.0
MAX_VELOCITY = 400.0
MIN_ACCELERATION = 100.0
MAX_ACCELERATION = 800.0
MAX_BACKSWING_HEIGHT = ROBOT1_CONFIG["ready_pos"][2]
MIN_BACKSWING_HEIGHT = ROBOT1_CONFIG["strike_pos"][2] + 10.0
EXPRESSION_EXPONENT = 0.75

SAFETY_LIMITS = {
    'x_min': 160.0, 'x_max': 250.0,
    'y_min': -180.0, 'y_max': 180.0,
    'z_min': 0, 'z_max': 130.0,
}

def get_distance(pos1, pos2):
    return math.sqrt((pos1[0] - pos2[0])**2 + (pos1[1] - pos2[1])**2 + (pos1[2] - pos2[2])**2)

class RobotController(QObject):
    log_message = pyqtSignal(str)
    finished = pyqtSignal()
    command_sent = pyqtSignal(str, dict)
    estimated_arrival = pyqtSignal(str, float, float) # ★ 推定到達時刻シグナル (前回から)

    def _clamp_position(self, position):
        x, y, z, r = position
        clamped_x = max(SAFETY_LIMITS['x_min'], min(SAFETY_LIMITS['x_max'], x))
        clamped_y = max(SAFETY_LIMITS['y_min'], min(SAFETY_LIMITS['y_max'], y))
        clamped_z = max(SAFETY_LIMITS['z_min'], min(SAFETY_LIMITS['z_max'], z))
        if (x, y, z) != (clamped_x, clamped_y, clamped_z):
            self.log_message.emit(f"警告: 目標座標({x:.1f},{y:.1f},{z:.1f})を安全範囲内に修正しました。")
        return (clamped_x, clamped_y, clamped_z, r)

    # ★★★ ここから新しいメソッドを追加 ★★★
    def _get_pause_for_bpm(self, bpm):
        """
        BPMに基づいてモーター反転ポーズ時間を動的に決定します。
        BPMマップにない値の場合、最も近いBPMの値を使用します。
        """
        
        # ★★★ BPMとポーズ時間(秒)の対応マップ ★★★
        # (↓の値は仮のものです。すべて手動で調整してください)
        BPM_PAUSE_MAP = {
            30:  0.400, # BPM 30 の時のポーズ時間
            40:  0.400, # BPM 40 ...
            50:  0.57,
            60:  0.25,
            70:  0.550,
            80:  0.600,
            90:  0.650,
            100: 0.700,
            110: 0.780,
            120: 0.850  # BPM 120 の時のポーズ時間
        }
        # ★★★ 調整はここまで ★★★

        # 1. マップにBPMがそのまま存在するか確認
        if bpm in BPM_PAUSE_MAP:
            pause_s = BPM_PAUSE_MAP[bpm]
            self.log_message.emit(f"[{self.track_name}] BPM {bpm} に一致。モーター反転ポーズを {pause_s:.3f}s に設定。")
            return pause_s

        # 2. 存在しない場合 (例: BPM 65 や 121)、最も近いBPMの値を流用する
        
        # マップのキー(BPM)と入力BPMとの差の絶対値を計算し、最も差が小さいキーを見つける
        closest_bpm = min(BPM_PAUSE_MAP.keys(), key=lambda k: abs(k - bpm))
        pause_s = BPM_PAUSE_MAP[closest_bpm]
        
        self.log_message.emit(f"[{self.track_name}] BPM {bpm} に一致なし。最も近いBPM {closest_bpm} の値 ( {pause_s:.3f}s ) を流用します。")
        return pause_s
    # ★★★ 追加ここまで ★★★

    def __init__(self, config, note_items, bpm, loop_duration, stop_event, device_list, track_name, controller, master_start_time):
        super().__init__()
        # --- __init__では、渡された変数を保存するだけにする ---
        self.config = config; self.note_items = note_items; self.bpm = bpm
        self.loop_duration = loop_duration; self.stop_event = stop_event
        self.device_list = device_list; self.track_name = track_name; self.controller = controller
        self.master_start_time = master_start_time
        
        # --- 初期化処理はrun()メソッドの先頭に移動 ---
        self.safe_ready_pos = self.config["ready_pos"]
        self.safe_strike_pos = self.config["strike_pos"]
        
        self.motion_profile_df = None
        self.kdtree = None
        self.motion_plan = []
        
        # ★★★ 新しいインスタンス変数を追加 ★★★
        # (run()メソッドでBPMに基づいて上書きされます)
        self.motor_reversal_pause_s = 0.050 


    def _load_motion_profile(self, filepath):
        if not PANDAS_SCIPY_AVAILABLE: self.log_message.emit("警告: pandas/scipy未インストール。"); return
        if not os.path.exists(filepath): self.log_message.emit(f"警告: {filepath} が見つかりません。"); return
        try:
            self.log_message.emit(f"運動特性データ {filepath} を読み込み中...")
            self.motion_profile_df = pd.read_csv(filepath)
            
            self.log_message.emit(f"  -> 読み込み成功。{len(self.motion_profile_df)}行のデータを検出。")
            self.log_message.emit(f"  -> カラム: {list(self.motion_profile_df.columns)}")
            
            profile_points = self.motion_profile_df[['distance', 'target_velocity', 'target_acceleration']].values
            self.kdtree = cKDTree(profile_points)
            self.log_message.emit("運動特性データの準備完了 (k-d tree構築完了)。")
            
        except Exception as e:
            self.log_message.emit(f"エラー: {filepath} の読み込みに失敗。{e}"); self.motion_profile_df = None
            
    def _find_best_motion_profile_for_duration(self, target_duration):
        """
        指定された目標時間に最も近い動作プロファイルをCSVから検索する。
        条件に合うものが複数ある場合は、移動距離が最大のを優先する。
        """
        if self.motion_profile_df is None or self.motion_profile_df.empty:
            self.log_message.emit(f"      -> 警告: 運動特性(CSV)なし。目標時間 {target_duration:.3f}s に対し、"
                                f"デフォルト値(Dist=30.0, V=150.0, A=150.0)を使用。")
            return 30.0, 150.0, 150.0 # distance, velocity, acceleration

        try:
            df = self.motion_profile_df
            df['duration_diff'] = (df['actual_duration'] - target_duration).abs()
            min_diff = df['duration_diff'].min()
            closest_matches = df[df['duration_diff'] == min_diff]
            best_match = closest_matches.loc[closest_matches['distance'].idxmax()]
            
            self.log_message.emit(f"      -> CSV検索結果: "
                                f"目標 {target_duration:.3f}s に最も近い行 (差={min_diff:.3f}s) を使用:")
            self.log_message.emit(f"         [Dist={best_match['distance']:.1f}, "
                                f"V={best_match['target_velocity']:.1f}, "
                                f"A={best_match['target_acceleration']:.1f}, "
                                f"ActualDuration={best_match['actual_duration']:.3f}s]")
            
            return best_match['distance'], best_match['target_velocity'], best_match['target_acceleration']
        except Exception as e:
            self.log_message.emit(f"      -> 運動特性データの検索中にエラー: {e}")
            return 30.0, 150.0, 150.0

    def _get_estimated_duration(self, distance, velocity, acceleration):
        if self.kdtree is None or self.motion_profile_df is None:
            if velocity > 0 and acceleration > 0:
                time_to_reach_vel = velocity / acceleration
                dist_to_reach_vel = 0.5 * acceleration * time_to_reach_vel**2
                if distance < 2 * dist_to_reach_vel: return 2 * math.sqrt(distance / acceleration)
                else: return 2 * time_to_reach_vel + (distance - 2 * dist_to_reach_vel) / velocity
            return 0.0
        query_point = np.array([distance, velocity, acceleration])
        _, nearest_index = self.kdtree.query(query_point)
        return self.motion_profile_df.iloc[nearest_index]['actual_duration']

    def _create_motion_plan(self):
        notes_only = sorted([item for item in self.note_items if item.get("class") == "note"], key=lambda x: x['beat'])
        
        self.log_message.emit(f"[{self.track_name}] モーションプランの作成開始... (BPM: {self.bpm}, ノート数: {len(notes_only)})")

        if not notes_only:
            self.log_message.emit(f"[{self.track_name}] ノートがないためプラン作成をスキップ。")
            return []

        motion_plan = []
        seconds_per_beat = 60.0 / self.bpm

        for i, current_note in enumerate(notes_only):
            current_strike_time = current_note.get("beat", 0) * seconds_per_beat

            # --- 1.「振り下ろし」動作の決定 ---
            prev_note_index = (i - 1 + len(notes_only)) % len(notes_only)
            prev_note = notes_only[prev_note_index]
            prev_strike_time = prev_note.get("beat", 0) * seconds_per_beat
            
            if i == 0: # ループの最初の音符の場合
                downstroke_interval = (self.loop_duration - prev_strike_time) + current_strike_time
            else:
                downstroke_interval = current_strike_time - prev_strike_time
            
            # ★★★ 修正: グローバル変数 -> self.motor_reversal_pause_s ★★★
            available_downstroke_time = max(0.01, downstroke_interval - self.motor_reversal_pause_s)
            target_downstroke_duration = available_downstroke_time / 2.0
            
            self.log_message.emit(f"  [{self.track_name}] --- ノート#{i} (Beat {current_note.get('beat', 0):.2f}) の計算 ---")
            self.log_message.emit(f"    [Strike] 前の音符(Beat {prev_note.get('beat', 0):.2f})からの間隔: {downstroke_interval:.3f}s")
            # ★★★ 修正: グローバル変数 -> self.motor_reversal_pause_s ★★★
            self.log_message.emit(f"    [Strike] モーター反転ポーズ({self.motor_reversal_pause_s:.3f}s)を除いた時間: {available_downstroke_time:.3f}s")
            self.log_message.emit(f"    [Strike] 振り下ろし目標時間 (上記/2): {target_downstroke_duration:.3f}s")
            
            _, strike_velocity, strike_acceleration = self._find_best_motion_profile_for_duration(target_downstroke_duration)

            motion_plan.append({
                "target_time": current_strike_time,
                "position": self.safe_strike_pos,
                "velocity": strike_velocity,
                "acceleration": strike_acceleration,
                "is_compensated": False, 
                "action": "strike"
            })

            # --- 2.「振り上げ」動作の決定 ---
            next_note_index = (i + 1) % len(notes_only)
            next_note = notes_only[next_note_index]
            next_strike_time = next_note.get("beat", 0) * seconds_per_beat

            if i == len(notes_only) - 1: # ループの最後の音符の場合
                upstroke_interval = (self.loop_duration - current_strike_time) + next_strike_time
            else:
                upstroke_interval = next_strike_time - current_strike_time

            # ★★★ 修正: グローバル変数 -> self.motor_reversal_pause_s ★★★
            available_upstroke_time = max(0.01, upstroke_interval - self.motor_reversal_pause_s)
            target_upstroke_duration = available_upstroke_time / 2.0
            
            self.log_message.emit(f"    [Upstroke] 次の音符(Beat {next_note.get('beat', 0):.2f})までの間隔: {upstroke_interval:.3f}s")
            # ★★★ 修正: グローバル変数 -> self.motor_reversal_pause_s ★★★
            self.log_message.emit(f"    [Upstroke] モーター反転ポーズ({self.motor_reversal_pause_s:.3f}s)を除いた時間: {available_upstroke_time:.3f}s")
            self.log_message.emit(f"    [Upstroke] 振り上げ目標時間 (上記/2): {target_upstroke_duration:.3f}s")
            
            backswing_distance, upstroke_velocity, upstroke_acceleration = self._find_best_motion_profile_for_duration(target_upstroke_duration)
            
            backswing_z = self.safe_strike_pos[2] + backswing_distance
            
            ready_x, ready_y, _, ready_r = self.safe_ready_pos
            backswing_pos = self._clamp_position((ready_x, ready_y, backswing_z, ready_r))
            
            upstroke_start_time = current_strike_time + 0.01 
            motion_plan.append({
                "target_time": upstroke_start_time,
                "position": backswing_pos,
                "velocity": upstroke_velocity,
                "acceleration": upstroke_acceleration,
                "is_compensated": True, 
                "action": "upstroke"
            })

        self.log_message.emit(f"[{self.track_name}] モーションプラン作成完了。 (全{len(motion_plan)}アクション)")
        return sorted(motion_plan, key=lambda x: x['target_time'])

    def run(self):
        device = None; port = self.config["port"]
        try:
            # ログシグナルが接続された *後* に、ログを発生させる処理を実行する
            self.log_message.emit(f"--- [{port}] スレッド開始 ---")
            
            # 1. 安全な座標を計算 (ここでログが出る可能性がある)
            self.safe_ready_pos = self._clamp_position(self.config["ready_pos"])
            self.safe_strike_pos = self._clamp_position(self.config["strike_pos"])

            # ★★★ ここでBPMに基づいて動的に設定 ★★★
            self.motor_reversal_pause_s = self._get_pause_for_bpm(self.bpm)
            # ★★★ 追加ここまで ★★★
            
            # 2. モーションプロファイル(CSV)を読み込む
            self._load_motion_profile(TUNING_DATA_CSV_PATH)
            
            # 3. モーションプランを作成する
            self.motion_plan = self._create_motion_plan()
            
            if not self.motion_plan:
                 self.log_message.emit(f"[{port}] モーションプランが空です。スレッドを終了します。")
                 self.finished.emit()
                 return
            
            self.log_message.emit(f"--- [{port}] 初期化完了、ロボット接続へ ---")

            if not PYDOBOT_AVAILABLE: raise ImportError("pydobotライブラリが見つかりません。")
            device = Dobot(port=port, verbose=False); self.device_list.append(device)
            self.log_message.emit(f"ロボット [{port}] 接続完了")
            device.speed(velocity=200, acceleration=200)
            device.move_to(*self.safe_ready_pos, wait=True)
            self.log_message.emit(f"ロボット [{port}] 準備完了、演奏開始を待機中...")
            
            loop_count = 0
            current_pos = self.safe_ready_pos
            
            while not self.stop_event.is_set():
                current_loop_start_time = self.master_start_time + (loop_count * self.loop_duration)
                
                loop_compensation = FIRST_HIT_COMPENSATION_S
                
                for motion in self.motion_plan:
                    if self.stop_event.is_set(): break
                    ideal_time_ms = motion["target_time"] * 1000
                    guided_time_ms = self.controller.get_guided_timing(self.track_name, ideal_time_ms)
                    
                    target_time = current_loop_start_time + (guided_time_ms / 1000.0) - loop_compensation
                    
                    move_duration = 0.0 # ★ 推定到達時刻のシグナル送信のため
                    is_compensated = motion.get("is_compensated", False)

                    if is_compensated:
                        send_command_time = target_time - COMMUNICATION_LATENCY_S
                    else:
                        distance = get_distance(current_pos, motion["position"])
                        move_duration = self._get_estimated_duration(distance, motion["velocity"], motion["acceleration"])
                        send_command_time = target_time - move_duration - COMMUNICATION_LATENCY_S
                    
                    wait_time = send_command_time - time.time()
                    target_time_rel = target_time - self.master_start_time
                    send_time_rel = send_command_time - self.master_start_time
                    
                    self.log_message.emit(
                        f"  [{self.track_name}] "
                        f"Exec: {motion.get('action', 'N/A').capitalize():<8} | " # 'Strike' or 'Upstroke'
                        f"GoalTime: {target_time_rel:6.3f}s | "    # 着弾目標時刻
                        f"MoveDur: {move_duration:5.3f}s | "      # 推定移動時間
                        f"SendTime: {send_time_rel:6.3f}s | "      # 逆算された送信時刻
                        f"Wait: {wait_time:6.3f}s"
                    )
                    if wait_time > 0:
                        if wait_time > 0.010:  
                            time.sleep(wait_time - 0.005)
                        while time.time() < send_command_time:
                            if self.stop_event.is_set(): break
                            time.sleep(0.0001)
                    
                    if self.stop_event.is_set(): break
                    
                    if not self.stop_event.is_set():
                        self.command_sent.emit(self.track_name, motion)
                        device.speed(velocity=motion["velocity"], acceleration=motion["acceleration"])
                        device.move_to(*motion["position"], wait=False)
                        current_pos = motion["position"]

                        # ★ 推定到達時刻を計算してシグナルを送出
                        if move_duration > 0:
                             estimated_arrival_abs = send_command_time + COMMUNICATION_LATENCY_S + move_duration
                             estimated_arrival_relative = estimated_arrival_abs - self.master_start_time
                             target_z = motion["position"][2]
                             self.estimated_arrival.emit(self.track_name, estimated_arrival_relative, target_z) # (前回から)
                
                if self.stop_event.is_set(): break
                loop_count += 1
        
        except Exception as e: self.log_message.emit(f"ロボット [{port}] エラー: {e}")
        finally:
            if device:
                try:
                    if device in self.device_list: self.device_list.remove(device)
                    safe_end_pos = self._clamp_position((230, 0, 60, 0))
                    device.move_to(*safe_end_pos, wait=True)  
                except: pass
                try: device.close()
                except: pass
                self.log_message.emit(f"ロボット [{port}] 接続解除")
            self.finished.emit()


# ★★★ ここから RobotManager (training_module_v3.py から移動) ★★★
class RobotManager(QObject):
    log_message = pyqtSignal(str)
    command_sent = pyqtSignal(str, dict)
    estimated_arrival = pyqtSignal(str, float, float) # ★ 推定到達時刻シグナル (前回から)
    
    def get_first_move_preparation_time(self, score_data):
        try:
            top_score = score_data.get("top", {})
            if not top_score.get("items"): return 0.2
            top_bpm = top_score.get("bpm", 120); top_items = top_score.get("items", [])
            loop_duration_sec = top_score.get("total_beats", 8) * (60.0 / top_bpm)
            
            # ダミーコントローラ (get_guided_timing を持つ)
            class DummyController:
                def get_guided_timing(self, _, ideal_time_ms): return ideal_time_ms
            
            stop_event = threading.Event() # ダミーのストップイベント
            temp_rc = RobotController(
                config=ROBOT1_CONFIG, 
                note_items=top_items, 
                bpm=top_bpm, 
                loop_duration=loop_duration_sec, 
                stop_event=stop_event, 
                device_list=[], 
                track_name='top', 
                controller=DummyController(), 
                master_start_time=0
            )
            
            # temp_rc.run() の冒頭の処理を手動で実行
            temp_rc.safe_ready_pos = temp_rc._clamp_position(temp_rc.config["ready_pos"])
            temp_rc.safe_strike_pos = temp_rc._clamp_position(temp_rc.config["strike_pos"])
            # ★★★ BPMマップのロジックも手動で実行 ★★★
            temp_rc.motor_reversal_pause_s = temp_rc._get_pause_for_bpm(temp_rc.bpm)
            
            temp_rc._load_motion_profile(TUNING_DATA_CSV_PATH)
            temp_rc.motion_plan = temp_rc._create_motion_plan()
            
            if not temp_rc.motion_plan: return 0.2
            
            ready_pos = temp_rc.safe_ready_pos
            first_motion = temp_rc.motion_plan[0]
            
            if first_motion.get("is_compensated", False):
                move_duration = 0.0 
            else:
                distance = get_distance(ready_pos, first_motion["position"])
                move_duration = temp_rc._get_estimated_duration(distance, first_motion["velocity"], first_motion["acceleration"])

            return move_duration + FIRST_HIT_COMPENSATION_S + COMMUNICATION_LATENCY_S
            
        except Exception as e:
            print(f"get_first_move_preparation_time でエラー: {e}")
            return 0.2
        
    def __init__(self, parent=None):
        super().__init__(parent)
        self.threads = []
        self.workers = []
        self.stop_event = threading.Event()
        self.active_devices = []
    
    def start_control(self, score_data, active_controller, master_start_time):
        self.stop_control(); self.stop_event.clear()
        
        self.log_message.emit("🎼 JSONデータ(score_data)受信。楽譜分析とモーションプランニング開始...")
        
        top_score = score_data.get("top", {}); bottom_score = score_data.get("bottom", {})
        top_bpm = top_score.get("bpm", 120); bottom_bpm = bottom_score.get("bpm", 120)
        top_items = top_score.get("items", []); bottom_items = bottom_score.get("items", [])
        
        self.log_message.emit(f"  [top] トラック情報: BPM={top_bpm}, ノート数={len([i for i in top_items if i.get('class') == 'note'])}")
        self.log_message.emit(f"  [bottom] トラック情報: BPM={bottom_bpm}, ノート数={len([i for i in bottom_items if i.get('class') == 'note'])}")
        
        top_beats = top_score.get("total_beats", 8); bottom_beats = bottom_score.get("total_beats", 8)
        top_duration = top_beats * (60.0 / top_bpm); bottom_duration = bottom_beats * (60.0 / bottom_bpm)
        loop_duration_sec = max(top_duration, bottom_duration)
        configs = [(ROBOT1_CONFIG, top_items, top_bpm, 'top'), (ROBOT2_CONFIG, bottom_items, bottom_bpm, 'bottom')]
        
        self.log_message.emit("🤖 各ロボットのコントローラを起動します...") 
        
        for config, items, bpm, track_name in configs:
            thread = QThread()
            # RobotController は同じファイル内で定義されている
            worker = RobotController(config, items, bpm, loop_duration_sec, self.stop_event, self.active_devices, track_name, active_controller, master_start_time)
            
            worker.command_sent.connect(self.command_sent.emit)
            worker.estimated_arrival.connect(self.estimated_arrival.emit) # ★ 推定到達シグナルを接続 (前回から)
            worker.moveToThread(thread)
            
            worker.log_message.connect(self.log_message.emit) 
            thread.started.connect(worker.run)
            
            worker.finished.connect(thread.quit); worker.finished.connect(worker.deleteLater); thread.finished.connect(thread.deleteLater)
            thread.finished.connect(lambda t=thread, w=worker: self._on_thread_finished(t, w)); thread.start()
            self.threads.append(thread); self.workers.append(worker)

    def stop_control(self):
        if not self.threads: return
        self.log_message.emit("🛑 演奏停止中..."); self.stop_event.set()

    def trigger_start(self):
        pass

    def _on_thread_finished(self, thread_obj, worker_obj):
        if thread_obj in self.threads: self.threads.remove(thread_obj)
        if worker_obj in self.workers: self.workers.remove(worker_obj)