import json
import math
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.collections import LineCollection
import numpy as np

# --- パラメータ（元のコードと同じ） ---
MIN_EXPECTED_INTERVAL_S = 0.1
MAX_EXPECTED_INTERVAL_S = 2.0
MIN_VELOCITY = 100.0
MAX_VELOCITY = 400.0
MIN_ACCELERATION = 100.0
MAX_ACCELERATION = 800.0
MAX_BACKSWING_HEIGHT = 70.0
MIN_BACKSWING_HEIGHT = 32.0
EXPRESSION_EXPONENT = 0.75
COMMUNICATION_LATENCY_S = 0.050

def generate_motion_plan(note_items, bpm, loop_duration):
    """モーションプランを生成（元のコードのロジックを再現）"""
    notes_only = sorted([item for item in note_items if item.get("class") == "note"], 
                       key=lambda x: x['beat'])
    
    if not notes_only:
        return []
    
    motion_plan = []
    seconds_per_beat = 60.0 / bpm
    
    for i, current_note in enumerate(notes_only):
        current_strike_time = current_note.get("beat", 0) * seconds_per_beat
        next_note = notes_only[(i + 1) % len(notes_only)]
        next_strike_time = next_note.get("beat", 0) * seconds_per_beat
        
        if i == len(notes_only) - 1:
            interval = (loop_duration - current_strike_time) + next_strike_time
        else:
            interval = next_strike_time - current_strike_time
        
        if interval <= 0.02:
            continue
        
        # 表現力パラメータの計算
        normalized_interval = max(0.0, min(1.0, 
            (interval - MIN_EXPECTED_INTERVAL_S) / (MAX_EXPECTED_INTERVAL_S - MIN_EXPECTED_INTERVAL_S)))
        eased_ratio = normalized_interval ** EXPRESSION_EXPONENT
        
        backswing_z = MIN_BACKSWING_HEIGHT + (MAX_BACKSWING_HEIGHT - MIN_BACKSWING_HEIGHT) * eased_ratio
        velocity = MIN_VELOCITY + (MAX_VELOCITY - MIN_VELOCITY) * (1.0 - eased_ratio)
        acceleration = MIN_ACCELERATION + (MAX_ACCELERATION - MIN_ACCELERATION) * (1.0 - eased_ratio)
        
        # Strike動作
        strike_motion = {
            "target_time": current_strike_time,
            "position_z": 22.0,
            "velocity": MAX_VELOCITY,
            "acceleration": MAX_ACCELERATION,
            "action": "strike",
            "send_time": current_strike_time - 0.1 - COMMUNICATION_LATENCY_S
        }
        motion_plan.append(strike_motion)
        
        # Upstroke動作
        upstroke_start_time = current_strike_time + 0.01
        upstroke_motion = {
            "target_time": upstroke_start_time,
            "position_z": backswing_z,
            "velocity": velocity,
            "acceleration": acceleration,
            "action": "upstroke",
            "send_time": upstroke_start_time - COMMUNICATION_LATENCY_S
        }
        motion_plan.append(upstroke_motion)
    
    return sorted(motion_plan, key=lambda x: x['target_time'])

def plot_motion_plan(score_data, output_file='motion_plan.png', dpi=150):
    """モーションプランを可視化してグラフとして出力"""
    
    # データ処理
    top_score = score_data.get("top", {})
    bottom_score = score_data.get("bottom", {})
    
    tracks = []
    if top_score and top_score.get("items"):
        top_bpm = top_score.get("bpm", 120)
        top_items = top_score.get("items", [])
        top_beats = top_score.get("total_beats", 8)
        top_duration = top_beats * (60.0 / top_bpm)
        top_notes = sorted([item for item in top_items if item.get("class") == "note"], 
                          key=lambda x: x['beat'])
        top_motion = generate_motion_plan(top_items, top_bpm, top_duration)
        tracks.append({
            'name': 'Top (Robot 1)',
            'notes': top_notes,
            'motion': top_motion,
            'duration': top_duration,
            'bpm': top_bpm,
            'color': '#a855f7'
        })
    
    if bottom_score and bottom_score.get("items"):
        bottom_bpm = bottom_score.get("bpm", 120)
        bottom_items = bottom_score.get("items", [])
        bottom_beats = bottom_score.get("total_beats", 8)
        bottom_duration = bottom_beats * (60.0 / bottom_bpm)
        bottom_notes = sorted([item for item in bottom_items if item.get("class") == "note"], 
                             key=lambda x: x['beat'])
        bottom_motion = generate_motion_plan(bottom_items, bottom_bpm, bottom_duration)
        tracks.append({
            'name': 'Bottom (Robot 2)',
            'notes': bottom_notes,
            'motion': bottom_motion,
            'duration': bottom_duration,
            'bpm': bottom_bpm,
            'color': '#3b82f6'
        })
    
    if not tracks:
        print("エラー: 有効なトラックデータがありません")
        return
    
    max_duration = max(track['duration'] for track in tracks)
    
    # プロット設定
    fig = plt.figure(figsize=(16, 4 * len(tracks) + 2))
    fig.patch.set_facecolor('#1f2937')
    
    # 各トラックごとにサブプロット
    for idx, track in enumerate(tracks):
        # タイムライン
        ax1 = plt.subplot(len(tracks), 2, idx * 2 + 1)
        ax1.set_facecolor('#374151')
        ax1.set_xlim(0, max_duration)
        ax1.set_ylim(-1, 4)
        ax1.set_xlabel('Time (s)', color='white', fontsize=10)
        ax1.set_title(f'{track["name"]} - Timeline (BPM: {track["bpm"]})', 
                     color='white', fontsize=12, fontweight='bold')
        ax1.tick_params(colors='white')
        ax1.spines['bottom'].set_color('white')
        ax1.spines['top'].set_color('white')
        ax1.spines['left'].set_color('white')
        ax1.spines['right'].set_color('white')
        ax1.set_yticks([])
        
        # グリッド線
        for t in np.arange(0, max_duration + 1, 1.0):
            ax1.axvline(t, color='#4b5563', linewidth=0.5, alpha=0.5)
        
        # 音符
        seconds_per_beat = 60.0 / track['bpm']
        note_times = [note['beat'] * seconds_per_beat for note in track['notes']]
        ax1.scatter(note_times, [3] * len(note_times), 
                   color=track['color'], s=100, alpha=0.6, 
                   label='Note', zorder=3, marker='o')
        
        # モーション（Strike）
        strike_send = [m['send_time'] for m in track['motion'] if m['action'] == 'strike']
        strike_target = [m['target_time'] for m in track['motion'] if m['action'] == 'strike']
        ax1.scatter(strike_send, [2] * len(strike_send), 
                   color='#ef4444', s=30, alpha=0.4, marker='|', zorder=2)
        ax1.scatter(strike_target, [2] * len(strike_target), 
                   color='#ef4444', s=100, alpha=0.8, marker='v', label='Strike', zorder=3)
        
        # 送信→到達の矢印
        for send, target in zip(strike_send, strike_target):
            ax1.plot([send, target], [2, 2], color='#ef4444', 
                    alpha=0.3, linewidth=1, zorder=1)
        
        # モーション（Upstroke）
        upstroke_send = [m['send_time'] for m in track['motion'] if m['action'] == 'upstroke']
        upstroke_target = [m['target_time'] for m in track['motion'] if m['action'] == 'upstroke']
        ax1.scatter(upstroke_send, [1] * len(upstroke_send), 
                   color='#3b82f6', s=30, alpha=0.4, marker='|', zorder=2)
        ax1.scatter(upstroke_target, [1] * len(upstroke_target), 
                   color='#3b82f6', s=100, alpha=0.8, marker='^', label='Upstroke', zorder=3)
        
        for send, target in zip(upstroke_send, upstroke_target):
            ax1.plot([send, target], [1, 1], color='#3b82f6', 
                    alpha=0.3, linewidth=1, zorder=1)
        
        ax1.legend(loc='upper right', facecolor='#374151', 
                  edgecolor='white', framealpha=0.9, fontsize=8)
        
        # Z軸高さグラフ
        ax2 = plt.subplot(len(tracks), 2, idx * 2 + 2)
        ax2.set_facecolor('#374151')
        ax2.set_xlim(0, max_duration)
        ax2.set_ylim(0, 90)
        ax2.set_xlabel('Time (s)', color='white', fontsize=10)
        ax2.set_ylabel('Z-axis Height (mm)', color='white', fontsize=10)
        ax2.set_title(f'{track["name"]} - Z-axis Motion', 
                     color='white', fontsize=12, fontweight='bold')
        ax2.tick_params(colors='white')
        ax2.spines['bottom'].set_color('white')
        ax2.spines['top'].set_color('white')
        ax2.spines['left'].set_color('white')
        ax2.spines['right'].set_color('white')
        ax2.grid(True, color='#4b5563', alpha=0.3, linewidth=0.5)
        
        # Z軸の動き
        motion_times = [m['target_time'] for m in track['motion']]
        motion_z = [m['position_z'] for m in track['motion']]
        
        # 線とエリアプロット
        ax2.plot(motion_times, motion_z, color=track['color'], 
                linewidth=2, alpha=0.9, zorder=2)
        ax2.fill_between(motion_times, 0, motion_z, 
                        color=track['color'], alpha=0.2, zorder=1)
        
        # Strike と Upstroke のマーカー
        strike_times = [m['target_time'] for m in track['motion'] if m['action'] == 'strike']
        strike_z = [m['position_z'] for m in track['motion'] if m['action'] == 'strike']
        upstroke_times = [m['target_time'] for m in track['motion'] if m['action'] == 'upstroke']
        upstroke_z = [m['position_z'] for m in track['motion'] if m['action'] == 'upstroke']
        
        ax2.scatter(strike_times, strike_z, color='#ef4444', 
                   s=60, alpha=0.8, marker='v', label='Strike', zorder=3)
        ax2.scatter(upstroke_times, upstroke_z, color='#3b82f6', 
                   s=60, alpha=0.8, marker='^', label='Upstroke', zorder=3)
        
        ax2.legend(loc='upper right', facecolor='#374151', 
                  edgecolor='white', framealpha=0.9, fontsize=8)
    
    plt.tight_layout()
    plt.savefig(output_file, dpi=dpi, facecolor='#1f2937')
    print(f"グラフを保存しました: {output_file}")
    plt.show()

# 使用例
if __name__ == "__main__":
    # デモデータ
    demo_data = {
        "top": {
            "bpm": 120,
            "total_beats": 8,
            "items": [
                {"class": "note", "beat": 0},
                {"class": "note", "beat": 1},
                {"class": "note", "beat": 2},
                {"class": "note", "beat": 3},
                {"class": "note", "beat": 4},
                {"class": "note", "beat": 5},
                {"class": "note", "beat": 6},
                {"class": "note", "beat": 7}
            ]
        },
        "bottom": {
            "bpm": 120,
            "total_beats": 8,
            "items": [
                {"class": "note", "beat": 0.5},
                {"class": "note", "beat": 1.5},
                {"class": "note", "beat": 2.5},
                {"class": "note", "beat": 3.5},
                {"class": "note", "beat": 4.5},
                {"class": "note", "beat": 5.5},
                {"class": "note", "beat": 6.5},
                {"class": "note", "beat": 7.5}
            ]
        }
    }
    
    # JSONファイルから読み込む場合
    # with open('score_data.json', 'r', encoding='utf-8') as f:
    #     score_data = json.load(f)
    # plot_motion_plan(score_data, 'my_motion_plan.png')
    
    # デモデータで実行
    plot_motion_plan(demo_data, 'motion_plan_demo.png')