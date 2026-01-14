import time
import threading
import math
import os
from PyQt6.QtCore import QObject, pyqtSignal, QThread
import threading

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
ROBOT1_CONFIG = { "port": "COM4", "ready_pos": (230, 0, 60, 0), "strike_pos": (226, 0.3, 41, 0) }
ROBOT2_CONFIG = { "port": "COM3", "ready_pos": (230, 0, 60, 0), "strike_pos": (226, 0.3, 41, 0) }
FIXED_VELOCITY = 1000.0      # ユーザー指定の固定速度
FIXED_ACCELERATION = 1000.0  # ユーザー指定の固定加速度

# --- 動作パラメータ ---
COMMUNICATION_LATENCY_S = 0.05
TUNING_DATA_CSV_PATH = 'tuning_data.csv'

# 一打目の遅延を強制的に補正する値 (秒)
FIRST_HIT_COMPENSATION_S = 0.4

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
    estimated_arrival = pyqtSignal(str, float, float)
    log_message_from_worker = pyqtSignal(str) 
    play_hit_sound = pyqtSignal()

    def _clamp_position(self, position):
        x, y, z, r = position
        clamped_x = max(SAFETY_LIMITS['x_min'], min(SAFETY_LIMITS['x_max'], x))
        clamped_y = max(SAFETY_LIMITS['y_min'], min(SAFETY_LIMITS['y_max'], y))
        clamped_z = max(SAFETY_LIMITS['z_min'], min(SAFETY_LIMITS['z_max'], z))
        if (x, y, z) != (clamped_x, clamped_y, clamped_z):
            # 頻繁に出るとログが見づらくなるため、プラン作成時以外はコメントアウトしても良い
            pass 
        return (clamped_x, clamped_y, clamped_z, r)

    def _get_pause_for_bpm(self, bpm):
        # (変更なしのため省略。元のコードをそのまま使用してください)
        BPM_PAUSE_MAP = {
            30:  0.00, 35: 0.0, 40:  0.400, 50:  0.57, 60:  0.25, 70:  0.550,
            80:  0.600, 90:  0.650, 100: 0.700, 110: 0.780, 120: 0.850
        }
        if bpm in BPM_PAUSE_MAP: return BPM_PAUSE_MAP[bpm]
        closest_bpm = min(BPM_PAUSE_MAP.keys(), key=lambda k: abs(k - bpm))
        return BPM_PAUSE_MAP[closest_bpm]

    def __init__(self, config, note_items, bpm, loop_duration, stop_event, device_list, track_name, controller, master_start_time):
        super().__init__()
        self.config = config; self.note_items = note_items; self.bpm = bpm
        self.loop_duration = loop_duration; self.stop_event = stop_event
        self.device_list = device_list; self.track_name = track_name; self.controller = controller
        self.master_start_time = master_start_time
        
        self.safe_ready_pos = self.config["ready_pos"]
        self.safe_strike_pos = self.config["strike_pos"]
        
        self.motion_profile_df = None
        self.fixed_profile_df = None # ★ V=1000, A=1000 のみのデータフレーム
        self.motion_plan = []
        self.motor_reversal_pause_s = 0.050 

    def _load_motion_profile(self, filepath):
        if not PANDAS_SCIPY_AVAILABLE: self.log_message.emit("警告: pandas/scipy未インストール。"); return
        if not os.path.exists(filepath): self.log_message.emit(f"警告: {filepath} が見つかりません。"); return
        try:
            self.log_message.emit(f"運動特性データ {filepath} を読み込み中...")
            df = pd.read_csv(filepath)
            self.motion_profile_df = df # 全データも一応保持
            
            # ★★★ フィルタリング処理 ★★★
            # target_velocity と target_acceleration が固定値(1000)のものだけを抽出
            self.fixed_profile_df = df[
                (df['target_velocity'] == FIXED_VELOCITY) & 
                (df['target_acceleration'] == FIXED_ACCELERATION)
            ].copy()
            
            # 線形補間のために actual_duration でソートしておく
            self.fixed_profile_df.sort_values(by='actual_duration', inplace=True)
            self.fixed_profile_df.reset_index(drop=True, inplace=True)

            count = len(self.fixed_profile_df)
            self.log_message.emit(f" -> V={FIXED_VELOCITY}, A={FIXED_ACCELERATION} のデータを {count}件 抽出しました。")
            
            if count == 0:
                self.log_message.emit("警告: 指定された速度・加速度のデータがCSVに存在しません。")

        except Exception as e:
            self.log_message.emit(f"エラー: {filepath} の読み込みに失敗。{e}"); self.motion_profile_df = None

    def _get_distance_from_duration_linear(self, target_duration):
        """
        ★新規メソッド: 時間(target_duration) から 距離(distance) を線形補間で求める。
        """
        if self.fixed_profile_df is None or self.fixed_profile_df.empty:
            # データがない場合はデフォルト値を返す
            return 30.0 

        df = self.fixed_profile_df
        
        # 範囲外のチェック
        min_duration = df['actual_duration'].min()
        max_duration = df['actual_duration'].max()
        
        if target_duration <= min_duration:
            return df.iloc[0]['distance']
        if target_duration >= max_duration:
            return df.iloc[-1]['distance']

        # 線形補間
        # target_duration を挟む2点を探す
        # (dfはソート済み)
        upper_idx = df[df['actual_duration'] >= target_duration].index[0]
        lower_idx = upper_idx - 1
        
        row_lower = df.iloc[lower_idx]
        row_upper = df.iloc[upper_idx]
        
        t1 = row_lower['actual_duration']
        t2 = row_upper['actual_duration']
        d1 = row_lower['distance']
        d2 = row_upper['distance']
        
        # 時間の比率を計算
        if t2 - t1 == 0: return d1
        ratio = (target_duration - t1) / (t2 - t1)
        
        # 距離を補間
        interpolated_distance = d1 + ratio * (d2 - d1)
        
        return interpolated_distance

    def _get_duration_from_distance_linear(self, target_distance):
        """
        ★新規メソッド: 距離(target_distance) から 時間(actual_duration) を線形補間で求める。
        （安全範囲制限で距離が縮まった場合に、正確な移動時間を再計算するために使用）
        """
        if self.fixed_profile_df is None or self.fixed_profile_df.empty:
            # 概算: 等加速度運動として計算 (x = 1/2 a t^2 => t = sqrt(2x/a)) ※加速のみの場合
            # ここでは簡易的に返す
            return 0.2

        df = self.fixed_profile_df
        # 距離でソート（元のDFは時間ソートだが、距離と時間は概ね正比例するためそのままでも使えるが念のため）
        # ただし、同じ距離でデータが複数あると困るので、ここでは元のDF（時間ソート済み）を使う
        
        min_dist = df['distance'].min()
        max_dist = df['distance'].max()

        if target_distance <= min_dist: return df.iloc[0]['actual_duration']
        if target_distance >= max_dist: return df.iloc[-1]['actual_duration']

        # 距離で挟む位置を探す
        # 注意: DFは duration でソートされているが、物理法則的に distance も昇順のはず
        upper_idx = df[df['distance'] >= target_distance].index[0]
        lower_idx = upper_idx - 1
        
        row_lower = df.iloc[lower_idx]
        row_upper = df.iloc[upper_idx]
        
        d1 = row_lower['distance']
        d2 = row_upper['distance']
        t1 = row_lower['actual_duration']
        t2 = row_upper['actual_duration']
        
        if d2 - d1 == 0: return t1
        ratio = (target_distance - d1) / (d2 - d1)
        
        interpolated_duration = t1 + ratio * (t2 - t1)
        return interpolated_duration

    def _create_motion_plan(self):
        notes_only = sorted([item for item in self.note_items if item.get("class") == "note"], key=lambda x: x['beat'])
        # ログメッセージも少し変更しておくと分かりやすいです
        self.log_message.emit(f"[{self.track_name}] モーションプラン作成 (固定距離=40.0mm, V={FIXED_VELOCITY}, A={FIXED_ACCELERATION})")

        if not notes_only: return []

        motion_plan = []
        seconds_per_beat = 60.0 / self.bpm

        for i, current_note in enumerate(notes_only):
            current_strike_time = current_note.get("beat", 0) * seconds_per_beat

            # --- 1.「振り下ろし (Strike)」動作 ---
            motion_plan.append({
                "target_time": current_strike_time,
                "position": self.safe_strike_pos,
                "velocity": FIXED_VELOCITY,
                "acceleration": FIXED_ACCELERATION,
                "is_compensated": False, 
                "action": "strike"
            })

            # --- 2.「振り上げ (Upstroke)」動作 ---
            
            # --- 以下、可変計算ロジックは不要になるため削除または無視 ---
            # next_note_index = (i + 1) % len(notes_only)
            # ... (中略: 時間計算ロジック) ...
            # target_upstroke_duration = available_time / 2.0
            
            # ★★★ 変更点: 距離を固定値 40.0mm に設定 ★★★
            ideal_backswing_distance = 35.0 
            # ------------------------------------------------
            
            # 安全範囲チェック (Z軸 130mmリミットなどは維持)
            strike_z = self.safe_strike_pos[2]
            max_safe_z = SAFETY_LIMITS['z_max']
            actual_backswing_distance = min(ideal_backswing_distance, max_safe_z - strike_z)
            
            # 振り上げ位置の決定
            backswing_z = strike_z + actual_backswing_distance
            ready_x, ready_y, _, ready_r = self.safe_ready_pos
            backswing_pos = self._clamp_position((ready_x, ready_y, backswing_z, ready_r))
            
            # 振り上げ開始タイミング (Strike直後)
            upstroke_start_time = current_strike_time + 0.01
            
            motion_plan.append({
                "target_time": upstroke_start_time,
                "position": backswing_pos,
                "velocity": FIXED_VELOCITY,
                "acceleration": FIXED_ACCELERATION,
                "is_compensated": True, 
                "action": "upstroke"
            })

        self.log_message.emit(f"[{self.track_name}] プラン作成完了 (全{len(motion_plan)}手)")
        return sorted(motion_plan, key=lambda x: x['target_time'])
    
    def run(self):
        device = None; port = self.config["port"]
        
        # ★ 音のタイミング微調整用 (秒)
        # まだ音が早い場合は、この数字を 0.1, 0.15 と大きくしてください
        SOUND_DELAY_ADJUST_S = 0.32

        try:
            self.log_message.emit(f"--- [{port}] スレッド開始 ---")
            self.safe_ready_pos = self._clamp_position(self.config["ready_pos"])
            self.safe_strike_pos = self._clamp_position(self.config["strike_pos"])
            self.motor_reversal_pause_s = self._get_pause_for_bpm(self.bpm)
            
            self._load_motion_profile(TUNING_DATA_CSV_PATH)
            self.motion_plan = self._create_motion_plan()
            
            if not self.motion_plan:
                self.finished.emit(); return
            
            if not PYDOBOT_AVAILABLE: raise ImportError("pydobotライブラリが見つかりません。")
            device = Dobot(port=port, verbose=False); self.device_list.append(device)
            
            # 初期移動
            device.speed(velocity=200, acceleration=200)
            device.move_to(*self.safe_ready_pos, wait=True)
            self.log_message.emit(f"ロボット [{port}] 準備完了")
            
            loop_count = 0
            current_pos = self.safe_ready_pos
            
            while not self.stop_event.is_set():
                current_loop_start_time = self.master_start_time + (loop_count * self.loop_duration)
                loop_compensation = FIRST_HIT_COMPENSATION_S
                
                for motion in self.motion_plan:
                    if self.stop_event.is_set(): break
                    ideal_time_ms = motion["target_time"] * 1000
                    
                    # コントローラー介入
                    guided_time_ms, log_msg = self.controller.get_guided_timing(self.track_name, ideal_time_ms)
                    if log_msg: self.log_message_from_worker.emit(f"[{self.track_name}] {log_msg}")
                    
                    target_time = current_loop_start_time + (guided_time_ms / 1000.0) - loop_compensation
                    
                    move_duration = 0.0
                    is_compensated = motion.get("is_compensated", False)

                    if is_compensated:
                        # 振り上げ等は補正済み時間として処理
                        send_command_time = target_time - COMMUNICATION_LATENCY_S
                    else:
                        # 振り下ろしは距離から時間を再計算
                        distance = get_distance(current_pos, motion["position"])
                        # 固定V/Aでの所要時間を取得
                        move_duration = self._get_duration_from_distance_linear(distance)
                        send_command_time = target_time - move_duration - COMMUNICATION_LATENCY_S
                    
                    wait_time = send_command_time - time.time()
                    
                    # Pre-motion等の短縮処理
                    if motion['action'] in ['upstroke', 'pre-motion']:
                        wait_time -= 0.05 

                    if wait_time > 0:
                        if wait_time > 0.010: time.sleep(wait_time - 0.005)
                        while time.time() < send_command_time:
                            if self.stop_event.is_set(): break
                            time.sleep(0.0001)
                    
                    if not self.stop_event.is_set():
                        self.command_sent.emit(self.track_name, motion)
                        
                        # --- 音の再生ロジック ---
                        if motion.get('action') == 'strike':
                            # 移動時間 + 通信ラグ + 手動調整値 だけ待ってから鳴らす
                            # これで「打撃の瞬間」に合わせる
                            delay = max(0, move_duration + COMMUNICATION_LATENCY_S + SOUND_DELAY_ADJUST_S)
                            threading.Timer(delay, self.play_hit_sound.emit).start()
                        # -----------------------

                        # 速度設定
                        device.speed(velocity=motion["velocity"], acceleration=motion["acceleration"])
                        
                        # ★★★ 修正: この行が抜けていたため動きませんでした。復活させます！ ★★★
                        device.move_to(*motion["position"], wait=False)
                        # -------------------------------------------------------------------
                        
                        current_pos = motion["position"]

                        if move_duration > 0:
                            est_arr_abs = send_command_time + COMMUNICATION_LATENCY_S + move_duration
                            self.estimated_arrival.emit(self.track_name, est_arr_abs - self.master_start_time, motion["position"][2])
                    
                if self.stop_event.is_set(): break
                loop_count += 1
        
        except Exception as e: self.log_message.emit(f"ロボット [{port}] エラー: {e}")
        finally:
            if device:
                try:
                    if device in self.device_list: self.device_list.remove(device)
                    device.move_to(*(self._clamp_position((230, 0, 60, 0))), wait=True)
                    device.close()
                except: pass
            self.finished.emit()


# ★★★ ここから RobotManager (training_module_v3.py から移動) ★★★
class RobotManager(QObject):
    log_message = pyqtSignal(str)
    command_sent = pyqtSignal(str, dict)
    estimated_arrival = pyqtSignal(str, float, float)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        # ★★★ 修正1: parent (MainWindow) を self.main_window として保存 ★★★
        self.main_window = parent 
        self.threads = []
        self.workers = []
        self.stop_event = threading.Event()
        self.active_devices = []

    def get_first_move_preparation_time(self, score_data):
        try:
            top_score = score_data.get("top", {})
            if not top_score.get("items"): return 0.2
            top_bpm = top_score.get("bpm", 120); top_items = top_score.get("items", [])
            loop_duration_sec = top_score.get("total_beats", 8) * (60.0 / top_bpm)
            
            # ダミーコントローラ
            class DummyController:
                def get_guided_timing(self, _, ideal_time_ms): return ideal_time_ms, None 
            
            stop_event = threading.Event()
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
            
            # 必要な初期化処理を手動実行
            temp_rc.safe_ready_pos = temp_rc._clamp_position(temp_rc.config["ready_pos"])
            temp_rc.safe_strike_pos = temp_rc._clamp_position(temp_rc.config["strike_pos"])
            temp_rc.motor_reversal_pause_s = temp_rc._get_pause_for_bpm(temp_rc.bpm)
            
            # CSV読み込みとプラン作成
            temp_rc._load_motion_profile(TUNING_DATA_CSV_PATH)
            temp_rc.motion_plan = temp_rc._create_motion_plan()
            
            if not temp_rc.motion_plan: return 0.2
            
            ready_pos = temp_rc.safe_ready_pos
            first_motion = temp_rc.motion_plan[0]
            
            if first_motion.get("is_compensated", False):
                move_duration = 0.0 
            else:
                distance = get_distance(ready_pos, first_motion["position"])
                
                # ★★★ 修正2: メソッド名を変更し、引数を distance だけにする ★★★
                # 旧: temp_rc._get_estimated_duration(distance, first_motion["velocity"], first_motion["acceleration"])
                move_duration = temp_rc._get_duration_from_distance_linear(distance)

            return move_duration + FIRST_HIT_COMPENSATION_S + COMMUNICATION_LATENCY_S
            
        except Exception as e:
            print(f"get_first_move_preparation_time でエラー: {e}")
            return 0.2
        
    def start_control(self, score_data, active_controller, master_start_time):
        self.stop_control(); self.stop_event.clear()
        
        self.log_message.emit("🎼 JSONデータ(score_data)受信。楽譜分析とモーションプランニング開始...")
        
        top_score = score_data.get("top", {}); bottom_score = score_data.get("bottom", {})
        top_bpm = top_score.get("bpm", 120); bottom_bpm = bottom_score.get("bpm", 120)
        top_items = top_score.get("items", []); bottom_items = bottom_score.get("items", [])
        
        self.log_message.emit(f"    [top] トラック情報: BPM={top_bpm}, ノート数={len([i for i in top_items if i.get('class') == 'note'])}")
        self.log_message.emit(f"    [bottom] トラック情報: BPM={bottom_bpm}, ノート数={len([i for i in bottom_items if i.get('class') == 'note'])}")
        
        top_beats = top_score.get("total_beats", 8); bottom_beats = bottom_score.get("total_beats", 8)
        top_duration = top_beats * (60.0 / top_bpm); bottom_duration = bottom_beats * (60.0 / bottom_bpm)
        loop_duration_sec = max(top_duration, bottom_duration)
        configs = [(ROBOT1_CONFIG, top_items, top_bpm, 'top'), (ROBOT2_CONFIG, bottom_items, bottom_bpm, 'bottom')]
        
        self.log_message.emit("🤖 各ロボットのコントローラを起動します...") 
        
        for config, items, bpm, track_name in configs:
            thread = QThread()
            worker = RobotController(config, items, bpm, loop_duration_sec, self.stop_event, self.active_devices, track_name, active_controller, master_start_time)
            
            worker.command_sent.connect(self.command_sent.emit)
            worker.estimated_arrival.connect(self.estimated_arrival.emit)
            worker.moveToThread(thread)
            
            worker.log_message.connect(self.log_message.emit) 
            thread.started.connect(worker.run)
            
            # ★★★ 修正3: ドラム音再生シグナルの接続 ★★★
            # self.main_window が None でないかチェックしてから接続
            if self.main_window and hasattr(self.main_window, 'play_robot_drum_sound'):
                worker.play_hit_sound.connect(self.main_window.play_robot_drum_sound)
            else:
                self.log_message.emit("警告: play_robot_drum_sound が見つからないため、ロボット音は再生されません。")

            worker.finished.connect(thread.quit); worker.finished.connect(worker.deleteLater); thread.finished.connect(thread.deleteLater)
            thread.finished.connect(lambda t=thread, w=worker: self._on_thread_finished(t, w)); thread.start()
            self.threads.append(thread); self.workers.append(worker)
            
            if hasattr(worker, 'log_message_from_worker'):
                worker.log_message_from_worker.connect(self.log_message)

    def stop_control(self):
        if not self.threads: return
        self.log_message.emit("🛑 演奏停止中..."); self.stop_event.set()

    def trigger_start(self):
        pass

    def _on_thread_finished(self, thread_obj, worker_obj):
        if thread_obj in self.threads: self.threads.remove(thread_obj)
        if worker_obj in self.workers: self.workers.remove(worker_obj)