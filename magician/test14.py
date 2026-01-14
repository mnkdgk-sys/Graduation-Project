import pydobot
from pydobot import Dobot
import time
import json
import threading
import signal
import sys

# --- ロボットごとの設定 ---
ROBOT1_CONFIG = {
    "port": "COM3",
    "ready_pos": (279, -25, 50, 0),
    "tap_pos": (264, -23, 11, 0),
    "short_ready_pos": (270, -24, 20, 0)
}
ROBOT2_CONFIG = {
    "port": "COM4",
    "ready_pos": (279, -25, 50, 0),
    "tap_pos": (264, -23, 11, 0),
    "short_ready_pos": (270, -24, 20, 0)
}
QUICK_TAP_THRESHOLD = 0.6

# --- グローバル変数 ---
stop_threads = False
active_devices = []
master_start_time = None  # ★追加: マスター開始時刻
loop_duration_seconds = None  # ★追加: ループ長（秒）

def signal_handler(sig, frame):
    """シグナルハンドラ（Ctrl+C対応）"""
    global stop_threads
    print("\nCtrl+Cを検知しました。全てのロボットを停止します...")
    stop_threads = True
    
    for device in active_devices:
        try:
            if device:
                device.move_to(250, 0, 80, 0, wait=False)
        except:
            pass
    
    time.sleep(2)
    sys.exit(0)

def robot_controller(config, note_items, bpm):
    """1台のロボットの演奏を制御する関数（スレッドとして実行される）"""
    global active_devices, master_start_time, loop_duration_seconds
    device = None
    try:
        port = config["port"]
        ready_pos = config["ready_pos"]
        tap_pos = config["tap_pos"]
        short_ready_pos = config["short_ready_pos"]
        seconds_per_beat = 60.0 / bpm
        velocity, acceleration = 1000, 1000

        device = Dobot(port=port, verbose=False)
        active_devices.append(device)
        print(f"[{port}] 接続しました。")
        device.speed(velocity, acceleration)
        device.move_to(*ready_pos, wait=True)
        print(f"[{port}] 準備完了。")
        
        # ★重要: マスター開始時刻が設定されるまで待機
        while master_start_time is None:
            if stop_threads:
                return
            time.sleep(0.01)
        
        loop_count = 0
        
        while not stop_threads:
            print(f"[{port}] ループ {loop_count + 1} 開始")
            
            # ★重要: 全ロボット共通のマスタータイミングを使用
            current_loop_start_time = master_start_time + (loop_count * loop_duration_seconds)

            for i, current_note in enumerate(note_items):
                if stop_threads: 
                    break
                
                target_beat = current_note.get("beat", 0)
                # ★重要: マスター時刻からの絶対時刻で計算
                target_time = current_loop_start_time + (target_beat * seconds_per_beat)

                # 指定時刻まで待機
                while time.time() < target_time:
                    if stop_threads: 
                        break
                    time.sleep(0.01)
                
                if stop_threads: 
                    break
                
                # 次の音符までの時間を計算してクイックタップ判定
                is_quick_tap = False
                if i + 1 < len(note_items):
                    next_note = note_items[i+1]
                    time_to_next = (next_note.get("beat", 0) - target_beat) * seconds_per_beat
                    if time_to_next < QUICK_TAP_THRESHOLD:
                        is_quick_tap = True
                
                return_pos = short_ready_pos if is_quick_tap else ready_pos
                
                if not stop_threads:
                    device.move_to(*tap_pos, wait=False)
                if not stop_threads:
                    device.move_to(*return_pos, wait=False)

            if stop_threads: 
                break
                
            loop_count += 1

    except Exception as e:
        print(f"[{config.get('port', 'Unknown')}] でエラーが発生しました: {e}")
    finally:
        if device:
            try:
                if device in active_devices:
                    active_devices.remove(device)
                device.move_to(250, 0, 80, 0, wait=True)
            except: 
                pass
            try:
                device.close()
            except:
                pass
            print(f"[{config.get('port', 'Unknown')}] 接続を解除しました。")

def main():
    global stop_threads, master_start_time, loop_duration_seconds
    
    signal.signal(signal.SIGINT, signal_handler)
    
    threads = []
    try:
        filename_part = input(f"ファイル名を入力してください（拡張子なし）：")
        score_file = f"C:/卒研/MIDI/{filename_part}.json"
        print(f"読み込むファイル: {score_file}")
        with open(score_file, 'r', encoding='utf-8') as f:
            score_data = json.load(f)

        top_score = score_data.get("top")
        bottom_score = score_data.get("bottom")
        if not top_score or not bottom_score:
            print("エラー: topまたはbottomの楽譜情報が見つかりません。")
            return
        
        bpm = top_score.get("bpm", 120)
        top_notes = [item for item in top_score.get("items", []) if item.get("class") == "note"]
        bottom_notes = [item for item in bottom_score.get("items", []) if item.get("class") == "note"]
        if not top_notes or not bottom_notes:
            print("エラー: topまたはbottomの楽譜に音符がありません。")
            return

        # ★重要: ループ長を事前に計算
        top_total_beats = top_score.get("total_beats", 0)
        bottom_total_beats = bottom_score.get("total_beats", 0)
        
        # より安全な方法でループ長を決定
        if top_total_beats > 0 and bottom_total_beats > 0:
            master_loop_beats = max(top_total_beats, bottom_total_beats)
        else:
            # total_beatsが無い場合は最後の音符から推定
            top_last_beat = max([note.get("beat", 0) for note in top_notes]) if top_notes else 0
            bottom_last_beat = max([note.get("beat", 0) for note in bottom_notes]) if bottom_notes else 0
            master_loop_beats = max(top_last_beat, bottom_last_beat) + 1
        
        loop_duration_seconds = master_loop_beats * (60.0 / bpm)
        print(f"ループ長: {master_loop_beats}拍 ({loop_duration_seconds:.2f}秒)")

        # スレッドを作成して開始
        thread1 = threading.Thread(target=robot_controller, args=(ROBOT1_CONFIG, top_notes, bpm))
        thread2 = threading.Thread(target=robot_controller, args=(ROBOT2_CONFIG, bottom_notes, bpm))
        threads = [thread1, thread2]
        
        for t in threads:
            t.daemon = True
            t.start()
        
        # 両方のロボットが準備完了するまで少し待機
        print("ロボットの準備完了を待っています...")
        time.sleep(2)
        
        # ★重要: マスター開始時刻を設定（全ロボット同期開始）
        print("3秒後に演奏開始...")
        time.sleep(3)
        master_start_time = time.time()
        print("演奏開始！停止するには Ctrl+C を押してください。")
        
        try:
            while any(t.is_alive() for t in threads) and not stop_threads:
                time.sleep(0.1)
        except KeyboardInterrupt:
            signal_handler(signal.SIGINT, None)

    except FileNotFoundError:
        print(f"エラー: ファイル '{score_file}' が見つかりませんでした。")
    except KeyboardInterrupt:
        signal_handler(signal.SIGINT, None)
    except Exception as e:
        print(f"メイン処理でエラーが発生しました: {e}")
    finally:
        stop_threads = True
        print("スレッドの終了を待っています...")
        
        for t in threads:
            if t.is_alive():
                t.join(timeout=2.0)
        
        print("全ての動作が終了しました。")

if __name__ == "__main__":
    main()