import numpy as np
import datetime
from .base_controller import BaseEntrainmentController

class LinearController(BaseEntrainmentController):
    """
    常に最新の学習者のズレを計測し、その位置から一定割合だけ
    「理想（ズレ0）」に近づけた位置を提示し続けるコントローラー。
    """
    @property
    def name(self):
        return "線形補間コントローラー"

    def __init__(self, score_data, ms_per_beat):
        super().__init__(score_data, ms_per_beat)
        self.reset()
        # --- 制御パラメータ ---
        self.ANALYSIS_LOOPS = 2      # 最初の1ループだけ様子見
        self.CORRECTION_RATE = 0.10  # ユーザーのズレの10%分だけ理想に寄せた位置で弾く
                                     # (0.10 は「優しく誘導」、0.50だと「強く矯正」)

    def reset(self):
        """状態をリセット"""
        self.phase_offset_ms = {'top': 0.0, 'bottom': 0.0}
        self.is_intervention_active = False

        self.guided_history = []

    def update_performance_data(self, full_judgement_history):
        """
        毎ループ実行され、常に最新の演奏データに基づいてオフセットを更新する。
        """
        current_loop = len(full_judgement_history)
        log_message = None

        # データ収集フェーズ
        if current_loop < self.ANALYSIS_LOOPS:
            log_message = f"Loop {current_loop}: Initial data collection..."
            return log_message

        # 最新のループ（直前の演奏）データを取得
        latest_loop_data = full_judgement_history[-1] 
        
        self.is_intervention_active = True
        
        status_texts = []
        
        for track in ['top', 'bottom']:
            # そのトラックの、最新ループにおける誤差データを抽出
            errors = [j['error_ms'] for j in latest_loop_data if j['pad'] == track and j['error_ms'] is not None]
            
            if errors:
                # 1. ユーザーの現在の平均的なズレを計算
                current_avg_error = np.mean(errors)
                
                # 2. ロボットの次のオフセットを決定
                #    「ユーザーの現在地」から「理想(0)」に向かって CORRECTION_RATE 分だけ進んだ位置
                new_offset = current_avg_error * (1.0 - self.CORRECTION_RATE)
                
                # 3. オフセットを更新
                self.phase_offset_ms[track] = new_offset
                
                status_texts.append(f"{track}: User={current_avg_error:+.0f}ms -> Robot={new_offset:+.0f}ms")
            else:
                # 打鍵がなかった場合は、前回のオフセットを少し減衰させて維持
                self.phase_offset_ms[track] *= 0.95
        
        # ループごとのサマリーログ
        status_str = ", ".join(status_texts) if status_texts else "No input"
        log_message = f"Loop {current_loop}: {status_str} (Rate: {self.CORRECTION_RATE*100:.0f}%)"
        print(f"[Controller] {log_message}")

        return log_message

    def get_guided_timing(self, track_name, ideal_note_time_ms):
        """
        個別の音符のタイミングを決定するメソッド。
        詳細なログを出力するように修正済み。
        """
        log_message = None
        offset = self.phase_offset_ms.get(track_name, 0.0)

        # 介入がアクティブで、かつ0.1ms以上のオフセットがある場合
        if abs(offset) > 0.1:
            # 理想のタイミングに現在のオフセットを加算
            guided_time = ideal_note_time_ms + offset
            
            # ★★★ 修正箇所: 音符ごとの詳細ログを出力 ★★★
            log_message = (
                f"[{track_name}] "
                f"Ideal: {ideal_note_time_ms:.0f}ms "
                f"+ Offset: {offset:+.1f}ms "
                f"-> Guided: {guided_time:.0f}ms"
            )
            
            self.guided_history.append({
            'timestamp': datetime.datetime.now().strftime("%H:%M:%S.%f")[:-3], # ミリ秒まで
            'track': track_name,
            'ideal': ideal_note_time_ms,
            'offset': offset,
            'guided': guided_time,
            'is_intervention': abs(offset) > 0.1
        })
            return guided_time, log_message
        
        # オフセットがない場合（介入なし）
        return ideal_note_time_ms, log_message