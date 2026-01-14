import sys
import os
import json
import time
import copy
import threading
import signal
import importlib
import inspect
import io
import wave
import datetime  # ★ タイムスタンプ用にインポート
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QPushButton, QWidget, QLabel, QVBoxLayout, QHBoxLayout,
    QFileDialog, QMessageBox, QDialog, QDialogButtonBox, QSlider, QComboBox, QFormLayout,
    QGraphicsDropShadowEffect, QScrollArea, QPlainTextEdit
)
from PyQt6.QtCore import Qt, QTimer, QRectF, QPointF, QObject, pyqtSignal, QThread, QPropertyAnimation, QEasingCurve, pyqtProperty, pyqtSlot
from PyQt6.QtGui import (
    QPainter, QColor, QFont, QPen, QPixmap, QLinearGradient, QCursor, QPolygonF, QRadialGradient, QBrush
)
import mido
import pygame

# --- オプショナルなライブラリのインポート ---
try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

try:
    import numpy as np
    NUMPY_AVAILABLE = True
except ImportError:
    NUMPY_AVAILABLE = False

# --- ★ロボット制御モジュールをここで読み込む★ ---
try:
    import robot_control_module_v3
    ROBOTS_AVAILABLE = True
except (ImportError, ModuleNotFoundError):
    print("警告: robot_control_module_v3.pyが見つからないため、ロボット機能は無効です。")
    ROBOTS_AVAILABLE = False

# --- ★ ui_theme.pyから読み込む ★ ---
try:
    from ui_theme import COLORS
except ImportError:
    print("エラー: ui_theme.pyが見つかりません。")
    # フォールバック用の基本的な色定義
    COLORS = {'background': QColor(248, 249, 250), 'surface': QColor(255, 255, 255), 'primary': QColor(59, 130, 246), 'text_primary': QColor(33, 37, 41), 'text_secondary': QColor(108, 117, 125), 'border': QColor(222, 226, 230), 'danger': QColor(220, 53, 69), 'success': QColor(25, 135, 84), 'warning': QColor(255, 193, 7), 'accent': QColor(102, 16, 242), 'text_muted': QColor(173, 181, 189), 'surface_light': QColor(241, 243, 245), 'note_glow': QColor(59, 130, 246, 80), 'rest_bg': QColor(233, 236, 239, 150), 'staff_line': QColor(173, 181, 189), 'cursor': QColor(214, 51, 132), 'perfect': QColor(255, 193, 7), 'great': QColor(25, 135, 84), 'good': QColor(59, 130, 246), 'miss': QColor(108, 117, 125), 'extra': QColor(220, 53, 69), 'primary_dark': QColor(37, 99, 235), 'success_dark': QColor(21, 115, 71), 'danger_dark': QColor(187, 45, 59), 'warning_dark': QColor(217, 164, 6), 'glow': QColor(59, 130, 246, 30)}


# --- ★ コマンドモニターをインポート (command_monitor.py から) ★ ---
try:
    from command_monitor import CommandVizWindow
    MONITOR_AVAILABLE = True
except ImportError:
    print("警告: command_monitor.pyが見つかりません。モニター機能は無効です。")
    MONITOR_AVAILABLE = False


# --- アプリ設定定数 ---
PAD_MAPPING = {'left': [47, 56], 'right': [48, 29]}; VELOCITY_THRESHOLD = 30; LIT_DURATION = 150; NUM_MEASURES = 2
JUDGEMENT_WINDOWS = {'perfect': 55, 'great': 90, 'good': 110}; DROPPED_THRESHOLD = 120
NOTE_DURATIONS = {'whole': {'duration': 4.0, 'name': "全音符"}, 'half': {'duration': 2.0, 'name': "2分音符"}, 'quarter': {'duration': 1.0, 'name': "4分音符"}, 'eighth': {'duration': 0.5, 'name': "8分音符"}, 'sixteenth': {'duration': 0.25, 'name': "16分音符"}}
REST_DURATIONS = {'quarter_rest': {'duration': 1.0, 'name': "4分休符"}, 'eighth_rest': {'duration': 0.5, 'name': "8分休符"}, 'sixteenth_rest': {'duration': 0.25, 'name': "16分休符"}}
ALL_DURATIONS = {**NOTE_DURATIONS, **REST_DURATIONS}
NOTE_IMAGE_FILES = {'whole': 'images/whole_note.PNG', 'half': 'images/half_note.PNG', 'quarter': 'images/quarter_note.PNG', 'eighth': 'images/eighth_note.PNG', 'sixteenth':'images/sixteenth_note.PNG'}
REST_IMAGE_FILES = {'quarter_rest': 'images/quarter_rest.PNG', 'eighth_rest': 'images/eighth_rest.PNG', 'sixteenth_rest': 'images/sixteenth_rest.PNG'}

def resource_path(relative_path):
    try: base_path = sys._MEIPASS
    except Exception: base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_path, relative_path)

def load_controllers():
    controllers = {}
    script_dir = os.path.dirname(os.path.abspath(__file__))
    controller_dir = os.path.join(script_dir, "controllers")
    if not os.path.exists(controller_dir): return {}
    if controller_dir not in sys.path: sys.path.insert(0, controller_dir)
    if script_dir not in sys.path: sys.path.insert(0, script_dir)
    try:
        from controllers.base_controller import BaseEntrainmentController
        for filename in os.listdir(controller_dir):
            if filename.endswith(".py") and filename not in ["base_controller.py", "__init__.py"]:
                module_name = f"controllers.{filename[:-3]}"
                try:
                    module = importlib.import_module(module_name)
                    for name, obj in inspect.getmembers(module, inspect.isclass):
                        if issubclass(obj, BaseEntrainmentController) and obj is not BaseEntrainmentController:
                            try:
                                instance = obj(None, 0); controllers[instance.name] = obj
                            except Exception as e: print(f"エラー: コントローラー {name} のインスタンス化に失敗: {e}")
                except ImportError as e: print(f"エラー: コントローラーモジュール {module_name} のインポートに失敗: {e}")
    except ImportError as e: print(f"エラー: BaseEntrainmentControllerをインポートできませんでした。詳細: {e}")
    return controllers

class ModernButton(QPushButton):
    def __init__(self, text, button_type="primary", parent=None):
        super().__init__(text, parent)
        self.button_type = button_type; self._glow_opacity = 0.0
        color_map = {"primary": (COLORS['primary'], COLORS['primary_dark']),"success": (COLORS['success'], COLORS['success_dark']),"danger": (COLORS['danger'], COLORS['danger_dark']),"warning": (COLORS['warning'], COLORS['warning_dark'])}
        self.bg_color, self.hover_color = color_map.get(button_type, (COLORS['primary'], COLORS['primary_dark']))
        shadow = QGraphicsDropShadowEffect(); shadow.setBlurRadius(15); shadow.setColor(QColor(0, 0, 0, 60)); shadow.setOffset(0, 4)
        self.setGraphicsEffect(shadow)
        self.setMinimumHeight(44); self.setCursor(Qt.CursorShape.PointingHandCursor); self.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        self.update_style()
        self.glow_animation = QPropertyAnimation(self, b"glow_opacity"); self.glow_animation.setDuration(150); self.glow_animation.setEasingCurve(QEasingCurve.Type.OutCubic)
    @pyqtProperty(float)
    def glow_opacity(self): return self._glow_opacity
    @glow_opacity.setter
    def glow_opacity(self, value): self._glow_opacity = value; self.update_style()
    def update_style(self):
        self.setStyleSheet(f"""QPushButton {{ background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 {self.bg_color.name()}, stop:1 {self.bg_color.darker(110).name()}); color: white; border: 1px solid {self.bg_color.lighter(120).name()}; border-radius: 12px; padding: 12px 24px; font-weight: bold;}} QPushButton:hover {{background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 {self.hover_color.name()}, stop:1 {self.hover_color.darker(110).name()}); border: 1px solid {self.hover_color.lighter(130).name()};}} QPushButton:pressed {{background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 {self.bg_color.darker(120).name()}, stop:1 {self.bg_color.darker(140).name()});}} QPushButton:disabled {{background: {COLORS['text_muted'].name()}; border: 1px solid {COLORS['text_muted'].darker(110).name()}; color: {COLORS['text_muted'].lighter(150).name()};}}""")
    def enterEvent(self, event): self.glow_animation.setStartValue(self._glow_opacity); self.glow_animation.setEndValue(1.0); self.glow_animation.start(); super().enterEvent(event)
    def leaveEvent(self, event): self.glow_animation.setStartValue(self._glow_opacity); self.glow_animation.setEndValue(0.0); self.glow_animation.start(); super().leaveEvent(event)

class ModernLabel(QLabel):
    def __init__(self, text, font_size=10, weight=QFont.Weight.Normal, color_key='text_secondary', parent=None):
        super().__init__(text, parent)
        self.set_style(font_size, weight, color_key)

    def set_style(self, font_size, weight, color_key):
        self.setFont(QFont("Segoe UI", font_size, weight))
        self.setStyleSheet(f"color: {COLORS[color_key].name()}; background: transparent;")

class GlowingWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent); self._glow_opacity = 0.0
        self.glow_animation = QPropertyAnimation(self, b"glow_opacity"); self.glow_animation.setDuration(2000); self.glow_animation.setEasingCurve(QEasingCurve.Type.InOutSine)
        self.glow_animation.setLoopCount(-1); self.glow_animation.setStartValue(0.3); self.glow_animation.setEndValue(1.0)
    @pyqtProperty(float)
    def glow_opacity(self): return self._glow_opacity
    @glow_opacity.setter
    def glow_opacity(self, value): self._glow_opacity = value; self.update()
    def start_glow(self): self.glow_animation.start()
    def stop_glow(self): self.glow_animation.stop(); self._glow_opacity = 0.0; self.update()

class AiFeedbackWorker(QObject):
    finished = pyqtSignal(str)
    def __init__(self, main_window_ref): super().__init__(); self.main_window = main_window_ref
    def run(self): feedback = self.main_window.generate_ai_feedback_logic(); self.finished.emit(feedback)

class SettingsDialog(QDialog):
    def __init__(self, current_settings, parent=None):
        super().__init__(parent)
        self.setWindowTitle("練習設定")
        self.setMinimumWidth(400)
        self.setStyleSheet(f"""QDialog{{background:{COLORS['background'].name()};color:{COLORS['text_primary'].name()};border:1px solid {COLORS['border'].name()};border-radius:15px;}}QSlider::groove:horizontal{{border:1px solid {COLORS['border'].name()};height:8px;background:{COLORS['background'].name()};border-radius:4px;}}QSlider::handle:horizontal{{background:{COLORS['primary'].name()};border:1px solid {COLORS['primary'].lighter(120).name()};width:18px;margin:-2px 0;border-radius:9px;}}QSlider::sub-page:horizontal{{background:{COLORS['primary'].name()};border-radius:4px;}}QComboBox{{background:{COLORS['surface'].name()};color:{COLORS['text_primary'].name()};border:1px solid {COLORS['border'].name()};border-radius:8px;padding:8px;font-weight:bold;}}QComboBox:hover{{border:1px solid {COLORS['primary'].name()};}}QComboBox::drop-down{{border:none;width:30px;}}QComboBox::down-arrow{{image:none;border:5px solid transparent;border-top:8px solid {COLORS['text_primary'].name()};margin-right:10px;}}QLabel{{color:{COLORS['text_secondary'].name()};font-weight:bold;}}""")
        
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
        
        self.blinking_toggle_button = ModernButton("", "success")
        self.blinking_toggle_button.setMinimumHeight(36)
        self.blinking_toggle_button.clicked.connect(self.toggle_blinking)
        
        self.guideline_toggle_button = ModernButton("", "success")
        self.guideline_toggle_button.setMinimumHeight(36)
        self.guideline_toggle_button.clicked.connect(self.toggle_guide_line)

        # ★ レイアウト切り替えボタンを追加
        self.layout_toggle_button = ModernButton("", "primary")
        self.layout_toggle_button.setMinimumHeight(36)
        self.layout_toggle_button.clicked.connect(self.toggle_layout)

        self.monitor_toggle_button = ModernButton("", "danger")
        self.monitor_toggle_button.setMinimumHeight(36)
        self.monitor_toggle_button.clicked.connect(self.toggle_monitor)
        
        self.update_metronome_button_style()
        self.update_guide_button_style()
        self.update_blinking_button_style()
        self.update_guide_line_button_style()
        self.update_layout_button_style() 
        self.update_monitor_button_style()

        self.level_combo = QComboBox()
        self.levels = {"p100": "PERFECT 100%", "p50_g100": "PERFECT 50%以上 & GREAT含め100%", "g100": "GREAT以上 100%"}
        for key, text in self.levels.items(): self.level_combo.addItem(text, userData=key)
        
        current_level_key = self.settings.get('practice_level', 'p100')
        if current_level_key in self.levels: self.level_combo.setCurrentIndex(list(self.levels.keys()).index(current_level_key))
        
        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        self.button_box.setStyleSheet(f"""QPushButton{{background:{COLORS['primary'].name()};color:white;border:1px solid {COLORS['primary'].lighter(120).name()};border-radius:8px;padding:8px 16px;font-weight:bold;min-width:80px;}}QPushButton:hover{{background:{COLORS['primary_dark'].name()};}}""")
        
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
        main_layout.addWidget(self.blinking_toggle_button)
        main_layout.addWidget(self.guideline_toggle_button)
        main_layout.addWidget(self.layout_toggle_button)
        main_layout.addWidget(self.monitor_toggle_button) 
        main_layout.addStretch()
        main_layout.addWidget(self.button_box)

    def toggle_metronome(self): 
        self.settings['metronome_on'] = not self.settings.get('metronome_on', False)
        self.update_metronome_button_style()
        
    def update_metronome_button_style(self):
        if self.settings.get('metronome_on', False): 
            self.metronome_toggle_button.setText("🎵 メトロノーム : ON")
            self.metronome_toggle_button.button_type = "success"
        else: 
            self.metronome_toggle_button.setText("🔇 メトロノーム : OFF")
            self.metronome_toggle_button.button_type = "danger"
        self.metronome_toggle_button.bg_color = COLORS['success'] if self.settings.get('metronome_on', False) else COLORS['danger']
        self.metronome_toggle_button.hover_color = COLORS['success_dark'] if self.settings.get('metronome_on', False) else COLORS['danger_dark']
        self.metronome_toggle_button.update_style()
        
    def toggle_guide(self): 
        self.settings['guide_cue_on'] = not self.settings.get('guide_cue_on', False)
        self.update_guide_button_style()
        
    def update_guide_button_style(self):
        if self.settings.get('guide_cue_on', False): 
            self.guide_toggle_button.setText("🔊 ガイド音 : ON")
            self.guide_toggle_button.button_type = "success"
        else: 
            self.guide_toggle_button.setText("🔇 ガイド音 : OFF")
            self.guide_toggle_button.button_type = "danger"
        self.guide_toggle_button.bg_color = COLORS['success'] if self.settings.get('guide_cue_on', False) else COLORS['danger']
        self.guide_toggle_button.hover_color = COLORS['success_dark'] if self.settings.get('guide_cue_on', False) else COLORS['danger_dark']
        self.guide_toggle_button.update_style()

    def toggle_blinking(self): 
        self.settings['score_blinking_on'] = not self.settings.get('score_blinking_on', True)
        self.update_blinking_button_style()

    def update_blinking_button_style(self):
        if self.settings.get('score_blinking_on', True):
            self.blinking_toggle_button.setText("✨ 楽譜の点滅 : ON")
            self.blinking_toggle_button.button_type = "success"
            self.blinking_toggle_button.bg_color = COLORS['success']
            self.blinking_toggle_button.hover_color = COLORS['success_dark']
        else:
            self.blinking_toggle_button.setText("🚫 楽譜の点滅 : OFF")
            self.blinking_toggle_button.button_type = "danger"
            self.blinking_toggle_button.bg_color = COLORS['danger']
            self.blinking_toggle_button.hover_color = COLORS['danger_dark']
        self.blinking_toggle_button.update_style()

    def toggle_guide_line(self):
        self.settings['guide_line_on'] = not self.settings.get('guide_line_on', True)
        self.update_guide_line_button_style()

    def update_guide_line_button_style(self):
        if self.settings.get('guide_line_on', True):
            self.guideline_toggle_button.setText("┃ ガイド線 : ON")
            self.guideline_toggle_button.button_type = "success"
            self.guideline_toggle_button.bg_color = COLORS['success']
            self.guideline_toggle_button.hover_color = COLORS['success_dark']
        else:
            self.guideline_toggle_button.setText("┃ ガイド線 : OFF")
            self.guideline_toggle_button.button_type = "danger"
            self.guideline_toggle_button.bg_color = COLORS['danger']
            self.guideline_toggle_button.hover_color = COLORS['danger_dark']
        self.guideline_toggle_button.update_style()
        
    # ★ レイアウト切り替え用メソッドを追加
    def toggle_layout(self):
        current_layout = self.settings.get('score_layout', 'vertical')
        self.settings['score_layout'] = 'horizontal' if current_layout == 'vertical' else 'vertical'
        self.update_layout_button_style()

    # ★ レイアウトボタンスタイル更新メソッドを追加
    def update_layout_button_style(self):
        if self.settings.get('score_layout', 'vertical') == 'vertical':
            self.layout_toggle_button.setText("📊 楽譜レイアウト : 縦")
            self.layout_toggle_button.button_type = "primary"
            self.layout_toggle_button.bg_color = COLORS['primary']
            self.layout_toggle_button.hover_color = COLORS['primary_dark']
        else:
            self.layout_toggle_button.setText("📊 楽譜レイアウト : 横")
            self.layout_toggle_button.button_type = "success"
            self.layout_toggle_button.bg_color = COLORS['success']
            self.layout_toggle_button.hover_color = COLORS['success_dark']
        self.layout_toggle_button.update_style()
        
    def accept(self):
        self.settings['drum_volume'] = self.drum_volume_slider.value() / 100.0
        self.settings['metronome_volume'] = self.metronome_volume_slider.value() / 100.0
        self.settings['guide_cue_volume'] = self.guide_volume_slider.value() / 100.0
        self.settings['practice_level'] = self.level_combo.currentData()
        # 'score_layout' は toggle_layout で設定済みなので、そのまま accept する
        super().accept()

    def toggle_monitor(self):
        self.settings['command_monitor_on'] = not self.settings.get('command_monitor_on', False)
        self.update_monitor_button_style()

    def update_monitor_button_style(self):
        if self.settings.get('command_monitor_on', False):
            self.monitor_toggle_button.setText("👁️ コマンドモニター : ON")
            self.monitor_toggle_button.button_type = "success"
            self.monitor_toggle_button.bg_color = COLORS['success']
            self.monitor_toggle_button.hover_color = COLORS['success_dark']
        else:
            self.monitor_toggle_button.setText("🚫 コマンドモニター : OFF")
            self.monitor_toggle_button.button_type = "danger"
            self.monitor_toggle_button.bg_color = COLORS['danger']
            self.monitor_toggle_button.hover_color = COLORS['danger_dark']
        self.monitor_toggle_button.update_style()
        
    @staticmethod
    def get_settings(parent, current_settings):
        dialog = SettingsDialog(current_settings, parent)
        if dialog.exec() == QDialog.DialogCode.Accepted: 
            return dialog.settings
        return None

class FileSelectionDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("ファイルを選択")
        self.setMinimumSize(600, 500)
        self.selected_filepath = None

        # スタイリング
        self.setStyleSheet(f"""
            QDialog {{ background-color: {COLORS['background'].name()}; }}
            QScrollArea {{ border: none; }}
        """)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(15)

        title_label = ModernLabel("ファイルを選択してください", 16, QFont.Weight.Bold, 'text_primary')
        main_layout.addWidget(title_label)

        # スクロールエリアのセットアップ
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setStyleSheet(f"background-color: {COLORS['surface'].name()}; border: 1px solid {COLORS['border'].name()}; border-radius: 10px;")
        
        scroll_content = QWidget()
        self.files_layout = QVBoxLayout(scroll_content)
        self.files_layout.setContentsMargins(15, 15, 15, 15)
        self.files_layout.setSpacing(10)
        
        self.populate_files() # ファイルリストを読み込む
        self.files_layout.addStretch()

        scroll_area.setWidget(scroll_content)
        main_layout.addWidget(scroll_area)

        # キャンセルボタン
        cancel_button = ModernButton("キャンセル", "danger")
        cancel_button.clicked.connect(self.reject)
        
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        button_layout.addWidget(cancel_button)
        main_layout.addLayout(button_layout)

    def populate_files(self):
        target_dir = 'C:\\卒研\\music'
        if not os.path.exists(target_dir):
            error_label = ModernLabel(f"ディレクトリが見つかりません:\n{target_dir}", 12, weight=QFont.Weight.Bold, color_key='danger')
            error_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.files_layout.addWidget(error_label)
            return

        try:
            json_files = [f for f in os.listdir(target_dir) if f.endswith('.json')]
        except Exception as e:
            error_label = ModernLabel(f"ファイルリストの取得に失敗しました:\n{e}", 12, weight=QFont.Weight.Bold, color_key='danger')
            error_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.files_layout.addWidget(error_label)
            return
        
        if not json_files:
            no_files_label = ModernLabel("このフォルダには .json ファイルが見つかりませんでした。", 12, color_key='text_muted')
            no_files_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.files_layout.addWidget(no_files_label)
            return

        for filename in sorted(json_files):
            filepath = os.path.join(target_dir, filename)
            btn = ModernButton(filename.replace('.json', ''), "primary")
            btn.clicked.connect(lambda checked, p=filepath: self.on_file_selected(p))
            self.files_layout.addWidget(btn)

    def on_file_selected(self, filepath):
        self.selected_filepath = filepath
        self.accept()

    @staticmethod
    def get_file(parent=None):
        dialog = FileSelectionDialog(parent)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            return dialog.selected_filepath
        return None


# ★★★ ログウィンドウ (タイムスタンプ付き) ★★★
class LogWindow(QDialog):
    """
    ログメッセージを表示するための専用ダイアログ
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("実行ログ (時系列)")
        self.setGeometry(50, 100, 800, 400) # (x, y, width, height)
        
        self.log_area = QPlainTextEdit(self)
        self.log_area.setReadOnly(True)
        self.log_area.setStyleSheet(f"""
            QPlainTextEdit {{
                background-color: {COLORS['surface_light'].name()};
                color: {COLORS['text_primary'].name()};
                font-family: Consolas, 'Courier New', monospace;
                font-size: 11px;
                border: 1px solid {COLORS['border'].name()};
                border-radius: 8px;
            }}
        """)
        
        layout = QVBoxLayout(self)
        layout.addWidget(self.log_area)
        self.setLayout(layout)
        self.setStyleSheet(f"QDialog {{ background-color: {COLORS['background'].name()}; }}")

    @pyqtSlot(str)
    def append_log(self, message):
        """
        RobotManagerからのlog_messageシグナルを受け取るスロット
        """
        # 現在時刻を取得し、ミリ秒までフォーマット
        now = datetime.datetime.now()
        timestamp = now.strftime("%H:%M:%S") + f".{now.microsecond // 1000:03d}"
        
        # ログメッセージにタイムスタンプと区切り文字を追加
        formatted_message = f"{timestamp} | {message}"
        
        self.log_area.appendPlainText(formatted_message) 
        self.log_area.verticalScrollBar().setValue(
            self.log_area.verticalScrollBar().maximum()
        )

    def closeEvent(self, event):
        """
        ウィンドウが閉じられたときに非表示にする（アプリは終了させない）
        """
        event.ignore() # 閉じるイベントを無視
        self.hide()      # 代わりに非表示にする

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Rhythm Interface")
        self.resize(1400, 800)        
        self.setStyleSheet(f"QMainWindow {{ background-color: {COLORS['background'].name()}; color: {COLORS['text_primary'].name()}; }}")
        self.settings = {
            'drum_volume': 0.8, 'metronome_volume': 0.3, 'metronome_on': True, 
            'guide_cue_volume': 0.5, 'guide_cue_on': False, 'practice_level': 'p100',
            'score_blinking_on': True, 'guide_line_on': True,
            'score_layout': 'horizontal',
            'command_monitor_on': False
        }
        self.state = "waiting" # waiting, result, または experiment_...
        
        # ★ 修正点: デモ再生からの復帰先を記憶する変数を追加
        self._demo_return_state = "waiting"
        self.experiment_sets = [f"test{i}.json" for i in range(1, 10)] # test1.json から test9.json
        self.current_experiment_set_index = 0
        self.current_experiment_step = 0 # 0: test1, 1: practice, 2: test2
        
        # 各ステップの設定 (注: 色設定は ui_theme.py に 'danger_dark' などが存在することを前提とします)
        self.experiment_steps_config = [
            {
                'title': "テスト (1/3)",
                'description': "最初にお手本を聞き、準備ができたら「テスト開始」ボタンを押してください。\nロボットは動作しません。",
                'button_text': "▶️ テスト (1/3) 開始",
                'is_perfect_mode': False,
                'force_robot': False,
                'force_controller_name': None,
                'max_loops': 1,
                'color': COLORS['danger'],
                'color_dark': COLORS.get('danger_dark', COLORS['danger'].darker(110))
            },
            # 変更後
            {
                'title': "練習 (2/3)",
                'description': "次に、ロボットのガイドと一緒に練習します。\n練習時間は1分間です。時間になるまで自動でループします。\n準備ができたら「練習開始」ボタンを押してください。", # ★ 説明文を変更
                'button_text': "💪 練習 (2/3) 開始",
                'is_perfect_mode': True, # ループさせるために True のまま
                'force_robot': True,
                'force_controller_name': "線形補間コントローラー", # 注意: この名前のコントローラーが存在する必要があります
                'max_loops': float('inf'), # ★ 無限ループに変更 (時間で止まるため)
                'color': COLORS['warning'],
                'color_dark': COLORS.get('warning_dark', COLORS['warning'].darker(110))
            },
            {
                'title': "テスト (3/3)",
                'description': "最後に、もう一度ロボットなしで演奏を記録します。\n準備ができたら「テスト開始」ボタンを押してください。",
                'button_text': "▶️ テスト (3/3) 開始",
                'is_perfect_mode': False,
                'force_robot': False,
                'force_controller_name': None,
                'max_loops': 1,
                'color': COLORS['danger'],
                'color_dark': COLORS.get('danger_dark', COLORS['danger'].darker(110))
            }
        ]
        # ★★★ 実験モード設定ここまで ★★★

        self.experiment_data = {}
        self.experiment_next_state = None
        self.practice_loop_count_max = float('inf')
        self.practice_start_time = 0 # ★ 練習開始時刻 (is_perfect_mode用)

        self.recorded_hits, self.judgements = [], []
        self.template_score, self.editor_window = None, None
        self.ai_feedback_text = ""
        self.result_stats, self.total_notes, self.judged_notes = {}, 0, set()
        self.thread, self.worker = None, None
        self.practice_loop_count = 0
        self.is_perfect_mode = False
        self.perfect_practice_history, self.judgement_history = [], []
        self.note_sound, self.metronome_click, self.metronome_accent_click, self.countdown_sound, self.snare_sound, self.tom_sound = None, None, None, None, None, None
        self.controller_classes = {}
        self.active_controller = None
        
        self.viz_window = None
        if MONITOR_AVAILABLE:
            self.viz_window = CommandVizWindow(self)
        
        self.silent_wav_buffer = None
        
        self.log_window = LogWindow(self) 
        
        if ROBOTS_AVAILABLE:
            self.robot_manager = robot_control_module_v3.RobotManager(self)
            self.robot_manager.log_message.connect(self.log_window.append_log)
            if hasattr(self.robot_manager, 'command_sent'):
                    self.robot_manager.command_sent.connect(self.on_robot_command_sent)
        else:
            self.robot_manager = None

        self.init_sounds()
        self.item_images = {}
        self.init_images()
        self.init_ui() # UI初期化
        self.init_midi()
        self.q_timer = QTimer(self); self.q_timer.timeout.connect(self.update_loop); self.q_timer.start(16)
        
        self.log_window.append_log("アプリケーションが起動しました。")
        if not ROBOTS_AVAILABLE:
            self.log_window.append_log("警告: robot_control_module_v3.py が見つからないため、ロボット機能は無効です。")
        
        self.retry()


    def init_ui(self):
        # (変更なし)
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        outer_layout = QHBoxLayout(main_widget)
        outer_layout.setContentsMargins(0, 0, 0, 0); outer_layout.setSpacing(0)
        
        content_wrapper = QWidget()
        content_layout = QVBoxLayout(content_wrapper)
        content_wrapper.setFixedWidth(1400)
        content_layout.setContentsMargins(30, 30, 30, 30); content_layout.setSpacing(25)

        header_layout = QHBoxLayout()
        title_label = QLabel("Rhythm Training System"); title_label.setFont(QFont("Segoe UI", 28, QFont.Weight.Bold))
        title_label.setStyleSheet(f"color: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {COLORS['primary'].name()}, stop:1 {COLORS['accent'].name()}); background: transparent;")
        header_layout.addWidget(title_label); header_layout.addStretch()
        
        self.btn_settings = QPushButton("⚙️"); self.btn_settings.setFixedSize(50, 50); self.btn_settings.setCursor(Qt.CursorShape.PointingHandCursor); self.btn_settings.setFont(QFont("Segoe UI", 16))
        self.btn_settings.setStyleSheet(f"""QPushButton {{ background: {COLORS['surface_light'].name()}; color: {COLORS['text_primary'].name()}; border: 1px solid {COLORS['border'].name()}; border-radius: 25px; }} QPushButton:hover {{ background: {COLORS['surface'].name()}; border: 1px solid {COLORS['primary'].name()}; }}""")
        self.btn_settings.clicked.connect(self.open_settings_dialog); header_layout.addWidget(self.btn_settings)

        self.btn_toggle_log = QPushButton("📋"); self.btn_toggle_log.setFixedSize(50, 50); self.btn_toggle_log.setCursor(Qt.CursorShape.PointingHandCursor); self.btn_toggle_log.setFont(QFont("Segoe UI", 16))
        self.btn_toggle_log.setStyleSheet(self.btn_settings.styleSheet()); self.btn_toggle_log.setToolTip("実行ログの表示/非表示")
        self.btn_toggle_log.clicked.connect(self.toggle_log_window); header_layout.addWidget(self.btn_toggle_log)
        
        content_layout.addLayout(header_layout)

        self.canvas = AnalyzerCanvas(self)
        content_layout.addWidget(self.canvas, 5)

        self.label_template_file = ModernLabel("ファイルが読み込まれていません", 12, color_key='text_muted'); self.label_template_file.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.label_info = ModernLabel("", 11, color_key='text_primary'); self.label_info.setAlignment(Qt.AlignmentFlag.AlignCenter)
        content_layout.addWidget(self.label_template_file, 1)
        content_layout.addWidget(self.label_info, 1)

        control_panel = QWidget()
        control_wrapper_layout = QVBoxLayout(control_panel)
        control_wrapper_layout.setContentsMargins(0, 0, 0, 0)
        
        self.free_mode_panel = QWidget()
        control_layout = QHBoxLayout(self.free_mode_panel)
        control_layout.setContentsMargins(0, 0, 0, 0); control_layout.setSpacing(15)
        
        self.label_controller = ModernLabel("制御方法:", 11, QFont.Weight.Bold, 'text_secondary')
        self.control_combo = QComboBox(); self.control_combo.setMinimumWidth(180)
        self.control_combo.setStyleSheet(f"""QComboBox {{ background:{COLORS['surface'].name()}; color:{COLORS['text_primary'].name()}; border:1px solid {COLORS['border'].name()}; border-radius:8px; padding: 8px; font-weight:bold; }} QComboBox:hover {{ border:1px solid {COLORS['primary'].name()}; }}""")
        self.controller_classes = load_controllers()
        if not self.controller_classes:
            self.control_combo.addItem("コントローラーが見つかりません"); self.control_combo.setEnabled(False)
        else:
            for name, cls in self.controller_classes.items(): self.control_combo.addItem(name, userData=cls)
        self.control_combo.currentIndexChanged.connect(self.on_controller_changed)
        
        self.btn_load_template = ModernButton("📁 ファイル", "primary"); self.btn_load_template.clicked.connect(self.load_template_file)
        self.btn_demo = ModernButton("👁️ お手本", "success"); self.btn_demo.clicked.connect(self.start_demo_playback)
        self.btn_practice = ModernButton("🥁 練習", "success"); self.btn_practice.clicked.connect(self.start_practice)
        self.btn_perfect_practice = ModernButton("🎯 PERFECT", "warning"); self.btn_perfect_practice.clicked.connect(self.start_perfect_practice)
        self.btn_retry = ModernButton("🔄 再試行", "danger"); self.btn_retry.clicked.connect(self.retry)
        
        self.btn_start_experiment = ModernButton("🧪 実験モード", "accent")
        if 'accent' not in COLORS: COLORS['accent'] = QColor(102, 16, 242)
        self.btn_start_experiment.clicked.connect(self.start_experiment_confirmation)

        control_layout.addStretch()
        control_layout.addWidget(self.label_controller); control_layout.addWidget(self.control_combo); control_layout.addSpacing(25)
        control_layout.addWidget(self.btn_load_template); control_layout.addWidget(self.btn_demo); control_layout.addWidget(self.btn_practice)
        control_layout.addWidget(self.btn_perfect_practice); control_layout.addWidget(self.btn_retry)
        control_layout.addSpacing(10)
        control_layout.addWidget(self.btn_start_experiment)
        control_layout.addStretch()

        self.experiment_panel = QWidget()
        exp_control_layout = QHBoxLayout(self.experiment_panel)
        exp_control_layout.setContentsMargins(0, 0, 0, 0); exp_control_layout.setSpacing(15)

        # ★★★ 汎用的な実験ボタンに修正 ★★★
        self.btn_exp_demo = ModernButton("👁️ お手本再生", "primary"); self.btn_exp_demo.clicked.connect(self.on_experiment_button_clicked)
        self.btn_exp_start = ModernButton("▶️ 開始", "danger"); self.btn_exp_start.clicked.connect(self.on_experiment_button_clicked) # 汎用スタートボタン
        self.btn_exp_next = ModernButton("次へ ➔", "success"); self.btn_exp_next.clicked.connect(self.on_experiment_button_clicked) # 説明画面用
        self.btn_exp_finish = ModernButton("🏠 実験中止", "primary"); self.btn_exp_finish.clicked.connect(self.on_experiment_button_clicked) # 中止/終了ボタン

        exp_control_layout.addStretch()
        exp_control_layout.addWidget(self.btn_exp_demo)
        exp_control_layout.addWidget(self.btn_exp_start)
        exp_control_layout.addWidget(self.btn_exp_next)
        exp_control_layout.addWidget(self.btn_exp_finish)
        exp_control_layout.addStretch()
        
        control_wrapper_layout.addWidget(self.free_mode_panel)
        control_wrapper_layout.addWidget(self.experiment_panel)
        
        content_layout.addWidget(control_panel, 1)

        self.free_mode_widgets = [self.label_controller, self.control_combo, self.btn_load_template, self.btn_demo, self.btn_practice, self.btn_perfect_practice, self.btn_retry, self.btn_start_experiment, self.free_mode_panel]
        # ★ 修正
        self.experiment_widgets = [self.btn_exp_demo, self.btn_exp_start, self.btn_exp_next, self.btn_exp_finish, self.experiment_panel]

        outer_layout.addStretch(1)
        outer_layout.addWidget(content_wrapper)
        outer_layout.addStretch(1)

        self.update_button_states()

    def on_controller_changed(self):
        # (変更なし)
        if not self.template_score: self.active_controller = None; return
        selected_class = self.control_combo.currentData()
        if selected_class:
            try:
                ms_per_beat = 60000.0 / self.template_score['top'].get('bpm', 120)
                self.active_controller = selected_class(copy.deepcopy(self.template_score), ms_per_beat)
                print(f"--- Controller '{self.active_controller.name}' が選択されました。---")
            except Exception as e: print(f"コントローラーのインスタンス化に失敗: {e}"); self.active_controller = None

    def init_sounds(self):
        # (変更なし)
        try:
            if not pygame.mixer.get_init(): pygame.mixer.init(frequency=44100, size=-16, channels=16, buffer=512)
            if NUMPY_AVAILABLE:
                sample_rate = pygame.mixer.get_init()[0]
                silence_array = np.zeros((sample_rate, 2), dtype=np.int16)
                wav_buffer = io.BytesIO()
                with wave.open(wav_buffer, 'wb') as wf:
                    wf.setnchannels(2); wf.setsampwidth(2); wf.setframerate(sample_rate)
                    wf.writeframes(silence_array.tobytes())
                self.silent_wav_buffer = wav_buffer.getvalue()
                self.snare_sound = self._generate_drum_sound(type='snare'); self.tom_sound = self._generate_drum_sound(type='tom')
                self.note_sound = self._generate_sound(880, 100); self.metronome_click = self._generate_sound(1500, 50)
                self.metronome_accent_click = self._generate_sound(2500, 50); self.countdown_sound = self._generate_sound(3000, 200)
                self.apply_settings()
        except Exception as e: QMessageBox.critical(self, "起動時エラー", f"音声初期化エラー:\n{e}")

    def init_images(self):
        # (変更なし)
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
        # (変更なし)
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
        # (変更なし)
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
        # (変更なし)
        try:
            input_ports = mido.get_input_names()
            if not input_ports: raise OSError("MIDI入力ポートが見つかりません。")
            self.inport = mido.open_input(input_ports[0])
            msg = f"✅ MIDIポートに接続: {input_ports[0]}"
            self.label_info.setText(msg); self.log_window.append_log(msg)
        except OSError as e:
            msg = f"❌ エラー: {e}\nMIDIデバイスを接続して再起動してください。"
            self.label_info.setText(msg.split('\n')[0]); self.log_window.append_log(msg)
            self.btn_load_template.setEnabled(False)

    def open_settings_dialog(self):
        # (変更なし)
        new_settings = SettingsDialog.get_settings(self, self.settings)
        if new_settings: self.settings = new_settings; self.apply_settings()

    def toggle_log_window(self):
        # (変更なし)
        if self.log_window.isVisible(): self.log_window.hide()
        else: self.log_window.show()

    def apply_settings(self):
        # (変更なし)
        if self.snare_sound: self.snare_sound.set_volume(self.settings['drum_volume'])
        if self.tom_sound: self.tom_sound.set_volume(self.settings['drum_volume'])
        if self.metronome_click: self.metronome_click.set_volume(self.settings['metronome_volume'])
        if self.metronome_accent_click: self.metronome_accent_click.set_volume(self.settings['metronome_volume'] * 1.2)
        if self.note_sound: self.note_sound.set_volume(self.settings['guide_cue_volume'])
    
    # ★★★★★ (A) load_template_file と _load_score_from_path を修正 ★★★★★

    def load_template_file(self):
        """
        ファイルダイアログを開き、お手本ファイルを選択してロードする（フリーモード用）
        """
        filepath = FileSelectionDialog.get_file(self)
        if filepath:
            if self._load_score_from_path(filepath):
                # ★ 修正: 呼び出し元 (フリーモード) がリセットをかける
                self.retry(force_reset=True)

    def _load_score_from_path(self, filepath):
        """
        指定されたファイルパスからお手本スコアをロードする（共通ロジック）
        """
        try:
            with open(filepath, 'r', encoding='utf-8') as f: 
                self.template_score = json.load(f)
            if 'top' not in self.template_score: 
                raise ValueError("無効なファイル形式です。")
            
            file_display_name = os.path.basename(filepath).replace('.json', '')
            self.label_template_file.setText(f"📄 ファイル: {file_display_name}")
            self.label_template_file.set_style(font_size=14, weight=QFont.Weight.Bold, color_key='primary')
            self.log_window.append_log(f"ファイルを読み込みました: {filepath}")

            # ★ 修正: この関数はロードするだけ。リセットは呼び出し元が判断する
            # self.retry(force_reset=True) # <-- BUG: これを削除
            self.on_controller_changed()
            return True # ロード成功
            
        except Exception as e:
            QMessageBox.critical(self, "ファイル読み込みエラー", f"ファイルの読み込みに失敗しました:\n{filepath}\n{e}")
            self.template_score = None
            # ★ 失敗した場合はリセットするのが安全
            self.retry(force_reset=True)
            return False # ロード失敗

    # ★★★★★ (B) start_demo_playback を修正 ★★★★★

    def start_demo_playback(self):
        # ★ 修正: 呼び出し元で _demo_return_state が設定されていることを前提とする
        self.state = "demo_playback" # 再生中は "demo_playback" 状態
        
        self.editor_window = EditorWindow(self.template_score, self, self.item_images, is_demo=True)
        self.editor_window.show()

    def on_robot_command_sent(self, track_name, motion):
        # (変更なし)
        if self.viz_window:
            self.viz_window.update_command(track_name, motion)

    def prepare_for_recording(self):
        # (変更なし)
        self.recorded_hits, self.judgements = [], []
        self.judged_notes.clear()
        self.total_notes = sum(1 for track in self.template_score.values() for item in track.get('items', []) if item['class'] == 'note')
        note_id = 0
        for track_name, track in self.template_score.items():
            for item in track.get('items', []):
                if item['class'] == 'note': item['id'] = f"{track_name}-{note_id}"; note_id += 1

    def on_robot_thread_finished(self, thread_obj, worker_obj):
        # (変更なし)
        if hasattr(self, 'robot_threads') and thread_obj in self.robot_threads: self.robot_threads.remove(thread_obj)
        if hasattr(self, 'robot_workers') and worker_obj in self.robot_workers: self.robot_workers.remove(worker_obj)

    def start_practice(self):
        # (変更なし)
        if not self.template_score: return
        self.start_generic_practice(is_perfect_mode=False)

    def start_perfect_practice(self):
        # (変更なし)
        if not self.template_score: return
        self.start_generic_practice(is_perfect_mode=True)

    def start_generic_practice(self, is_perfect_mode, force_robot=None, force_controller_name=None, max_loops=None):
        # (変更なし)
        if is_perfect_mode:
            self.perfect_practice_history.clear(); self.judgement_history.clear()
            self.practice_start_time = time.time() # ★ 練習開始時刻を記録

        self.is_perfect_mode = is_perfect_mode
        self.practice_loop_count = 1
        self.practice_loop_count_max = max_loops or float('inf') 
        
        self.prepare_for_recording()
        top_score = self.template_score.get("top", {})
        bottom_score = self.template_score.get("bottom", {})
        top_bpm = top_score.get("bpm", 120); bottom_bpm = bottom_score.get("bpm", 120)
        top_beats = top_score.get("total_beats", 8); bottom_beats = bottom_score.get("total_beats", 8)
        top_duration_ms = top_beats * (60000.0 / top_bpm) if top_bpm > 0 else 0
        bottom_duration_ms = bottom_beats * (60000.0 / bottom_bpm) if bottom_bpm > 0 else 0
        master_loop_duration_ms = max(top_duration_ms, bottom_duration_ms)
        
        countdown_duration_s = (4 * (60.0 / top_bpm))
        
        robot_prep_time_s = 0
        motion_plan_data = {}
        
        use_robot = False
        if force_robot is True:
            use_robot = True
        elif force_robot is False:
            use_robot = False
        elif self.robot_manager and ROBOTS_AVAILABLE:
            use_robot = True
        
        if use_robot:
            if not self.robot_manager:
                QMessageBox.warning(self, "エラー", "ロボットマネージャーが初期化されていません。")
                return

            robot_prep_time_s = self.robot_manager.get_first_move_preparation_time(self.template_score)
            master_start_time = time.time() + countdown_duration_s + robot_prep_time_s
            
            controller_to_use = None
            if force_controller_name:
                controller_class = self.controller_classes.get(force_controller_name)
                if controller_class:
                    try:
                        ms_per_beat = 60000.0 / top_bpm
                        controller_to_use = controller_class(copy.deepcopy(self.template_score), ms_per_beat)
                        print(f"--- 実験モード: '{force_controller_name}' を強制使用します。---")
                    except Exception as e:
                        print(f"コントローラー '{force_controller_name}' のインスタンス化に失敗: {e}")
                else:
                    QMessageBox.warning(self, "コントローラーエラー", f"指定されたコントローラー '{force_controller_name}' が見つかりません。")
                    return
            else:
                self.on_controller_changed()
                controller_to_use = self.active_controller

            if controller_to_use:
                self.robot_manager.start_control(self.template_score, controller_to_use, master_start_time)
                time.sleep(0.5)
                
                for worker in self.robot_manager.workers:
                    motion_plan_data[worker.track_name] = worker.motion_plan
                
                if self.viz_window:
                    self.viz_window.start_monitoring(self.template_score, master_start_time, motion_plan_data)
                    if self.settings.get('command_monitor_on', False):
                        self.viz_window.show()
            else:
                QMessageBox.warning(self, "コントローラー未選択", "有効な制御方法が選択されていません。")
                return
        else:
            master_start_time = time.time() + countdown_duration_s

        if self.state.startswith("experiment_"):
            # ★ 修正: 実行中の状態を汎用的なものに変更
            self.state = "experiment_running"
        else:
            self.state = "practice_countdown"
            
        self.editor_window = EditorWindow(
            self.template_score, self, self.item_images, is_demo=False, 
            loop_duration_ms=master_loop_duration_ms, 
            robot_prep_time_s=robot_prep_time_s,
            master_start_time=master_start_time
        )
        self.editor_window.show()
        self.update_button_states()

    def on_ai_feedback_received(self, feedback):
        # (変更なし)
        self.ai_feedback_text = feedback; self.canvas.update()
        self.btn_retry.setEnabled(True); self.btn_load_template.setEnabled(True)

    def on_thread_finished(self):
        # (変更なし)
        self.thread = None; self.worker = None

    # ★★★★★ (B) finish_performance を修正 ★★★★★
    def finish_performance(self, is_demo, force_stop=False):
        pygame.mixer.music.stop()

        if self.viz_window:
            self.viz_window.stop_monitoring()

        if self.robot_manager: self.robot_manager.stop_control()
        
        editor = self.editor_window
        if editor:
            self.editor_window = None
            editor.close()

        # ★ 状態遷移ロジック
        if is_demo:
            # --- デモの終了処理 ---
            # ★ 修正: 記憶した状態に戻る
            self.state = self._demo_return_state 
            self._demo_return_state = "waiting" # 念のためリセット
            self.log_window.append_log(f"デモ再生終了。状態を {self.state} に戻しました。")
            self.update_button_states() # ★ UI を復元
            self.canvas.update()
            return # ★★★ ここで終了（advance は呼ばない）★★★
            
        elif self.state.startswith("experiment_"):
            # --- 実験モードの終了処理 ---
            
            # ★ 修正: 実行中の状態を汎用化
            is_running_state = self.state == "experiment_running"

            if force_stop and is_running_state:
                # ★ 練習 (is_perfect_mode) または テスト が中止された場合
                # 現在のステップのイントロに戻る
                self.log_window.append_log("実行が中止されました。現在のステップのイントロに戻ります。")
                self.enter_experiment_state("experiment_intro", 
                                            set_index=self.current_experiment_set_index, 
                                            step=self.current_experiment_step)
                return

            # --- 通常のフェーズ終了処理 (中止されなかった場合) ---
            
            # 結果を保存
            self.result_stats = self.summarize_performance()
            
            # ★ 修正: 保存キーを汎用化
            current_state_key = f"set_{self.current_experiment_set_index}_step_{self.current_experiment_step}"
            self.experiment_data[current_state_key] = self.result_stats
            
            self.log_window.append_log(f"--- 実験シーケンス: {current_state_key} 完了 ---")
            self.log_window.append_log(json.dumps(self.result_stats, indent=2))
            
            # ★ 修正: ハードコードされた次の状態ではなく、advanceメソッドを呼ぶ
            self.advance_experiment_step() # <-- 次のステップへ自動遷移
            return # ★★★ ここで終了 ★★★
        
        else:
            # --- フリーモード（練習/PERFECT）の終了処理 ---
            self.state = "result"
            self.ai_feedback_text = "🤖 AIによるフィードバックを生成中..."
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

    def closeEvent(self, event):
        # (変更なし)
        pygame.mixer.music.stop()
        if self.viz_window: 
            self.viz_window.stop_monitoring()
            self.viz_window.closeEvent = lambda e: e.accept()
            self.viz_window.close()
        if self.robot_manager: self.robot_manager.stop_control()
        if self.thread and self.thread.isRunning(): self.thread.quit(); self.thread.wait()
        if hasattr(self, 'inport') and self.inport and not self.inport.closed: self.inport.close()
        if self.log_window:
            self.log_window.closeEvent = lambda e: e.accept() 
            self.log_window.close()
        pygame.quit()
        event.accept()

    def evaluate_and_continue_loop(self):
        # (変更なし)
        if not self.is_perfect_mode: return
        
        self.judgement_history.append(list(self.judgements))
        if self.active_controller and hasattr(self.active_controller, 'update_performance_data'):
            # コントローラーに履歴全体を渡し、分析ログを受け取る
            log_msg = self.active_controller.update_performance_data(self.judgement_history)
            
            if log_msg:
                # ログをコントローラー名と共にログウィンドウに直接送信
                self.log_window.append_log(f"[{self.active_controller.name}] {log_msg}")
        stats = self.summarize_performance()
        history_entry = { 'loop': self.practice_loop_count, 'perfects': stats['perfect'], 'std_dev': stats['std_dev'] if stats['std_dev'] > 0 else 0 }
        self.perfect_practice_history.append(history_entry)
        
        # self.practice_start_time は is_perfect_mode=True の時だけ設定される
        time_limit_seconds = 180.0 # 3分
        elapsed_practice_time = time.time() - self.practice_start_time

        # 1分経過しているかチェック
        if elapsed_practice_time >= time_limit_seconds:
            # --- 1分経過したら終了 ---
            self.log_window.append_log(f"練習時間が {time_limit_seconds:.0f} 秒に達したため、練習を終了します。")
            self.result_stats = stats
            self.ai_feedback_text = f"規定の {time_limit_seconds:.0f}秒 に達したため練習を終了します。"
            if self.editor_window: self.editor_window.close()

        else:
            # --- 1分経過していない場合はループ継続 ---
            self.practice_loop_count += 1
            self.recorded_hits.clear(); self.judgements.clear(); self.judged_notes.clear()
            pygame.mixer.music.rewind()
            if self.editor_window:
                self.editor_window.rhythm_widget.reset_for_loop()
                current_elapsed = self.get_elapsed_time()
                loop_num = int(current_elapsed / self.editor_window.rhythm_widget.loop_duration_ms) + 1
                self.editor_window.rhythm_widget.next_evaluation_time = loop_num * self.editor_window.rhythm_widget.loop_duration_ms
            # ★★★★★ 変更ここまで ★★★★★

    def retry(self, force_reset=False):
        # (変更なし)
        if self.state.startswith("experiment_") and not force_reset:
            pass
        else:
            self.state = "waiting"

        self.recorded_hits, self.judgements = [], []
        self.result_stats = {}; pygame.mixer.stop()
        pygame.mixer.music.stop()
        self.practice_loop_count = 0; self.is_perfect_mode = False
        self.practice_loop_count_max = float('inf')
        self.experiment_data.clear()
        self.experiment_next_state = None
        self._demo_return_state = "waiting" # ★ 復帰先もリセット
        
        self.update_button_states()
        if not self.template_score and self.state == "waiting":
            self.label_template_file.setText("ファイルが読み込まれていません")
            self.label_template_file.set_style(font_size=12, weight=QFont.Weight.Normal, color_key='text_muted')

    def update_button_states(self):
        # ★ デバッグ用ログを追加
        self.log_window.append_log(f"update_button_states 呼び出し: state = {self.state}")
        
        # 1. 現在の状態を分類
        is_free_mode = self.state == "waiting" or self.state == "result"
        is_playing = self.state in ["recording", "demo_playback", "practice_countdown",
                                     "experiment_running"]
        is_experiment_intro = self.state.startswith("experiment_") and not is_playing
        
        # ★ デバッグ用ログを追加
        self.log_window.append_log(f"  is_free_mode = {is_free_mode}")
        self.log_window.append_log(f"  is_playing = {is_playing}")
        self.log_window.append_log(f"  is_experiment_intro = {is_experiment_intro}")
        
        # 2. メインパネルの表示/非表示を制御
        self.free_mode_panel.setVisible(is_free_mode)
        self.experiment_panel.setVisible(is_experiment_intro)
        
        # ★ デバッグ用ログを追加
        self.log_window.append_log(f"  free_mode_panel.isVisible = {self.free_mode_panel.isVisible()}")
        self.log_window.append_log(f"  experiment_panel.isVisible = {self.experiment_panel.isVisible()}")

        # 3. 個別のウィジェットを制御
        if is_free_mode:
            # --- フリーモード ---
            is_ready = self.template_score is not None
            is_result = self.state == "result"
            
            self.btn_settings.setVisible(not is_playing)
            self.btn_load_template.setVisible(not is_result)
            self.btn_demo.setVisible(not is_result and is_ready)
            self.btn_practice.setVisible(not is_result and is_ready)
            self.btn_perfect_practice.setVisible(not is_result and is_ready)
            self.btn_retry.setVisible(is_result)
            self.btn_start_experiment.setVisible(not is_result)
            
            self.btn_demo.setEnabled(is_ready)
            self.btn_practice.setEnabled(is_ready)
            self.btn_perfect_practice.setEnabled(is_ready)
            
            self.control_combo.setVisible(not is_result)
            self.label_controller.setVisible(not is_result)
        
        elif is_experiment_intro:
            # --- 実験モード (イントロ/説明画面) ---
            is_ready = self.template_score is not None
            
            # ★ デバッグ用ログを追加
            self.log_window.append_log(f"  実験イントロモード: state={self.state}, is_ready={is_ready}")
            
            # デフォルトですべて非表示
            self.btn_exp_demo.setVisible(False)
            self.btn_exp_start.setVisible(False)
            self.btn_exp_next.setVisible(False)
            self.btn_exp_finish.setVisible(False)
            self.btn_settings.setVisible(False)

            # 状態ごとに出すボタンを決定
            if self.state == "experiment_explanation":
                self.btn_exp_next.setVisible(True)
                self.btn_exp_finish.setVisible(True) # 中止できるように
                self.btn_exp_finish.setText("🏠 実験中止")
                self.log_window.append_log(f"  「次へ」「中止」ボタンを表示設定")
            
            elif self.state == "experiment_intro":
                # ★★★ ここが新しいロジック ★★★
                self.btn_exp_demo.setVisible(is_ready)
                self.btn_exp_start.setVisible(is_ready)
                self.btn_exp_finish.setVisible(True) # 中止できるように
                self.btn_exp_finish.setText("🏠 実験中止")
                
                self.btn_exp_demo.setEnabled(is_ready)
                self.btn_exp_start.setEnabled(is_ready)

                # 現在のステップ設定に基づいてスタートボタンを更新
                try:
                    config = self.experiment_steps_config[self.current_experiment_step]
                    self.btn_exp_start.setText(config['button_text'])
                    self.btn_exp_start.bg_color = config['color']
                    self.btn_exp_start.hover_color = config['color_dark']
                    self.btn_exp_start.update_style()
                except IndexError:
                    self.log_window.append_log("エラー: experiment_steps_config のインデックスが不正です。")

                self.log_window.append_log(f"  experiment_intro: ボタン表示設定完了 (Step {self.current_experiment_step})")

            elif self.state == "experiment_finished":
                self.btn_exp_finish.setVisible(True)
                self.btn_exp_finish.setText("🏠 メインメニューに戻る") # テキスト変更
        
        elif is_playing:
            # --- 演奏中 ---
            self.btn_settings.setVisible(False)
    def process_midi_input(self):
        # (変更なし)
        if not hasattr(self, 'inport') or not self.inport: return
        for msg in self.inport.iter_pending():
            if msg.type == 'note_on' and msg.velocity >= VELOCITY_THRESHOLD:
                pad = 'top' if msg.note in PAD_MAPPING['left'] else 'bottom' if msg.note in PAD_MAPPING['right'] else None
                if not pad: continue
                if self.state in ["practice_countdown", "recording", "experiment_test_A1_running", "experiment_practice_A_running", "experiment_test_A2_running"]:
                    if self.snare_sound: self.snare_sound.play()
                
                is_recording_state = self.state == "recording" or \
                                     self.state == "experiment_test_A1_running" or \
                                     self.state == "experiment_practice_A_running" or \
                                     self.state == "experiment_test_A2_running"

                if is_recording_state:
                    hit_time_ms = self.get_elapsed_time()
                    new_hit = {'time': hit_time_ms, 'pad': pad}
                    self.recorded_hits.append(new_hit)
                    judgement, error_ms, note_id = self.judge_hit(new_hit)
                    self.judgements.append({'judgement': judgement, 'error_ms': error_ms, 'pad': pad, 'note_id': note_id, 'hit_time': hit_time_ms})
                    if note_id is not None: self.judged_notes.add(note_id)
                    if self.editor_window:
                        self.editor_window.rhythm_widget.add_user_hit(new_hit)
                        self.editor_window.rhythm_widget.add_feedback_animation(judgement, new_hit)

    def judge_hit(self, hit):
        # (変更なし)
        pad, hit_time = hit['pad'], hit['time']; track_data = self.template_score.get(pad)
        if not track_data: return 'extra', None, None
        bpm = track_data.get('bpm', 120); ms_per_beat = 60000.0 / bpm
        
        # ( clustering_threshold の定義はもう不要 )
        # sixteenth_note_duration = ms_per_beat / 4.0
        # clustering_threshold = max(JUDGEMENT_WINDOWS['good'] + 20, sixteenth_note_duration * 0.8)
        
        num = track_data.get('numerator', 4); den = track_data.get('denominator', 4)
        beats_per_measure = (num / den) * 4.0; total_beats = beats_per_measure * NUM_MEASURES
        loop_duration_ms = ms_per_beat * total_beats
        if loop_duration_ms == 0: return 'extra', None, None
        
        hit_time_in_loop = hit_time % loop_duration_ms
        closest_note, min_diff = None, float('inf')
        
        for note in track_data.get('items', []):
            if note['class'] == 'note':
                note_time = note['beat'] * ms_per_beat
                # ループを考慮した最短距離を計算 (このロジックは正しかった)
                diffs = [abs(hit_time_in_loop - note_time), abs(hit_time_in_loop - (note_time - loop_duration_ms)), abs(hit_time_in_loop - (note_time + loop_duration_ms))]
                diff = min(diffs)
                
                # 既に判定済みのノートでなく、かつ最短距離なら更新
                if note.get('id') not in self.judged_notes and diff < min_diff:
                    min_diff, closest_note = diff, note

        # ★★★ ここからロジックを修正 ★★★
        
        # 1. 最も近いノートが見つかったか？
        if closest_note:
            # 2. 見つかったノートを基準に、符号付きの「正確な誤差」を計算する
            note_time = closest_note['beat'] * ms_per_beat
            actual_note_time_instance = min([note_time, note_time - loop_duration_ms, note_time + loop_duration_ms], key=lambda x: abs(hit_time_in_loop - x))
            error_ms = hit_time_in_loop - actual_note_time_instance
            
            # 3. 誤差が 'Good' (100ms) の範囲内か？
            if abs(error_ms) <= JUDGEMENT_WINDOWS['good']:
                # 4. 'Good' の範囲内なら、'Perfect', 'Great', 'Good' のどれかを返す
                if abs(error_ms) <= JUDGEMENT_WINDOWS['perfect']: 
                    return 'perfect', error_ms, closest_note['id']
                if abs(error_ms) <= JUDGEMENT_WINDOWS['great']: 
                    return 'great', error_ms, closest_note['id']
                
                # 'Good' の範囲内 (e.g. 100ms) で P/G 以外なら 'Good'
                return 'good', error_ms, closest_note['id']

            # 5. 'Good' (100ms) の枠から外れていた場合
            # (e.g. 誤差 -110ms だった場合、'extra' 扱いとする)
            # (以前は clustering_threshold(120) のせいでここでバグっていた)
            pass # 'extra' に進む

        # 最も近いノートが見つからない、または 'Good' の枠外だった場合は 'extra'
        return 'extra', None, None

    def register_dropped_note(self, note_id, pad):
        # (変更なし)
        if note_id not in self.judged_notes:
            self.judged_notes.add(note_id)
            self.judgements.append({'judgement': 'dropped', 'error_ms': None, 'pad': pad, 'note_id': note_id, 'hit_time': None})

    def get_elapsed_time(self):
        # (変更なし)
        return pygame.mixer.music.get_pos()

    def play_note_sound(self):
        # (変更なし)
        if self.note_sound: self.note_sound.play()

    def play_metronome_sound(self, is_accent):
        # (変更なし)
        if is_accent and self.metronome_accent_click: self.metronome_accent_click.play()
        elif not is_accent and self.metronome_click: self.metronome_click.play()

    def play_countdown_sound(self):
        # (変更なし)
        if self.countdown_sound: self.countdown_sound.play()

    def update_loop(self):
        # ★ 修正: update_button_states() を削除
        # self.update_button_states() # 毎秒60回も呼ぶのをやめる
        if self.state in ["practice_countdown", "recording", "experiment_test_A1_running", "experiment_practice_A_running", "experiment_test_A2_running"]: 
            self.process_midi_input()
        self.canvas.update()

    def summarize_performance(self):
        # (変更なし)
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
        # (変更なし)
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
        # (変更なし)
        full_log = ""
        original_judgements = list(self.judgements)
        history_to_log = []
        if len(self.judgement_history) <= 3:
            history_to_log = enumerate(self.judgement_history)
        else:
            history_to_log.append((0, self.judgement_history[0]))
            history_to_log.append((len(self.judgement_history) - 2, self.judgement_history[-2]))
            history_to_log.append((len(self.judgement_history) - 1, self.judgement_history[-1]))
        for i, loop_judgements in history_to_log:
            self.judgements = loop_judgements
            full_log += f"\n\n========== 練習 {i + 1}回目 ==========\n"
            full_log += self.create_performance_log_text()
        self.judgements = original_judgements
        return full_log

    def generate_ai_feedback_logic(self):
        # (変更なし)
        if not OPENAI_AVAILABLE: return "OpenAIライブラリが見つかりません。"
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key: return "環境変数 OPENAI_API_KEY が設定されていません。"
        stats = self.result_stats
        summary_text = f"""- 全体達成率: {stats['accuracy']:.1f}%\n- 判定: PERFECT {stats['perfect']}回, GREAT {stats['great']}回, GOOD {stats['good']}回, EXTRA {stats['extra']}回, 見逃し {stats['dropped']}回\n- 平均タイミング誤差: {stats['avg_error']:+.0f}ms ({'遅れ気味' if stats['avg_error'] > 5 else '走り気味' if stats['avg_error'] < -5 else '正確'})\n- タイミングのばらつき(標準偏差): {stats['std_dev']:.2f}ms"""
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

    def begin_real_recording(self):
        is_demo = False
        if self.editor_window:
            is_demo = self.editor_window.is_demo

        if is_demo:
            # デモ再生中: UI更新はしない
            self.log_window.append_log("begin_real_recording: デモ再生が開始されました。(UI更新はスキップ)")
            return

        # テスト/練習開始時も update_button_states() は呼ばない
        # (EditorWindow が全画面表示されるため)
        if self.state.startswith("experiment_"):
            if self.state != "experiment_running": 
                self.state = "experiment_running"
                self.log_window.append_log("状態を 'experiment_running' に変更しました。")
                self.canvas.update()
        elif not self.state.startswith("experiment_"):
            if self.state != "recording":
                self.state = "recording"
                self.log_window.append_log("状態を 'recording' (フリー練習) に変更しました。")
                self.canvas.update()

    # ★★★★★ ここから実験モード用メソッド群 ★★★★★

    def advance_experiment_step(self):
        """ 
        実験のステップを次に進める。
        finish_performance から呼ばれる。
        """
        self.log_window.append_log("--- advance_experiment_step 呼び出し ---")
        
        next_step = self.current_experiment_step + 1
        next_set_index = self.current_experiment_set_index

        if next_step >= len(self.experiment_steps_config):
            # ステップが最後まで行ったら (2 -> 3)、次のセットへ
            next_step = 0
            next_set_index += 1
            self.log_window.append_log(f"セット {self.current_experiment_set_index + 1} が完了。次のセット {next_set_index + 1} へ。")
        else:
            self.log_window.append_log(f"ステップ {self.current_experiment_step + 1} が完了。次のステップ {next_step + 1} へ。")

        if next_set_index >= len(self.experiment_sets):
            # 全セット完了 (0-8 だったので 9 になったら完了)
            self.log_window.append_log("--- 全実験セットが完了しました ---")
            self.enter_experiment_state("experiment_finished")
        else:
            # 次のステップ/セットの導入画面へ
            self.enter_experiment_state("experiment_intro", set_index=next_set_index, step=next_step)

    def start_experiment_confirmation(self):
        """
        「実験モードを開始しますか？」という確認ダイアログを表示する
        """
        reply = QMessageBox.question(self, "実験モードの開始",
                                     "実験モードを開始しますか？\n(フリー練習モードに戻るには、実験を完了するかアプリを再起動してください)",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                     QMessageBox.StandardButton.No)
        
        if reply == QMessageBox.StandardButton.Yes:
            self.log_window.append_log("--- 実験モード開始 ---")
            self.experiment_data.clear()
            # ★ 修正: "explanation" -> "experiment_explanation"
            self.enter_experiment_state("experiment_explanation")

    def enter_experiment_state(self, new_state, set_index=None, step=None):
        """
        実験モードの状態を遷移させ、関連するUIを更新する
        new_state: "explanation", "intro", "finished" のいずれか
        set_index: "intro" の場合に必須 (0-8)
        step: "intro" の場合に必須 (0-2)
        """
        if not new_state.startswith("experiment_"):
            new_state = "experiment_" + new_state
            
        self.log_window.append_log(f"実験状態遷移: {self.state} -> {new_state}")
        self.state = new_state
        self.label_info.setText("")
        
        # 状態ごとの初期化処理
        if new_state == "experiment_explanation":
            self.label_template_file.setText("実験モード")
            self.label_template_file.set_style(font_size=14, weight=QFont.Weight.Bold, color_key='accent')
        
        elif new_state == "experiment_intro":
            if set_index is None or step is None:
                self.log_window.append_log("エラー: enter_experiment_state('intro') が set_index/step なしで呼ばれました。")
                self.retry(force_reset=True)
                return

            self.current_experiment_set_index = set_index
            self.current_experiment_step = step
            
            try:
                filename = self.experiment_sets[self.current_experiment_set_index]
                config = self.experiment_steps_config[self.current_experiment_step]
            except IndexError:
                self.log_window.append_log("エラー: 実験セットまたはステップのインデックスが範囲外です。")
                self.retry(force_reset=True)
                return

            self.log_window.append_log(f"--- イントロ画面: セット {set_index+1}/9, ステップ {step+1}/3 ---")
            self.log_window.append_log(f"使用ファイル: {filename}")

            filepath = os.path.join(r"C:\卒研\music", filename)
            
            # 楽譜をロードし、失敗したら中断する
            load_success = self._load_score_from_path(filepath)
            
            if not load_success:
                QMessageBox.critical(self, "実験エラー",
                                     f"楽譜ファイルが見つかりません:\n{filepath}\n"
                                     "実験を中止し、メインメニューに戻ります。")
                self.retry(force_reset=True)
                return
            
            # (表示ラベルは AnalyzerCanvas が担当する)
            self.label_template_file.setText(f"📄 {filename.replace('.json', '')} ({config['title']})")
            self.label_template_file.set_style(font_size=14, weight=QFont.Weight.Bold, color_key='primary')
            self.label_info.setText(config['description'])

            # コントローラーを初期化
            self.on_controller_changed()
            
        elif new_state == "experiment_finished":
            self.label_template_file.setText("実験完了")
            self.label_template_file.set_style(font_size=14, weight=QFont.Weight.Bold, color_key='success')
            self.label_info.setText("ご協力ありがとうございました。")
            # (AnalyzerCanvas が詳細を描画)

        # ★★★ 修正箇所 ★★★
        # if/elif ブロックがすべて終わった後、関数の最後に配置する。
        # これにより、どの状態遷移でも必ずUIが更新される。
        self.update_button_states()
        self.canvas.update() # Canvas の表示を更新

    def on_experiment_button_clicked(self):
        # (変更なし)
        sender = self.sender()
        
        if sender == self.btn_exp_next:
            if self.state == "experiment_explanation":
                # ★ 修正: 最初のステップ (0, 0) で "intro" を開始
                self.enter_experiment_state("experiment_intro", set_index=0, step=0)
        
        elif sender == self.btn_exp_demo:
            if self.template_score and self.state == "experiment_intro":
                # ★ 修正: デモ再生後の復帰先を現在の実験状態に設定
                self._demo_return_state = self.state # "experiment_intro"
                self.start_demo_playback()
                # デモ終了後も自動的に現在の実験状態 (e.g., "experiment_intro") に戻る)
                return

        elif sender == self.btn_exp_start:
            # ★ 修正: "experiment_intro" 状態の時のみ反応
            if self.state == "experiment_intro":
                # 現在のステップの設定を取得
                try:
                    config = self.experiment_steps_config[self.current_experiment_step]
                except IndexError:
                    self.log_window.append_log("エラー: btn_exp_start が押されましたが、config が見つかりません。")
                    return
                
                self.experiment_next_state = "advance_step" # (古いロジックのためだが、念のためセット)
                
                self.start_generic_practice(
                    is_perfect_mode=config['is_perfect_mode'],
                    force_robot=config['force_robot'],
                    force_controller_name=config['force_controller_name'],
                    max_loops=config['max_loops']
                )

        elif sender == self.btn_exp_finish:
            # ★ 修正: どの実験状態からでもフリーモードに戻る
            self.log_window.append_log("--- 実験が手動で中止/完了されました ---")
            self.retry(force_reset=True)
            
        # self.update_button_states() # start_generic_practice が呼ぶので不要

class AnalyzerCanvas(GlowingWidget):
    def __init__(self, main_window):
        super().__init__(); self.main = main_window; self.setMinimumHeight(480)
        
    def paintEvent(self, event):
        painter = QPainter(self); painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), COLORS['surface'])
        painter.setPen(QPen(COLORS['border'], 1)); painter.drawRect(self.rect().adjusted(0, 0, -1, -1))
        
        # ★ 状態名に 'experiment_' が含まれていたら、専用の描画メソッドを呼ぶ
        if self.main.state.startswith("experiment_"):
            # ★ 修正: 汎用的な状態名に対応
            if self.main.state == "experiment_explanation":
                draw_method = self.draw_experiment_explanation_state
            elif self.main.state == "experiment_intro":
                draw_method = self.draw_experiment_intro_state
            elif self.main.state == "experiment_running":
                draw_method = self.draw_experiment_running_state
            elif self.main.state == "experiment_finished":
                draw_method = self.draw_experiment_finished_state
            else:
                # (フォールバック)
                draw_method = self.draw_experiment_default_state
        else:
            # 通常の描画メソッド
            draw_method = getattr(self, f"draw_{self.main.state}_state", self.draw_waiting_state)
            
        draw_method(painter)

    # --- フリーモード用 ---
    def draw_waiting_state(self, painter):
        glow_color = QColor(COLORS['primary']); glow_color.setAlpha(int(self._glow_opacity * 50))
        painter.save(); painter.setPen(QPen(glow_color, 3)); painter.setFont(QFont("Segoe UI", 42, QFont.Weight.Bold))
        painter.drawText(self.rect().adjusted(0, -120, 0, 0), Qt.AlignmentFlag.AlignCenter, "Ready"); painter.restore()
        painter.setPen(COLORS['text_primary']); painter.setFont(QFont("Segoe UI", 42, QFont.Weight.Bold))
        painter.drawText(self.rect().adjusted(0, -120, 0, 0), Qt.AlignmentFlag.AlignCenter, "Ready ")
        painter.setPen(COLORS['text_secondary']); painter.setFont(QFont("Segoe UI", 16))
        instruction = "ファイルを選択して、練習を開始してください。"
        if not self.main.template_score:
            instruction = "まず、下部の「📁 」ボタンからファイル (.json) を読み込んでください。"; self.start_glow()
        else: self.stop_glow()
        painter.drawText(self.rect().adjusted(0, -20, 0, 0), Qt.AlignmentFlag.AlignCenter, instruction)

    def draw_practice_countdown_state(self, painter):
        painter.setPen(COLORS['text_primary']); painter.setFont(QFont("Segoe UI", 42, QFont.Weight.Bold))
        painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "ロボット準備中...")
        painter.setPen(COLORS['text_secondary']); painter.setFont(QFont("Segoe UI", 16))
        painter.drawText(self.rect().adjusted(0, 80, 0, 0), Qt.AlignmentFlag.AlignCenter, "楽譜ウィンドウでカウントダウンが始まります")

    def draw_recording_state(self, painter):
        painter.setPen(COLORS['text_primary']); painter.setFont(QFont("Segoe UI", 42, QFont.Weight.Bold))
        painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "頑張って！ 👍")
        painter.setPen(COLORS['text_secondary']); painter.setFont(QFont("Segoe UI", 16))
        painter.drawText(self.rect().adjusted(0, 80, 0, 0), Qt.AlignmentFlag.AlignCenter, "演奏に集中してください...")

    def draw_demo_playback_state(self, painter):
        # ★★★ 修正: self.draw_recording_state(painter) を以下に置き換え ★★★
        painter.setPen(COLORS['success']) # 'recording' の 'primary' と区別
        painter.setFont(QFont("Segoe UI", 42, QFont.Weight.Bold))
        painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "👁️ お手本を再生中...")
        painter.setPen(COLORS['text_secondary'])
        painter.setFont(QFont("Segoe UI", 16))
        painter.drawText(self.rect().adjusted(0, 80, 0, 0), Qt.AlignmentFlag.AlignCenter, "楽譜ウィンドウをご覧ください。")
    
    def draw_result_state(self, painter):
        # (変更なし)
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

    # (draw_perfect_practice_history_graph, draw_result_graph, draw_result_stats, draw_ai_feedback は変更なし)
    def draw_perfect_practice_history_graph(self, painter, rect):
        # (変更なし)
        painter.save(); painter.setBrush(COLORS['surface']); painter.setPen(QPen(COLORS['border'], 1)); painter.drawRoundedRect(rect, 15, 15)
        history = self.main.perfect_practice_history
        if not history:
            painter.setPen(COLORS['text_muted']); painter.setFont(QFont("Segoe UI", 14)); painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, "履歴データがありません"); painter.restore(); return
        margin_top, margin_bottom, margin_left, margin_right = 50, 50, 80, 80
        plot_area = rect.adjusted(margin_left, margin_top, -margin_right, -margin_bottom)
        num_points = len(history)
        max_perfects = self.main.total_notes if self.main.total_notes > 0 else 1
        max_std_dev = max(h['std_dev'] for h in history) if any(h['std_dev'] > 0 for h in history) else 50.0
        painter.setPen(QPen(COLORS['border'], 1, Qt.PenStyle.DotLine))
        for i in range(6): y = plot_area.top() + i * plot_area.height() / 5; painter.drawLine(QPointF(plot_area.left(), y), QPointF(plot_area.right(), y))
        painter.setPen(COLORS['perfect']); painter.drawText(rect.adjusted(10,0,0,0), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, "PERFECT数")
        for i in range(6): y = plot_area.top() + i * plot_area.height() / 5; label = f"{max_perfects * (1 - i/5.0):.0f}"; painter.drawText(QRectF(plot_area.left() - 70, y - 12, 60, 24), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight, label)
        painter.setPen(COLORS['primary']); painter.drawText(rect.adjusted(0,0,-10,0), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight, "ばらつき(ms)")
        for i in range(6): y = plot_area.top() + i * plot_area.height() / 5; label = f"{max_std_dev * (1 - i/5.0):.1f}"; painter.drawText(QRectF(plot_area.right() + 10, y - 12, 60, 24), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, label)
        painter.setPen(COLORS['text_secondary']); painter.setFont(QFont("Segoe UI", 10, QFont.Weight.Medium)); painter.drawText(rect.adjusted(0,0,0, -10), Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignBottom, "試行回数")
        perfects_poly = QPolygonF(); std_dev_poly = QPolygonF()
        for i, h in enumerate(history):
            x = 0
            if num_points == 1: x = plot_area.center().x()
            else: x = plot_area.left() + i * plot_area.width() / (num_points - 1)
            painter.setPen(QPen(COLORS['border'], 1, Qt.PenStyle.DotLine)); painter.drawLine(QPointF(x, plot_area.top()), QPointF(x, plot_area.bottom())); painter.setPen(COLORS['text_secondary'])
            painter.drawText(QRectF(x - 20, plot_area.bottom() + 5, 40, 25), Qt.AlignmentFlag.AlignCenter, str(h['loop']))
            y_perf = plot_area.bottom() - (h['perfects'] / max_perfects) * plot_area.height()
            y_std = plot_area.bottom() - (h['std_dev'] / max_std_dev if max_std_dev > 0 else 0) * plot_area.height()
            perfects_poly.append(QPointF(x, y_perf)); std_dev_poly.append(QPointF(x, y_std))
        painter.setPen(QPen(COLORS['primary'], 3)); painter.drawPolyline(std_dev_poly); painter.setPen(QPen(COLORS['perfect'], 4)); painter.drawPolyline(perfects_poly)
        painter.setBrush(COLORS['primary']); 
        for point in std_dev_poly: painter.drawEllipse(point, 5, 5)
        painter.setBrush(COLORS['perfect']); 
        for point in perfects_poly: painter.drawEllipse(point, 6, 6)
        painter.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        painter.setPen(COLORS['perfect']); painter.drawText(QPointF(plot_area.left(), plot_area.top() - 30), "● PERFECT数")
        painter.setPen(COLORS['primary']); painter.drawText(QPointF(plot_area.left() + 140, plot_area.top() - 30), "● タイミングのばらつき")
        painter.restore()

    def draw_result_graph(self, painter, rect):
        # (変更なし)
        painter.save(); painter.setBrush(COLORS['surface']); painter.setPen(QPen(COLORS['border'], 1)); painter.drawRoundedRect(rect, 15, 15)
        if not self.main.template_score or 'top' not in self.main.template_score: painter.restore(); return
        template = self.main.template_score; top_track = template.get('top')
        bpm = top_track.get('bpm', 120); num = top_track.get('numerator', 4); den = top_track.get('denominator', 4)
        beats_per_measure = (num / den) * 4.0; total_beats = beats_per_measure * NUM_MEASURES
        max_time_ms = (60.0 / bpm * total_beats) * 1000.0 if bpm > 0 else 0
        if max_time_ms <= 0: painter.restore(); return
        lanes = {'template_top': {'y': rect.top() + rect.height() * 0.25, 'label': "左（お手本）", 'color': COLORS['text_secondary'], 'data': top_track}, 'measured_top': {'y': rect.top() + rect.height() * 0.45, 'label': "左（演奏）", 'color': COLORS['primary'], 'data': [h for h in self.main.recorded_hits if h['pad'] == 'top']},}
        if 'bottom' in template:
            lanes['template_bottom'] = {'y': rect.top() + rect.height() * 0.65, 'label': "右（お手本）", 'color': COLORS['text_secondary'], 'data': template['bottom']}
            lanes['measured_bottom'] = {'y': rect.top() + rect.height() * 0.85, 'label': "右（演奏）", 'color': COLORS['success'], 'data': [h for h in self.main.recorded_hits if h['pad'] == 'bottom']}
        painter.setFont(QFont("Segoe UI", 11, QFont.Weight.Medium))
        for key, lane in lanes.items():
            painter.setPen(COLORS['text_secondary']); label_rect = QRectF(rect.left() - 100, lane['y'] - 12, 90, 24); painter.drawText(label_rect, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight, lane['label'])
            painter.setPen(QPen(COLORS['border'], 1, Qt.PenStyle.DashLine)); painter.drawLine(int(rect.left()), int(lane['y']), int(rect.right()), int(lane['y']))
        for key in ['template_top', 'template_bottom']:
            if key not in lanes: continue
            lane = lanes[key]; track_data, track_bpm = lane['data'], lane['data'].get('bpm', 120); painter.setBrush(lane['color']); painter.setPen(Qt.PenStyle.NoPen)
            for item in track_data.get('items', []):
                if item['class'] == 'note': time_ms = (item['beat'] / track_bpm * 60.0) * 1000.0; x = rect.left() + (time_ms / max_time_ms) * rect.width(); painter.drawRect(int(x - 2), int(lane['y']) - 10, 4, 20)
        for key in ['measured_top', 'measured_bottom']:
            if key not in lanes: continue
            lane = lanes[key]; painter.setBrush(lane['color']); painter.setPen(QPen(lane['color'].darker(120), 2))
            for hit in lane['data']:
                if max_time_ms > 0: x = rect.left() + (hit['time'] % max_time_ms) / max_time_ms * rect.width(); painter.drawEllipse(int(x) - 6, int(lane['y']) - 6, 12, 12)
        painter.restore()

    def draw_result_stats(self, painter, rect):
        # (変更なし)
        painter.save(); painter.setBrush(COLORS['surface']); painter.setPen(QPen(COLORS['border'], 1)); painter.drawRoundedRect(rect, 15, 15); painter.setPen(COLORS['text_primary']); painter.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        painter.drawText(rect.adjusted(0, 15, 0, 0), Qt.AlignmentFlag.AlignHCenter, "📊 パフォーマンス分析"); stats = self.main.result_stats
        if not stats: painter.restore(); return
        if self.main.is_perfect_mode and self.main.practice_loop_count > 0:
            painter.setFont(QFont("Segoe UI", 12, QFont.Weight.Medium)); painter.setPen(COLORS['warning']); painter.drawText(rect.adjusted(0, 45, 0, 0), Qt.AlignmentFlag.AlignHCenter, f"🎯 PERFECT練習: {self.main.practice_loop_count}回目で達成")
        font = QFont("Segoe UI", 11); y_pos = rect.top() + (75 if self.main.is_perfect_mode else 55); line_height = 24
        judgement_data = [('PERFECT', 'perfect', '🟡'), ('GREAT', 'great', '🟢'), ('GOOD', 'good', '🔵'), ('EXTRA', 'extra', '🔴'), ('見逃し', 'dropped', '⚫')]
        for label, key, emoji in judgement_data:
            painter.setFont(font); painter.setPen(COLORS['text_secondary']); painter.drawText(QPointF(rect.left() + 20, y_pos), f"{emoji} {label}")
            painter.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold)); painter.setPen(COLORS.get(key, COLORS['text_primary'])); painter.drawText(QRectF(rect.left(), y_pos - line_height/2, rect.width() - 20, line_height), Qt.AlignmentFlag.AlignRight, str(stats.get(key, 0)))
            y_pos += line_height
        y_pos += 2; painter.setPen(QPen(COLORS['border'], 1)); painter.drawLine(int(rect.left() + 20), int(y_pos), int(rect.right() - 20), int(y_pos)); y_pos += 12
        label_font = QFont("Segoe UI", 11); value_font = QFont("Segoe UI", 12, QFont.Weight.Bold)
        label_col_rect = QRectF(rect.left() + 20, y_pos, rect.width() / 2 - 20, line_height * 2); value_col_rect = QRectF(label_col_rect.right(), y_pos, rect.width() / 2 - 20, line_height * 2)
        painter.setFont(label_font); painter.setPen(COLORS['text_secondary']); painter.drawText(label_col_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop, "📈 達成率"); painter.drawText(label_col_rect.translated(0, line_height), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop, "📏 ばらつき")
        painter.setFont(value_font); painter.setPen(COLORS['text_primary']); painter.drawText(value_col_rect, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop, f"{stats.get('accuracy', 0):.1f}%"); painter.drawText(value_col_rect.translated(0, line_height), Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop, f"{stats.get('std_dev', 0):.2f}ms")
        painter.restore()

    def draw_ai_feedback(self, painter, rect):
        # (変更なし)
        painter.save(); painter.setBrush(COLORS['surface_light']); painter.setPen(QPen(COLORS['accent'], 1)); painter.drawRoundedRect(rect, 15, 15); painter.setPen(COLORS['accent'])
        painter.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold)); painter.drawText(rect.adjusted(20, 15, 0, 0), "🤖 AI講師からのアドバイス"); painter.setPen(COLORS['text_primary']); painter.setFont(QFont("Segoe UI", 12))
        text_rect = rect.adjusted(20, 45, -20, -15); flags = Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop | Qt.TextFlag.TextWordWrap
        painter.drawText(text_rect, flags, self.main.ai_feedback_text); painter.restore()


    # ★★★★★ ここから実験モード用描画メソッド群 ★★★★★

    def draw_experiment_default_state(self, painter):
        """ 実験モードの未定義状態 (フォールバック) """
        self.draw_waiting_state(painter) # とりあえず Ready を表示

    def draw_experiment_explanation_state(self, painter):
        """ 実験説明画面 """
        painter.setPen(COLORS['accent'])
        painter.setFont(QFont("Segoe UI", 36, QFont.Weight.Bold))
        painter.drawText(self.rect().adjusted(0, -100, 0, 0), Qt.AlignmentFlag.AlignCenter, "🧪 実験モード")
        
        painter.setPen(COLORS['text_primary'])
        painter.setFont(QFont("Segoe UI", 16))
        
        # 本来はここに説明文が入る
        text = "実験の説明文をここに追加します。\n\n(現在は空白です)\n\n準備ができたら「次へ」ボタンを押してください。"
        painter.drawText(self.rect().adjusted(50, 20, -50, 0), Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap, text)

    def draw_experiment_intro_state(self, painter):
        """ 
        実験の各ステップ (テスト/練習) の待機画面
        self.main から現在のセット/ステップ番号を取得して描画する
        """
        try:
            set_num = self.main.current_experiment_set_index + 1
            step_num = self.main.current_experiment_step
            config = self.main.experiment_steps_config[step_num]
            
            title = f"セット {set_num}/{len(self.main.experiment_sets)}: {config['title']}"
            description = config['description']
            color = config['color']
            
        except Exception as e:
            # (フォールバック)
            title = "エラー"
            description = f"実験データの読み込みに失敗しました: {e}"
            color = COLORS['danger']

        painter.setPen(color)
        painter.setFont(QFont("Segoe UI", 36, QFont.Weight.Bold))
        painter.drawText(self.rect().adjusted(0, -100, 0, 0), Qt.AlignmentFlag.AlignCenter, title)
        
        painter.setPen(COLORS['text_secondary'])
        painter.setFont(QFont("Segoe UI", 16))
        painter.drawText(self.rect().adjusted(50, 20, -50, 0), Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap, description)

    def draw_experiment_finished_state(self, painter):
        """ 実験終了画面 """
        painter.setPen(COLORS['success'])
        painter.setFont(QFont("Segoe UI", 36, QFont.Weight.Bold))
        painter.drawText(self.rect().adjusted(0, -100, 0, 0), Qt.AlignmentFlag.AlignCenter, "🎉 実験終了")
        
        painter.setPen(COLORS['text_primary'])
        painter.setFont(QFont("Segoe UI", 16))
        text = "ご協力ありがとうございました。\n「メインメニューに戻る」ボタンを押してください。"
        painter.drawText(self.rect().adjusted(50, 20, -50, 0), Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap, text)
        
        # (ここに結果のサマリーを表示してもよい)

    # --- 走行中の描画 (フリーモードと共通) ---
    def draw_experiment_running_state(self, painter):
        self.draw_recording_state(painter) # "頑張って！" を表示
        
        # (ここに結果のサマリーを表示してもよい)

    # --- 走行中の描画 (フリーモードと共通) ---
    def draw_experiment_test_A1_running_state(self, painter):
        self.draw_recording_state(painter) # "頑張って！" を表示
    
    def draw_experiment_practice_A_running_state(self, painter):
        self.draw_recording_state(painter) # "頑張って！" を表示
        
    def draw_experiment_test_A2_running_state(self, painter):
        self.draw_recording_state(painter) # "頑張って！" を表示

class EditorRhythmWidget(QWidget):
    def __init__(self, item_images, editor_window, parent=None):
        super().__init__(parent)
        self.editor_window = editor_window
        self.setMinimumHeight(240)
        self.item_images, self.score, self.is_playing = item_images, {}, False
        self.playback_timer = QTimer(self); self.playback_timer.timeout.connect(self.update_playback)
        self.last_metronome_beat, self.margin = -1, 60
        self.last_loop_num = -1
        self.user_hits, self.feedback_animations = [], []
        self.next_evaluation_time = 0
        self.loop_duration_ms = 0
        
    def reset_for_loop(self):
        self.user_hits.clear(); self.feedback_animations.clear()
        for track in self.score.values():
            for item in track.get('items', []):
                item['played_in_loop'] = False
                if 'lit_start_time' in item: del item['lit_start_time']
            track['last_elapsed_ms'] = -1
        self.last_metronome_beat = -1
        self.next_evaluation_time = self.loop_duration_ms

    def get_loop_duration(self):
        return self.loop_duration_ms
    def add_user_hit(self, hit_data):
        hit_data['received_time'] = time.perf_counter()
        self.user_hits.append(hit_data)
    def add_feedback_animation(self, judgement, hit_data):
        if judgement in ('extra', 'dropped'): return
        animation = {'text': judgement.upper() + "!", 'hit_time': hit_data['time'], 'pad': hit_data['pad'], 'start_time': time.perf_counter(), 'color': COLORS.get(judgement.lower(), COLORS['text_secondary'])}
        self.feedback_animations.append(animation)
    def update_playback(self):
        if not self.is_playing or not self.score: return
        
        # 1. 絶対的な経過時間を取得
        absolute_elapsed_ms = self.editor_window.get_elapsed_time()
        is_demo = self.editor_window.is_demo
        main_window = self.editor_window.main_window
        
        # 2. 練習の終了判定 (PERFECTモードまたは通常ループ)
        if not is_demo and self.loop_duration_ms > 0:
            if main_window.is_perfect_mode:
                if absolute_elapsed_ms >= self.next_evaluation_time:
                    main_window.evaluate_and_continue_loop()
                    return
            else:
                if absolute_elapsed_ms >= self.loop_duration_ms:  
                    self.editor_window.close(); return
        
        # 3. メトロノーム処理 (変更なし)
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
        
        # ★★★ ここからがポリリズム対応の修正 ★★★
        
        if self.loop_duration_ms <= 0:
            self.update()
            return # マスターのループ時間が未定義なら何もしない

        # 4. 全トラック共通の「マスター時間」における現在位置を計算
        current_time_in_loop = absolute_elapsed_ms % self.loop_duration_ms

        # 5. 全トラック共通の「マスター」ループ番号を計算
        current_loop_num = int(absolute_elapsed_ms / self.loop_duration_ms)
        
        # ★ 修正: self.score.get(...) を self.last_loop_num に変更
        last_loop_num = self.last_loop_num 

        # 6. ループが切り替わったら、全トラックのフラグをリセット
        if current_loop_num != last_loop_num:
            for track_data in self.score.values():
                # ★ 修正: int型などをスキップするガードを追加
                if not isinstance(track_data, dict):
                    continue
                for item in track_data.get('items', []):
                    item['played_in_loop'] = False
            
            # ★ 修正: self.score['...'] を self.last_loop_num に変更
            self.last_loop_num = current_loop_num 

        # 7. 全トラックを共通の `current_time_in_loop` で処理
        for track_data in self.score.values():
            # ★ 修正: int型などをスキップするガードを追加 (これがエラー箇所)
            if not isinstance(track_data, dict):
                continue
                
            track_ms_per_beat = 60000.0 / track_data.get('bpm', 120) # <- Error was here
            if track_ms_per_beat <= 0: continue
            
            for item in track_data.get('items', []):
                if item.get('played_in_loop', False):
                    continue  
                
                note_start_ms = item['beat'] * track_ms_per_beat
                time_diff = current_time_in_loop - note_start_ms
                
                if -16 <= time_diff <= 50:
                    if item.get('class') == 'note':
                        item['lit_start_time'] = absolute_elapsed_ms
                        if is_demo or (not is_demo and main_window.settings.get('guide_cue_on', False)):  
                            self.editor_window.play_note_sound()
                    
                    item['played_in_loop'] = True 
            
            # 8. 見逃し(dropped)判定 
            if not is_demo:
                # 'track_name' を track_data 辞書に保存しておく (set_data でやるのが望ましい)
                # ここでは 'top' か 'bottom' かをキーから探す
                track_name_key = 'unknown'
                for key, value in self.score.items():
                    if value is track_data:
                        track_name_key = key
                        break

                for note in track_data.get('items', []):
                    if note['class'] == 'note' and note.get('id') not in main_window.judged_notes:
                        note_time = note['beat'] * track_ms_per_beat
                        if current_time_in_loop > note_time + DROPPED_THRESHOLD:  
                            main_window.register_dropped_note(note['id'], track_name_key) # 修正

        # ★★★ 修正ここまで ★★★
        
        self.update()
        
        self.update()
    def set_data(self, score_data, loop_duration_ms=0):
        self.score = score_data
        for track_data in self.score.values():
            num, den = track_data.get('numerator', 4), track_data.get('denominator', 4)
            track_data['beats_per_measure'] = (num / den) * 4.0
            track_data['total_beats'] = track_data['beats_per_measure'] * NUM_MEASURES
        if loop_duration_ms > 0:
            self.loop_duration_ms = loop_duration_ms
        else:
            if 'top' in self.score:
                top_track = self.score['top']
                ms_per_beat = 60000.0 / top_track.get('bpm', 120)
                self.loop_duration_ms = ms_per_beat * top_track.get('total_beats', 1)
        self.next_evaluation_time = self.loop_duration_ms
        self.update()
    def start_playback(self):
        if not self.is_playing:
            self.is_playing = True
            self.reset_for_loop()
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
        
        if not self.score: return

        current_time_abs = self.editor_window.get_elapsed_time()
        layout_mode = self.editor_window.main_window.settings.get('score_layout', 'vertical')

        # 1. アイテムの点灯状態を更新 (全トラック共通)
        for track_data in self.score.values():
            for item in track_data.get('items', []):
                item['is_lit'] = item.get('class') == 'note' and 'lit_start_time' in item and (current_time_abs - item['lit_start_time']) < LIT_DURATION

        # 2. レイアウト固有の変数を定義
        staff_contexts = {} # 描画に必要なコンテキストを格納 {'top': {...}, 'bottom': {...}}
        is_two_track_mode = 'top' in self.score and 'bottom' in self.score

        if layout_mode == 'vertical' or not is_two_track_mode:
            # --- 縦表示 (または1トラックのみの場合) ---
            start_x, drawable_width = self.margin, self.width() - (self.margin * 2)
            if drawable_width <= 0: return

            staff_y_positions = {}
            if is_two_track_mode:
                staff_y_positions['top'] = self.height() * 0.4
                staff_y_positions['bottom'] = self.height() * 0.7
            elif 'top' in self.score: 
                staff_y_positions['top'] = self.height() * 0.55
            elif 'bottom' in self.score: # 'bottom' しかない場合
                staff_y_positions['bottom'] = self.height() * 0.55
            
            for track_name, staff_y in staff_y_positions.items():
                staff_contexts[track_name] = {
                    'y': staff_y,
                    'start_x': start_x,
                    'width': drawable_width,
                    'label_x_offset': 0 # 縦表示はオフセットなし
                }

        else: 
            # --- 横表示 (かつ2トラックモード) ---
            mid_x = self.width() / 2
            gap = self.margin / 2 # 中央の隙間

            # Top (Left) Area
            top_start_x = self.margin
            top_drawable_width = mid_x - self.margin - gap
            top_staff_y = self.height() / 2
            
            if top_drawable_width > 0 and 'top' in self.score:
                 staff_contexts['top'] = {
                    'y': top_staff_y,
                    'start_x': top_start_x,
                    'width': top_drawable_width,
                    'label_x_offset': 0 # 左側はオフセットなし
                }

            # Bottom (Right) Area
            bottom_start_x = mid_x + gap
            bottom_drawable_width = self.width() - bottom_start_x - self.margin
            bottom_staff_y = self.height() / 2

            if bottom_drawable_width > 0 and 'bottom' in self.score:
                staff_contexts['bottom'] = {
                    'y': bottom_staff_y,
                    'start_x': bottom_start_x,
                    'width': bottom_drawable_width,
                    'label_x_offset': bottom_start_x - 55 # L/Rラベルや拍子を描画するX座標を調整
                }

            # 中央の分割線を描画
            painter.setPen(QPen(COLORS['border'], 2, Qt.PenStyle.DashLine))
            painter.drawLine(int(mid_x), 40, int(mid_x), self.height() - 40)

        # 3. 楽譜 (Staff) の描画
        for track_name, ctx in staff_contexts.items():
            if track_name in self.score:
                self.draw_staff(
                    painter, 
                    track_name, # ★ track_name を渡す
                    self.score[track_name], 
                    ctx['y'], 
                    ctx['start_x'], 
                    ctx['width'], 
                    is_two_track_mode,
                    ctx['label_x_offset'] # ★ label_x_offset を渡す
                )
        
        # 4. ユーザーヒットとフィードバックの描画
        if not self.editor_window.is_demo:
            # staff_contexts をそのまま渡す
            self.draw_user_hits(painter, staff_contexts)
            self.draw_feedback_animations(painter, staff_contexts)
        
        # 5. 再生カーソルの描画
        is_in_countdown = (hasattr(self.editor_window, 'countdown_timer') and 
                           self.editor_window.countdown_timer.isActive())
        
        # (再生中 または カウントダウン中) かつ ループが定義済み の場合のみ描画
        if (self.is_playing or is_in_countdown) and self.loop_duration_ms > 0:
            
            current_time_abs = 0 # 現在の時間をms単位で計算するための変数
            
            # トラック'top'からBPMと拍数を取得 (BPMは負の時間の計算に必要)
            bpm = 120
            total_beats = 8.0
            if 'top' in self.score:
                track = self.score['top']
            elif 'bottom' in self.score: # 'top'がなければ'bottom'を見る
                track = self.score['bottom']
            else:
                track = {} # スコアが空ならデフォルト値
                
            bpm = track.get('bpm', 120)
            total_beats = track.get('total_beats', 8.0)
            
            ms_per_beat = (60000.0 / bpm) if bpm > 0 else 500.0 # 1拍あたりのミリ秒
            
            if self.is_playing:
                # 1. 再生中の場合 (時間は 0ms から増加)
                current_time_abs = self.editor_window.get_elapsed_time()
            
            else:
                # 2. カウントダウン中の場合 (時間は 0ms より前)
                time_until_start_s = self.editor_window.master_start_time - time.time()
                
                # time_until_start_s は 4, 3, 2, 1, 0... と減っていく
                # current_time_abs を -4000, -3000, ..., 0 のように負のmsで表現
                current_time_abs = time_until_start_s * -1000.0
                
                # ただし、我々が描画したいのは最後の1拍 (-1拍目から0拍目)
                # 最後の1拍 (e.g., -500ms) よりも前 (e.g., -3000ms) なら、カーソルは-1拍目に固定
                if current_time_abs < -ms_per_beat:
                    current_time_abs = -ms_per_beat

            # --- ここからX座標の計算 (再生中・カウントダウン共通) ---

            if self.editor_window.main_window.settings.get('guide_line_on', True):

                total_display_beats = total_beats + 1.0 # 助走(1拍) + 本体(8拍) = 9拍
                
                # 1. 現在の絶対時間 (ms) を「ビート」に変換する
                current_beat = 0.0
                if self.is_playing:
                    # ループを考慮 (e.g. 4500ms -> 4.5拍目)
                    current_time_in_loop_ms = current_time_abs % self.loop_duration_ms
                    current_beat = current_time_in_loop_ms / ms_per_beat
                else:
                    # 負の時間 (e.g., -250ms) を負のビート (e.g., -0.5拍目) に変換
                    current_beat = current_time_abs / ms_per_beat
                    if current_beat < -1.0: # 固定
                        current_beat = -1.0

                # 2. 「ビート」(-1.0 ~ 8.0) を X座標の「進捗率」(0.0 ~ 1.0) に変換
                # (beat -1.0 -> 0.0)
                # (beat 0.0  -> 1/9 = 0.111)
                # (beat 8.0  -> 9/9 = 1.0)
                cursor_progress_fraction = (current_beat + 1.0) / total_display_beats
                
                # 3. 全てのトラックコンテキストに描画
                for track_name, ctx in staff_contexts.items():
                    cursor_x = ctx['start_x'] + cursor_progress_fraction * ctx['width']
                    self.draw_glowing_cursor(painter, cursor_x, 40, self.height() - 40)

    def draw_user_hits(self, painter, staff_contexts):
        if not self.score or self.loop_duration_ms <= 0: return
        
        visible_hits = [h for h in self.user_hits if time.perf_counter() - h['received_time'] <= 1.5]
        self.user_hits = visible_hits
        
        for hit in visible_hits:
            pad = hit['pad']
            if pad not in staff_contexts: continue # このパッドの描画コンテキストがないならスキップ
            
            ctx = staff_contexts[pad]
            track_data = self.score.get(pad)
            if not track_data: continue
            total_beats = track_data.get('total_beats', 8.0)
            if total_beats <= 0: continue
            total_display_beats = total_beats + 1.0
            
            hit_progress = (hit['time'] % self.loop_duration_ms) / self.loop_duration_ms
            hit_beat = hit_progress * total_beats
            hit_pos_fraction = (hit_beat + 1.0) / total_display_beats
            
            x = ctx['start_x'] + hit_pos_fraction * ctx['width']
            y = ctx['y']
            
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
    def draw_feedback_animations(self, painter, staff_contexts):
        if self.loop_duration_ms <= 0: return
        
        visible_animations = [a for a in self.feedback_animations if time.perf_counter() - a['start_time'] <= 1.0]
        self.feedback_animations = visible_animations
        
        for anim in visible_animations:
            pad = anim['pad']
            if pad not in staff_contexts: continue # コンテキストがなければスキップ
            
            ctx = staff_contexts[pad]
            track_data = self.score.get(pad)
            if not track_data: continue
            total_beats = track_data.get('total_beats', 8.0)
            if total_beats <= 0: continue
            total_display_beats = total_beats + 1.0

            hit_progress = (anim['hit_time'] % self.loop_duration_ms) / self.loop_duration_ms
            hit_beat = hit_progress * total_beats
            hit_pos_fraction = (hit_beat + 1.0) / total_display_beats

            x = ctx['start_x'] + hit_pos_fraction * ctx['width']
            y_start = ctx['y']
            
            age = time.perf_counter() - anim['start_time']
            y = y_start - (age * 60) # アニメーションで上昇
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
        painter.setPen(Qt.PenStyle.NoPen)
        glow_layers = [
            (14, 20),
            (10, 40),
            (6, 80),
            (2, 255)
        ]
        for width, alpha in glow_layers:
            cursor_color = QColor(COLORS['cursor'])
            cursor_color.setAlpha(alpha)
            painter.setBrush(cursor_color)
            rect_x = x - (width / 2)
            painter.drawRect(QRectF(rect_x, y1, width, y2 - y1))
    def draw_staff(self, painter, track_name, track_data, staff_y, start_x, drawable_width, is_two_track_mode, label_x_offset=0):
        beats_per_measure = track_data.get('beats_per_measure', 4.0)
        total_beats = track_data.get('total_beats', 8.0)

        if total_beats <= 0: return # ガード
        total_display_beats = total_beats + 1.0
        
        painter.save()
        
        # L/R ラベル と 拍子記号
        if is_two_track_mode:
            # L/R ラベル
            label_color = COLORS['primary'] if track_name == 'top' else COLORS['success']
            painter.setFont(QFont("Segoe UI", 18, QFont.Weight.Bold))
            painter.setPen(label_color)
            label = "L" if track_name == 'top' else "R"
            
            label_bg = QColor(label_color)
            label_bg.setAlpha(30)
            painter.setBrush(label_bg)
            
            # ★ label_x_offset を使用
            label_center_x = label_x_offset + 30
            painter.drawEllipse(QPointF(label_center_x, staff_y), 20, 20)
            
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawText(QRectF(label_center_x - 20, staff_y - 15, 40, 30), Qt.AlignmentFlag.AlignCenter, label)
            
            # 拍子記号
            painter.setFont(QFont("Segoe UI", 12, QFont.Weight.Medium))
            painter.setPen(COLORS['text_secondary'])
            ts_text = f"{track_data.get('numerator', 4)}\n─\n{track_data.get('denominator', 4)}"
            
            # ★ label_x_offset を使用
            ts_rect_x = label_x_offset + 5
            painter.drawText(QRectF(ts_rect_x, staff_y - 10, 50, 35), Qt.AlignmentFlag.AlignCenter, ts_text)

        elif 'top' in self.score or 'bottom' in self.score: # 1トラックモード (縦表示)
            # 拍子記号のみ (label_x_offset は 0 のはず)
            painter.setFont(QFont("Segoe UI", 12, QFont.Weight.Medium))
            painter.setPen(COLORS['text_secondary'])
            ts_text = f"{track_data.get('numerator', 4)}\n─\n{track_data.get('denominator', 4)}"
            painter.drawText(QRectF(label_x_offset + 5, staff_y - 10, 50, 35), Qt.AlignmentFlag.AlignCenter, ts_text)

        painter.restore()
        
        # 譜面線
        painter.setPen(QPen(COLORS['staff_line'], 2))
        painter.drawLine(int(start_x), int(staff_y), int(start_x + drawable_width), int(staff_y)) # ✅ This is the fix
        beat_zero_x = start_x + (1.0 / total_display_beats) * drawable_width
        painter.setPen(QPen(COLORS['text_primary'], 3)) # 目立つように
        painter.drawLine(int(beat_zero_x), int(staff_y - 15), int(beat_zero_x), int(staff_y + 15))
        
        # 拍の線
        if total_beats > 0:
            # i = 0, 1, ..., 8
            for i in range(0, int(total_beats) + 1):
                beat = float(i) # 0.0, 1.0, ..., 8.0
                x_fraction = (beat + 1.0) / total_display_beats
                x = start_x + x_fraction * drawable_width
                
                # i=0 (ビート0) の開始線
                if i == 0:
                    painter.setPen(QPen(COLORS['text_primary'], 3)) # 目立つように
                    painter.drawLine(int(x), int(staff_y - 15), int(x), int(staff_y + 15))
                # i=1...8 の線
                else:
                    is_measure_line = (i > 0 and i % beats_per_measure == 0) and i != total_beats
                    if is_measure_line:
                        painter.setPen(QPen(COLORS['text_secondary'], 2))
                        painter.drawLine(int(x), int(staff_y - 15), int(x), int(staff_y + 15))
                    else:
                        painter.setPen(QPen(COLORS['text_muted'], 1, Qt.PenStyle.DotLine))
                        painter.drawLine(int(x), int(staff_y - 8), int(x), int(staff_y + 8))

            # --- 助走領域 (ビート 0 より左) の線を追加 ---
            
            # 1. ビート -1 (左端) の線
            beat_minus_1 = -1.0
            x_fraction = (beat_minus_1 + 1.0) / total_display_beats # (0.0 / 9.0) = 0.0
            x = start_x + x_fraction * drawable_width # start_x
            
            painter.setPen(QPen(COLORS['text_secondary'], 2)) # 小節線と同じ
            painter.drawLine(int(x), int(staff_y - 15), int(x), int(staff_y + 15))

            # 2. 助走領域の間の線 (4/4拍子なら -0.75, -0.5, -0.25)
            # (ここでは単純に 0.25 刻みで描画)
            if beats_per_measure > 1: # 1/4拍子とかでなければ
                sub_beats = [b * 0.25 for b in range(1, 4)] # [0.25, 0.5, 0.75]
                for sub in sub_beats:
                    beat = -1.0 + sub # -0.75, -0.5, -0.25
                    x_frac = (beat + 1.0) / total_display_beats
                    x_sub = start_x + x_frac * drawable_width
                    painter.setPen(QPen(COLORS['text_muted'], 1, Qt.PenStyle.DotLine))
                    painter.drawLine(int(x_sub), int(staff_y - 8), int(x_sub), int(staff_y + 8))
        
        # ノートと休符
        for item in track_data.get('items', []):
            self.draw_item(painter, item, staff_y, start_x, drawable_width, total_beats, total_display_beats)

    def draw_item(self, painter, item, staff_y, start_x, drawable_width, total_beats_on_track, total_display_beats):
        # if total_beats_on_track <= 0: return # 古い
        if total_display_beats <= 0: return # ★新しいガード
        
        # ★★★ x と width の計算を修正 ★★★
        x_fraction = (item['beat'] + 1.0) / total_display_beats
        x = start_x + x_fraction * drawable_width
        
        width_fraction = item['duration'] / total_display_beats
        width = width_fraction * drawable_width
        item_rect = QRectF(x, staff_y - 30, width, 60)
        painter.save()
        if item.get('class') == 'note':
            guide_circle_radius = 6; guide_circle_center_x = item_rect.left(); guide_circle_center_y = staff_y
            painter.setBrush(COLORS['primary']); painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(QPointF(guide_circle_center_x, guide_circle_center_y), guide_circle_radius, guide_circle_radius)
            
            if self.editor_window.main_window.settings.get('score_blinking_on', True):
                if item.get('is_lit', False):
                    for radius, alpha in [(40, 20), (30, 40), (20, 60)]:
                        glow_color = QColor(COLORS['note_glow']); glow_color.setAlpha(alpha)
                        painter.setBrush(glow_color); painter.setPen(Qt.PenStyle.NoPen); painter.drawEllipse(QPointF(guide_circle_center_x, guide_circle_center_y), radius, radius)
                    painter.setBrush(COLORS['note_glow']); painter.setPen(QPen(COLORS['primary'].lighter(150), 3))
                    painter.drawRoundedRect(item_rect.adjusted(-4, -4, 4, 4), 10, 10)

            painter.setBrush(Qt.BrushStyle.NoBrush); painter.setPen(QPen(COLORS['primary'], 2)); painter.drawRoundedRect(item_rect, 8, 8)
        else:
            painter.setBrush(COLORS['rest_bg']); painter.setPen(QPen(COLORS['border'], 1)); painter.drawRoundedRect(item_rect, 8, 8)
        painter.restore()
        image_to_draw = self.item_images.get(item['type'])
        if image_to_draw:
            draw_y = item_rect.top() + (item_rect.height() - image_to_draw.height()) / 2
            draw_point = QPointF(item_rect.left() + 8, draw_y)
            painter.drawPixmap(draw_point, image_to_draw)
            if item.get('dotted', False):
                dot_x, dot_y = draw_point.x() + image_to_draw.width() + 6, staff_y + 18
                painter.save(); painter.setBrush(COLORS['text_primary']); painter.setPen(Qt.PenStyle.NoPen); painter.drawEllipse(QPointF(dot_x, dot_y), 4, 4); painter.restore()
        else:
            painter.setPen(COLORS['text_primary']); painter.setFont(QFont("Segoe UI", 10, QFont.Weight.Medium)); painter.drawText(item_rect, Qt.AlignmentFlag.AlignCenter, ALL_DURATIONS[item['type']]['name'])

class EditorWindow(QMainWindow):
    def __init__(self, template_data, main_window, item_images, is_demo=False, parent=None, loop_duration_ms=0, robot_prep_time_s=0, master_start_time=0):
        super().__init__(parent)
        self.main_window = main_window; self.is_demo = is_demo; self.template_data = template_data
        self.robot_prep_time_s = robot_prep_time_s; self.robot_triggered = False; self.master_start_time = master_start_time
        self.was_manually_stopped = False
        title = "🎼 お手本再生" if is_demo else "🥁 練習中"; self.setWindowTitle(title)

        # ★★★ ここから修正 ★★★
        # メインウィンドウの設定から現在のレイアウトモードを取得
        layout_mode = self.main_window.settings.get('score_layout', 'vertical')
        
        if layout_mode == 'horizontal':
            # 横並びモードの場合、ウィンドウをより広くする
            self.resize(2000, 650) 
        else:
            # 縦並びモードの場合 (元のサイズか、少し縦長に)
            self.resize(1500, 750) # 縦に2つ並べるため、少し高さを増やす
        
        self.setStyleSheet(f"QMainWindow {{ background-color: {COLORS['background'].name()}; color: {COLORS['text_primary'].name()}; }}")
        try:
            screen = QApplication.screenAt(QCursor.pos())
            if not screen: screen = QApplication.primaryScreen()
            center_point = screen.availableGeometry().center()
            self.move(int(center_point.x() - self.width() / 2), int(center_point.y() - self.height() / 2))
        except Exception: self.setGeometry(150, 150, 1300, 450)
        central_widget = QWidget(); self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        layout.setContentsMargins(0, 0, 0, 0); layout.setSpacing(0)
        header_widget = QWidget(); header_widget.setFixedHeight(60)
        header_widget.setStyleSheet(f"background: {COLORS['surface'].name()}; border-bottom: 1px solid {COLORS['border'].name()};")
        header_layout = QHBoxLayout(header_widget); header_layout.setContentsMargins(20, 0, 20, 0)
        title_label = QLabel(title); title_label.setFont(QFont("Segoe UI", 20, QFont.Weight.Bold))
        title_color_key = 'success' if is_demo else 'primary'; title_label.setStyleSheet(f"color: {COLORS[title_color_key].name()}; background: transparent;")
        header_layout.addWidget(title_label); header_layout.addStretch()
        self.stop_button = ModernButton("⏹️ " + ("再生停止" if is_demo else "練習中止"), "danger"); self.stop_button.clicked.connect(self.force_stop_practice)
        header_layout.addWidget(self.stop_button); layout.addWidget(header_widget)
        self.rhythm_widget = EditorRhythmWidget(item_images, self)
        layout.addWidget(self.rhythm_widget)
        self.rhythm_widget.set_data(copy.deepcopy(template_data), loop_duration_ms)
        self.countdown_label = QLabel(self)
        self.countdown_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.countdown_label.setStyleSheet(f"color: {COLORS['text_primary'].name()}; background-color: rgba(248, 249, 250, 0.8); border-radius: 20px;")
        self.countdown_label.setFont(QFont("Segoe UI", 150, QFont.Weight.Bold))
        if self.is_demo:
            self.countdown_label.hide(); self.start_actual_playback()
        else:
            self.countdown_timer = QTimer(self); self.countdown_timer.timeout.connect(self.update_countdown); self.countdown_timer.start(50)
            
    def update_countdown(self):
        time_until_start = self.master_start_time - time.time()
        if self.main_window.robot_manager and not self.robot_triggered:
            if time_until_start <= self.robot_prep_time_s:
                self.main_window.robot_manager.trigger_start(); self.robot_triggered = True
        bpm = self.template_data['top'].get('bpm', 120); beat_duration_s = 60.0 / bpm
        current_text = self.countdown_label.text(); new_text = ""
        if time_until_start > beat_duration_s * 3:
            new_text = "3"
            if current_text == "": self.main_window.play_countdown_sound()
        elif time_until_start > beat_duration_s * 2: new_text = "2"
        elif time_until_start > beat_duration_s * 1: new_text = "1"
        elif time_until_start > 0: new_text = "START!"
        else:
            self.countdown_timer.stop(); self.countdown_label.hide()
            self.start_actual_playback(); return
        if new_text != "" and current_text != new_text:
            if new_text in ["2", "1", "START!"]: self.main_window.play_countdown_sound()
            if new_text == "START!": self.countdown_label.setFont(QFont("Segoe UI", 70, QFont.Weight.Bold))
            else: self.countdown_label.setFont(QFont("Segoe UI", 150, QFont.Weight.Bold))
            self.countdown_label.setText(new_text)
        self.rhythm_widget.update()
        
    def start_actual_playback(self):
        if self.main_window.silent_wav_buffer:
            buffer_copy = io.BytesIO(self.main_window.silent_wav_buffer)
            pygame.mixer.music.load(buffer_copy)
            pygame.mixer.music.play(-1)
        if self.main_window.robot_manager and not self.robot_triggered:
            self.main_window.robot_manager.trigger_start()
        self.main_window.begin_real_recording()
        self.rhythm_widget.start_playback()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        label_size = min(self.width(), self.height()) * 0.7
        self.countdown_label.setGeometry(int((self.width() - label_size) / 2), int((self.height() - label_size) / 2), int(label_size), int(label_size))
        
    def force_stop_practice(self): 
        self.was_manually_stopped = True # ★★★ この行を追加 ★★★
        self.close()
    
    def closeEvent(self, event):
        self.rhythm_widget.stop_playback()
        if hasattr(self, 'countdown_timer'): self.countdown_timer.stop()
        if self.main_window.editor_window is self:
            
            # ★★★ 以下のように修正 ★★★
            # 理由が何であれ (force_stop=True) を渡すのをやめる
            # self.main_window.finish_performance(is_demo=self.is_demo, force_stop=True)
            
            # 停止ボタンが押された場合のみ force_stop=True を渡す
            is_forced = getattr(self, 'was_manually_stopped', False)
            self.main_window.finish_performance(is_demo=self.is_demo, force_stop=is_forced)
            # ★★★ 修正ここまで ★★★
            
        event.accept()
        
    def get_elapsed_time(self):
        if pygame.mixer.get_init():
            return pygame.mixer.music.get_pos()
        else:
            return 0 # ミキサーが終了済みの場合は 0 を返す
        #return self.main_window.get_elapsed_time()

    def play_note_sound(self): self.main_window.play_note_sound()
    def play_metronome_sound(self, is_accent): self.main_window.play_metronome_sound(is_accent)

def run_drum_trainer():
    app = QApplication.instance() or QApplication(sys.argv)
    if not pygame.get_init(): pygame.init()
    win = MainWindow()
    win.showMaximized()
    timer = QTimer(); timer.start(500); timer.timeout.connect(lambda: None)
    sys.exit(app.exec())

if __name__ == "__main__":
    run_drum_trainer()