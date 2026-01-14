#モダンUI（ホワイトテーマ）
import sys
import os
import json
import time
import copy
import threading
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QPushButton, QWidget, QLabel, QVBoxLayout, QHBoxLayout,
    QFileDialog, QMessageBox, QDialog, QDialogButtonBox, QSlider, QCheckBox, QComboBox, QFormLayout,
    QGraphicsDropShadowEffect
)
from PyQt6.QtCore import Qt, QTimer, QRectF, QPointF, QObject, pyqtSignal, QThread, QPropertyAnimation, QEasingCurve, QParallelAnimationGroup, QSequentialAnimationGroup, pyqtProperty
from PyQt6.QtGui import (QPainter, QColor, QFont, QIcon, QPen, QPixmap, QLinearGradient, QCursor, QFontDatabase, QPolygonF, QRadialGradient, QBrush)

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

# --- モダンUIのカラーテーマ (ホワイト) ---
COLORS = {
    'background': QColor(248, 249, 250),      # Almost white
    'surface': QColor(255, 255, 255),          # White
    'surface_light': QColor(241, 243, 245),   # Off-white
    'primary': QColor(59, 130, 246),          # Blue-500
    'primary_dark': QColor(37, 99, 235),      # Blue-600
    'success': QColor(25, 135, 84),           # Green
    'success_dark': QColor(21, 115, 71),      # Darker Green
    'danger': QColor(220, 53, 69),            # Red
    'danger_dark': QColor(187, 45, 59),       # Darker Red
    'warning': QColor(255, 193, 7),           # Yellow (Amber)
    'warning_dark': QColor(217, 164, 6),      # Darker Yellow
    'note_glow': QColor(59, 130, 246, 80),     # Blue glow
    'rest_bg': QColor(233, 236, 239, 150),     # Light gray for rests
    'staff_line': QColor(173, 181, 189),      # Gray for staff line
    'cursor': QColor(214, 51, 132),           # Pink
    'text_primary': QColor(33, 37, 41),        # Almost black
    'text_secondary': QColor(108, 117, 125),   # Gray
    'text_muted': QColor(173, 181, 189),      # Lighter Gray
    'border': QColor(222, 226, 230),          # Very light gray border
    'perfect': QColor(255, 193, 7),           # Yellow (Amber)
    'great': QColor(25, 135, 84),             # Green
    'good': QColor(59, 130, 246),             # Blue
    'miss': QColor(108, 117, 125),            # Gray
    'extra': QColor(220, 53, 69),             # Red
    'accent': QColor(102, 16, 242),           # Purple
    'glow': QColor(59, 130, 246, 30),         # Blue with transparency
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
        self.button_type = button_type
        self._glow_opacity = 0.0
        
        color_map = {
            "primary": (COLORS['primary'], COLORS['primary_dark']),
            "success": (COLORS['success'], COLORS['success_dark']),
            "danger": (COLORS['danger'], COLORS['danger_dark']),
            "warning": (COLORS['warning'], COLORS['warning_dark']),
        }
        self.bg_color, self.hover_color = color_map.get(button_type, (COLORS['primary'], COLORS['primary_dark']))
        
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(15)
        shadow.setColor(QColor(0, 0, 0, 60))
        shadow.setOffset(0, 4)
        self.setGraphicsEffect(shadow)
        
        self.setMinimumHeight(44)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        self.update_style()
        
        self.glow_animation = QPropertyAnimation(self, b"glow_opacity")
        self.glow_animation.setDuration(150)
        self.glow_animation.setEasingCurve(QEasingCurve.Type.OutCubic)

    @pyqtProperty(float)
    def glow_opacity(self):
        return self._glow_opacity
    
    @glow_opacity.setter
    def glow_opacity(self, value):
        self._glow_opacity = value
        self.update_style()

    def update_style(self):
        self.setStyleSheet(f"""
            QPushButton {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 {self.bg_color.name()}, 
                    stop:1 {self.bg_color.darker(110).name()});
                color: white;
                border: 1px solid {self.bg_color.lighter(120).name()};
                border-radius: 12px;
                padding: 12px 24px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 {self.hover_color.name()}, 
                    stop:1 {self.hover_color.darker(110).name()});
                border: 1px solid {self.hover_color.lighter(130).name()};
            }}
            QPushButton:pressed {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 {self.bg_color.darker(120).name()}, 
                    stop:1 {self.bg_color.darker(140).name()});
            }}
            QPushButton:disabled {{
                background: {COLORS['text_muted'].name()};
                border: 1px solid {COLORS['text_muted'].darker(110).name()};
                color: {COLORS['text_muted'].lighter(150).name()};
            }}
        """)

    def enterEvent(self, event):
        self.glow_animation.setStartValue(self._glow_opacity)
        self.glow_animation.setEndValue(1.0)
        self.glow_animation.start()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.glow_animation.setStartValue(self._glow_opacity)
        self.glow_animation.setEndValue(0.0)
        self.glow_animation.start()
        super().leaveEvent(event)

class ModernLabel(QLabel):
    def __init__(self, text, font_size=10, weight=QFont.Weight.Normal, color_key='text_secondary', parent=None):
        super().__init__(text, parent)
        self.setFont(QFont("Segoe UI", font_size, weight))
        self.setStyleSheet(f"color: {COLORS[color_key].name()}; background: transparent;")

class GlowingWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._glow_opacity = 0.0
        
        self.glow_animation = QPropertyAnimation(self, b"glow_opacity")
        self.glow_animation.setDuration(2000)
        self.glow_animation.setEasingCurve(QEasingCurve.Type.InOutSine)
        self.glow_animation.setLoopCount(-1)
        self.glow_animation.setStartValue(0.3)
        self.glow_animation.setEndValue(1.0)

    @pyqtProperty(float)
    def glow_opacity(self):
        return self._glow_opacity
    
    @glow_opacity.setter
    def glow_opacity(self, value):
        self._glow_opacity = value
        self.update()

    def start_glow(self):
        self.glow_animation.start()

    def stop_glow(self):
        self.glow_animation.stop()
        self._glow_opacity = 0.0
        self.update()

class AiFeedbackWorker(QObject):
    finished = pyqtSignal(str)
    def __init__(self, main_window_ref):
        super().__init__()
        self.main_window = main_window_ref
    def run(self):
        feedback = self.main_window.generate_ai_feedback_logic()
        self.finished.emit(feedback)

class SettingsDialog(QDialog):
    def __init__(self, current_settings, parent=None):
        super().__init__(parent)
        self.setWindowTitle("練習設定")
        self.setMinimumWidth(400)
        self.setStyleSheet(f"""
            QDialog {{
                background: {COLORS['background'].name()};
                color: {COLORS['text_primary'].name()};
                border: 1px solid {COLORS['border'].name()};
                border-radius: 15px;
            }}
            QSlider::groove:horizontal {{
                border: 1px solid {COLORS['border'].name()};
                height: 8px;
                background: {COLORS['background'].name()};
                border-radius: 4px;
            }}
            QSlider::handle:horizontal {{
                background: {COLORS['primary'].name()};
                border: 1px solid {COLORS['primary'].lighter(120).name()};
                width: 18px;
                margin: -2px 0;
                border-radius: 9px;
            }}
            QSlider::sub-page:horizontal {{
                background: {COLORS['primary'].name()};
                border-radius: 4px;
            }}
            QComboBox {{
                background: {COLORS['surface'].name()};
                color: {COLORS['text_primary'].name()};
                border: 1px solid {COLORS['border'].name()};
                border-radius: 8px;
                padding: 8px;
                font-weight: bold;
            }}
            QComboBox:hover {{
                border: 1px solid {COLORS['primary'].name()};
            }}
            QComboBox::drop-down {{
                border: none;
                width: 30px;
            }}
            QComboBox::down-arrow {{
                image: none;
                border: 5px solid transparent;
                border-top: 8px solid {COLORS['text_primary'].name()};
                margin-right: 10px;
            }}
            QLabel {{
                color: {COLORS['text_secondary'].name()};
                font-weight: bold;
            }}
        """)

        self.settings = current_settings.copy()
        self.drum_volume_slider = QSlider(Qt.Orientation.Horizontal)
        self.drum_volume_slider.setRange(0, 100)
        self.drum_volume_slider.setValue(int(self.settings['drum_volume'] * 100))
        self.metronome_volume_slider = QSlider(Qt.Orientation.Horizontal)
        self.metronome_volume_slider.setRange(0, 100)
        self.metronome_volume_slider.setValue(int(self.settings['metronome_volume'] * 100))
        self.metronome_toggle_button = ModernButton("", "success")
        self.metronome_toggle_button.setMinimumHeight(36)
        self.metronome_toggle_button.clicked.connect(self.toggle_metronome)
        self.guide_volume_slider = QSlider(Qt.Orientation.Horizontal)
        self.guide_volume_slider.setRange(0, 100)
        self.guide_volume_slider.setValue(int(self.settings['guide_cue_volume'] * 100))
        self.guide_toggle_button = ModernButton("", "success")
        self.guide_toggle_button.setMinimumHeight(36)
        self.guide_toggle_button.clicked.connect(self.toggle_guide)
        self.update_metronome_button_style()
        self.update_guide_button_style()
        self.level_combo = QComboBox()
        self.levels = {"p100": "PERFECT 100%", "p50_g100": "PERFECT 50%以上 & GREAT含め100%", "g100": "GREAT以上 100%"}
        for key, text in self.levels.items(): self.level_combo.addItem(text, userData=key)
        current_level_key = self.settings.get('practice_level', 'p100')
        if current_level_key in self.levels: self.level_combo.setCurrentIndex(list(self.levels.keys()).index(current_level_key))
        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        self.button_box.setStyleSheet(f"""
            QPushButton {{
                background: {COLORS['primary'].name()}; color: white; border: 1px solid {COLORS['primary'].lighter(120).name()};
                border-radius: 8px; padding: 8px 16px; font-weight: bold; min-width: 80px;
            }}
            QPushButton:hover {{ background: {COLORS['primary_dark'].name()}; }}
        """)
        form_layout = QFormLayout()
        form_layout.setSpacing(15)
        form_layout.addRow("ドラム音量:", self.drum_volume_slider)
        form_layout.addRow("メトロノーム音量:", self.metronome_volume_slider)
        form_layout.addRow("ガイド音音量:", self.guide_volume_slider)
        form_layout.addRow("PERFECT練習レベル:", self.level_combo)
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(20)
        main_layout.setContentsMargins(30, 30, 30, 30)
        main_layout.addLayout(form_layout)
        main_layout.addWidget(self.metronome_toggle_button)
        main_layout.addWidget(self.guide_toggle_button)
        main_layout.addStretch()
        main_layout.addWidget(self.button_box)

    def toggle_metronome(self):
        self.settings['metronome_on'] = not self.settings.get('metronome_on', False)
        self.update_metronome_button_style()

    def update_metronome_button_style(self):
        if self.settings.get('metronome_on', False):
            self.metronome_toggle_button.setText("🎵 メトロノーム : ON"); self.metronome_toggle_button.button_type = "success"
        else:
            self.metronome_toggle_button.setText("🔇 メトロノーム : OFF"); self.metronome_toggle_button.button_type = "danger"
        self.metronome_toggle_button.bg_color = COLORS['success'] if self.settings.get('metronome_on', False) else COLORS['danger']
        self.metronome_toggle_button.hover_color = COLORS['success_dark'] if self.settings.get('metronome_on', False) else COLORS['danger_dark']
        self.metronome_toggle_button.update_style()

    def toggle_guide(self):
        self.settings['guide_cue_on'] = not self.settings.get('guide_cue_on', False)
        self.update_guide_button_style()
        
    def update_guide_button_style(self):
        if self.settings.get('guide_cue_on', False):
            self.guide_toggle_button.setText("🔊 ガイド音 : ON"); self.guide_toggle_button.button_type = "success"
        else:
            self.guide_toggle_button.setText("🔇 ガイド音 : OFF"); self.guide_toggle_button.button_type = "danger"
        self.guide_toggle_button.bg_color = COLORS['success'] if self.settings.get('guide_cue_on', False) else COLORS['danger']
        self.guide_toggle_button.hover_color = COLORS['success_dark'] if self.settings.get('guide_cue_on', False) else COLORS['danger_dark']
        self.guide_toggle_button.update_style()

    def accept(self):
        self.settings['drum_volume'] = self.drum_volume_slider.value() / 100.0
        self.settings['metronome_volume'] = self.metronome_volume_slider.value() / 100.0
        self.settings['guide_cue_volume'] = self.guide_volume_slider.value() / 100.0
        self.settings['practice_level'] = self.level_combo.currentData()
        super().accept()

    @staticmethod
    def get_settings(parent, current_settings):
        dialog = SettingsDialog(current_settings, parent)
        if dialog.exec() == QDialog.DialogCode.Accepted: return dialog.settings
        return None

# --- アナライザーのメインウィンドウ ---
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("🥁 ドラムリズムアナライザー")
        self.setFixedSize(1400, 800)
        self.setStyleSheet(f"QMainWindow {{ background-color: {COLORS['background'].name()}; color: {COLORS['text_primary'].name()}; }}")
        self.settings = {'drum_volume': 0.8, 'metronome_volume': 0.3, 'metronome_on': True, 'guide_cue_volume': 0.5, 'guide_cue_on': False, 'practice_level': 'p100'}
        self.state = "waiting"
        self.recorded_hits, self.judgements = [], []
        self.template_score, self.editor_window = None, None
        self.start_time, self.ai_feedback_text = 0, ""
        self.result_stats, self.total_notes, self.judged_notes = {}, 0, set()
        self.thread, self.worker = None, None
        self.practice_loop_count, self.is_perfect_mode = 0, False
        self.perfect_practice_history, self.judgement_history = [], []
        self.note_sound, self.metronome_click, self.metronome_accent_click, self.countdown_sound, self.snare_sound, self.tom_sound = None, None, None, None, None, None
        self.init_sounds()
        self.item_images = {}
        self.init_images()
        self.init_ui()
        self.init_midi()
        self.q_timer = QTimer(self); self.q_timer.timeout.connect(self.update_loop); self.q_timer.start(16)

    def init_ui(self):
        main_widget = QWidget(); main_layout = QVBoxLayout(main_widget)
        main_layout.setContentsMargins(30, 30, 30, 30); main_layout.setSpacing(25)
        self.setCentralWidget(main_widget)
        header_layout = QHBoxLayout()
        title_label = QLabel("🥁 ドラムリズムアナライザー"); title_label.setFont(QFont("Segoe UI", 28, QFont.Weight.Bold))
        title_label.setStyleSheet(f"color: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {COLORS['primary'].name()}, stop:1 {COLORS['accent'].name()}); background: transparent;")
        header_layout.addWidget(title_label); header_layout.addStretch()
        self.btn_settings = QPushButton("⚙️"); self.btn_settings.setFixedSize(50, 50)
        self.btn_settings.setCursor(Qt.CursorShape.PointingHandCursor); self.btn_settings.setFont(QFont("Segoe UI", 16))
        self.btn_settings.setStyleSheet(f"""
            QPushButton {{ background: {COLORS['surface_light'].name()}; color: {COLORS['text_primary'].name()}; border: 1px solid {COLORS['border'].name()}; border-radius: 25px; }}
            QPushButton:hover {{ background: {COLORS['surface'].name()}; border: 1px solid {COLORS['primary'].name()}; }}
        """)
        self.btn_settings.clicked.connect(self.open_settings_dialog); header_layout.addWidget(self.btn_settings)
        main_layout.addLayout(header_layout)
        self.canvas = AnalyzerCanvas(self)
        self.label_template_file = ModernLabel("お手本ファイルが読み込まれていません", 12, color_key='text_muted')
        self.label_template_file.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.label_info = ModernLabel("", 11, color_key='text_primary'); self.label_info.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(self.canvas); main_layout.addWidget(self.label_template_file); main_layout.addWidget(self.label_info)
        control_panel = QWidget(); control_layout = QHBoxLayout(control_panel)
        control_layout.setContentsMargins(0, 0, 0, 0); control_layout.setSpacing(20)
        self.btn_load_template = ModernButton("📁 お手本を選択", "primary"); self.btn_load_template.clicked.connect(self.load_template_file)
        self.btn_demo = ModernButton("👁️ お手本を見る", "success"); self.btn_demo.clicked.connect(self.start_demo_playback)
        self.btn_practice = ModernButton("🥁 練習スタート", "success"); self.btn_practice.clicked.connect(self.start_practice)
        self.btn_perfect_practice = ModernButton("🎯 PERFECT練習", "warning"); self.btn_perfect_practice.clicked.connect(self.start_perfect_practice)
        self.btn_retry = ModernButton("🔄 再試行", "danger"); self.btn_retry.clicked.connect(self.retry)
        control_layout.addStretch(); control_layout.addWidget(self.btn_load_template); control_layout.addWidget(self.btn_demo)
        control_layout.addWidget(self.btn_practice); control_layout.addWidget(self.btn_perfect_practice); control_layout.addWidget(self.btn_retry)
        control_layout.addStretch()
        main_layout.addWidget(control_panel); self.update_button_states()

    def init_sounds(self):
        try:
            if not pygame.mixer.get_init(): pygame.mixer.init(frequency=44100, size=-16, channels=16, buffer=512)
            if NUMPY_AVAILABLE:
                self.snare_sound = self._generate_drum_sound(type='snare'); self.tom_sound = self._generate_drum_sound(type='tom')
                self.note_sound = self._generate_sound(880, 100); self.metronome_click = self._generate_sound(1500, 50)
                self.metronome_accent_click = self._generate_sound(2500, 50); self.countdown_sound = self._generate_sound(3000, 200)
                self.apply_settings()
        except Exception as e: QMessageBox.critical(self, "起動時エラー", f"音声初期化エラー:\n{e}")

    def init_images(self):
        all_image_files = {**NOTE_IMAGE_FILES, **REST_IMAGE_FILES}; note_color = COLORS['text_primary']
        for item_type, filename in all_image_files.items():
            path = resource_path(filename)
            if os.path.exists(path):
                original_pixmap = QPixmap(path)
                if not original_pixmap.isNull():
                    colorized_pixmap = QPixmap(original_pixmap.size()); colorized_pixmap.fill(Qt.GlobalColor.transparent)
                    painter = QPainter(colorized_pixmap)
                    painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Source)
                    painter.drawPixmap(0, 0, original_pixmap)
                    painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
                    painter.fillRect(colorized_pixmap.rect(), note_color); painter.end()
                    h = 20 if item_type in ['eighth_rest', 'sixteenth_rest'] else 40
                    self.item_images[item_type] = colorized_pixmap.scaledToHeight(h, Qt.TransformationMode.SmoothTransformation)

    def _generate_sound(self, frequency, duration_ms):
        try:
            sample_rate = pygame.mixer.get_init()[0]; n_samples = int(round(duration_ms / 1000 * sample_rate))
            buf = np.zeros((n_samples, 2), dtype=np.int16); max_val = 2**15 - 1; amplitude = max_val * 0.5
            period = int(sample_rate / frequency)
            for i in range(n_samples): val = amplitude if (i // (period / 2)) % 2 == 0 else -amplitude; buf[i, :] = val
            fade_out = np.linspace(1, 0, n_samples)
            buf[:, 0] = np.int16(buf[:, 0] * fade_out); buf[:, 1] = np.int16(buf[:, 1] * fade_out)
            return pygame.sndarray.make_sound(buf)
        except Exception: return None

    def _generate_drum_sound(self, type='snare'):
        try:
            sample_rate = pygame.mixer.get_init()[0]
            if type == 'snare':
                duration_ms = 150; n_samples = int(round(duration_ms / 1000 * sample_rate))
                noise = (2 * np.random.random(n_samples) - 1); decay = np.exp(-np.linspace(0, 5, n_samples)); signal = noise * decay
            elif type == 'tom':
                duration_ms = 200; frequency = 150.0; n_samples = int(round(duration_ms / 1000 * sample_rate))
                t = np.linspace(0., duration_ms / 1000., n_samples); wave = np.sin(2. * np.pi * frequency * t)
                decay = np.exp(-np.linspace(0, 8, n_samples)); signal = wave * decay
            else: return None
            amplitude = 2**14; signal = np.int16(signal * amplitude)
            buf = np.zeros((n_samples, 2), dtype=np.int16); buf[:, 0] = signal; buf[:, 1] = signal
            return pygame.sndarray.make_sound(buf)
        except Exception as e: print(f"ドラム音の生成に失敗: {e}"); return None

    def init_midi(self):
        try:
            input_ports = mido.get_input_names()
            if not input_ports: raise OSError("MIDI入力ポートが見つかりません。")
            self.inport = mido.open_input(input_ports[0]); self.label_info.setText(f"✅ MIDIポートに接続: {input_ports[0]}")
        except OSError as e:
            self.label_info.setText(f"❌ エラー: {e}\nMIDIデバイスを接続して再起動してください。")
            self.btn_load_template.setEnabled(False)

    def open_settings_dialog(self):
        new_settings = SettingsDialog.get_settings(self, self.settings)
        if new_settings: self.settings = new_settings; self.apply_settings()

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
                self.label_template_file.setText(f"📄 お手本: {os.path.basename(filepath)}"); self.retry()
            except Exception as e:
                QMessageBox.critical(self, "ファイル読み込みエラー", f"ファイルの読み込みに失敗しました:\n{e}")
                self.template_score = None; self.retry()

    def start_demo_playback(self):
        self.state = "demo_playback"; self.start_time = time.perf_counter()
        self.editor_window = EditorWindow(self.template_score, self, self.item_images, is_demo=True)
        self.editor_window.show()

    def prepare_for_recording(self):
        self.start_time = 0
        self.practice_loop_count = 1
        self.recorded_hits, self.judgements = [], []
        self.judged_notes.clear()
        self.total_notes = sum(1 for track in self.template_score.values() for item in track.get('items', []) if item['class'] == 'note')
        note_id = 0
        for track_name, track in self.template_score.items():
            for item in track.get('items', []):
                if item['class'] == 'note': item['id'] = f"{track_name}-{note_id}"; note_id += 1
    
    def start_practice(self):
        if not self.template_score or 'top' not in self.template_score: return
        self.is_perfect_mode = False
        self.practice_loop_count = 0
        self.prepare_for_recording()
        self.state = "practice_countdown"  # "recording" から変更
        self.editor_window = EditorWindow(self.template_score, self, self.item_images, is_demo=False)
        self.editor_window.show()
        self.update_button_states()
        
    def start_perfect_practice(self):
        if not self.template_score or 'top' not in self.template_score: return
        self.is_perfect_mode = True
        self.practice_loop_count = 0
        self.perfect_practice_history.clear()
        self.judgement_history.clear()
        self.prepare_for_recording()
        self.state = "practice_countdown"  # "recording" から変更
        self.editor_window = EditorWindow(self.template_score, self, self.item_images, is_demo=False)
        self.editor_window.show()
        self.update_button_states()
        

    def on_ai_feedback_received(self, feedback):
        self.ai_feedback_text = feedback; self.canvas.update()
        self.btn_retry.setEnabled(True); self.btn_load_template.setEnabled(True)

    def on_thread_finished(self): self.thread = None; self.worker = None

    def evaluate_and_continue_loop(self):
        if not self.is_perfect_mode: return
        self.judgement_history.append(list(self.judgements))
        stats = self.summarize_performance()
        history_entry = { 'loop': self.practice_loop_count, 'perfects': stats['perfect'], 'std_dev': stats['std_dev'] if stats['std_dev'] > 0 else 0 }
        self.perfect_practice_history.append(history_entry)
        level = self.settings.get('practice_level', 'p100')
        total_notes = self.total_notes if self.total_notes > 0 else 1
        perfect_pct = (stats['perfect'] / total_notes) * 100; great_pct = (stats['great'] / total_notes) * 100
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
        if editor: self.editor_window = None; editor.close()
        if is_demo: self.state = "waiting"
        elif force_stop or self.is_perfect_mode:
            self.state = "result"; self.ai_feedback_text = "🤖 AIによるフィードバックを生成中..."
            self.result_stats = self.summarize_performance()
            self.thread = QThread(); self.worker = AiFeedbackWorker(self)
            self.worker.moveToThread(self.thread); self.thread.started.connect(self.worker.run)
            self.worker.finished.connect(self.on_ai_feedback_received); self.worker.finished.connect(self.thread.quit)
            self.worker.finished.connect(self.worker.deleteLater); self.thread.finished.connect(self.thread.deleteLater)
            self.thread.finished.connect(self.on_thread_finished); self.thread.start()
            self.btn_retry.setEnabled(False); self.btn_load_template.setEnabled(False)
        self.update_button_states()

    def retry(self):
        self.state = "waiting"; self.recorded_hits, self.judgements = [], []
        self.result_stats = {}; pygame.mixer.stop()
        self.practice_loop_count = 0; self.is_perfect_mode = False
        self.update_button_states()

    def update_button_states(self):
        is_ready = self.template_score is not None
        is_playing = self.state in ["recording", "demo_playback"]
        self.btn_settings.setVisible(not is_playing)
        self.btn_load_template.setVisible(not is_playing)
        self.btn_demo.setVisible(not is_playing and is_ready)
        self.btn_practice.setVisible(not is_playing and is_ready)
        self.btn_perfect_practice.setVisible(not is_playing and is_ready)
        self.btn_retry.setVisible(self.state == "result")
        self.btn_demo.setEnabled(is_ready)
        self.btn_practice.setEnabled(is_ready)
        self.btn_perfect_practice.setEnabled(is_ready)

    def process_midi_input(self):
        if not hasattr(self, 'inport') or not self.inport:
            return

        for msg in self.inport.iter_pending():
            if msg.type == 'note_on' and msg.velocity >= VELOCITY_THRESHOLD:
                pad = 'top' if msg.note in PAD_MAPPING['left'] else 'bottom' if msg.note in PAD_MAPPING['right'] else None
                if not pad:
                    continue

                # 1. 音を鳴らす処理 (カウントダウン中も録音中も実行)
                if self.state in ["practice_countdown", "recording"]:
                    if self.snare_sound: self.snare_sound.play()

                # 2. データを記録する処理 (録音中のみ実行)
                if self.state == "recording":
                    hit_time_ms = (time.perf_counter() - self.start_time) * 1000
                    new_hit = {'time': hit_time_ms, 'pad': pad}
                    self.recorded_hits.append(new_hit)
                    judgement, error_ms, note_id = self.judge_hit(new_hit)
                    self.judgements.append({'judgement': judgement, 'error_ms': error_ms, 'pad': pad, 'note_id': note_id, 'hit_time': hit_time_ms})
                    if note_id is not None: self.judged_notes.add(note_id)
                    if self.editor_window:
                        self.editor_window.rhythm_widget.add_user_hit(new_hit)
                        self.editor_window.rhythm_widget.add_feedback_animation(judgement, new_hit)

    def judge_hit(self, hit):
        pad, hit_time = hit['pad'], hit['time']; track_data = self.template_score.get(pad)
        if not track_data: return 'extra', None, None
        bpm = track_data.get('bpm', 120); ms_per_beat = 60000.0 / bpm
        sixteenth_note_duration = ms_per_beat / 4.0
        clustering_threshold = max(JUDGEMENT_WINDOWS['good'] + 20, sixteenth_note_duration * 0.8)
        num = track_data.get('numerator', 4); den = track_data.get('denominator', 4)
        beats_per_measure = (num / den) * 4.0; total_beats = beats_per_measure * NUM_MEASURES
        loop_duration_ms = ms_per_beat * total_beats
        if loop_duration_ms == 0: return 'extra', None, None
        hit_time_in_loop = hit_time % loop_duration_ms
        closest_note, min_diff = None, float('inf')
        for note in track_data.get('items', []):
            if note['class'] == 'note':
                note_time = note['beat'] * ms_per_beat
                diffs = [abs(hit_time_in_loop - note_time), abs(hit_time_in_loop - (note_time - loop_duration_ms)), abs(hit_time_in_loop - (note_time + loop_duration_ms))]
                diff = min(diffs)
                if note.get('id') not in self.judged_notes and diff < min_diff: min_diff, closest_note = diff, note
        if closest_note and min_diff < clustering_threshold:
            note_time = closest_note['beat'] * ms_per_beat
            actual_note_time_instance = min([note_time, note_time - loop_duration_ms, note_time + loop_duration_ms], key=lambda x: abs(hit_time_in_loop - x))
            error_ms = hit_time_in_loop - actual_note_time_instance
            if abs(error_ms) <= JUDGEMENT_WINDOWS['perfect']: return 'perfect', error_ms, closest_note['id']
            if abs(error_ms) <= JUDGEMENT_WINDOWS['great']: return 'great', error_ms, closest_note['id']
            return 'good', error_ms, closest_note['id']
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
        self.update_button_states()
        # カウントダウン中と録音中の両方でMIDI入力を処理する
        if self.state in ["practice_countdown", "recording"]:
            self.process_midi_input()
        self.canvas.update()

    def summarize_performance(self):
        stats = { 'perfect': 0, 'great': 0, 'good': 0, 'extra': 0, 'dropped': 0 }
        for j in self.judgements:
            if j['judgement'] in stats: stats[j['judgement']] += 1
        notes_judged = stats['perfect'] + stats['great'] + stats['good']
        stats['dropped'] = self.total_notes - notes_judged if self.total_notes > 0 else 0
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
            log_table = f"\n# {hand_label}のパフォーマンスログ\n| Note # | Beat | Judgement | Timing Error(ms) |\n|--------|------|-----------|------------------|\n"
            note_num = 1
            for note in sorted(notes_in_track, key=lambda x: x['beat']):
                judgement_found = next((j for j in self.judgements if j.get('note_id') == note.get('id')), None)
                beat = note['beat']
                if judgement_found:
                    judgement = judgement_found['judgement'].upper()
                    error = f"{judgement_found['error_ms']:+.0f}" if judgement_found['error_ms'] is not None else "-"
                else: judgement = "DROPPED"; error = "-"
                log_table += f"| {note_num:<6} | {beat:<4.2f} | {judgement:<9} | {error:<16} |\n"; note_num += 1
            final_log_text += log_table
        extra_hits = sum(1 for j in self.judgements if j['judgement'] == 'extra')
        if extra_hits > 0: final_log_text += f"\n# EXTRA HITS (お手本にない打鍵)\n- {extra_hits}回\n"
        return final_log_text

    def create_multi_loop_log_text(self):
        full_log = ""; original_judgements = list(self.judgements)
        for i, loop_judgements in enumerate(self.judgement_history):
            self.judgements = loop_judgements
            full_log += f"\n\n========== 練習 {i + 1}回目 ==========\n"; full_log += self.create_performance_log_text()
        self.judgements = original_judgements; return full_log

    def generate_ai_feedback_logic(self):
        if not OPENAI_AVAILABLE: return "OpenAIライブラリが見つかりません。"
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key: return "環境変数 OPENAI_API_KEY が設定されていません。"
        stats = self.result_stats
        summary_text = f"""- 全体達成率: {stats['accuracy']:.1f}%\n- 判定: PERFECT {stats['perfect']}回, GREAT {stats['great']}回, GOOD {stats['good']}回, EXTRA {stats['extra']}回, 見逃し {stats['dropped']}回
- 平均タイミング誤差: {stats['avg_error']:+.0f}ms ({'遅れ気味' if stats['avg_error'] > 5 else '走り気味' if stats['avg_error'] < -5 else '正確'})\n- タイミングのばらつき(標準偏差): {stats['std_dev']:.2f}ms"""
        if self.is_perfect_mode and self.judgement_history:
            log_text = self.create_multi_loop_log_text()
            prompt_intro = "生徒が「PERFECT練習」モードを終えました。以下の複数回の練習ログを分析し、**成長の過程**（例：初回と最後の比較）を褒めつつ、最終的に改善すべき点を1つ指摘してください。"
        else:
            log_text = self.create_performance_log_text()
            prompt_intro = "生徒がリズム練習を終えました。以下のパフォーマンスデータを分析し、改善のための具体的なフィードバックを生成してください。"
        prompt = f"あなたは親切で優秀なドラム講師です。\n{prompt_intro}\n# 指示\n- 必ず日本語で、100文字程度で回答してください。\n- まずは何か一つ良い点を褒めてから、最も改善すべき点を一つだけ、具体的に指摘してください。\n- **左右の手それぞれの詳細パフォーマンスログ**を最優先で分析し、「〇手の〇番目の音符がどうだったか」や「余計な打鍵」について言及してください。\n- **パフォーマンスサマリー**は全体的な傾向（特に最終ループの結果）を把握するために使用してください。\n- 生徒がやる気をなくさないよう、ポジティブで分かりやすい言葉を選んでください。\n\n# パフォーマンスサマリー (最終結果)\n{summary_text}\n{log_text}\n\n# フィードバック文章："
        try:
            client = OpenAI(api_key=api_key)
            response = client.chat.completions.create(model="gpt-4o", messages=[{"role": "user", "content": prompt}], temperature=0.7, max_tokens=200)
            return response.choices[0].message.content.strip()
        except Exception as e: return f"フィードバック生成エラー: {e}"

    def closeEvent(self, event):
        if self.thread and self.thread.isRunning(): self.thread.quit(); self.thread.wait() 
        if hasattr(self, 'inport') and self.inport and not self.inport.closed: self.inport.close()
        pygame.quit(); event.accept()

    def begin_real_recording(self):
        """EditorWindowのカウントダウン終了後に呼び出され、実際の録音を開始する"""
        self.state = "recording"

# --- アナライザーの描画キャンバス ---
class AnalyzerCanvas(GlowingWidget):
    def __init__(self, main_window):
        super().__init__(); self.main = main_window; self.setMinimumHeight(480)

    def paintEvent(self, event):
        painter = QPainter(self); painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), COLORS['surface'])
        painter.setPen(QPen(COLORS['border'], 1)); painter.drawRect(self.rect().adjusted(0, 0, -1, -1))
        draw_method = getattr(self, f"draw_{self.main.state}_state", self.draw_waiting_state)
        draw_method(painter)

    def draw_waiting_state(self, painter):
        glow_color = QColor(COLORS['primary']); glow_color.setAlpha(int(self._glow_opacity * 50))
        painter.save(); painter.setPen(QPen(glow_color, 3)); painter.setFont(QFont("Segoe UI", 42, QFont.Weight.Bold))
        painter.drawText(self.rect().adjusted(0, -120, 0, 0), Qt.AlignmentFlag.AlignCenter, "🎵 Ready to Rock!"); painter.restore()
        painter.setPen(COLORS['text_primary']); painter.setFont(QFont("Segoe UI", 42, QFont.Weight.Bold))
        painter.drawText(self.rect().adjusted(0, -120, 0, 0), Qt.AlignmentFlag.AlignCenter, "🎵 Ready to Rock!")
        painter.setPen(COLORS['text_secondary']); painter.setFont(QFont("Segoe UI", 16))
        instruction = "お手本ファイルを選択して、練習を開始してください。"
        if not self.main.template_score:
            instruction = "まず、上部の「📁 お手本を選択」ボタンからファイル (.json) を読み込んでください。"; self.start_glow()
        else: self.stop_glow()
        painter.drawText(self.rect().adjusted(0, -20, 0, 0), Qt.AlignmentFlag.AlignCenter, instruction)

    def draw_recording_state(self, painter):
        painter.setPen(COLORS['text_primary']); painter.setFont(QFont("Segoe UI", 42, QFont.Weight.Bold))
        painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "頑張って！ 👍")
        painter.setPen(COLORS['text_secondary']); painter.setFont(QFont("Segoe UI", 16))
        painter.drawText(self.rect().adjusted(0, 80, 0, 0), Qt.AlignmentFlag.AlignCenter, "演奏に集中してください...")

    def draw_demo_playback_state(self, painter): self.draw_recording_state(painter)
        
    def draw_result_state(self, painter):
        painter.save(); painter.setPen(QPen(QBrush(COLORS['text_primary']), 2))
        painter.setFont(QFont("Segoe UI", 36, QFont.Weight.Bold))
        painter.drawText(QRectF(0, 20, self.width(), 50), Qt.AlignmentFlag.AlignCenter, "🏆 演奏結果"); painter.restore()
        if self.main.is_perfect_mode and self.main.perfect_practice_history:
            margin = 40; graph_height = self.height() - 220
            graph_rect = QRectF(margin, 80, self.width() - margin * 2, graph_height)
            feedback_rect = QRectF(margin, graph_rect.bottom() + 30, self.width() - (margin * 2), 100)
            self.draw_perfect_practice_history_graph(painter, graph_rect); self.draw_ai_feedback(painter, feedback_rect)
        else:
            margin = 40; stats_width = 380; top_y = 80
            feedback_height = 110; feedback_spacing = 25; bottom_padding = 20
            main_height = self.height() - top_y - feedback_height - feedback_spacing - bottom_padding
            graph_width = self.width() - stats_width - (margin * 3)
            graph_rect = QRectF(margin, top_y, graph_width, main_height)
            stats_rect = QRectF(graph_rect.right() + margin, top_y, stats_width, main_height)
            feedback_rect = QRectF(margin, graph_rect.bottom() + feedback_spacing, self.width() - (margin * 2), feedback_height)
            self.draw_result_graph(painter, graph_rect); self.draw_result_stats(painter, stats_rect); self.draw_ai_feedback(painter, feedback_rect)

    def draw_perfect_practice_history_graph(self, painter, rect):
        painter.save()
        
        # 背景
        painter.setBrush(COLORS['surface'])
        painter.setPen(QPen(COLORS['border'], 1))
        painter.drawRoundedRect(rect, 15, 15)

        history = self.main.perfect_practice_history
        if not history:
            painter.setPen(COLORS['text_muted'])
            painter.setFont(QFont("Segoe UI", 14))
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, "履歴データがありません")
            painter.restore()
            return

        margin_top, margin_bottom, margin_left, margin_right = 50, 50, 80, 80
        plot_area = rect.adjusted(margin_left, margin_top, -margin_right, -margin_bottom)
        
        max_loop = history[-1]['loop']
        max_perfects = self.main.total_notes
        max_std_dev = max(h['std_dev'] for h in history) if any(h['std_dev'] > 0 for h in history) else 50.0

        # グリッド線
        painter.setPen(QPen(COLORS['border'], 1, Qt.PenStyle.DotLine))
        for i in range(6):
            y = plot_area.top() + i * plot_area.height() / 5
            painter.drawLine(QPointF(plot_area.left(), y), QPointF(plot_area.right(), y))
        if max_loop > 1:
            for i in range(max_loop):
                x = plot_area.left() + i * plot_area.width() / (max_loop - 1)
                painter.drawLine(QPointF(x, plot_area.top()), QPointF(x, plot_area.bottom()))

        # 軸ラベル
        painter.setPen(COLORS['text_secondary'])
        painter.setFont(QFont("Segoe UI", 10, QFont.Weight.Medium))
        painter.drawText(rect.adjusted(0,0,0, -10), Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignBottom, "試行回数")
        
        # X軸ラベル
        for i in range(max_loop):
            loop_num = i + 1
            x = plot_area.left() + i * plot_area.width() / (max_loop - 1 if max_loop > 1 else 1)
            painter.drawText(QRectF(x - 20, plot_area.bottom() + 5, 40, 25), Qt.AlignmentFlag.AlignCenter, str(loop_num))

        # Y軸ラベル (PERFECT数)
        painter.setPen(COLORS['perfect'])
        painter.drawText(rect.adjusted(10,0,0,0), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, "PERFECT数")
        for i in range(6):
            y = plot_area.top() + i * plot_area.height() / 5
            label = f"{max_perfects * (1 - i/5.0):.0f}"
            painter.drawText(QRectF(plot_area.left() - 70, y - 12, 60, 24), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight, label)

        # Y軸ラベル (ばらつき)
        painter.setPen(COLORS['primary'])
        painter.drawText(rect.adjusted(0,0,-10,0), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight, "ばらつき(ms)")
        for i in range(6):
            y = plot_area.top() + i * plot_area.height() / 5
            label = f"{max_std_dev * (1 - i/5.0):.1f}"
            painter.drawText(QRectF(plot_area.right() + 10, y - 12, 60, 24), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, label)

        # データプロット
        perfects_poly = QPolygonF()
        std_dev_poly = QPolygonF()
        for h in history:
            x = plot_area.left() + (h['loop']-1) * plot_area.width() / (max_loop - 1 if max_loop > 1 else 1)
            y_perf = plot_area.bottom() - (h['perfects'] / max_perfects if max_perfects > 0 else 0) * plot_area.height()
            y_std = plot_area.bottom() - (h['std_dev'] / max_std_dev if max_std_dev > 0 else 0) * plot_area.height()
            perfects_poly.append(QPointF(x, y_perf))
            std_dev_poly.append(QPointF(x, y_std))

        # ばらつき線
        painter.setPen(QPen(COLORS['primary'], 3))
        painter.drawPolyline(std_dev_poly)
        painter.setBrush(COLORS['primary'])
        for point in std_dev_poly:
            painter.drawEllipse(point, 5, 5)
            
        # PERFECT線  
        painter.setPen(QPen(COLORS['perfect'], 4))
        painter.drawPolyline(perfects_poly)
        painter.setBrush(COLORS['perfect'])
        for point in perfects_poly:
            painter.drawEllipse(point, 6, 6)

        # 凡例
        painter.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        painter.setPen(COLORS['perfect'])
        painter.drawText(QPointF(plot_area.left(), plot_area.top() - 30), "● PERFECT数")
        painter.setPen(COLORS['primary'])
        painter.drawText(QPointF(plot_area.left() + 140, plot_area.top() - 30), "● タイミングのばらつき")

        painter.restore()

    def draw_result_graph(self, painter, rect):
        painter.save()
        
        # 背景
        painter.setBrush(COLORS['surface'])
        painter.setPen(QPen(COLORS['border'], 1))
        painter.drawRoundedRect(rect, 15, 15)
        
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

        # レーン設定
        lanes = {
            'template_top': {'y': rect.top() + rect.height() * 0.25, 'label': "左（お手本）", 'color': COLORS['text_secondary'], 'data': top_track},
            'measured_top': {'y': rect.top() + rect.height() * 0.45, 'label': "左（演奏）", 'color': COLORS['primary'], 'data': [h for h in self.main.recorded_hits if h['pad'] == 'top']},
        }
        if 'bottom' in template:
            lanes['template_bottom'] = {'y': rect.top() + rect.height() * 0.65, 'label': "右（お手本）", 'color': COLORS['text_secondary'], 'data': template['bottom']}
            lanes['measured_bottom'] = {'y': rect.top() + rect.height() * 0.85, 'label': "右（演奏）", 'color': COLORS['success'], 'data': [h for h in self.main.recorded_hits if h['pad'] == 'bottom']}

        # レーンラベルとライン
        painter.setFont(QFont("Segoe UI", 11, QFont.Weight.Medium))
        for key, lane in lanes.items():
            painter.setPen(COLORS['text_secondary'])
            label_rect = QRectF(rect.left() - 100, lane['y'] - 12, 90, 24)
            painter.drawText(label_rect, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight, lane['label'])
            painter.setPen(QPen(COLORS['border'], 1, Qt.PenStyle.DashLine))
            painter.drawLine(int(rect.left()), int(lane['y']), int(rect.right()), int(lane['y']))
        
        # お手本ノート描画
        for key in ['template_top', 'template_bottom']:
            if key not in lanes: continue
            lane = lanes[key]
            track_data, track_bpm = lane['data'], lane['data'].get('bpm', 120)
            painter.setBrush(lane['color']); painter.setPen(Qt.PenStyle.NoPen)
            for item in track_data.get('items', []):
                if item['class'] == 'note':
                    time_ms = (item['beat'] / track_bpm * 60.0) * 1000.0
                    x = rect.left() + (time_ms / max_time_ms) * rect.width()
                    painter.drawRect(int(x - 2), int(lane['y']) - 10, 4, 20)
        
        # 実際の打鍵描画
        for key in ['measured_top', 'measured_bottom']:
            if key not in lanes: continue
            lane = lanes[key]
            painter.setBrush(lane['color'])
            painter.setPen(QPen(lane['color'].darker(120), 2))
            for hit in lane['data']:
                if max_time_ms > 0:
                    x = rect.left() + (hit['time'] % max_time_ms) / max_time_ms * rect.width()
                    painter.drawEllipse(int(x) - 6, int(lane['y']) - 6, 12, 12)
        
        painter.restore()

    def draw_result_graph(self, painter, rect):
        painter.save()
        
        # 背景
        painter.setBrush(COLORS['surface'])
        painter.setPen(QPen(COLORS['border'], 1))
        painter.drawRoundedRect(rect, 15, 15)
        
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

        # レーン設定
        lanes = {
            'template_top': {'y': rect.top() + rect.height() * 0.25, 'label': "左（お手本）", 'color': COLORS['text_secondary'], 'data': top_track},
            'measured_top': {'y': rect.top() + rect.height() * 0.45, 'label': "左（演奏）", 'color': COLORS['primary'], 'data': [h for h in self.main.recorded_hits if h['pad'] == 'top']},
        }
        if 'bottom' in template:
            lanes['template_bottom'] = {'y': rect.top() + rect.height() * 0.65, 'label': "右（お手本）", 'color': COLORS['text_secondary'], 'data': template['bottom']}
            lanes['measured_bottom'] = {'y': rect.top() + rect.height() * 0.85, 'label': "右（演奏）", 'color': COLORS['success'], 'data': [h for h in self.main.recorded_hits if h['pad'] == 'bottom']}

        # レーンラベルとライン
        painter.setFont(QFont("Segoe UI", 11, QFont.Weight.Medium))
        for key, lane in lanes.items():
            painter.setPen(COLORS['text_secondary'])
            label_rect = QRectF(rect.left() - 100, lane['y'] - 12, 90, 24)
            painter.drawText(label_rect, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight, lane['label'])
            painter.setPen(QPen(COLORS['border'], 1, Qt.PenStyle.DashLine))
            painter.drawLine(int(rect.left()), int(lane['y']), int(rect.right()), int(lane['y']))
        
        # お手本ノート描画
        for key in ['template_top', 'template_bottom']:
            if key not in lanes: continue
            lane = lanes[key]
            track_data, track_bpm = lane['data'], lane['data'].get('bpm', 120)
            painter.setBrush(lane['color']); painter.setPen(Qt.PenStyle.NoPen)
            for item in track_data.get('items', []):
                if item['class'] == 'note':
                    time_ms = (item['beat'] / track_bpm * 60.0) * 1000.0
                    x = rect.left() + (time_ms / max_time_ms) * rect.width()
                    painter.drawRect(int(x - 2), int(lane['y']) - 10, 4, 20)
        
        # 実際の打鍵描画
        for key in ['measured_top', 'measured_bottom']:
            if key not in lanes: continue
            lane = lanes[key]
            painter.setBrush(lane['color'])
            painter.setPen(QPen(lane['color'].darker(120), 2))
            for hit in lane['data']:
                if max_time_ms > 0:
                    x = rect.left() + (hit['time'] % max_time_ms) / max_time_ms * rect.width()
                    painter.drawEllipse(int(x) - 6, int(lane['y']) - 6, 12, 12)
        
        painter.restore()

    def draw_result_stats(self, painter, rect):
        painter.save()
        painter.setBrush(COLORS['surface']); painter.setPen(QPen(COLORS['border'], 1))
        painter.drawRoundedRect(rect, 15, 15)
        painter.setPen(COLORS['text_primary']); painter.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        painter.drawText(rect.adjusted(0, 15, 0, 0), Qt.AlignmentFlag.AlignHCenter, "📊 パフォーマンス分析")
        stats = self.main.result_stats
        if not stats: painter.restore(); return
        if self.main.is_perfect_mode and self.main.practice_loop_count > 0:
            painter.setFont(QFont("Segoe UI", 12, QFont.Weight.Medium)); painter.setPen(COLORS['warning'])
            painter.drawText(rect.adjusted(0, 45, 0, 0), Qt.AlignmentFlag.AlignHCenter, f"🎯 PERFECT練習: {self.main.practice_loop_count}回目で達成")
        font = QFont("Segoe UI", 11); y_pos = rect.top() + (85 if self.main.is_perfect_mode else 65); line_height = 27
        judgement_data = [('PERFECT', 'perfect', '🟡'), ('GREAT', 'great', '🟢'), ('GOOD', 'good', '🔵'), ('EXTRA', 'extra', '🔴'), ('見逃し', 'dropped', '⚫')]
        for label, key, emoji in judgement_data:
            painter.setFont(font); painter.setPen(COLORS['text_secondary'])
            painter.drawText(QPointF(rect.left() + 20, y_pos), f"{emoji} {label}")
            painter.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold)); painter.setPen(COLORS.get(key, COLORS['text_primary']))
            painter.drawText(QRectF(rect.left(), y_pos - line_height/2, rect.width() - 20, line_height), Qt.AlignmentFlag.AlignRight, str(stats.get(key, 0)))
            y_pos += line_height
        y_pos += 10; painter.setPen(QPen(COLORS['border'], 1)); painter.drawLine(int(rect.left() + 20), int(y_pos), int(rect.right() - 20), int(y_pos)); y_pos += 20
        
        # --- 「ばらつき」表示のレイアウト修正 ---
        label_font = QFont("Segoe UI", 11)
        value_font = QFont("Segoe UI", 12, QFont.Weight.Bold)
        label_col_rect = QRectF(rect.left() + 20, y_pos, rect.width() / 2 - 20, line_height * 2)
        value_col_rect = QRectF(label_col_rect.right(), y_pos, rect.width() / 2 - 20, line_height * 2)

        painter.setFont(label_font); painter.setPen(COLORS['text_secondary'])
        painter.drawText(label_col_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop, "📈 達成率")
        painter.drawText(label_col_rect.translated(0, line_height), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop, "📏 ばらつき")

        painter.setFont(value_font); painter.setPen(COLORS['text_primary'])
        painter.drawText(value_col_rect, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop, f"{stats.get('accuracy', 0):.1f}%")
        painter.drawText(value_col_rect.translated(0, line_height), Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop, f"{stats.get('std_dev', 0):.2f}ms")
        painter.restore()
        
    def draw_ai_feedback(self, painter, rect):
        painter.save(); painter.setBrush(COLORS['surface_light']); painter.setPen(QPen(COLORS['accent'], 1))
        painter.drawRoundedRect(rect, 15, 15); painter.setPen(COLORS['accent'])
        painter.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold)); painter.drawText(rect.adjusted(20, 15, 0, 0), "🤖 AI講師からのアドバイス")
        painter.setPen(COLORS['text_primary']); painter.setFont(QFont("Segoe UI", 12))
        text_rect = rect.adjusted(20, 45, -20, -15)
        flags = Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop | Qt.TextFlag.TextWordWrap
        painter.drawText(text_rect, flags, self.main.ai_feedback_text); painter.restore()

# --- モダンUIの楽譜表示ウィジェット ---
class EditorRhythmWidget(QWidget):
    def __init__(self, item_images, editor_window, parent=None):
        super().__init__(parent)
        self.editor_window = editor_window
        self.setMinimumHeight(240)
        self.item_images, self.score, self.is_playing = item_images, {}, False
        self.playback_timer = QTimer(self); self.playback_timer.timeout.connect(self.update_playback)
        self.last_metronome_beat, self.margin = -1, 60
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
        
        painter.fillRect(self.rect(), COLORS['surface'])
        painter.setPen(QPen(COLORS['border'], 1))
        painter.drawRoundedRect(self.rect().adjusted(1, 1, -1, -1), 15, 15)
        
        start_x, drawable_width = self.margin, self.width() - (self.margin * 2)
        if drawable_width <= 0 or not self.score: return
        current_time_abs = self.editor_window.get_elapsed_time()
        
        for track_data in self.score.values():
            for item in track_data.get('items', []):
                item['is_lit'] = item.get('class') == 'note' and 'lit_start_time' in item and (current_time_abs - item['lit_start_time']) < LIT_DURATION
        
        staff_y_positions = {}
        is_two_track_mode = 'top' in self.score and 'bottom' in self.score
        if is_two_track_mode:
            staff_y_positions['top'] = self.height() * 0.4; staff_y_positions['bottom'] = self.height() * 0.7
        elif 'top' in self.score: staff_y_positions['top'] = self.height() * 0.55
        
        for track_name, staff_y in staff_y_positions.items():
            self.draw_staff(painter, self.score[track_name], staff_y, start_x, drawable_width, is_two_track_mode)
        
        if not self.editor_window.is_demo:
                 self.draw_user_hits(painter, start_x, drawable_width, staff_y_positions)
                 self.draw_feedback_animations(painter, start_x, drawable_width, staff_y_positions)
        
        if self.is_playing and self.loop_duration_ms > 0:
            progress = (current_time_abs % self.loop_duration_ms) / self.loop_duration_ms
            cursor_x = start_x + progress * drawable_width
            self.draw_glowing_cursor(painter, cursor_x, 40, self.height() - 40)

    def draw_user_hits(self, painter, start_x, drawable_width, staff_y_positions):
        if not self.score.get('top') or self.loop_duration_ms <= 0: return
        visible_hits = [h for h in self.user_hits if time.perf_counter() - h['received_time'] <= 1.5]
        self.user_hits = visible_hits
        
        for hit in visible_hits:
            pad = hit['pad']
            if pad not in staff_y_positions: continue
            
            hit_progress = (hit['time'] % self.loop_duration_ms) / self.loop_duration_ms
            x = start_x + hit_progress * drawable_width
            y = staff_y_positions.get(pad)
            
            age = time.perf_counter() - hit['received_time']
            opacity = max(0, 255 * (1.0 - age / 1.5))

            base_color = COLORS['primary'] if pad == 'top' else COLORS['success']
            
            for radius, alpha_mult in [(15, 0.3), (12, 0.5), (8, 0.8)]:
                glow_color = QColor(base_color)
                glow_color.setAlpha(int(opacity * alpha_mult))
                painter.setBrush(glow_color)
                painter.setPen(Qt.PenStyle.NoPen)
                painter.drawEllipse(QPointF(x, y), radius, radius)
            
            main_color = QColor(base_color)
            main_color.setAlpha(int(opacity))
            painter.setBrush(main_color)
            painter.setPen(QPen(main_color.lighter(150), 2))
            radius = 6
            painter.drawEllipse(QPointF(x, y), radius, radius)

    def draw_feedback_animations(self, painter, start_x, drawable_width, staff_y_positions):
        if self.loop_duration_ms <= 0: return
        visible_animations = [a for a in self.feedback_animations if time.perf_counter() - a['start_time'] <= 1.0]
        self.feedback_animations = visible_animations

        for anim in visible_animations:
            hit_progress = (anim['hit_time'] % self.loop_duration_ms) / self.loop_duration_ms
            x = start_x + hit_progress * drawable_width
            y_start = staff_y_positions.get(anim['pad'])
            if y_start is None: continue
            
            age = time.perf_counter() - anim['start_time']
            y = y_start - (age * 60)
            opacity = max(0, 255 * (1.0 - (age / 1.0)))
            scale = 1.0 + (age * 0.5)

            glow_color = QColor(anim['color'])
            glow_color.setAlpha(int(opacity * 0.5))
            painter.setPen(QPen(glow_color, 4))
            font = QFont("Segoe UI", int(20 * scale), QFont.Weight.Bold)
            painter.setFont(font)
            text_rect = QRectF(x - 60, y - 25, 120, 50)
            painter.drawText(text_rect, Qt.AlignmentFlag.AlignCenter, anim['text'])

            main_color = QColor(anim['color'])
            main_color.setAlpha(int(opacity))
            painter.setPen(main_color)
            painter.drawText(text_rect, Qt.AlignmentFlag.AlignCenter, anim['text'])

    def draw_glowing_cursor(self, painter, x, y1, y2):
        for width, alpha in [(12, 30), (8, 60), (4, 120), (2, 255)]:
            cursor_color = QColor(COLORS['cursor'])
            cursor_color.setAlpha(alpha)
            painter.setPen(QPen(cursor_color, width))
            painter.drawLine(int(x), int(y1), int(x), int(y2))

    def draw_staff(self, painter, track_data, staff_y, start_x, drawable_width, is_two_track_mode):
        beats_per_measure = track_data.get('beats_per_measure', 4.0)
        total_beats = track_data.get('total_beats', 8.0)
        
        painter.save()
        
        if is_two_track_mode:
            label_color = COLORS['primary'] if staff_y < self.height() / 2 else COLORS['success']
            painter.setFont(QFont("Segoe UI", 18, QFont.Weight.Bold))
            painter.setPen(label_color)
            label = "L" if staff_y < self.height() / 2 else "R"
            
            label_bg = QColor(label_color)
            label_bg.setAlpha(30)
            painter.setBrush(label_bg)
            painter.drawEllipse(QPointF(30, staff_y), 20, 20)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            
            painter.drawText(QRectF(10, staff_y - 15, 40, 30), Qt.AlignmentFlag.AlignCenter, label)
        
        painter.setFont(QFont("Segoe UI", 12, QFont.Weight.Medium))
        painter.setPen(COLORS['text_secondary'])
        ts_text = f"{track_data.get('numerator', 4)}\n─\n{track_data.get('denominator', 4)}"
        painter.drawText(QRectF(5, staff_y - 10, 50, 35), Qt.AlignmentFlag.AlignCenter, ts_text)
        painter.restore()
        
        painter.setPen(QPen(COLORS['staff_line'], 2))
        painter.drawLine(start_x, int(staff_y), start_x + drawable_width, int(staff_y))
        
        if total_beats > 0:
            for i in range(1, int(total_beats) + 1):
                x = start_x + (i / total_beats) * drawable_width
                is_measure_line = (i > 0 and i % beats_per_measure == 0) and i != total_beats
                if is_measure_line:
                    painter.setPen(QPen(COLORS['text_secondary'], 2))
                    painter.drawLine(int(x), int(staff_y - 15), int(x), int(staff_y + 15))
                else:
                    painter.setPen(QPen(COLORS['text_muted'], 1, Qt.PenStyle.DotLine))
                    painter.drawLine(int(x), int(staff_y - 8), int(x), int(staff_y + 8))
        
        for item in track_data.get('items', []):
            self.draw_item(painter, item, staff_y, start_x, drawable_width, total_beats)

    def draw_item(self, painter, item, staff_y, start_x, drawable_width, total_beats_on_track):
        if total_beats_on_track <= 0: return
        x = start_x + (item['beat'] / total_beats_on_track) * drawable_width
        width = (item['duration'] / total_beats_on_track) * drawable_width
        item_rect = QRectF(x, staff_y - 30, width, 60)
        
        painter.save()
        if item.get('class') == 'note':
            guide_circle_radius = 6
            guide_circle_center_x = item_rect.left()
            guide_circle_center_y = staff_y
            
            painter.setBrush(COLORS['primary'])
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(QPointF(guide_circle_center_x, guide_circle_center_y), guide_circle_radius, guide_circle_radius)

            if item.get('is_lit', False):
                for radius, alpha in [(40, 20), (30, 40), (20, 60)]:
                    glow_color = QColor(COLORS['note_glow'])
                    glow_color.setAlpha(alpha)
                    painter.setBrush(glow_color)
                    painter.setPen(Qt.PenStyle.NoPen)
                    painter.drawEllipse(QPointF(guide_circle_center_x, guide_circle_center_y), radius, radius)
                
                painter.setBrush(COLORS['note_glow'])
                painter.setPen(QPen(COLORS['primary'].lighter(150), 3))
                painter.drawRoundedRect(item_rect.adjusted(-4, -4, 4, 4), 10, 10)
            
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(QPen(COLORS['primary'], 2))
            painter.drawRoundedRect(item_rect, 8, 8)
        else:
            painter.setBrush(COLORS['rest_bg'])
            painter.setPen(QPen(COLORS['border'], 1))
            painter.drawRoundedRect(item_rect, 8, 8)
        painter.restore()
        
        image_to_draw = self.item_images.get(item['type'])
        if image_to_draw:
            draw_y = item_rect.top() + (item_rect.height() - image_to_draw.height()) / 2
            draw_point = QPointF(item_rect.left() + 8, draw_y)
            painter.drawPixmap(draw_point, image_to_draw)
            
            if item.get('dotted', False):
                dot_x, dot_y = draw_point.x() + image_to_draw.width() + 6, staff_y + 18
                painter.save()
                painter.setBrush(COLORS['text_primary']); painter.setPen(Qt.PenStyle.NoPen)
                painter.drawEllipse(QPointF(dot_x, dot_y), 4, 4)
                painter.restore()
        else:
            painter.setPen(COLORS['text_primary'])
            painter.setFont(QFont("Segoe UI", 10, QFont.Weight.Medium))
            painter.drawText(item_rect, Qt.AlignmentFlag.AlignCenter, ALL_DURATIONS[item['type']]['name'])

# --- モダンUIの楽譜表示ウィンドウ ---
class EditorWindow(QMainWindow):
    def __init__(self, template_data, main_window, item_images, is_demo=False, parent=None):
        super().__init__(parent)
        self.main_window = main_window
        self.is_demo = is_demo
        self.template_data = template_data
        title = "🎼 お手本再生" if is_demo else "🥁 練習中"
        self.setWindowTitle(title)
        self.resize(1300, 450)
        self.setStyleSheet(f"QMainWindow {{ background-color: {COLORS['background'].name()}; color: {COLORS['text_primary'].name()}; }}")
        
        try:
            screen = QApplication.screenAt(QCursor.pos())
            if not screen: screen = QApplication.primaryScreen()
            center_point = screen.availableGeometry().center()
            self.move(int(center_point.x() - self.width() / 2), int(center_point.y() - self.height() / 2))
        except Exception: self.setGeometry(150, 150, 1300, 450)
        
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        header_widget = QWidget(); header_widget.setFixedHeight(60)
        header_widget.setStyleSheet(f"background: {COLORS['surface'].name()}; border-bottom: 1px solid {COLORS['border'].name()};")
        header_layout = QHBoxLayout(header_widget); header_layout.setContentsMargins(20, 0, 20, 0)
        
        title_label = QLabel(title); title_label.setFont(QFont("Segoe UI", 20, QFont.Weight.Bold))
        title_color_key = 'success' if is_demo else 'primary'
        title_label.setStyleSheet(f"color: {COLORS[title_color_key].name()}; background: transparent;")
        header_layout.addWidget(title_label); header_layout.addStretch()

        self.stop_button = ModernButton("⏹️ " + ("再生停止" if is_demo else "練習中止"), "danger")
        self.stop_button.clicked.connect(self.force_stop_practice)
        header_layout.addWidget(self.stop_button)
        layout.addWidget(header_widget)
        
        self.rhythm_widget = EditorRhythmWidget(item_images, self)
        layout.addWidget(self.rhythm_widget)
        self.rhythm_widget.set_data(copy.deepcopy(template_data))
        
        # --- カウントダウン機能の追加 ---
        self.countdown_label = QLabel(self)
        self.countdown_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.countdown_label.setStyleSheet(f"color: {COLORS['text_primary'].name()}; background-color: rgba(248, 249, 250, 0.8); border-radius: 20px;")
        self.countdown_label.setFont(QFont("Segoe UI", 150, QFont.Weight.Bold))
        
        if self.is_demo:
            self.countdown_label.hide()
            self.start_actual_playback()
        else:
            self.countdown_start_time = 0
            self.countdown_timer = QTimer(self)
            self.countdown_timer.timeout.connect(self.update_countdown)
            self.countdown_timer.start(50)

    def update_countdown(self):
        if self.countdown_start_time == 0:
            self.countdown_start_time = time.perf_counter()
            self.main_window.play_countdown_sound()

        bpm = self.template_data['top'].get('bpm', 120)
        beat_duration_ms = 60000.0 / bpm
        elapsed_ms = (time.perf_counter() - self.countdown_start_time) * 1000
        
        current_text = self.countdown_label.text()
        new_text = ""
        
        if elapsed_ms < beat_duration_ms:
            new_text = "3"
        elif elapsed_ms < beat_duration_ms * 2:
            new_text = "2"
        elif elapsed_ms < beat_duration_ms * 3:
            new_text = "1"
        elif elapsed_ms < beat_duration_ms * 4:
            new_text = "START!"
        else:
            self.countdown_timer.stop()
            self.countdown_label.hide()
            self.start_actual_playback()
            return

        # --- ここから変更点 ---
        # テキストの内容に応じてフォントサイズを動的に変更する
        if new_text == "START!":
            # "START!" の場合はフォントを小さくする
            self.countdown_label.setFont(QFont("Segoe UI", 70, QFont.Weight.Bold))
        else:
            # 数字の場合は元の大きいフォントを維持する
            self.countdown_label.setFont(QFont("Segoe UI", 150, QFont.Weight.Bold))
        # --- ここまで変更点 ---
            
        if current_text != new_text and new_text in ["2", "1", "START!"]:
            self.main_window.play_countdown_sound()
            
        self.countdown_label.setText(new_text)


    def start_actual_playback(self):
        self.main_window.start_time = time.perf_counter()
        self.main_window.begin_real_recording()  # MainWindowに録音開始を通知
        self.rhythm_widget.start_playback()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        label_size = min(self.width(), self.height()) * 0.7
        self.countdown_label.setGeometry(
            int((self.width() - label_size) / 2),
            int((self.height() - label_size) / 2),
            int(label_size),
            int(label_size)
        )

    def force_stop_practice(self):
        self.close()

    def closeEvent(self, event):
        self.rhythm_widget.stop_playback()
        if hasattr(self, 'countdown_timer'): self.countdown_timer.stop()
        if self.main_window.editor_window is self:
            self.main_window.finish_performance(is_demo=self.is_demo, force_stop=True)
        event.accept()

    def get_elapsed_time(self): return self.main_window.get_elapsed_time()
    def play_note_sound(self): self.main_window.play_note_sound()
    def play_metronome_sound(self, is_accent): self.main_window.play_metronome_sound(is_accent)

# --- アプリケーション実行 ---
if __name__ == "__main__":
    app = QApplication.instance(); 
    if app is None: app = QApplication(sys.argv)
    if not pygame.get_init(): pygame.init()
    win = MainWindow(); win.show(); app.exec()