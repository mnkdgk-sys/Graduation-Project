#ベストコード
import sys
import os
import json
import time
import copy
import threading
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QPushButton, QWidget, QLabel, QVBoxLayout, QHBoxLayout,
    QFileDialog, QMessageBox, QDialog, QDialogButtonBox, QSlider, QCheckBox, QComboBox, QFormLayout
)
from PyQt6.QtCore import Qt, QTimer, QRectF, QPointF, QObject, pyqtSignal, QThread
from PyQt6.QtGui import (QPainter, QColor, QFont, QIcon, QPen, QPixmap, QLinearGradient, QCursor, QFontDatabase, QPolygonF)

import mido
import pygame

# OpenAIライブラリをインポート
try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

# numpyライブラリをインポートしようと試みる
try:
    import numpy as np
    NUMPY_AVAILABLE = True
except ImportError:
    NUMPY_AVAILABLE = False

# --- モダンUIのカラーテーマ ---
COLORS = {
    'background': QColor(245, 245, 245),
    'surface': QColor(255, 255, 255),
    'primary': QColor(0, 123, 255),
    'success': QColor(40, 167, 69),
    'danger': QColor(220, 53, 69),
    'warning': QColor(255, 193, 7),
    'note_glow': QColor(0, 123, 255, 100),
    'rest_bg': QColor(230, 230, 230, 200),
    'staff_line': QColor(50, 50, 50),
    'cursor': QColor(255, 0, 100),
    'text_primary': QColor(33, 37, 41),
    'text_secondary': QColor(108, 117, 125),
    'text_muted': QColor(170, 170, 170),
    'border': QColor(221, 221, 221),
    'perfect': QColor(255, 193, 7),
    'great': QColor(40, 167, 69),
    'good': QColor(0, 123, 255),
    'miss': QColor(108, 117, 125),
    'extra': QColor(220, 53, 69),
}

# --- 設定定数 ---
PAD_MAPPING = {'left': [47, 56], 'right': [48, 29]}
VELOCITY_THRESHOLD = 30
LIT_DURATION = 150
NUM_MEASURES = 2

# --- 判定ロジック定数 ---
JUDGEMENT_WINDOWS = {
    'perfect': 30, 'great': 60, 'good': 100,
}
DROPPED_THRESHOLD = 120

# --- 音符/休符データ ---
NOTE_DURATIONS = {
    'whole': {'duration': 4.0, 'name': "全音符"}, 'half': {'duration': 2.0, 'name': "2分音符"},
    'quarter': {'duration': 1.0, 'name': "4分音符"}, 'eighth': {'duration': 0.5, 'name': "8分音符"},
    'sixteenth': {'duration': 0.25, 'name': "16分音符"},
}
REST_DURATIONS = {
    'quarter_rest': {'duration': 1.0, 'name': "4分休符"}, 'eighth_rest': {'duration': 0.5, 'name': "8分休符"},
    'sixteenth_rest': {'duration': 0.25, 'name': "16分休符"},
}
ALL_DURATIONS = {**NOTE_DURATIONS, **REST_DURATIONS}
NOTE_IMAGE_FILES = {
    'whole': 'images/whole_note.PNG', 'half': 'images/half_note.PNG', 'quarter': 'images/quarter_note.PNG',
    'eighth': 'images/eighth_note.PNG', 'sixteenth':'images/sixteenth_note.PNG',
}
REST_IMAGE_FILES = {
    'quarter_rest': 'images/quarter_rest.PNG', 'eighth_rest': 'images/eighth_rest.PNG', 'sixteenth_rest': 'images/sixteenth_rest.PNG',
}


def resource_path(relative_path):
    try: base_path = sys._MEIPASS
    except Exception: base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_path, relative_path)

# --- モダンUIコンポーネントクラス ---
class ModernButton(QPushButton):
    def __init__(self, text, button_type="primary", parent=None):
        super().__init__(text, parent)
        color_map = {
            "primary": (COLORS['primary'], COLORS['primary'].darker(120)),
            "success": (COLORS['success'], COLORS['success'].darker(120)),
            "danger": (COLORS['danger'], COLORS['danger'].darker(120)),
            "warning": (COLORS['warning'], COLORS['warning'].darker(120)),
        }
        bg_color, hover_color = color_map.get(button_type, (COLORS['primary'], COLORS['primary'].darker(120)))
        self.setMinimumHeight(36)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFont(QFont("SansSerif", 10, QFont.Weight.Bold))
        self.setStyleSheet(f"""
            QPushButton {{ background-color: {bg_color.name()}; color: white; border: none; border-radius: 6px; padding: 8px 16px; }}
            QPushButton:hover {{ background-color: {hover_color.name()}; }}
            QPushButton:pressed {{ background-color: {bg_color.darker(140).name()}; }}
            QPushButton:disabled {{ background-color: {COLORS['text_muted'].name()}; }}
        """)

class ModernLabel(QLabel):
    def __init__(self, text, font_size=10, weight=QFont.Weight.Normal, color_key='text_secondary', parent=None):
        super().__init__(text, parent)
        self.setFont(QFont("SansSerif", font_size, weight))
        self.setStyleSheet(f"color: {COLORS[color_key].name()}; background: transparent;")


# --- AIフィードバック生成を別スレッドで行うためのWorkerクラス ---
class AiFeedbackWorker(QObject):
    finished = pyqtSignal(str)
    def __init__(self, main_window_ref):
        super().__init__()
        self.main_window = main_window_ref
    def run(self):
        feedback = self.main_window.generate_ai_feedback_logic()
        self.finished.emit(feedback)


# --- 設定ダイアログクラス ---
class SettingsDialog(QDialog):
    def __init__(self, current_settings, parent=None):
        super().__init__(parent)
        self.setWindowTitle("練習設定")
        self.setMinimumWidth(350)

        self.settings = current_settings.copy()

        # --- ウィジェットの作成 ---
        self.drum_volume_slider = QSlider(Qt.Orientation.Horizontal)
        self.drum_volume_slider.setRange(0, 100)
        self.drum_volume_slider.setValue(int(self.settings['drum_volume'] * 100))

        self.metronome_volume_slider = QSlider(Qt.Orientation.Horizontal)
        self.metronome_volume_slider.setRange(0, 100)
        self.metronome_volume_slider.setValue(int(self.settings['metronome_volume'] * 100))

        self.metronome_toggle_button = QPushButton()
        self.metronome_toggle_button.setMinimumHeight(32)
        self.metronome_toggle_button.clicked.connect(self.toggle_metronome)

        self.guide_volume_slider = QSlider(Qt.Orientation.Horizontal)
        self.guide_volume_slider.setRange(0, 100)
        self.guide_volume_slider.setValue(int(self.settings['guide_cue_volume'] * 100))

        self.guide_toggle_button = QPushButton()
        self.guide_toggle_button.setMinimumHeight(32)
        self.guide_toggle_button.clicked.connect(self.toggle_guide)
        
        self.update_metronome_button_style()
        self.update_guide_button_style()


        self.level_combo = QComboBox()
        self.levels = {
            "p100": "PERFECT 100%",
            "p50_g100": "PERFECT 50%以上 & GREAT含め100%",
            "g100": "GREAT以上 100%"
        }
        for key, text in self.levels.items():
            self.level_combo.addItem(text, userData=key)
        
        current_level_key = self.settings.get('practice_level', 'p100')
        if current_level_key in self.levels:
            self.level_combo.setCurrentIndex(list(self.levels.keys()).index(current_level_key))

        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)

        # --- レイアウトの構築 ---
        form_layout = QFormLayout()
        form_layout.addRow("ドラム音量:", self.drum_volume_slider)
        form_layout.addRow("メトロノーム音量:", self.metronome_volume_slider)
        form_layout.addRow("ガイド音音量:", self.guide_volume_slider)
        form_layout.addRow("PERFECT練習レベル:", self.level_combo)

        main_layout = QVBoxLayout(self)
        main_layout.addLayout(form_layout)
        main_layout.addWidget(self.metronome_toggle_button)
        main_layout.addWidget(self.guide_toggle_button)
        main_layout.addStretch()
        main_layout.addWidget(self.button_box)

    def toggle_metronome(self):
        self.settings['metronome_on'] = not self.settings.get('metronome_on', False)
        self.update_metronome_button_style()

    def update_metronome_button_style(self):
        font = QFont("SansSerif", 10, QFont.Weight.Bold)
        self.metronome_toggle_button.setFont(font)
        if self.settings.get('metronome_on', False):
            self.metronome_toggle_button.setText("メトロノーム : ON")
            self.metronome_toggle_button.setStyleSheet(f"""
                background-color: {COLORS['success'].name()}; color: white; border: 1px solid {COLORS['success'].darker(110).name()}; border-radius: 6px;
            """)
        else:
            self.metronome_toggle_button.setText("メトロノーム : OFF")
            self.metronome_toggle_button.setStyleSheet(f"""
                background-color: {COLORS['text_muted'].name()}; color: white; border: 1px solid {COLORS['text_muted'].darker(110).name()}; border-radius: 6px;
            """)

    def toggle_guide(self):
        self.settings['guide_cue_on'] = not self.settings.get('guide_cue_on', False)
        self.update_guide_button_style()
        
    def update_guide_button_style(self):
        font = QFont("SansSerif", 10, QFont.Weight.Bold)
        self.guide_toggle_button.setFont(font)
        if self.settings.get('guide_cue_on', False):
            self.guide_toggle_button.setText("ガイド音 (練習中) : ON")
            self.guide_toggle_button.setStyleSheet(f"""
                background-color: {COLORS['success'].name()}; color: white; border: 1px solid {COLORS['success'].darker(110).name()}; border-radius: 6px;
            """)
        else:
            self.guide_toggle_button.setText("ガイド音 (練習中) : OFF")
            self.guide_toggle_button.setStyleSheet(f"""
                background-color: {COLORS['text_muted'].name()}; color: white; border: 1px solid {COLORS['text_muted'].darker(110).name()}; border-radius: 6px;
            """)

    def accept(self):
        self.settings['drum_volume'] = self.drum_volume_slider.value() / 100.0
        self.settings['metronome_volume'] = self.metronome_volume_slider.value() / 100.0
        self.settings['guide_cue_volume'] = self.guide_volume_slider.value() / 100.0
        self.settings['practice_level'] = self.level_combo.currentData()
        super().accept()

    @staticmethod
    def get_settings(parent, current_settings):
        dialog = SettingsDialog(current_settings, parent)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            return dialog.settings
        return None

# -----------------------------------------------------------------------------
# --- アナライザーのメインウィンドウ ---
# -----------------------------------------------------------------------------
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("ドラムリズムアナライザー")
        self.setFixedSize(1280, 670)
        self.setStyleSheet(f"background-color: {COLORS['background'].name()};")
        
        self.settings = {
            'drum_volume': 0.8, 'metronome_volume': 0.3, 'metronome_on': True,
            'guide_cue_volume': 0.5, 'guide_cue_on': False, 'practice_level': 'p100',
        }
        
        self.state = "waiting"
        self.recorded_hits = []
        self.template_score = None
        self.editor_window = None
        self.start_time = 0
        self.countdown_start_time = 0
        self.countdown_text = ""
        self.countdown_beat_duration = 0
        self.countdown_beat_count = 0
        self.judgements = []
        self.ai_feedback_text = ""
        self.result_stats = {}
        self.total_notes = 0
        self.judged_notes = set()
        self.thread = None
        self.worker = None
        self.practice_loop_count = 0
        self.is_perfect_mode = False
        self.perfect_practice_history = []
        self.judgement_history = []
        self.note_sound = None
        self.metronome_click = None
        self.metronome_accent_click = None
        self.countdown_sound = None
        self.snare_sound = None
        self.tom_sound = None
        self.init_sounds()
        self.item_images = {}
        self.init_images()
        self.init_ui()
        self.init_midi()
        self.q_timer = QTimer(self)
        self.q_timer.timeout.connect(self.update_loop)
        self.q_timer.start(16)

    def init_ui(self):
        main_widget = QWidget()
        main_layout = QVBoxLayout(main_widget)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(15)
        self.setCentralWidget(main_widget)
        
        self.canvas = AnalyzerCanvas(self)
        self.label_template_file = ModernLabel("お手本ファイルが読み込まれていません", 9, color_key='text_muted')
        self.label_template_file.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.label_info = ModernLabel("", 9, color_key='text_primary')
        self.label_info.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        main_layout.addWidget(self.canvas)
        main_layout.addWidget(self.label_template_file)
        main_layout.addWidget(self.label_info)

        control_panel = QWidget()
        control_layout = QHBoxLayout(control_panel)
        control_layout.setContentsMargins(0, 0, 0, 0)
        
        self.btn_load_template = ModernButton("お手本を選択", "primary")
        self.btn_load_template.clicked.connect(self.load_template_file)
        self.btn_demo = ModernButton("お手本を見る", "success")
        self.btn_demo.clicked.connect(self.start_demo_playback)
        self.btn_practice = ModernButton("練習スタート", "success")
        self.btn_practice.clicked.connect(self.start_practice_countdown)
        self.btn_perfect_practice = ModernButton("PERFECT練習", "warning")
        self.btn_perfect_practice.clicked.connect(self.start_perfect_practice_countdown)
        self.btn_retry = ModernButton("再試行", "danger")
        self.btn_retry.clicked.connect(self.retry)
        
        self.btn_settings = QPushButton("⚙️ 設定")
        self.btn_settings.setFixedSize(80, 36)
        self.btn_settings.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_settings.setStyleSheet(f"""
            QPushButton {{ background-color: {COLORS['text_secondary'].name()}; color: white; border-radius: 6px; font-weight: bold; }}
            QPushButton:hover {{ background-color: {COLORS['text_secondary'].darker(120).name()}; }}
        """)
        self.btn_settings.clicked.connect(self.open_settings_dialog)

        control_layout.addStretch()
        control_layout.addWidget(self.btn_load_template)
        control_layout.addWidget(self.btn_demo)
        control_layout.addWidget(self.btn_practice)
        control_layout.addWidget(self.btn_perfect_practice)
        control_layout.addWidget(self.btn_retry)
        control_layout.addStretch()
        control_layout.addWidget(self.btn_settings)

        main_layout.addWidget(control_panel)
        self.update_button_states()

    def init_sounds(self):
        try:
            if not pygame.mixer.get_init(): pygame.mixer.init(frequency=44100, size=-16, channels=16, buffer=512)
            
            if NUMPY_AVAILABLE:
                self.snare_sound = self._generate_drum_sound(type='snare')
                self.tom_sound = self._generate_drum_sound(type='tom')
                self.note_sound = self._generate_sound(880, 100) # Guide cue sound
                self.metronome_click = self._generate_sound(1500, 50)
                self.metronome_accent_click = self._generate_sound(2500, 50)
                self.countdown_sound = self._generate_sound(3000, 200)
                
                self.apply_settings()

        except Exception as e: QMessageBox.critical(self, "起動時エラー", f"音声初期化エラー:\n{e}")

    def init_images(self):
        all_image_files = {**NOTE_IMAGE_FILES, **REST_IMAGE_FILES}
        for item_type, filename in all_image_files.items():
            path = resource_path(filename)
            if os.path.exists(path):
                pixmap = QPixmap(path)
                if not pixmap.isNull():
                    h = 20 if item_type in ['eighth_rest', 'sixteenth_rest'] else 40
                    self.item_images[item_type] = pixmap.scaledToHeight(h, Qt.TransformationMode.SmoothTransformation)

    def _generate_sound(self, frequency, duration_ms):
        try:
            sample_rate = pygame.mixer.get_init()[0]
            n_samples = int(round(duration_ms / 1000 * sample_rate))
            buf = np.zeros((n_samples, 2), dtype=np.int16)
            max_val = 2**15 - 1; amplitude = max_val * 0.5
            period = int(sample_rate / frequency)
            for i in range(n_samples):
                val = amplitude if (i // (period / 2)) % 2 == 0 else -amplitude
                buf[i, :] = val
            fade_out = np.linspace(1, 0, n_samples)
            buf[:, 0] = np.int16(buf[:, 0] * fade_out); buf[:, 1] = np.int16(buf[:, 1] * fade_out)
            return pygame.sndarray.make_sound(buf)
        except Exception: return None

    def _generate_drum_sound(self, type='snare'):
        try:
            sample_rate = pygame.mixer.get_init()[0]
            
            if type == 'snare':
                duration_ms = 150
                n_samples = int(round(duration_ms / 1000 * sample_rate))
                noise = (2 * np.random.random(n_samples) - 1)
                decay = np.exp(-np.linspace(0, 5, n_samples))
                signal = noise * decay
            
            elif type == 'tom':
                duration_ms = 200
                frequency = 150.0
                n_samples = int(round(duration_ms / 1000 * sample_rate))
                t = np.linspace(0., duration_ms / 1000., n_samples)
                wave = np.sin(2. * np.pi * frequency * t)
                decay = np.exp(-np.linspace(0, 8, n_samples))
                signal = wave * decay
            else: return None

            amplitude = 2**14
            signal = np.int16(signal * amplitude)
            buf = np.zeros((n_samples, 2), dtype=np.int16)
            buf[:, 0] = signal; buf[:, 1] = signal
            return pygame.sndarray.make_sound(buf)
        except Exception as e:
            print(f"ドラム音の生成に失敗: {e}")
            return None

    def init_midi(self):
        try:
            input_ports = mido.get_input_names()
            if not input_ports: raise OSError("MIDI入力ポートが見つかりません。")
            self.inport = mido.open_input(input_ports[0])
            self.label_info.setText(f"✅ MIDIポートに接続: {input_ports[0]}")
        except OSError as e:
            self.label_info.setText(f"❌ エラー: {e}\nMIDIデバイスを接続して再起動してください。")
            self.btn_load_template.setEnabled(False)

    def open_settings_dialog(self):
        new_settings = SettingsDialog.get_settings(self, self.settings)
        if new_settings:
            self.settings = new_settings
            self.apply_settings()

    def apply_settings(self):
        if self.snare_sound: self.snare_sound.set_volume(self.settings['drum_volume'])
        if self.tom_sound: self.tom_sound.set_volume(self.settings['drum_volume'])
        if self.metronome_click: self.metronome_click.set_volume(self.settings['metronome_volume'])
        if self.metronome_accent_click: self.metronome_accent_click.set_volume(self.settings['metronome_volume'] * 1.2)
        if self.note_sound: self.note_sound.set_volume(self.settings['guide_cue_volume'])

    def load_template_file(self):
        filepath, _ = QFileDialog.getOpenFileName(self, "お手本ファイルを開く", "", "JSON Files (*.json)")
        if filepath:
            try:
                with open(filepath, 'r', encoding='utf-8') as f: self.template_score = json.load(f)
                if 'top' not in self.template_score: raise ValueError("無効なファイル形式です。")
                self.label_template_file.setText(f"お手本: {os.path.basename(filepath)}")
                self.retry()
            except Exception as e:
                QMessageBox.critical(self, "ファイル読み込みエラー", f"ファイルの読み込みに失敗しました:\n{e}")
                self.template_score = None; self.retry()

    def start_demo_playback(self):
        self.state = "demo_playback"; self.start_time = time.perf_counter()
        self.editor_window = EditorWindow(self.template_score, self, self.item_images, is_demo=True)
        self.editor_window.show()

    def start_practice_countdown(self):
        if not self.template_score or 'top' not in self.template_score: return
        self.is_perfect_mode = False
        self.practice_loop_count = 0
        self._start_countdown()
        
    def start_perfect_practice_countdown(self):
        if not self.template_score or 'top' not in self.template_score: return
        self.is_perfect_mode = True
        self.practice_loop_count = 0
        self.perfect_practice_history.clear()
        self.judgement_history.clear()
        self._start_countdown()

    def _start_countdown(self):
        bpm = self.template_score['top'].get('bpm', 120)
        self.countdown_beat_duration = 60000.0 / bpm
        self.state = "practice_countdown"; self.countdown_start_time = time.perf_counter()
        self.countdown_beat_count = -1; self.countdown_text = "3"
        self.play_countdown_sound()

    def start_actual_recording(self):
        self.state = "recording"; self.start_time = time.perf_counter()
        self.practice_loop_count = 1
        self.recorded_hits, self.judgements = [], []
        self.judged_notes.clear()
        self.total_notes = sum(1 for track in self.template_score.values() for item in track.get('items', []) if item['class'] == 'note')
        note_id = 0
        for track_name, track in self.template_score.items():
            for item in track.get('items', []):
                if item['class'] == 'note':
                    item['id'] = f"{track_name}-{note_id}"
                    note_id += 1
        self.editor_window = EditorWindow(self.template_score, self, self.item_images, is_demo=False)
        self.editor_window.show()

    def on_ai_feedback_received(self, feedback):
        self.ai_feedback_text = feedback
        self.canvas.update()
        self.btn_retry.setEnabled(True)
        self.btn_load_template.setEnabled(True)

    def on_thread_finished(self):
        self.thread = None
        self.worker = None

    def evaluate_and_continue_loop(self):
        if not self.is_perfect_mode: return

        self.judgement_history.append(list(self.judgements))

        stats = self.summarize_performance()
        history_entry = { 'loop': self.practice_loop_count, 'perfects': stats['perfect'], 'std_dev': stats['std_dev'] if stats['std_dev'] > 0 else 0 }
        self.perfect_practice_history.append(history_entry)
        level = self.settings.get('practice_level', 'p100')
        total_notes = self.total_notes if self.total_notes > 0 else 1
        perfect_pct = (stats['perfect'] / total_notes) * 100
        great_pct = (stats['great'] / total_notes) * 100
        success = False
        if level == 'p100':
            if perfect_pct >= 100.0: success = True
        elif level == 'p50_g100':
            if perfect_pct >= 50.0 and (perfect_pct + great_pct) >= 100.0: success = True
        elif level == 'g100':
            if (perfect_pct + great_pct) >= 100.0: success = True

        if success:
            self.result_stats = stats
            self.ai_feedback_text = f"🎉 クリア！ {self.practice_loop_count}回目で目標を達成しました！"
            if self.editor_window: self.editor_window.close()
        else:
            self.practice_loop_count += 1
            self.recorded_hits.clear(); self.judgements.clear(); self.judged_notes.clear()
            if self.editor_window: self.editor_window.rhythm_widget.user_hits.clear()
    
    def finish_performance(self, is_demo, force_stop=False):
        editor = self.editor_window
        if editor:
            self.editor_window = None 
            editor.close()

        if is_demo: self.state = "waiting"
        elif force_stop or not self.is_perfect_mode or self.is_perfect_mode:
            self.state = "result"
            self.ai_feedback_text = "AIによるフィードバックを生成中..."
            self.result_stats = self.summarize_performance()
            self.thread = QThread()
            self.worker = AiFeedbackWorker(self)
            self.worker.moveToThread(self.thread)
            self.thread.started.connect(self.worker.run)
            self.worker.finished.connect(self.on_ai_feedback_received)
            self.worker.finished.connect(self.thread.quit)
            self.worker.finished.connect(self.worker.deleteLater)
            self.thread.finished.connect(self.thread.deleteLater)
            self.thread.finished.connect(self.on_thread_finished)
            self.thread.start()
            self.btn_retry.setEnabled(False)
            self.btn_load_template.setEnabled(False)

        self.update_button_states()

    def retry(self):
        self.state = "waiting"; self.recorded_hits, self.judgements = [], []
        self.result_stats = {}; pygame.mixer.stop()
        self.practice_loop_count = 0
        self.is_perfect_mode = False
        self.update_button_states()

    def update_button_states(self):
        is_ready = self.template_score is not None
        is_waiting = self.state == "waiting"; is_result = self.state == "result"
        is_playing = self.state in ["recording", "demo_playback", "practice_countdown"]
        self.btn_settings.setVisible(not is_playing)
        self.btn_load_template.setVisible(not is_playing)
        self.btn_demo.setVisible(not is_playing and is_ready)
        self.btn_practice.setVisible(not is_playing and is_ready)
        self.btn_perfect_practice.setVisible(not is_playing and is_ready)
        self.btn_retry.setVisible(is_result)
        self.btn_demo.setEnabled(is_ready)
        self.btn_practice.setEnabled(is_ready)
        self.btn_perfect_practice.setEnabled(is_ready)

    def process_midi_input(self):
        if self.state != "recording": return
        if hasattr(self, 'inport') and self.inport:
            for msg in self.inport.iter_pending():
                if msg.type == 'note_on' and msg.velocity >= VELOCITY_THRESHOLD:
                    pad = 'top' if msg.note in PAD_MAPPING['left'] else 'bottom' if msg.note in PAD_MAPPING['right'] else None
                    if pad:
                        if self.snare_sound: self.snare_sound.play()
                        hit_time_ms = (time.perf_counter() - self.start_time) * 1000
                        new_hit = {'time': hit_time_ms, 'pad': pad}
                        self.recorded_hits.append(new_hit)
                        judgement, error_ms, note_id = self.judge_hit(new_hit)
                        self.judgements.append({'judgement': judgement, 'error_ms': error_ms, 'pad': pad, 'note_id': note_id, 'hit_time': hit_time_ms})
                        if note_id is not None: self.judged_notes.add(note_id)
                        if self.editor_window:
                            self.editor_window.rhythm_widget.add_user_hit(new_hit)
                            self.editor_window.rhythm_widget.add_feedback_animation(judgement, new_hit)

    # ★修正: EXTRA判定ロジックを全面的に改善
    def judge_hit(self, hit):
        pad, hit_time = hit['pad'], hit['time']
        track_data = self.template_score.get(pad)
        if not track_data: return 'extra', None, None
        
        bpm = track_data.get('bpm', 120)
        ms_per_beat = 60000.0 / bpm
        
        # 1. BPMに連動した「吸い寄せ範囲」を計算
        sixteenth_note_duration = ms_per_beat / 4.0
        # 16分音符の80%を基準としつつ、どんなに速い曲でも最低120msは保証する
        clustering_threshold = max(JUDGEMENT_WINDOWS['good'] + 20, sixteenth_note_duration * 0.8)

        # 2. ループ再生を考慮した時間の計算
        num = track_data.get('numerator', 4)
        den = track_data.get('denominator', 4)
        beats_per_measure = (num / den) * 4.0
        total_beats = beats_per_measure * NUM_MEASURES
        loop_duration_ms = ms_per_beat * total_beats
        if loop_duration_ms == 0: return 'extra', None, None

        hit_time_in_loop = hit_time % loop_duration_ms

        # 3. 最も近い未判定ノートを探す
        closest_note, min_diff = None, float('inf')
        for note in track_data.get('items', []):
            if note['class'] == 'note':
                note_time = note['beat'] * ms_per_beat
                diffs = [abs(hit_time_in_loop - note_time), abs(hit_time_in_loop - (note_time - loop_duration_ms)), abs(hit_time_in_loop - (note_time + loop_duration_ms))]
                diff = min(diffs)
                if note.get('id') not in self.judged_notes and diff < min_diff:
                    min_diff, closest_note = diff, note

        # 4. 吸い寄せ範囲内にあるか判定
        if closest_note and min_diff < clustering_threshold:
            # 範囲内なら、そのノートに対する打鍵として判定処理に進む
            note_time = closest_note['beat'] * ms_per_beat
            actual_note_time_instance = min([note_time, note_time - loop_duration_ms, note_time + loop_duration_ms], key=lambda x: abs(hit_time_in_loop - x))
            error_ms = hit_time_in_loop - actual_note_time_instance

            # 5. 絶対的な時間精度で perfect/great/good を判定
            if abs(error_ms) <= JUDGEMENT_WINDOWS['perfect']:
                return 'perfect', error_ms, closest_note['id']
            if abs(error_ms) <= JUDGEMENT_WINDOWS['great']:
                return 'great', error_ms, closest_note['id']
            # goodの窓(100ms)を超えても、吸い寄せ範囲内ならgood判定とする
            return 'good', error_ms, closest_note['id']

        # どのノートの吸い寄せ範囲にも入らなければEXTRA
        return 'extra', None, None


    def register_dropped_note(self, note_id, pad):
        if note_id not in self.judged_notes:
            self.judged_notes.add(note_id)
            self.judgements.append({'judgement': 'dropped', 'error_ms': None, 'pad': pad, 'note_id': note_id, 'hit_time': None})

    def get_elapsed_time(self):
        if self.start_time == 0: return 0
        return (time.perf_counter() - self.start_time) * 1000

    def play_note_sound(self):
        if self.note_sound: self.note_sound.play()

    def play_metronome_sound(self, is_accent):
        if is_accent and self.metronome_accent_click: self.metronome_accent_click.play()
        elif not is_accent and self.metronome_click: self.metronome_click.play()

    def play_countdown_sound(self):
        if self.countdown_sound: self.countdown_sound.play()

    def update_loop(self):
        if self.state == "practice_countdown":
            elapsed_ms = (time.perf_counter() - self.countdown_start_time) * 1000
            current_beat = int(elapsed_ms / self.countdown_beat_duration)
            if current_beat != self.countdown_beat_count and current_beat < 4:
                self.play_countdown_sound(); self.countdown_beat_count = current_beat
            if elapsed_ms < self.countdown_beat_duration: self.countdown_text = "3"
            elif elapsed_ms < self.countdown_beat_duration * 2: self.countdown_text = "2" 
            elif elapsed_ms < self.countdown_beat_duration * 3: self.countdown_text = "1"
            elif elapsed_ms < self.countdown_beat_duration * 4: self.countdown_text = "START!"
            else: self.start_actual_recording(); return
        
        self.update_button_states()
        if self.state == "recording": self.process_midi_input()
        self.canvas.update()

    def summarize_performance(self):
        stats = { 'perfect': 0, 'great': 0, 'good': 0, 'extra': 0, 'dropped': 0 }
        for j in self.judgements:
            if j['judgement'] in stats: stats[j['judgement']] += 1
        
        notes_judged = stats['perfect'] + stats['great'] + stats['good']
        if self.total_notes > 0:
            stats['dropped'] = self.total_notes - notes_judged
        else:
            stats['dropped'] = 0

        all_errors = [j['error_ms'] for j in self.judgements if j['error_ms'] is not None]
        stats['accuracy'] = (notes_judged / self.total_notes * 100) if self.total_notes > 0 else 0
        stats['avg_error'] = np.mean(all_errors) if NUMPY_AVAILABLE and all_errors else 0
        stats['std_dev'] = np.std(all_errors) if NUMPY_AVAILABLE and all_errors else 0
        return stats

    def create_performance_log_text(self):
        final_log_text = ""
        for track_name, hand_label in [('top', '左手'), ('bottom', '右手')]:
            if track_name not in self.template_score: continue
            track_data = self.template_score[track_name]
            notes_in_track = [item for item in track_data.get('items', []) if item['class'] == 'note']
            if not notes_in_track: continue
            log_table = f"\n# {hand_label}のパフォーマンスログ\n"
            log_table += "| Note # | Beat | Judgement | Timing Error(ms) |\n"
            log_table += "|--------|------|-----------|------------------|\n"
            note_num = 1
            for note in sorted(notes_in_track, key=lambda x: x['beat']):
                judgement_found = next((j for j in self.judgements if j.get('note_id') == note.get('id')), None)
                beat = note['beat']
                if judgement_found:
                    judgement = judgement_found['judgement'].upper()
                    error = f"{judgement_found['error_ms']:+.0f}" if judgement_found['error_ms'] is not None else "-"
                else:
                    judgement = "DROPPED"; error = "-"
                log_table += f"| {note_num:<6} | {beat:<4.2f} | {judgement:<9} | {error:<16} |\n"
                note_num += 1
            final_log_text += log_table
        extra_hits = sum(1 for j in self.judgements if j['judgement'] == 'extra')
        if extra_hits > 0:
            final_log_text += f"\n# EXTRA HITS (お手本にない打鍵)\n- {extra_hits}回\n"
        return final_log_text

    def create_multi_loop_log_text(self):
        full_log = ""
        original_judgements = list(self.judgements)

        for i, loop_judgements in enumerate(self.judgement_history):
            self.judgements = loop_judgements
            full_log += f"\n\n========== 練習 {i + 1}回目 ==========\n"
            full_log += self.create_performance_log_text()

        self.judgements = original_judgements
        return full_log

    def generate_ai_feedback_logic(self):
        if not OPENAI_AVAILABLE: return "OpenAIライブラリが見つかりません。"
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key: return "環境変数 OPENAI_API_KEY が設定されていません。"
        
        stats = self.result_stats
        summary_text = f"""
- 全体達成率: {stats['accuracy']:.1f}%
- 判定: PERFECT {stats['perfect']}回, GREAT {stats['great']}回, GOOD {stats['good']}回, EXTRA {stats['extra']}回, 見逃し {stats['dropped']}回
- 平均タイミング誤差: {stats['avg_error']:+.0f}ms ({'遅れ気味' if stats['avg_error'] > 5 else '走り気味' if stats['avg_error'] < -5 else '正確'})
- タイミングのばらつき(標準偏差): {stats['std_dev']:.2f}ms"""

        if self.is_perfect_mode and self.judgement_history:
             log_text = self.create_multi_loop_log_text()
             prompt_intro = "生徒が「PERFECT練習」モードを終えました。以下の複数回の練習ログを分析し、**成長の過程**（例：初回と最後の比較）を褒めつつ、最終的に改善すべき点を1つ指摘してください。"
        else:
             log_text = self.create_performance_log_text()
             prompt_intro = "生徒がリズム練習を終えました。以下のパフォーマンスデータを分析し、改善のための具体的なフィードバックを生成してください。"

        prompt = f"""
あなたは親切で優秀なドラム講師です。
{prompt_intro}

# 指示
- 必ず日本語で、100文字程度で回答してください。
- まずは何か一つ良い点を褒めてから、最も改善すべき点を一つだけ、具体的に指摘してください。
- **左右の手それぞれの詳細パフォーマンスログ**を最優先で分析し、「〇手の〇番目の音符がどうだったか」や「余計な打鍵」について言及してください。
- **パフォーマンスサマリー**は全体的な傾向（特に最終ループの結果）を把握するために使用してください。
- 生徒がやる気をなくさないよう、ポジティブで分かりやすい言葉を選んでください。

# パフォーマンスサマリー (最終結果)
{summary_text}
{log_text}

# フィードバック文章：
"""
        try:
            client = OpenAI(api_key=api_key)
            response = client.chat.completions.create(
                model="gpt-4o", messages=[{"role": "user", "content": prompt}],
                temperature=0.7, max_tokens=200
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            return f"フィードバック生成エラー: {e}"

    def closeEvent(self, event):
        if self.thread and self.thread.isRunning():
            self.thread.quit()
            self.thread.wait() 
        
        if hasattr(self, 'inport') and self.inport and not self.inport.closed:
            self.inport.close()
        pygame.quit()
        event.accept()

# -----------------------------------------------------------------------------
# --- アナライザーの描画キャンバス ---
# -----------------------------------------------------------------------------
class AnalyzerCanvas(QWidget):
    def __init__(self, main_window):
        super().__init__()
        self.main = main_window
        self.setMinimumHeight(400)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        gradient = QLinearGradient(0, 0, 0, self.height())
        gradient.setColorAt(0, COLORS['background'].lighter(110))
        gradient.setColorAt(1, COLORS['background'])
        painter.fillRect(self.rect(), gradient)
        draw_method = getattr(self, f"draw_{self.main.state}_state", self.draw_waiting_state)
        draw_method(painter)

    def draw_waiting_state(self, painter):
        painter.setPen(COLORS['text_primary'])
        painter.setFont(QFont("SansSerif", 32, QFont.Weight.Bold))
        painter.drawText(self.rect().adjusted(0, -100, 0, 0), Qt.AlignmentFlag.AlignCenter, "ドラムリズムアナライザー")
        
        painter.setPen(COLORS['text_secondary'])
        painter.setFont(QFont("SansSerif", 12))
        instruction = "お手本ファイルを選択して、練習を開始してください。"
        if not self.main.template_score:
            instruction = "まず、上部の「お手本を選択」ボタンからファイル (.json) を読み込んでください。"
        painter.drawText(self.rect().adjusted(0, 20, 0, 0), Qt.AlignmentFlag.AlignCenter, instruction)

    def draw_practice_countdown_state(self, painter):
        painter.setPen(COLORS['primary'])
        painter.setFont(QFont("SansSerif", 100, QFont.Weight.Bold))
        painter.drawText(self.rect().adjusted(0, -50, 0, 0), Qt.AlignmentFlag.AlignCenter, self.main.countdown_text)
        
        if self.main.template_score and 'top' in self.main.template_score:
            bpm = self.main.template_score['top'].get('bpm', 120)
            painter.setPen(COLORS['text_secondary'])
            painter.setFont(QFont("SansSerif", 16))
            painter.drawText(self.rect().adjusted(0, 100, 0, 0), Qt.AlignmentFlag.AlignCenter, f"BPM: {bpm}")
        
        painter.setFont(QFont("SansSerif", 12))
        if self.main.is_perfect_mode:
            painter.drawText(self.rect().adjusted(0, 135, 0, 0), Qt.AlignmentFlag.AlignCenter, 
                             "🎯 PERFECT 100%まで続けます！")
        else:
            painter.drawText(self.rect().adjusted(0, 135, 0, 0), Qt.AlignmentFlag.AlignCenter, "🥁 準備してください...")

    def draw_demo_playback_state(self, painter):
        painter.setPen(COLORS['text_primary'])
        painter.setFont(QFont("SansSerif", 24, QFont.Weight.Medium))
        painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "🎼 お手本を再生中...")

    def draw_recording_state(self, painter):
        painter.setPen(COLORS['success'])
        painter.setFont(QFont("SansSerif", 24, QFont.Weight.Medium))
        
        if self.main.is_perfect_mode:
            painter.drawText(self.rect().adjusted(0, -20, 0, 0), Qt.AlignmentFlag.AlignCenter, 
                             f"🎯 PERFECT練習 {self.main.practice_loop_count}回目")
            painter.setFont(QFont("SansSerif", 16))
            painter.drawText(self.rect().adjusted(0, 20, 0, 0), Qt.AlignmentFlag.AlignCenter, 
                             "PERFECT 100%を目指そう！")
        else:
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "🥁 演奏中... Keep the beat!")

    def draw_result_state(self, painter):
        painter.setPen(COLORS['text_primary'])
        painter.setFont(QFont("SansSerif", 24, QFont.Weight.Bold))
        painter.drawText(QRectF(0, 10, self.width(), 40), Qt.AlignmentFlag.AlignCenter, "演奏結果")

        if self.main.is_perfect_mode and self.main.perfect_practice_history:
            margin = 30
            graph_height = self.height() - 180
            graph_rect = QRectF(margin, 60, self.width() - margin * 2, graph_height)
            feedback_rect = QRectF(margin, graph_rect.bottom() + 20, self.width() - (margin * 2), 80)
            
            self.draw_perfect_practice_history_graph(painter, graph_rect)
            self.draw_ai_feedback(painter, feedback_rect)
        else:
            margin = 30
            stats_width = 320
            graph_width = self.width() - stats_width - (margin * 3)
            top_y = 60
            main_height = self.height() - 180
            graph_rect = QRectF(margin, top_y, graph_width, main_height)
            stats_rect = QRectF(graph_rect.right() + margin, top_y, stats_width, main_height)
            feedback_rect = QRectF(margin, graph_rect.bottom() + 20, self.width() - (margin * 2), 80)
            
            self.draw_result_graph(painter, graph_rect) 
            self.draw_result_stats(painter, stats_rect)
            self.draw_ai_feedback(painter, feedback_rect)

    def draw_perfect_practice_history_graph(self, painter, rect):
        painter.save()
        painter.setBrush(COLORS['surface'])
        painter.setPen(COLORS['border'])
        painter.drawRoundedRect(rect, 10, 10)

        history = self.main.perfect_practice_history
        if not history:
            painter.restore()
            return

        margin_top, margin_bottom, margin_left, margin_right = 40, 40, 60, 60
        plot_area = rect.adjusted(margin_left, margin_top, -margin_right, -margin_bottom)
        
        max_loop = history[-1]['loop']
        max_perfects = self.main.total_notes
        max_std_dev = max(h['std_dev'] for h in history) if any(h['std_dev'] > 0 for h in history) else 50.0

        painter.setPen(QPen(COLORS['border'], 1, Qt.PenStyle.DotLine))
        for i in range(6):
            y = plot_area.top() + i * plot_area.height() / 5
            painter.drawLine(QPointF(plot_area.left(), y), QPointF(plot_area.right(), y))
        if max_loop > 1:
            for i in range(max_loop):
                x = plot_area.left() + i * plot_area.width() / (max_loop - 1)
                painter.drawLine(QPointF(x, plot_area.top()), QPointF(x, plot_area.bottom()))

        painter.setPen(COLORS['text_secondary'])
        painter.setFont(QFont("SansSerif", 8))
        painter.drawText(rect.adjusted(0,0,0, -5), Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignBottom, "試行回数")
        for i in range(max_loop):
            loop_num = i + 1
            x = plot_area.left() + i * plot_area.width() / (max_loop - 1 if max_loop > 1 else 1)
            painter.drawText(QRectF(x - 20, plot_area.bottom() + 2, 40, 20), Qt.AlignmentFlag.AlignCenter, str(loop_num))

        painter.setPen(COLORS['perfect'])
        painter.drawText(rect.adjusted(5,0,0,0), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, "PERFECT数")
        for i in range(6):
            y = plot_area.top() + i * plot_area.height() / 5
            label = f"{max_perfects * (1 - i/5.0):.0f}"
            painter.drawText(QRectF(plot_area.left() - 50, y - 10, 40, 20), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight, label)

        painter.setPen(COLORS['primary'])
        painter.drawText(rect.adjusted(0,0,-5,0), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight, "ばらつき(ms)")
        for i in range(6):
            y = plot_area.top() + i * plot_area.height() / 5
            label = f"{max_std_dev * (1 - i/5.0):.1f}"
            painter.drawText(QRectF(plot_area.right() + 5, y - 10, 45, 20), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, label)

        perfects_poly = QPolygonF()
        std_dev_poly = QPolygonF()
        for h in history:
            x = plot_area.left() + (h['loop']-1) * plot_area.width() / (max_loop - 1 if max_loop > 1 else 1)
            y_perf = plot_area.bottom() - (h['perfects'] / max_perfects if max_perfects > 0 else 0) * plot_area.height()
            y_std = plot_area.bottom() - (h['std_dev'] / max_std_dev if max_std_dev > 0 else 0) * plot_area.height()
            perfects_poly.append(QPointF(x, y_perf))
            std_dev_poly.append(QPointF(x, y_std))

        painter.setPen(QPen(COLORS['primary'], 2))
        painter.drawPolyline(std_dev_poly)
        painter.setBrush(COLORS['primary'])
        for point in std_dev_poly:
            painter.drawEllipse(point, 3, 3)
            
        painter.setPen(QPen(COLORS['perfect'], 2))
        painter.drawPolyline(perfects_poly)
        painter.setBrush(COLORS['perfect'])
        for point in perfects_poly:
            painter.drawEllipse(point, 4, 4)

        painter.setFont(QFont("SansSerif", 9, QFont.Weight.Bold))
        painter.setPen(COLORS['perfect'])
        painter.drawText(QPointF(plot_area.left(), plot_area.top() - 25), "■ PERFECT数")
        painter.setPen(COLORS['primary'])
        painter.drawText(QPointF(plot_area.left() + 120, plot_area.top() - 25), "● タイミングのばらつき")

        painter.restore()

    def draw_result_graph(self, painter, rect):
        painter.save()
        painter.setBrush(COLORS['surface']); painter.setPen(COLORS['border'])
        painter.drawRoundedRect(rect, 10, 10)
        if not self.main.template_score or 'top' not in self.main.template_score:
            painter.restore(); return
        
        template = self.main.template_score
        top_track = template.get('top')
        bpm = top_track.get('bpm', 120)
        
        num = top_track.get('numerator', 4)
        den = top_track.get('denominator', 4)
        beats_per_measure = (num / den) * 4.0
        total_beats = beats_per_measure * NUM_MEASURES
        
        max_time_ms = (60.0 / bpm * total_beats) * 1000.0 if bpm > 0 else 0
        if max_time_ms <= 0: painter.restore(); return

        lanes = {
            'template_top': {'y': rect.top() + rect.height() * 0.2, 'label': "左（お手本）", 'color': COLORS['text_secondary'], 'data': top_track},
            'measured_top': {'y': rect.top() + rect.height() * 0.4, 'label': "左（演奏）", 'color': COLORS['primary'], 'data': [h for h in self.main.recorded_hits if h['pad'] == 'top']},
        }
        if 'bottom' in template:
            lanes['template_bottom'] = {'y': rect.top() + rect.height() * 0.6, 'label': "右（お手本）", 'color': COLORS['text_secondary'], 'data': template['bottom']}
            lanes['measured_bottom'] = {'y': rect.top() + rect.height() * 0.8, 'label': "右（演奏）", 'color': COLORS['success'], 'data': [h for h in self.main.recorded_hits if h['pad'] == 'bottom']}

        painter.setFont(QFont("SansSerif", 9))
        for key, lane in lanes.items():
            painter.setPen(COLORS['text_secondary'])
            label_rect = QRectF(rect.left() - 85, lane['y'] - 10, 80, 20)
            painter.drawText(label_rect, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight, lane['label'])
            painter.setPen(QPen(COLORS['border'], 1, Qt.PenStyle.DashLine))
            painter.drawLine(int(rect.left()), int(lane['y']), int(rect.right()), int(lane['y']))
        
        for key in ['template_top', 'template_bottom']:
            if key not in lanes: continue
            lane = lanes[key]
            track_data, track_bpm = lane['data'], lane['data'].get('bpm', 120)
            painter.setBrush(lane['color']); painter.setPen(Qt.PenStyle.NoPen)
            for item in track_data.get('items', []):
                if item['class'] == 'note':
                    time_ms = (item['beat'] / track_bpm * 60.0) * 1000.0
                    x = rect.left() + (time_ms / max_time_ms) * rect.width()
                    painter.drawRect(int(x - 1), int(lane['y']) - 8, 3, 16)
        
        for key in ['measured_top', 'measured_bottom']:
            if key not in lanes: continue
            lane = lanes[key]
            painter.setBrush(lane['color'])
            painter.setPen(QPen(lane['color'].darker(120)))
            for hit in lane['data']:
                if max_time_ms > 0:
                    x = rect.left() + (hit['time'] % max_time_ms) / max_time_ms * rect.width()
                    painter.drawEllipse(int(x) - 5, int(lane['y']) - 5, 10, 10)
        painter.restore()

    def draw_result_stats(self, painter, rect):
        painter.save()
        painter.setPen(COLORS['text_primary'])
        painter.setFont(QFont("SansSerif", 11, QFont.Weight.Bold))
        painter.drawText(rect.adjusted(0, 5, 0, 0), Qt.AlignmentFlag.AlignHCenter, "パフォーマンス分析")
        stats = self.main.result_stats
        if not stats: painter.restore(); return
        
        if self.main.is_perfect_mode and self.main.practice_loop_count > 0:
            painter.setFont(QFont("SansSerif", 10))
            painter.setPen(COLORS['warning'])
            painter.drawText(rect.adjusted(0, 25, 0, 0), Qt.AlignmentFlag.AlignHCenter, 
                             f"PERFECT練習: {self.main.practice_loop_count}回目で達成")
        
        font = QFont("SansSerif", 10); y_pos = rect.top() + 60 if self.main.is_perfect_mode else rect.top() + 40; line_height = 22
        for key in ['perfect', 'great', 'good', 'extra', 'dropped']:
            painter.setFont(font)
            painter.setPen(COLORS['text_secondary'])
            painter.drawText(QPointF(rect.left() + 10, y_pos), key.upper())
            painter.setFont(QFont("SansSerif", 10, QFont.Weight.Bold))
            painter.setPen(COLORS.get(key, COLORS['text_primary']))
            painter.drawText(QRectF(rect.left(), y_pos - line_height/2, rect.width() - 10, line_height), 
                             Qt.AlignmentFlag.AlignRight, str(stats.get(key, 0)))
            y_pos += line_height
        y_pos += 10; painter.setPen(QPen(COLORS['border']))
        painter.drawLine(int(rect.left() + 10), int(y_pos), int(rect.right() - 10), int(y_pos))
        y_pos += 15
        
        painter.setFont(font)
        painter.setPen(COLORS['text_secondary'])
        painter.drawText(QPointF(rect.left() + 10, y_pos), "達成率")
        painter.drawText(QPointF(rect.left() + 10, y_pos + line_height), "タイミングのばらつき")
        
        painter.setFont(QFont("SansSerif", 10, QFont.Weight.Bold))
        painter.setPen(COLORS['text_primary'])
        painter.drawText(QRectF(rect.left(), y_pos - line_height/2, rect.width() - 10, line_height), 
                         Qt.AlignmentFlag.AlignRight, f"{stats.get('accuracy', 0):.1f} %")
        painter.drawText(QRectF(rect.left(), y_pos + line_height - line_height/2, rect.width() - 10, line_height), 
                         Qt.AlignmentFlag.AlignRight, f"{stats.get('std_dev', 0):.2f} ms")
        painter.restore()
        
    def draw_ai_feedback(self, painter, rect):
        painter.save()
        painter.setBrush(COLORS['surface'])
        painter.setPen(COLORS['border'])
        painter.drawRoundedRect(rect, 10, 10)
        
        painter.setPen(COLORS['primary'])
        painter.setFont(QFont("SansSerif", 10, QFont.Weight.Bold))
        painter.drawText(rect.adjusted(10, 5, 0, 0), "AI講師からのアドバイス 🤖")
        
        painter.setPen(COLORS['text_primary'])
        painter.setFont(QFont("SansSerif", 10))
        text_rect = rect.adjusted(10, 25, -10, -5)
        flags = Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop | Qt.TextFlag.TextWordWrap
        painter.drawText(text_rect, flags, self.main.ai_feedback_text)
        painter.restore()

# -----------------------------------------------------------------------------
# --- モダンUIの楽譜表示ウィジェット ---
# -----------------------------------------------------------------------------
class EditorRhythmWidget(QWidget):
    def __init__(self, item_images, editor_window, parent=None):
        super().__init__(parent)
        self.editor_window = editor_window
        self.setMinimumHeight(200)
        self.item_images, self.score, self.is_playing = item_images, {}, False
        self.playback_timer = QTimer(self); self.playback_timer.timeout.connect(self.update_playback)
        self.last_metronome_beat, self.margin = -1, 50
        self.user_hits, self.feedback_animations = [], []
        self.next_evaluation_time = 0
        self.loop_duration_ms = 0

    def get_loop_duration(self):
        return self.loop_duration_ms

    def add_user_hit(self, hit_data):
        hit_data['received_time'] = time.perf_counter()
        self.user_hits.append(hit_data)

    def add_feedback_animation(self, judgement, hit_data):
        if judgement in ('extra', 'dropped'): return
        animation = {
            'text': judgement.upper() + "!", 'hit_time': hit_data['time'], 'pad': hit_data['pad'],
            'start_time': time.perf_counter(), 'color': COLORS.get(judgement.lower(), COLORS['text_secondary'])
        }
        self.feedback_animations.append(animation)

    def update_playback(self):
        if not self.is_playing or not self.score: return
        
        absolute_elapsed_ms = self.editor_window.get_elapsed_time()
        is_demo = self.editor_window.is_demo
        main_window = self.editor_window.main_window

        if not is_demo and self.loop_duration_ms > 0:
            if main_window.is_perfect_mode:
                if absolute_elapsed_ms >= self.next_evaluation_time:
                    main_window.evaluate_and_continue_loop()
                    self.next_evaluation_time += self.loop_duration_ms
            else:
                if absolute_elapsed_ms >= self.loop_duration_ms:
                    self.editor_window.close()
                    return
        
        if not is_demo and self.loop_duration_ms > 0:
            current_time_in_loop = absolute_elapsed_ms % self.loop_duration_ms
            for track_name, track_data in self.score.items():
                ms_per_beat = 60000.0 / track_data.get('bpm', 120)
                for note in track_data.get('items', []):
                    if note['class'] == 'note' and note.get('id') not in main_window.judged_notes:
                        note_time = note['beat'] * ms_per_beat
                        if current_time_in_loop > note_time + DROPPED_THRESHOLD:
                             main_window.register_dropped_note(note['id'], track_name)

        if main_window.settings.get('metronome_on', True) and 'top' in self.score:
            top_track = self.score['top']
            top_ms_per_beat = 60000.0 / top_track.get('bpm', 120)
            if top_ms_per_beat > 0:
                current_beat_num = int(absolute_elapsed_ms / top_ms_per_beat)
                if current_beat_num != self.last_metronome_beat:
                    beats_per_measure = top_track.get('beats_per_measure', 0)
                    if beats_per_measure > 0:
                        is_accent = (current_beat_num % int(beats_per_measure) == 0)
                        self.editor_window.play_metronome_sound(is_accent)
                    self.last_metronome_beat = current_beat_num
        
        for track_data in self.score.values():
            track_ms_per_beat = 60000.0 / track_data.get('bpm', 120)
            if track_ms_per_beat <= 0: continue
            track_loop_ms = track_ms_per_beat * track_data.get('total_beats', 1)
            if track_loop_ms <= 0: continue
            
            track_current_ms = absolute_elapsed_ms % track_loop_ms
            last_ms = track_data.get('last_elapsed_ms', 0)
            if last_ms > track_current_ms:
                for item in track_data.get('items', []): item['played_in_loop'] = False
            track_data['last_elapsed_ms'] = track_current_ms

            for item in track_data.get('items', []):
                note_start_ms = item['beat'] * track_ms_per_beat
                if not item.get('played_in_loop', False) and track_current_ms >= note_start_ms:
                    if item.get('class') == 'note':
                        item['lit_start_time'] = self.editor_window.get_elapsed_time()
                        if is_demo or (not is_demo and main_window.settings.get('guide_cue_on', False)):
                            self.editor_window.play_note_sound()
                    item['played_in_loop'] = True
        self.update()

    def set_data(self, score_data):
        self.score = score_data
        for track_data in self.score.values():
            num, den = track_data.get('numerator', 4), track_data.get('denominator', 4)
            track_data['beats_per_measure'] = (num / den) * 4.0
            track_data['total_beats'] = track_data['beats_per_measure'] * NUM_MEASURES
        
        if 'top' in self.score:
            top_track = self.score['top']
            ms_per_beat = 60000.0 / top_track.get('bpm', 120)
            self.loop_duration_ms = ms_per_beat * top_track.get('total_beats', 1)
            self.next_evaluation_time = self.loop_duration_ms
        self.update()
    
    def start_playback(self):
        if not self.is_playing:
            self.is_playing = True
            self.user_hits.clear(); self.feedback_animations.clear()
            for track in self.score.values():
                for item in track.get('items', []):
                    item['played_in_loop'] = False
                    if 'lit_start_time' in item: del item['lit_start_time']
                track['last_elapsed_ms'] = -1
            self.last_metronome_beat = -1
            self.playback_timer.start(16)
            self.update()

    def stop_playback(self):
        if self.is_playing: self.is_playing = False; self.playback_timer.stop(); self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        gradient = QLinearGradient(0, 0, 0, self.height())
        gradient.setColorAt(0, COLORS['background']); gradient.setColorAt(1, COLORS['surface'])
        painter.fillRect(self.rect(), gradient)
        start_x, drawable_width = self.margin, self.width() - (self.margin * 2)
        if drawable_width <= 0 or not self.score: return
        current_time_abs = self.editor_window.get_elapsed_time()
        for track_data in self.score.values():
            for item in track_data.get('items', []):
                item['is_lit'] = item.get('class') == 'note' and 'lit_start_time' in item and (current_time_abs - item['lit_start_time']) < LIT_DURATION
        staff_y_positions = {}
        is_two_track_mode = 'top' in self.score and 'bottom' in self.score
        if is_two_track_mode:
            staff_y_positions['top'] = self.height() * 0.35; staff_y_positions['bottom'] = self.height() * 0.65
        elif 'top' in self.score: staff_y_positions['top'] = self.height() * 0.5
        for track_name, staff_y in staff_y_positions.items():
            self.draw_staff(painter, self.score[track_name], staff_y, start_x, drawable_width, is_two_track_mode)
        if not self.editor_window.is_demo:
             self.draw_user_hits(painter, start_x, drawable_width, staff_y_positions)
             self.draw_feedback_animations(painter, start_x, drawable_width, staff_y_positions)
        if self.is_playing and self.loop_duration_ms > 0:
            progress = (current_time_abs % self.loop_duration_ms) / self.loop_duration_ms
            cursor_x = start_x + progress * drawable_width
            self.draw_glowing_line(painter, cursor_x, 30, self.height() - 30)

    def draw_user_hits(self, painter, start_x, drawable_width, staff_y_positions):
        if not self.score.get('top') or self.loop_duration_ms <= 0: return
        visible_hits = [h for h in self.user_hits if time.perf_counter() - h['received_time'] <= 1.0]
        self.user_hits = visible_hits
        
        for hit in visible_hits:
            pad = hit['pad']
            if pad not in staff_y_positions: continue
            
            hit_progress = (hit['time'] % self.loop_duration_ms) / self.loop_duration_ms
            x = start_x + hit_progress * drawable_width
            y = staff_y_positions.get(pad)
            
            age = time.perf_counter() - hit['received_time']
            opacity = max(0, 255 * (1.0 - age))

            base_color = COLORS['primary'] if pad == 'top' else COLORS['success']
            color = QColor(base_color)
            
            color.setAlpha(int(opacity))
            painter.setBrush(color)
            painter.setPen(Qt.PenStyle.NoPen)
            radius = 10 * (1.0 - age) + 3
            painter.drawEllipse(QPointF(x, y), radius, radius)

    def draw_feedback_animations(self, painter, start_x, drawable_width, staff_y_positions):
        if self.loop_duration_ms <= 0: return
        visible_animations = [a for a in self.feedback_animations if time.perf_counter() - a['start_time'] <= 0.75]
        self.feedback_animations = visible_animations

        for anim in visible_animations:
            hit_progress = (anim['hit_time'] % self.loop_duration_ms) / self.loop_duration_ms
            x = start_x + hit_progress * drawable_width
            y_start = staff_y_positions.get(anim['pad'])
            if y_start is None: continue
            
            age = time.perf_counter() - anim['start_time']
            y = y_start - (age * 50)
            opacity = max(0, 255 * (1.0 - (age / 0.75)))

            base_color = anim['color']
            color = QColor(base_color)
            color.setAlpha(int(opacity))

            painter.setPen(color)
            font = QFont("SansSerif", 20, QFont.Weight.Bold)
            painter.setFont(font)
            text_rect = QRectF(x - 50, y - 20, 100, 40)
            painter.drawText(text_rect, Qt.AlignmentFlag.AlignCenter, anim['text'])

    def draw_glowing_line(self, painter, x, y1, y2, base_width=6):
        for width, alpha in [(base_width, 100), (base_width-2, 150), (base_width-4, 255)]:
            if width <= 0: continue
            cursor_color = QColor(COLORS['cursor'])
            cursor_color.setAlpha(alpha)
            painter.setPen(QPen(cursor_color, width))
            painter.drawLine(int(x), int(y1), int(x), int(y2))

    def draw_staff(self, painter, track_data, staff_y, start_x, drawable_width, is_two_track_mode):
        beats_per_measure = track_data.get('beats_per_measure', 4.0)
        total_beats = track_data.get('total_beats', 8.0)
        
        painter.save()
        if is_two_track_mode:
            painter.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
            painter.setPen(COLORS['primary'])
            label = "L" if staff_y < self.height() / 2 else "R"
            painter.drawText(QRectF(5, staff_y - 28, 40, 25), Qt.AlignmentFlag.AlignCenter, label)
        
        painter.setFont(QFont("Segoe UI", 10))
        painter.setPen(COLORS['text_secondary'])
        ts_text = f"{track_data.get('numerator', 4)}\n─\n{track_data.get('denominator', 4)}"
        painter.drawText(QRectF(5, staff_y - 5, 40, 30), Qt.AlignmentFlag.AlignCenter, ts_text)
        painter.restore()
        
        painter.setPen(QPen(COLORS['staff_line'], 2))
        painter.drawLine(start_x, int(staff_y), start_x + drawable_width, int(staff_y))
        
        if total_beats > 0:
            for i in range(1, int(total_beats) + 1):
                x = start_x + (i / total_beats) * drawable_width
                is_measure_line = (i > 0 and i % beats_per_measure == 0) and i != total_beats
                if is_measure_line:
                    painter.setPen(QPen(COLORS['staff_line'], 2))
                    painter.drawLine(int(x), int(staff_y - 10), int(x), int(staff_y + 10))
                else:
                    painter.setPen(QPen(COLORS['text_muted'], 1, Qt.PenStyle.DotLine))
                    painter.drawLine(int(x), int(staff_y - 5), int(x), int(staff_y + 5))
        
        for item in track_data.get('items', []):
            self.draw_item(painter, item, staff_y, start_x, drawable_width, total_beats)

    def draw_item(self, painter, item, staff_y, start_x, drawable_width, total_beats_on_track):
        if total_beats_on_track <= 0: return
        x = start_x + (item['beat'] / total_beats_on_track) * drawable_width
        width = (item['duration'] / total_beats_on_track) * drawable_width
        item_rect = QRectF(x, staff_y - 25, width, 50)
        
        painter.save()
        if item.get('class') == 'note':
            guide_circle_radius = 4
            guide_circle_center_x = item_rect.left()
            guide_circle_center_y = staff_y
            guide_color = QColor(COLORS['primary'])
            guide_color.setAlpha(80)
            painter.setBrush(guide_color)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(QPointF(guide_circle_center_x, guide_circle_center_y), guide_circle_radius, guide_circle_radius)

            if item.get('is_lit', False):
                painter.setBrush(COLORS['note_glow'])
                painter.setPen(Qt.PenStyle.NoPen)
                painter.drawRoundedRect(item_rect.adjusted(-2, -2, 2, 2), 8, 8)
            
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(QPen(COLORS['primary'], 1))
            painter.drawRoundedRect(item_rect, 6, 6)
        else:
            painter.setBrush(COLORS['rest_bg'])
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(item_rect, 6, 6)
        painter.restore()
        
        image_to_draw = self.item_images.get(item['type'])
        if image_to_draw:
            draw_y = item_rect.top() + (item_rect.height() - image_to_draw.height()) / 2
            draw_point = QPointF(item_rect.left() + 5, draw_y)
            painter.drawPixmap(draw_point, image_to_draw)
            
            if item.get('dotted', False):
                dot_x, dot_y = draw_point.x() + image_to_draw.width() + 4, staff_y + 15
                painter.save()
                painter.setBrush(COLORS['text_primary']); painter.setPen(Qt.PenStyle.NoPen)
                painter.drawEllipse(QPointF(dot_x, dot_y), 3, 3)
                painter.restore()
        else:
            painter.setPen(COLORS['text_primary'])
            painter.drawText(item_rect, Qt.AlignmentFlag.AlignCenter, ALL_DURATIONS[item['type']]['name'])

# -----------------------------------------------------------------------------
# --- モダンUIの楽譜表示ウィンドウ ---
# -----------------------------------------------------------------------------
class EditorWindow(QMainWindow):
    def __init__(self, template_data, main_window, item_images, is_demo=False, parent=None):
        super().__init__(parent)
        self.main_window = main_window
        self.is_demo = is_demo
        title = "お手本再生" if is_demo else "練習中"
        self.setWindowTitle(title)
        self.resize(1200, 400)
        try:
            screen = QApplication.screenAt(QCursor.pos())
            if not screen: screen = QApplication.primaryScreen()
            center_point = screen.availableGeometry().center()
            x, y = center_point.x() - self.width() / 2, center_point.y() - self.height() / 2
            self.move(int(x), int(y))
        except Exception as e: self.setGeometry(150, 150, 1200, 400)
        self.setStyleSheet(f"background-color: {COLORS['background'].name()};")
        central_widget = QWidget()
        layout = QVBoxLayout(central_widget)
        layout.setContentsMargins(0, 0, 0, 5)
        self.rhythm_widget = EditorRhythmWidget(item_images, self)
        layout.addWidget(self.rhythm_widget)
        
        hbox = QHBoxLayout()
        hbox.addStretch()
        if is_demo:
            self.stop_button = ModernButton("再生停止", "danger")
        else:
            self.stop_button = ModernButton("練習中止", "danger")
        self.stop_button.clicked.connect(self.force_stop_practice)
        hbox.addWidget(self.stop_button)
        hbox.addStretch()
        layout.addLayout(hbox)
        
        self.setCentralWidget(central_widget)
        self.rhythm_widget.set_data(copy.deepcopy(template_data))
        self.rhythm_widget.start_playback()
        
    def force_stop_practice(self):
        self.close()

    def closeEvent(self, event):
        self.rhythm_widget.stop_playback()
        if self.main_window.editor_window is self:
            self.main_window.finish_performance(is_demo=self.is_demo, force_stop=True)
        event.accept()

    def get_elapsed_time(self): return self.main_window.get_elapsed_time()
    def play_note_sound(self): self.main_window.play_note_sound()
    def play_metronome_sound(self, is_accent): self.main_window.play_metronome_sound(is_accent)

# --- アプリケーション実行のエントリーポイント ---
def run_analyzer():
    app = QApplication.instance() 
    if app is None: app = QApplication(sys.argv)
    if not pygame.get_init(): pygame.init()
    win = MainWindow()
    win.show()
    app.exec()

if __name__ == "__main__":
    run_analyzer()