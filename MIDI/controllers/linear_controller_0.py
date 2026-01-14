import numpy as np
from .base_controller import BaseEntrainmentController


class LinearController(BaseEntrainmentController):

    @property
    def name(self):
        return "線形補間コントローラー"

    def __init__(self, score_data, ms_per_beat):
        super().__init__(score_data, ms_per_beat)
        self.reset()

        # --- 制御パラメータ ---
        self.ANALYSIS_LOOPS = 3
        self.INTERVENTION_START_LOOP = 5
        self.CORRECTION_RATE = 0.07

        # 🔄 再ループ管理用
        self.loop_offset = 0

    def reset(self):
        self.phase_offset_ms = {'top': 0.0, 'bottom': 0.0}
        self.is_intervention_active = False
        self.loop_offset = 0  # 再ループ時にずらす

    def update_performance_data(self, full_judgement_history):
        # 🔄 ループ番号を「再スタート」に対応させる
        raw_loop = len(full_judgement_history)
        current_loop = raw_loop - self.loop_offset

        log_message = None

        # ---- データ収集 ----
        if current_loop < self.ANALYSIS_LOOPS:
            log_message = f"Loop {current_loop}: Data collection phase..."
            print(f"[Controller] {log_message}")

        # ---- 平均計算 ----
        elif current_loop == self.ANALYSIS_LOOPS:
            all_judgements = [j for loop in full_judgement_history for j in loop]

            for track in ['top', 'bottom']:
                errors = [
                    j['error_ms'] for j in all_judgements
                    if j['pad'] == track and j['error_ms'] is not None
                ]
                if errors:
                    self.phase_offset_ms[track] = np.mean(errors)

            log_message = (
                f"Analysis complete. Initial offset set: "
                f"L={self.phase_offset_ms['top']:.1f}ms, "
                f"R={self.phase_offset_ms['bottom']:.1f}ms"
            )
            print(f"[Controller] {log_message}")

        # ---- 介入 ----
        elif current_loop >= self.INTERVENTION_START_LOOP:
            self.is_intervention_active = True

            # 補正適用
            self.phase_offset_ms['top'] *= (1.0 - self.CORRECTION_RATE)
            self.phase_offset_ms['bottom'] *= (1.0 - self.CORRECTION_RATE)

            log_message = (
                f"Loop {current_loop}: Intervention active. "
                f"Reducing offset by {self.CORRECTION_RATE*100:.0f}%. "
                f"Current offset: L={self.phase_offset_ms['top']:.2f}ms, "
                f"R={self.phase_offset_ms['bottom']:.2f}ms"
            )
            print(f"[Controller] {log_message}")

            # --- 🔄 NEW: ほぼ0 になったらリセットして再計測へ ---
            if (
                abs(self.phase_offset_ms['top']) < 0.1 and
                abs(self.phase_offset_ms['bottom']) < 0.1
            ):
                print("[Controller] Offset almost zero. Restarting analysis loop.")
                self.is_intervention_active = False
                self.phase_offset_ms = {'top': 0.0, 'bottom': 0.0}

                # 今のループ番号を保存し、そこから再スタート
                self.loop_offset = raw_loop
                log_message = "Offset converged. Restarting analysis phase."

        return log_message

    def get_guided_timing(self, track_name, ideal_note_time_ms):
        log_message = None
        offset = self.phase_offset_ms.get(track_name, 0.0)

        if self.is_intervention_active and abs(offset) > 0.1:
            guided_time = ideal_note_time_ms + offset
            log_message = (
                f"Intervention: Ideal {ideal_note_time_ms:.0f}ms. "
                f"Applying offset {offset:+.1f}ms. "
                f"New time: {guided_time:.0f}ms"
            )
            return guided_time, log_message

        return ideal_note_time_ms, log_message
