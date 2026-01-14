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
from PyQt6.QtCore import (
    Qt, QTimer, QRectF, QPointF, QObject, pyqtSignal, QThread, QPropertyAnimation,
    QEasingCurve, pyqtProperty, pyqtSlot
)
from PyQt6.QtGui import (
    QPainter, QColor, QFont, QPen, QPixmap, QLinearGradient, QCursor, QPolygonF, QRadialGradient, QBrush, QPainterPath
)
import mido
import pygame
import pyttsx3
from PyQt6.QtWidgets import QFrame

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
    import robot_control_module_v4
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
PAD_MAPPING = {'left': [47, 56], 'right': [48, 29]}; VELOCITY_THRESHOLD = 25; LIT_DURATION = 150; NUM_MEASURES = 2
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

        # ★ 2. 他
        for filename in os.listdir(controller_dir):
            if filename.endswith(".py") and filename not in ["base_controller.py", "__init__.py"]:
                module_name = f"controllers.{filename[:-3]}"
                try:
                    module = importlib.import_module(module_name)
                    for name, obj in inspect.getmembers(module, inspect.isclass):
                        if issubclass(obj, BaseEntrainmentController) and obj is not BaseEntrainmentController:
                            try:
                                instance = obj(None, 0); 
                                # ★★★ ここからが修正点 ★★★
                                 # 1. まず、ファイルに定義された名前で登録する
                                controllers[instance.name] = obj
 
                            except Exception as e: print(f"エラー: コントローラー {name} のインスタンス化に失敗: {e}")
                except ImportError as e: print(f"エラー: コントローラーモジュール {module_name} のインポートに失敗: {e}")
    except ImportError as e: print(f"エラー: BaseEntrainmentControllerをインポートできませんでした。詳細: {e}")

    # 登録確認
    print(f"読み込まれたコントローラー: {list(controllers.keys())}")
    return controllers


# ★★★ 修正版: 順次再生制御（キューイング）を実装した音声クラス ★★★

class SpeechWorker(QObject):
    """ 音声合成を別スレッドで実行するワーカー """
    finished = pyqtSignal()
    started = pyqtSignal()

    def __init__(self):
        super().__init__()
        self._is_stopping = False
        self._engine = None

    def _on_word(self, name, location, length):
        """ 単語コールバック: 停止フラグがあれば止める """
        if self._is_stopping:
            if self._engine:
                try:
                    self._engine.stop()
                except: pass

    @pyqtSlot(str)
    def speak(self, text):
        # 1. フラグ初期化
        self._is_stopping = False
        
        try:
            # 2. エンジン初期化 (使い捨て)
            engine = pyttsx3.init()
            self._engine = engine
            
            # 設定
            voices = engine.getProperty('voices')
            for v in voices:
                if "jp" in v.id.lower() or "japanese" in v.name.lower():
                    engine.setProperty('voice', v.id)
                    break
            engine.setProperty('rate', 160)
            engine.setProperty('volume', 1.0)
            
            # 停止検知用のコールバック
            engine.connect('started-word', self._on_word)
            
            # 3. 再生
            self.started.emit()
            
            # --- ★★★ 読み間違いの補正処理 ★★★ ---
            clean_text = text.replace('\n', '。').replace(' ', '、')

            # 読み替え辞書: { "元の単語": "読ませたいひらがな" }
            # ※ 注意: 「音符(おんぷ)」を「おとぷ」と読まないよう、単体ではなく文脈で指定すると安全です
            replacements = {
                "間": "あいだ",           # "かん" -> "あいだ"
                "音を": "おとを",         # "おんを" -> "おとを"
                "この音": "このおと",     # "このおん" -> "このおと"
                "音の": "おとの",
                "音符": "おんぷ",         # これは "おん" のままでOK（明示的に指定しておくと安全）
                "打撃": "だげき",         # 念のため
                "左手": "ひだりて",       # "さしゅ" と読まれるのを防ぐ
                "右手": "みぎて",         # "うしゅ" と読まれるのを防ぐ
                "進め方": "すすめかた",
                "行って": " おこなって",
            }

            for original, reading in replacements.items():
                clean_text = clean_text.replace(original, reading)
            # -------------------------------------------

            engine.say(clean_text)
            engine.runAndWait()
            
        except Exception as e:
            print(f"TTS Error: {e}")
        finally:
            self._engine = None
            self.finished.emit()

    @pyqtSlot()
    def stop(self):
        """ 停止リクエスト """
        self._is_stopping = True
        # 即時停止を試みる
        if self._engine:
            try:
                self._engine.stop()
            except: pass


class SpeechManager(QObject):
    """ 音声の再生順序を管理するクラス（連打対策済み） """
    request_speak = pyqtSignal(str)
    request_stop = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.thread = QThread()
        self.worker = SpeechWorker()
        self.worker.moveToThread(self.thread)
        
        # シグナル接続
        self.request_speak.connect(self.worker.speak)
        self.request_stop.connect(self.worker.stop)
        self.worker.finished.connect(self._on_worker_finished)
        
        self.thread.start()

        # 状態管理変数
        self._is_busy = False      # 現在再生中かどうか
        self._pending_text = None  # 次に再生待ちのテキスト

    def speak(self, text):
        """ 読み上げリクエスト """
        if not text: return

        if self._is_busy:
            # 再生中なら、停止命令を出しつつ、次のテキストを「予約」する
            # 「次へ」を連打した場合は、最新のテキストで上書きされる
            self._pending_text = text
            self.request_stop.emit()
        else:
            # アイドル状態なら即再生
            self._is_busy = True
            self._pending_text = None
            self.request_speak.emit(text)

    def stop(self):
        """ 完全停止（予約もクリア） """
        self._pending_text = None
        self.request_stop.emit()

    def _on_worker_finished(self):
        """ 再生（または停止処理）が終わったときに呼ばれる """
        self._is_busy = False
        
        # 次に再生すべきテキストが待機しているか？
        if self._pending_text:
            text = self._pending_text
            self._pending_text = None # 予約消費
            
            # 少しだけ間隔を空けて次の再生を開始（エンジンのリソース解放待ち）
            self._is_busy = True
            QTimer.singleShot(50, lambda: self.request_speak.emit(text))

    def cleanup(self):
        self.stop()
        self.thread.quit()
        self.thread.wait()


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
        
        # ★ 修正: 縦幅を大きく確保し、スクロールなしで収める (600x500 -> 650x750)
        self.setMinimumSize(650, 750)
        
        self.setStyleSheet(f"""
            QDialog {{
                background: {COLORS['background'].name()};
                color: {COLORS['text_primary'].name()};
                border: 1px solid {COLORS['border'].name()};
                border-radius: 15px;
            }}
            /* スクロールエリアを削除したため、直接Widgetのスタイルを定義 */
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
                margin: -5px 0;
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
            QLabel {{
                color: {COLORS['text_secondary'].name()};
                font-weight: bold;
                font-size: 15px; /* 見やすく少し大きく */
            }}
        """)
        
        self.settings = current_settings.copy()
        
        # --- メインレイアウト ---
        # スクロールエリアを使わず、直接レイアウトに配置します
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(20) # 項目間のゆとりを持たせる
        main_layout.setContentsMargins(30, 30, 30, 30)
        
        # タイトル的なものを入れるとおさまりが良い
        title_label = QLabel("詳細設定")
        title_label.setStyleSheet(f"color: {COLORS['accent'].name()}; font-size: 20px; font-weight: bold;")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(title_label)

        # ------------------------------------------------
        # 1. スライダー・コンボボックス (フォームレイアウト)
        # ------------------------------------------------
        form_layout = QFormLayout()
        form_layout.setSpacing(15)
        form_layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight) # ラベル右寄せで見やすく
        
        self.drum_volume_slider = QSlider(Qt.Orientation.Horizontal)
        self.drum_volume_slider.setRange(0, 100)
        self.drum_volume_slider.setValue(int(self.settings['drum_volume'] * 100))
        
        self.metronome_volume_slider = QSlider(Qt.Orientation.Horizontal)
        self.metronome_volume_slider.setRange(0, 100)
        self.metronome_volume_slider.setValue(int(self.settings['metronome_volume'] * 100))
        
        self.guide_volume_slider = QSlider(Qt.Orientation.Horizontal)
        self.guide_volume_slider.setRange(0, 100)
        self.guide_volume_slider.setValue(int(self.settings['guide_cue_volume'] * 100))
        
        self.level_combo = QComboBox()
        self.levels = {"p100": "PERFECT 100%", "p50_g100": "PERFECT 50%以上 & GREAT含め100%", "g100": "GREAT以上 100%"}
        for key, text in self.levels.items(): self.level_combo.addItem(text, userData=key)
        current_level_key = self.settings.get('practice_level', 'p100')
        if current_level_key in self.levels: self.level_combo.setCurrentIndex(list(self.levels.keys()).index(current_level_key))
        
        self.score_order_combo = QComboBox()
        self.score_orders = {
            'test1_test2_test3': "test1 -> test2 -> test3 (標準)",
            'test1_test3_test2': "test1 -> test3 -> test2",
            'test2_test1_test3': "test2 -> test1 -> test3",
            'test2_test3_test1': "test2 -> test3 -> test1",
            'test3_test1_test2': "test3 -> test1 -> test2",
            'test3_test2_test1': "test3 -> test2 -> test1",
        }
        default_score_order = ['test1', 'test2', 'test3']
        current_score_order_key = "_".join(self.settings.get('score_order', default_score_order))
        idx = 0; current_score_index = 0
        for key, text in self.score_orders.items():
            self.score_order_combo.addItem(text, userData=key)
            if key == current_score_order_key: current_score_index = idx
            idx += 1
        self.score_order_combo.setCurrentIndex(current_score_index)

        self.experiment_order_combo = QComboBox()
        self.experiment_orders = {
            'linear_passthrough_metronome': "線形 -> 介入なし -> メトロノーム",
            'linear_metronome_passthrough': "線形 -> メトロノーム -> 介入なし",
            'passthrough_linear_metronome': "介入なし -> 線形 -> メトロノーム",
            'passthrough_metronome_linear': "介入なし -> メトロノーム -> 線形",
            'metronome_linear_passthrough': "メトロノーム -> 線形 -> 介入なし",
            'metronome_passthrough_linear': "メトロノーム -> 介入なし -> 線形",
        }
        default_order = ['linear', 'passthrough', 'metronome']
        current_order_key = "_".join(self.settings.get('experiment_order', default_order))
        current_index = 0; idx = 0
        for key, text in self.experiment_orders.items():
            self.experiment_order_combo.addItem(text, userData=key)
            if key == current_order_key: current_index = idx
            idx += 1
        self.experiment_order_combo.setCurrentIndex(current_index)

        form_layout.addRow("🥁 ドラム音量:", self.drum_volume_slider)
        form_layout.addRow("🎵 メトロノーム音量:", self.metronome_volume_slider)
        form_layout.addRow("🔊 ガイド音音量:", self.guide_volume_slider)
        form_layout.addRow("🎯 PERFECT練習レベル:", self.level_combo)
        form_layout.addRow("🎼 楽譜セット順序:", self.score_order_combo)
        form_layout.addRow("🧪 実験練習順序:", self.experiment_order_combo)
        
        main_layout.addLayout(form_layout)
        
        # 区切り線
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)
        line.setStyleSheet(f"background-color: {COLORS['border'].name()};")
        main_layout.addWidget(line)

        # ------------------------------------------------
        # 2. トグルボタン (グリッドレイアウト)
        # ------------------------------------------------
        from PyQt6.QtWidgets import QGridLayout
        grid_layout = QGridLayout()
        grid_layout.setSpacing(15)
        
        # ボタン生成 (高さ固定で揃える)
        btn_height = 45
        
        self.metronome_toggle_button = ModernButton("", "success"); self.metronome_toggle_button.setFixedHeight(btn_height)
        self.metronome_toggle_button.clicked.connect(self.toggle_metronome)
        
        self.guide_toggle_button = ModernButton("", "success"); self.guide_toggle_button.setFixedHeight(btn_height)
        self.guide_toggle_button.clicked.connect(self.toggle_guide)
        
        self.blinking_toggle_button = ModernButton("", "success"); self.blinking_toggle_button.setFixedHeight(btn_height)
        self.blinking_toggle_button.clicked.connect(self.toggle_blinking)
        
        self.guideline_toggle_button = ModernButton("", "success"); self.guideline_toggle_button.setFixedHeight(btn_height)
        self.guideline_toggle_button.clicked.connect(self.toggle_guide_line)

        self.layout_toggle_button = ModernButton("", "primary"); self.layout_toggle_button.setFixedHeight(btn_height)
        self.layout_toggle_button.clicked.connect(self.toggle_layout)

        self.monitor_toggle_button = ModernButton("", "danger"); self.monitor_toggle_button.setFixedHeight(btn_height)
        self.monitor_toggle_button.clicked.connect(self.toggle_monitor)
        
        self.show_score_toggle_button = ModernButton("", "primary"); self.show_score_toggle_button.setFixedHeight(btn_height)
        self.show_score_toggle_button.clicked.connect(self.toggle_show_score)

        self.feedback_toggle_button = ModernButton("", "primary")
        self.feedback_toggle_button.setFixedHeight(btn_height)
        self.feedback_toggle_button.clicked.connect(self.toggle_feedback)

        # グリッド配置
        grid_layout.addWidget(self.metronome_toggle_button, 0, 0)
        grid_layout.addWidget(self.guide_toggle_button, 0, 1)
        
        grid_layout.addWidget(self.blinking_toggle_button, 1, 0)
        grid_layout.addWidget(self.guideline_toggle_button, 1, 1)
        
        grid_layout.addWidget(self.layout_toggle_button, 2, 0)
        grid_layout.addWidget(self.monitor_toggle_button, 2, 1)
        
        grid_layout.addWidget(self.show_score_toggle_button, 3, 0, 1, 2)
        grid_layout.addWidget(self.feedback_toggle_button, 4, 0, 1, 2)
        
        main_layout.addLayout(grid_layout)
        
        # スペーサー (下詰め)
        main_layout.addStretch()

        # --- OK / Cancel ボタン ---
        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        self.button_box.setStyleSheet(f"""
            QPushButton {{
                background: {COLORS['primary'].name()};
                color: white;
                border: 1px solid {COLORS['primary'].lighter(120).name()};
                border-radius: 8px;
                padding: 12px 30px;
                font-weight: bold;
                font-size: 14px;
                min-width: 120px;
            }}
            QPushButton:hover {{
                background: {COLORS['primary_dark'].name()};
            }}
        """)
        main_layout.addWidget(self.button_box, 0, Qt.AlignmentFlag.AlignCenter)

        # スタイルの初期更新
        self.update_metronome_button_style()
        self.update_guide_button_style()
        self.update_blinking_button_style()
        self.update_guide_line_button_style()
        self.update_layout_button_style() 
        self.update_monitor_button_style()
        self.update_show_score_button_style()

        self.update_feedback_button_style()

    # --- 各トグル処理 (ロジックは変更なし) ---
    def toggle_metronome(self): 
        self.settings['metronome_on'] = not self.settings.get('metronome_on', False)
        self.update_metronome_button_style()
        
    def update_metronome_button_style(self):
        if self.settings.get('metronome_on', False): 
            self.metronome_toggle_button.setText("🎵 メトロノーム : ON")
            self.metronome_toggle_button.button_type = "success"
            self.metronome_toggle_button.bg_color = COLORS['success']
            self.metronome_toggle_button.hover_color = COLORS['success_dark']
        else: 
            self.metronome_toggle_button.setText("🔇 メトロノーム : OFF")
            self.metronome_toggle_button.button_type = "danger"
            self.metronome_toggle_button.bg_color = COLORS['danger']
            self.metronome_toggle_button.hover_color = COLORS['danger_dark']
        self.metronome_toggle_button.update_style()
        
    def toggle_guide(self): 
        self.settings['guide_cue_on'] = not self.settings.get('guide_cue_on', False)
        self.update_guide_button_style()
        
    def update_guide_button_style(self):
        if self.settings.get('guide_cue_on', False): 
            self.guide_toggle_button.setText("🔊 ガイド音 : ON")
            self.guide_toggle_button.button_type = "success"
            self.guide_toggle_button.bg_color = COLORS['success']
            self.guide_toggle_button.hover_color = COLORS['success_dark']
        else: 
            self.guide_toggle_button.setText("🔇 ガイド音 : OFF")
            self.guide_toggle_button.button_type = "danger"
            self.guide_toggle_button.bg_color = COLORS['danger']
            self.guide_toggle_button.hover_color = COLORS['danger_dark']
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
        
    def toggle_layout(self):
        current_layout = self.settings.get('score_layout', 'vertical')
        self.settings['score_layout'] = 'horizontal' if current_layout == 'vertical' else 'vertical'
        self.update_layout_button_style()

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

    def toggle_show_score(self):
        current = self.settings.get('show_score_during_practice', True)
        self.settings['show_score_during_practice'] = not current
        self.update_show_score_button_style()

    def update_show_score_button_style(self):
        if self.settings.get('show_score_during_practice', True):
            self.show_score_toggle_button.setText("🎼 ロボット練習時の楽譜 : 表示")
            self.show_score_toggle_button.button_type = "success"
            self.show_score_toggle_button.bg_color = COLORS['success']
            self.show_score_toggle_button.hover_color = COLORS['success_dark']
        else:
            self.show_score_toggle_button.setText("🙈 ロボット練習時の楽譜 : 非表示")
            self.show_score_toggle_button.button_type = "warning"
            self.show_score_toggle_button.bg_color = COLORS['warning']
            self.show_score_toggle_button.hover_color = COLORS['warning_dark']
        self.show_score_toggle_button.update_style()

    def accept(self):
        self.settings['drum_volume'] = self.drum_volume_slider.value() / 100.0
        self.settings['metronome_volume'] = self.metronome_volume_slider.value() / 100.0
        self.settings['guide_cue_volume'] = self.guide_volume_slider.value() / 100.0
        self.settings['practice_level'] = self.level_combo.currentData()
        
        selected_score_key = self.score_order_combo.currentData()
        self.settings['score_order'] = selected_score_key.split('_')
        
        selected_order_key = self.experiment_order_combo.currentData()
        self.settings['experiment_order'] = selected_order_key.split('_')
        super().accept()
    
    @staticmethod
    def get_settings(parent, current_settings):
        dialog = SettingsDialog(current_settings, parent)
        if dialog.exec() == QDialog.DialogCode.Accepted: 
            return dialog.settings
        return None

    def toggle_feedback(self):
        self.settings['show_feedback_on_score'] = not self.settings.get('show_feedback_on_score', False)
        self.update_feedback_button_style()

    def update_feedback_button_style(self):
        if self.settings.get('show_feedback_on_score', False):
            self.feedback_toggle_button.setText("👀 打撃位置・判定の表示 : ON")
            self.feedback_toggle_button.button_type = "success"
            self.feedback_toggle_button.bg_color = COLORS['success']
            self.feedback_toggle_button.hover_color = COLORS['success_dark']
        else:
            self.feedback_toggle_button.setText("🙈 打撃位置・判定の表示 : OFF")
            self.feedback_toggle_button.button_type = "danger"
            self.feedback_toggle_button.bg_color = COLORS['danger']
            self.feedback_toggle_button.hover_color = COLORS['danger_dark']
        self.feedback_toggle_button.update_style()

    
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
            'drum_volume': 1.0, 'metronome_volume': 0.3, 'metronome_on': True, 
            'guide_cue_volume': 0.5, 'guide_cue_on': False, 'practice_level': 'p100',
            'score_blinking_on': True, 'guide_line_on': False,
            'score_layout': 'vertical',
            'command_monitor_on': False,
            'experiment_order': ['linear', 'passthrough', 'metronome'],
            'score_order': ['test1', 'test2', 'test3'],
            'show_score_during_practice': True,
            'show_feedback_on_score': False
        }
        self.state = "waiting" # waiting, result, または experiment_...
        self.last_input_time = {'top': 0, 'bottom': 0}
        # 不感帯の時間（ミリ秒）。60ms～80msくらいが適切です。
        self.DEBOUNCE_TIME_MS = 70
        # ★ 修正点: デモ再生からの復帰先を記憶する変数を追加
        self._demo_return_state = "waiting"
        self.experiment_sets = []
        
        self.current_experiment_set_index = 0
        self.current_experiment_step = 0 # 0: test1, 1: practice, 2: test2
        
        # 各ステップの設定 (注: step=1 の設定は 'linear' のデフォルト値として使われる)
        self.experiment_steps_config = [
            {
                'title': "テスト (1/2)",
                'description': "最初にお手本を聞いてください。お手本は２回だけ再生されます。\n再生終了後「テスト開始」ボタンを押してください。\nテストの際は、お手本のようなガイド線や音符の点滅はありません。\nテストは 1回限りの計測 となります。\nやり直しはできませんので、集中して取り組んでください。",
                'button_text': "▶️ テスト (1/2) 開始",
                'is_perfect_mode': False,
                'force_robot': False,
                'force_controller_name': None,
                'max_loops': 1,
                'color': COLORS['danger'],
                'color_dark': COLORS.get('danger_dark', COLORS['danger'].darker(110)),
                'setting_overrides': {
                    'guide_line_on': False,      # ガイド線を非表示
                    'score_blinking_on': False, # 音符の点滅を無効化
                    'guide_cue_on': False       # ガイド音（正解音）を消音
                }
            },
            # ★注意: このステップ(index=1)は、下の 'linear' の定義と一致させておく
            {
                'title': "練習",
                'description': "次に、ロボットのガイドと一緒に練習します。\n練習時間は5分間です。時間になるまで自動でループします。\nロボットがリズムを提示するので、それに合わせてドラムをたたいてください。\n準備ができたら「練習開始」ボタンを押してください。", 
                'button_text': "練習開始",
                'is_perfect_mode': True, 
                'force_robot': True,
                'force_controller_name': "線形補間コントローラー", 
                'max_loops': float('inf'), 
                'color': COLORS['warning'],
                'color_dark': COLORS.get('warning_dark', COLORS['warning'].darker(110)),
                'setting_overrides': {'metronome_on': False, 'guide_cue_on': False} 
            },
            {
                'title': "テスト (2/2)",
                'description': "最後に、もう一度ロボットなしで演奏を記録します。\nテストの際は、お手本のようなガイド線や音符の点滅はありません。\nテストは 1回限りの計測 となります。\nやり直しはできませんので、集中して取り組んでください。\n準備ができたら「テスト開始」ボタンを押してください。",
                'button_text': "▶️ テスト (2/2) 開始",
                'is_perfect_mode': False,
                'force_robot': False,
                'force_controller_name': None,
                'max_loops': 1,
                'color': COLORS['danger'],
                'color_dark': COLORS.get('danger_dark', COLORS['danger'].darker(110)),
                'setting_overrides': {
                    'guide_line_on': False,
                    'score_blinking_on': False,
                    'guide_cue_on': False
                }
            }
        ]

        # ★★★ ここから追加 (実験の「練習」ステップ (step=1) の設定定義) ★★★
        # ★★★ 修正: 実験の「練習」ステップ (step=1) の設定定義 ★★★
        # 「練習」では、ガイド線・点滅はON、ガイド音(cue)はOFFにします。
        # ★★★ 実験モード設定: 練習パートの設定 (step=1) ★★★
        self.experiment_practice_configs = {
            # 1. 同調あり (Linear)
            'linear': {
                'title': "練習",
                'description': "次に、ロボットのガイドと一緒に練習します。\n練習時間は5分間です。時間になるまで自動でループします。\nロボットがリズムを提示するので、それに合わせてドラムをたたいてください。\n準備ができたら「練習開始」ボタンを押してください。",
                'button_text': "練習開始",
                'is_perfect_mode': True, 
                'force_robot': True,
                'force_controller_name': "線形補間コントローラー", 
                'max_loops': float('inf'), 
                'color': COLORS['warning'],
                'color_dark': COLORS.get('warning_dark', COLORS['warning'].darker(110)),
                'setting_overrides': {
                    'guide_line_on': False,   # ★★★ 修正: OFFに変更 ★★★
                    'score_blinking_on': True,  # 点滅ON (練習モードなので自動的に一音目のみになります)
                    'guide_cue_on': False,
                    'metronome_on': True 
                }
            },
            # 2. 従来手法 (Metronome)
            'metronome': {
                'title': "練習",
                'description': "メトロノーム音と楽譜に合わせて演奏してください。\nロボットは動作せず、ガイドカーソルも表示されません。\n練習時間5分間です。",
                'button_text': "メトロノーム練習開始",
                'is_perfect_mode': True,
                'force_robot': False,
                'force_controller_name': None,
                'max_loops': float('inf'),
                'color': COLORS['primary'],
                'color_dark': COLORS.get('primary_dark', COLORS['primary'].darker(110)),
                'setting_overrides': {
                    'guide_line_on': False,   # ★★★ 修正: OFFに変更 ★★★
                    'score_blinking_on': True,  # 点滅ON
                    'guide_cue_on': False,
                    'metronome_on': True
                }
            },
            # 3. 同調なし (Passthrough)
            'passthrough': {
                'title': "練習",
                'description': "ロボットの動きに合わせて練習します。\n練習時間は5分間です。\n準備ができたら「練習開始」ボタンを押してください。",
                'button_text': "練習開始",
                'is_perfect_mode': True,
                'force_robot': True,
                'force_controller_name': "介入なし (お手本通り)",
                'max_loops': float('inf'),
                'color': COLORS['success'],
                'color_dark': COLORS.get('success_dark', COLORS['success'].darker(110)),
                'setting_overrides': {
                    'guide_line_on': False,   # ★★★ 修正: OFFに変更 ★★★
                    'score_blinking_on': True,  # 点滅ON
                    'guide_cue_on': False,
                    'metronome_on': True 
                }
            }
        }
        
        # ★★★ 実験モード設定ここまで ★★★

        self.experiment_data = {}
        self.experiment_next_state = None
        self.practice_loop_count_max = float('inf')
        self.practice_start_time = 0 # ★ 練習開始時刻 (is_perfect_mode用)
        self.original_settings = None # ★ 設定復元用に追加
        self.setting_overrides = None # ★ 設定上書き用に追加

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
            self.robot_manager = robot_control_module_v4.RobotManager(self)
            self.robot_manager.log_message.connect(self.log_window.append_log)
            if hasattr(self.robot_manager, 'command_sent'):
                    self.robot_manager.command_sent.connect(self.on_robot_command_sent)
        else:
            self.robot_manager = None

        # ★★★ 音声管理マネージャーの初期化 ★★★
        self.speech_manager = SpeechManager(self)

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
        self.tutorial_page_index = 0
        self.is_tutorial_active = False # 実験チュートリアル（模擬実験）中かどうかのフラグ
        self._ensure_tutorial_score_exists() # tutorial.json を作成
        

    def _ensure_tutorial_score_exists(self):
        """tutorial.json がなければ作成する (4/4拍子, シンプルなリズム)"""
        target_path = os.path.join(r"C:\卒研\music", "tutorial.json")
        if os.path.exists(target_path): return
        
        # シンプルな4分音符のリズム
        data = {
            "top": {
                "bpm": 100, "numerator": 4, "denominator": 4, "total_beats": 4,
                "items": [
                    {"class": "note", "type": "quarter", "beat": 0.0, "duration": 1.0},
                    {"class": "note", "type": "quarter", "beat": 1.0, "duration": 1.0},
                    {"class": "note", "type": "quarter", "beat": 2.0, "duration": 1.0},
                    {"class": "note", "type": "quarter", "beat": 3.0, "duration": 1.0}
                ]
            },
            "bottom": {
                "bpm": 100, "numerator": 4, "denominator": 4, "total_beats": 4,
                "items": [
                    {"class": "note", "type": "quarter", "beat": 0.0, "duration": 1.0},
                    {"class": "rest", "type": "quarter_rest", "beat": 1.0, "duration": 1.0},
                    {"class": "note", "type": "quarter", "beat": 2.0, "duration": 1.0},
                    {"class": "rest", "type": "quarter_rest", "beat": 3.0, "duration": 1.0}
                ]
            }
        }
        try:
            with open(target_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=4)
        except Exception: pass

    def closeEvent(self, event):
        # ... (既存の終了処理) ...
        if hasattr(self, 'speech_manager'):
            self.speech_manager.cleanup()
        event.accept()

    # ★★★ 追加: チュートリアルの文章を定義するメソッド ★★★
    def get_tutorial_text(self, state_name, page_index=0):
        """ 状態とページ番号に応じたテキストを返す """
        
        # 1. 機能説明スライド
        if state_name == "experiment_explanation":
            if page_index == 0:
                return (
                    "本システムはロボットと一緒にリズム練習をするシステムです。\n"
                    "これから、各機能や画面の表示、ロボットの動きについて説明します。\n\n"
                    "準備ができたら下の「次へ」ボタンで進んでください。"
                )
            elif page_index == 1:
                return (
                    "楽譜が再生されている間、メトロノーム音が流れます。\n"
                    "この音を基準にリズムを取るようにしてください。\n\n"
                    "下の「メトロノーム再生」ボタンを押して、音を確認してみてください。"
                )
            elif page_index == 2:
                return (
                    "上の楽譜は左手、下の楽譜は右手で叩くリズムです。\n"
                    "練習では表示されている楽譜を繰り返し叩いてもらいます。\n"
                    "お手本ではすべての音符が点滅しますが、練習では一音目のみ点滅します。\n\n"
                    "下の「楽譜再生」ボタンを押して、実際の動きを確認してみてください。"
                )
            elif page_index == 3:
                return (
                    "ロボットアームは、楽譜のリズムに合わせて物理的に動きます。\n"
                    "振り下ろす動作が「打撃」のタイミングです。\n\n"
                    "下の「ロボット動作確認」ボタンを押して、実際の動きを見てください。"
                )
            elif page_index == 4:
                return (
                    "体験の際、練習前と練習後にテストを行ってもらいます。\n"
                    "テストでは、ガイド線や音符の点滅はありません。\n"
                    "カウントダウン後にメトロノームが流れるので自力でリズムを叩いてもらいます。\n\n"
                    "下の「テスト再生」ボタンで、テストの際の楽譜について確認してください。"
                )
        
        # 2. チュートリアル開始前
        elif state_name == "experiment_pre_tutorial":
            return (
                "これより、実際の練習の流れを確認するための\n"
                "「チュートリアル」を行います。\n\n"
                "事前テスト、練習、事後テストの一連の流れを体験していただきます。\n"
                "準備ができたら「次へ」を押して開始してください。"
            )

        # 3. 本番開始前
        elif state_name == "experiment_pre_real":
            return (
                "チュートリアルお疲れ様でした。\n"
                "練習の進め方は理解できましたか？\n\n"
                "これより「本番体験」を開始します。\n"
                "本番ではデータが記録されます。\n\n"
                "準備ができたら「次へ」を押して、本番の第1セットへ進んでください。"
            )
            
        return ""
    
    def init_ui(self):
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
        
        # --- 設定ボタン ---
        self.btn_settings = QPushButton("⚙️"); self.btn_settings.setFixedSize(50, 50); self.btn_settings.setCursor(Qt.CursorShape.PointingHandCursor); self.btn_settings.setFont(QFont("Segoe UI", 16))
        self.btn_settings.setStyleSheet(f"""QPushButton {{ background: {COLORS['surface_light'].name()}; color: {COLORS['text_primary'].name()}; border: 1px solid {COLORS['border'].name()}; border-radius: 25px; }} QPushButton:hover {{ background: {COLORS['surface'].name()}; border: 1px solid {COLORS['primary'].name()}; }}""")
        self.btn_settings.clicked.connect(self.open_settings_dialog); header_layout.addWidget(self.btn_settings)

        # --- ログボタン ---
        self.btn_toggle_log = QPushButton("📋"); self.btn_toggle_log.setFixedSize(50, 50); self.btn_toggle_log.setCursor(Qt.CursorShape.PointingHandCursor); self.btn_toggle_log.setFont(QFont("Segoe UI", 16))
        self.btn_toggle_log.setStyleSheet(self.btn_settings.styleSheet()); self.btn_toggle_log.setToolTip("実行ログの表示/非表示")
        self.btn_toggle_log.clicked.connect(self.toggle_log_window); header_layout.addWidget(self.btn_toggle_log)
        
        # --- ★★★ 追加: 実験中止（ホーム）ボタン (ヘッダーに配置) ★★★ ---
        self.btn_exp_finish = QPushButton("🏠")
        self.btn_exp_finish.setFixedSize(50, 50)
        self.btn_exp_finish.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_exp_finish.setFont(QFont("Segoe UI", 16))
        self.btn_exp_finish.setStyleSheet(self.btn_settings.styleSheet()) # 設定ボタンと同じスタイル
        self.btn_exp_finish.setToolTip("実験を中止してメインメニューに戻る")
        self.btn_exp_finish.clicked.connect(self.on_experiment_button_clicked)
        self.btn_exp_finish.hide() # デフォルトは非表示
        header_layout.addWidget(self.btn_exp_finish)
        # ----------------------------------------------------------------

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
        exp_control_layout.setContentsMargins(0, 0, 0, 0)
        exp_control_layout.setSpacing(15)

        # 1. ボタンの定義 (既存の定義があれば上書きされます)
        self.btn_exp_prev = ModernButton("⬅ 前へ", "primary")
        self.btn_exp_prev.clicked.connect(self.on_experiment_button_clicked)
        
        self.btn_exp_action = ModernButton("▶️ 再生して確認", "warning")
        self.btn_exp_action.clicked.connect(self.on_experiment_action_clicked)

        self.btn_exp_demo = ModernButton("👁️ お手本再生", "primary")
        self.btn_exp_demo.clicked.connect(self.on_experiment_button_clicked)
        
        self.btn_exp_start = ModernButton("▶️ 開始", "danger")
        self.btn_exp_start.clicked.connect(self.on_experiment_button_clicked) 
        
        self.btn_exp_next = ModernButton("次へ ➔", "success")
        self.btn_exp_next.clicked.connect(self.on_experiment_button_clicked)

        # 2. レイアウトへの追加 (ここが重複の原因になりやすいので、順序通りに1回だけ追加)
        exp_control_layout.addStretch()
        exp_control_layout.addWidget(self.btn_exp_prev)   # 前へ
        exp_control_layout.addWidget(self.btn_exp_action) # アクション
        exp_control_layout.addWidget(self.btn_exp_demo)   # お手本
        exp_control_layout.addWidget(self.btn_exp_start)  # 開始
        exp_control_layout.addWidget(self.btn_exp_next)   # 次へ
        exp_control_layout.addStretch()
        
        # 3. 親レイアウトへの追加
        control_wrapper_layout.addWidget(self.free_mode_panel)
        control_wrapper_layout.addWidget(self.experiment_panel) # これが2回書かれていないか注意！

        content_layout.addWidget(control_panel, 1)

        self.free_mode_widgets = [self.label_controller, self.control_combo, self.btn_load_template, self.btn_demo, self.btn_practice, self.btn_perfect_practice, self.btn_retry, self.btn_start_experiment, self.free_mode_panel]
        
        # リストの更新
        self.experiment_widgets = [self.btn_exp_prev, self.btn_exp_action, self.btn_exp_demo, self.btn_exp_start, self.btn_exp_next, self.experiment_panel]
        
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

    def _generate_drum_hit_sound(self):
        """NumPyでドラムの打撃音（スネア風）を合成する（音量最大化版）"""
        if not NUMPY_AVAILABLE: return None
        try:
            sample_rate = pygame.mixer.get_init()[0]
            duration_ms = 150
            n_samples = int(round(duration_ms / 1000 * sample_rate))
            
            # ノイズ成分
            noise = (2 * np.random.random(n_samples) - 1)
            
            # ★ 修正A: 減衰を少し緩やかにして、音の存在感を増す
            # (以前は 0->10 でしたが、0->6 くらいにすると余韻が少し伸びて大きく聞こえます)
            decay = np.exp(-np.linspace(0, 6, n_samples))
            
            signal = noise * decay
            
            # ★ 修正B: 音割れしないギリギリまでノーマライズ（最大化）する
            max_val = np.max(np.abs(signal))
            if max_val > 0:
                signal = signal / max_val  # -1.0 〜 1.0 に正規化
            
            # 16bit整数の最大値 (32767) に近い値を掛ける
            # (少し余裕を持たせて 30000 くらいにする)
            amplitude = 30000
            signal = np.int16(signal * amplitude)
            
            buf = np.zeros((n_samples, 2), dtype=np.int16)
            buf[:, 0] = signal
            buf[:, 1] = signal
            return pygame.sndarray.make_sound(buf)
        except Exception as e:
            print(f"ドラム音生成失敗: {e}")
            return None
        
    def play_robot_drum_sound(self):
        """RobotManagerからのシグナルを受け取って音を鳴らす"""
        if hasattr(self, 'robot_drum_sound') and self.robot_drum_sound:
            self.robot_drum_sound.play()
    
    def init_sounds(self):
        self.robot_drum_sound = None # ★ 初期化しておく

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
                
                self.snare_sound = self._generate_drum_sound(type='snare')
                self.tom_sound = self._generate_drum_sound(type='tom')
                self.note_sound = self._generate_sound(880, 100)
                self.metronome_click = self._generate_sound(1500, 50)
                self.metronome_accent_click = self._generate_sound(2500, 50)
                self.countdown_sound = self._generate_sound(3000, 200)

                # ★ ロボット音の生成
                self.robot_drum_sound = self._generate_drum_hit_sound()

            # ★ インデントを戻して判定
            if self.robot_drum_sound:
                # 音量を設定（設定値があればそれを使う、なければ最大）
                vol = self.settings.get('drum_volume', 1.0)
                self.robot_drum_sound.set_volume(vol)
            
            self.apply_settings()
            
        except Exception as e:
            QMessageBox.critical(self, "起動時エラー", f"音声初期化エラー:\n{e}")

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
        try:
            input_ports = mido.get_input_names()
            if not input_ports:
                raise OSError("MIDI入力ポートが見つかりません。")
            
            self.inport = mido.open_input(input_ports[0])
            msg = f"✅ MIDIポートに接続: {input_ports[0]}"
            self.label_info.setText(msg)
            self.label_info.set_style(11, QFont.Weight.Normal, 'text_primary') # 通常スタイル
            self.log_window.append_log(msg)

        except OSError as e:
            # ★ 修正: MIDIが見つからない場合でもボタンを無効化せず、inportをNoneにして続行可能にする
            msg = f"⚠️ MIDI未接続: {e} (再生モードのみ利用可能)"
            
            # 画面上の表示は残す（赤字で警告）
            self.label_info.setText(msg.split('\n')[0])
            self.label_info.set_style(11, QFont.Weight.Bold, 'danger') 
            self.log_window.append_log(msg)
            
            self.inport = None
            
            # ★★★ 変更点: ここでボタンを無効化（False）していた行を削除またはTrueにする ★★★
            self.btn_load_template.setEnabled(True)

    def open_settings_dialog(self):
        # (変更なし)
        new_settings = SettingsDialog.get_settings(self, self.settings)
        if new_settings: self.settings = new_settings; self.apply_settings()

    def toggle_log_window(self):
        # (変更なし)
        if self.log_window.isVisible(): self.log_window.hide()
        else: self.log_window.show()

    def apply_settings(self):
        """ 設定を各音源に適用する（バランス調整版） """
        
        # --- 1. ドラム音 (スネア/タム/ロボット) ---
        # ドラムは迫力を出すため、設定値をそのまま(1.0倍)適用
        drum_vol = self.settings['drum_volume']
        
        if self.snare_sound: self.snare_sound.set_volume(drum_vol)
        if self.tom_sound: self.tom_sound.set_volume(drum_vol)
        
        if hasattr(self, 'robot_drum_sound') and self.robot_drum_sound:
            self.robot_drum_sound.set_volume(drum_vol)

        # --- 2. メトロノーム音 ---
        # ★★★ 修正: メトロノームがうるさすぎないよう、設定値の 50% 程度に抑える ★★★
        base_metro_vol = self.settings['metronome_volume']
        adjusted_metro_vol = base_metro_vol * 0.5  # 係数を小さくするとより静かになります

        if self.metronome_click: 
            self.metronome_click.set_volume(adjusted_metro_vol)
        
        if self.metronome_accent_click: 
            # アクセントは少し強調 (1.2倍) するが、上限を超えないように
            accent_vol = min(1.0, adjusted_metro_vol * 1.2)
            self.metronome_accent_click.set_volume(accent_vol)
        
        # --- 3. カウントダウン音 ---
        # メトロノーム連動。高音で耳に刺さるのでさらに絞る (メトロノーム補正後の 30%)
        if self.countdown_sound:
            count_vol = adjusted_metro_vol * 0.3
            self.countdown_sound.set_volume(count_vol)
        
        # --- 4. ガイド音 (正解音) ---
        if self.note_sound: 
            self.note_sound.set_volume(self.settings['guide_cue_volume'])

        # 楽譜順序設定の適用 (既存処理)
        score_order = self.settings.get('score_order', ['test1', 'test2', 'test3'])
        self.experiment_sets = [f"{name}.json" for name in score_order]

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

    # 変更後
    def start_demo_playback(self):
        """
        お手本再生（デモ）を開始するメソッド
        """
        if not hasattr(self, '_demo_return_state') or not self._demo_return_state:
             self._demo_return_state = "waiting"

        self.state = "demo_playback"

        # --- 設定の一時退避と上書き ---
        self.original_settings_demo = self.settings.copy()

        demo_settings = self.settings.copy()
        
        # ★★★ 修正: ガイド線をOFFに変更 ★★★
        demo_settings['guide_line_on'] = False   # 変更前: True
        
        demo_settings['score_blinking_on'] = True    # 音符の点滅は有効化
        demo_settings['metronome_on'] = False        # メトロノーム音は消す
        demo_settings['guide_cue_on'] = True
        demo_settings['demo_blink_mode'] = 'all'

        self.settings = demo_settings
        self.apply_settings()

        # ... (以下変更なし) ...
        # --- ★★★ 追加: カウントダウン時間の計算 ★★★ ---
        # テンポ情報の取得 (デフォルト120)
        top_bpm = self.template_score['top'].get('bpm', 120)
        
        # 4拍分のカウントダウン時間を計算
        countdown_duration_s = (4 * (60.0 / top_bpm))
        
        # 開始時刻を決定 (現在時刻 + カウントダウン時間)
        master_start_time = time.time() + countdown_duration_s

        # エディタウィンドウを開く (master_start_time を渡す)
        self.editor_window = EditorWindow(
            self.template_score, 
            self, 
            self.item_images, 
            is_demo=True,
            master_start_time=master_start_time # ★ 時間を渡す
        )
        self.editor_window.show()

    def on_robot_command_sent(self, track_name, motion):
        # (変更なし)
        if self.viz_window:
            self.viz_window.update_command(track_name, motion)

    def prepare_for_recording(self):
        """ 記録用バッファの完全初期化 """
        # 1. 打撃ログと判定結果リストを空にする
        self.recorded_hits = []
        self.judgements = []
        
        # 2. 判定済みノート管理辞書を空にする (辞書として初期化)
        # ★★★ ここが重要: 前のセットのデータが残らないように新しく作り直す ★★★
        self.judged_notes = {} 
        
        # 3. ノート総数の再計算とIDの割り振り
        self.total_notes = sum(1 for track in self.template_score.values() for item in track.get('items', []) if item['class'] == 'note')
        
        note_id = 0
        for track_name, track in self.template_score.items():
            for item in track.get('items', []):
                if item['class'] == 'note': 
                    # トラック名と連番で一意なIDを振る (例: top-0, top-1...)
                    item['id'] = f"{track_name}-{note_id}"
                    note_id += 1
        
        # ログ確認用
        # self.log_window.append_log(f"記録準備完了: {self.total_notes} ノート, バッファをリセットしました。")

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

    def start_generic_practice(self, is_perfect_mode, force_robot=None, force_controller_name=None, max_loops=None, setting_overrides=None):
        # (変更なし)
        self.original_settings = self.settings.copy()
        self.setting_overrides = setting_overrides
        if self.setting_overrides:
            self.log_window.append_log(f"設定を一時的に上書き: {self.setting_overrides}")
            self.settings.update(self.setting_overrides)
            self.apply_settings()

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

        # --------------------------------------------------------------
        # ★★★ 追加: 楽譜UIを隠すかどうかの判定 ★★★
        # 条件: 「ロボットを使用する」かつ「設定で非表示になっている」
        # --------------------------------------------------------------
        should_hide_score = False
        if use_robot:
            if not self.settings.get('show_score_during_practice', True):
                should_hide_score = True
                self.log_window.append_log("設定に基づき、練習中の楽譜UIを非表示にします。")
        # --------------------------------------------------------------

        if self.state.startswith("experiment_"):
            # ★ 修正: 実行中の状態を汎用的なものに変更
            self.state = "experiment_running"
        else:
            self.state = "practice_countdown"
            
        self.editor_window = EditorWindow(
            self.template_score, self, self.item_images, is_demo=False, 
            loop_duration_ms=master_loop_duration_ms, 
            robot_prep_time_s=robot_prep_time_s,
            master_start_time=master_start_time,
            hide_score=should_hide_score
        )
        show_metronome_ui = False
        
        # 設定でメトロノームがONになっているか確認
        if self.setting_overrides and self.setting_overrides.get('metronome_on') is True:
            # さらに「ロボットを使っていない(＝従来手法)」場合のみUIを出す
            if not use_robot:
                show_metronome_ui = True
        
        if show_metronome_ui:
            # JSONから拍子を読み込む (top と bottom で異なる可能性があるため)
            numerator_top = self.template_score.get('top', {}).get('numerator', 4)
            numerator_bottom = self.template_score.get('bottom', {}).get('numerator', 4)

            # EditorWindow にある visualizer を設定して表示
            if self.editor_window.beat_visualizer_top:
                self.editor_window.beat_visualizer_top.set_beat(0, numerator_top)
                self.editor_window.beat_visualizer_top.show()

            if self.editor_window.beat_visualizer_bottom:
                self.editor_window.beat_visualizer_bottom.set_beat(0, numerator_bottom)
                self.editor_window.beat_visualizer_bottom.show()
            if self.editor_window.visualizer_container:
                self.editor_window.visualizer_container.show()
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
    

    # -------------------------------------------------------
    # ★★★ 修正版 finish_performance ★★★
    # -------------------------------------------------------
    def finish_performance(self, is_demo, force_stop=False):
        """
        演奏（練習・テスト・デモ）終了時の処理
        """
        # --- 共通のクリーンアップ処理 ---
        pygame.mixer.music.stop()
        if self.viz_window: self.viz_window.stop_monitoring()
        if self.robot_manager: self.robot_manager.stop_control()
        
        editor = self.editor_window
        if editor:
            self.editor_window = None
            editor.close()

        # ==========================================
        # 1. お手本（デモ）モードの終了
        # ==========================================
        if is_demo:
            # 設定を復元
            if hasattr(self, 'original_settings_demo') and self.original_settings_demo:
                self.settings = self.original_settings_demo
                self.original_settings_demo = None
                self.apply_settings()
            
            # デモ完了フラグを立てる (テスト開始ボタンの有効化などに使用)
            self.experiment_demo_completed = True
            
            # 状態を復帰（experiment_intro などに戻る）
            self.state = self._demo_return_state
            self._demo_return_state = "waiting"
            
            self.log_window.append_log(f"デモ再生終了。状態を {self.state} に戻しました。")
            self.update_button_states()
            self.canvas.update()
            return

        # ==========================================
        # 2. 実験モード（本番 または チュートリアル）の終了
        # ==========================================
        elif self.state.startswith("experiment_"):
            is_running_state = self.state == "experiment_running"

            # --- 中止ボタンが押された場合 ---
            if force_stop and is_running_state:
                self.log_window.append_log("実行が中止されました。")
                
                # イントロ画面に戻る
                self.enter_experiment_state("experiment_intro", set_index=self.current_experiment_set_index, step=self.current_experiment_step)
                
                # 設定を復元
                if self.original_settings:
                    self.settings = self.original_settings
                    self.original_settings = None
                    self.setting_overrides = None
                    self.apply_settings()
                return

            # 多重呼び出し防止ガード
            if not is_running_state:
                return

            # --- データの集計 ---
            self.result_stats = self.summarize_performance() # 全体統計
            pad_stats = self.get_stats_per_pad()             # 左右別統計
            
            current_set_idx = self.current_experiment_set_index
            current_step_idx = self.current_experiment_step
            
            # ファイル名の取得 (チュートリアル中は固定)
            if getattr(self, 'is_tutorial_active', False):
                filename = "tutorial.json"
            else:
                filename = self.experiment_sets[current_set_idx]
            
            # ログデータの構築
            step_log = {
                'set_index': current_set_idx + 1,
                'step_index': current_step_idx + 1,
                'score_file': filename,
                'timestamp': datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                'stats': self.result_stats,
                'pad_stats': pad_stats,
                'raw_hits': []
            }

            # ロボットの制御ログがあれば取得
            if self.active_controller and hasattr(self.active_controller, 'guided_history'):
                step_log['robot_history'] = list(self.active_controller.guided_history)
                self.active_controller.guided_history = [] # クリア

            # 手法名の特定
            if getattr(self, 'is_tutorial_active', False) and hasattr(self, 'tutorial_steps_config'):
                config = self.tutorial_steps_config[current_step_idx]
            elif hasattr(self, '_current_step_config'):
                config = self._current_step_config
            else:
                config = self.experiment_steps_config[current_step_idx]
            
            method_name = "Test (None)"
            overrides = config.get('setting_overrides') or {}
            
            if config.get('force_robot'):
                method_name = config.get('force_controller_name', 'Robot')
            elif overrides.get('metronome_on'):
                method_name = "Metronome"
            
            step_log['method'] = method_name

            # データの格納（練習パートならループ詳細、テストなら全打鍵データ）
            # ※ ステップ1が練習とは限らない場合もあるが、experiment_steps_configの構造に依存
            is_practice_step = (config.get('max_loops') != 1) # ループ回数が1じゃない＝練習とみなす

            if is_practice_step: 
                step_log['practice_loops'] = getattr(self, 'current_practice_logs', [])
                self.current_practice_logs = [] 
            else: 
                detailed_hits = []
                for j in self.judgements:
                    detailed_hits.append({
                        'note_id': j.get('note_id'),
                        'judgement': j.get('judgement'),
                        'error_ms': j.get('error_ms'),
                        'pad': j.get('pad')
                    })
                step_log['raw_hits'] = detailed_hits

            # --- ログリストへの追加 (本番のみ) ---
            # チュートリアル中はログを保存しない
            if not getattr(self, 'is_tutorial_active', False):
                self.experiment_logs.append(step_log)
                self.log_window.append_log(f"データを記録しました: Set {current_set_idx+1} - Step {current_step_idx+1}")
            else:
                self.log_window.append_log(f"チュートリアルのためデータ記録はスキップします。")

            # 設定を元に戻す
            if self.original_settings:
                self.settings = self.original_settings
                self.original_settings = None
                self.setting_overrides = None
                self.apply_settings()

            self.update_button_states()
            
            # --- 次のステップへの遷移判定 ---
            
            # [A] チュートリアル中の場合
            if getattr(self, 'is_tutorial_active', False):
                next_step = current_step_idx + 1
                if hasattr(self, 'tutorial_steps_config') and next_step >= len(self.tutorial_steps_config):
                    # チュートリアル全完了 -> 本番へ移行
                    self.log_window.append_log("チュートリアル完了。本番前確認画面へ移行します。")
                    
                    # ここではまだ is_tutorial_active = False にしない (Pre-Real画面で「前へ」を押した時のため)
                    # ただしボタンクリック時に False にする
                    
                    self.enter_experiment_state("experiment_pre_real")
                else:
                    # チュートリアルの次のステップへ
                    self.enter_experiment_state("experiment_intro", set_index=0, step=next_step)
            
            # [B] 本番実験の場合
            else:
                # 全実験終了判定 (ここで保存処理を呼び出す)
                is_last_set = (current_set_idx >= len(self.experiment_sets) - 1)
                is_last_step = (current_step_idx >= len(self.experiment_steps_config) - 1)
                
                if is_last_set and is_last_step:
                    self.save_experiment_data_to_file() # ★ 保存実行
                
                # 次のステップへ進む
                self.advance_experiment_step()

        # ==========================================
        # 3. フリー（練習）モードの終了
        # ==========================================
        else:
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
            
            if self.original_settings:
                self.settings = self.original_settings
                self.original_settings = None
                self.setting_overrides = None
                self.apply_settings()
            
            self.update_button_states()

    # -------------------------------------------------------
    # ★★★ 修正版 save_experiment_data_to_file ★★★
    # インデントを戻して MainWindow のメソッドとして正しく定義
    # -------------------------------------------------------
    def save_experiment_data_to_file(self):
        """
        実験データをテキストファイルに出力する
        （Score対応、練習ループ詳細記録対応、完了ポップアップ削除版）
        """
        now_str = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"experiment_result_{now_str}.txt"
        
        # 保存先ディレクトリ
        target_dir = r"C:\卒研\実験データ"
   
        # ディレクトリが存在しない場合は作成する
        if not os.path.exists(target_dir):
            try:
                os.makedirs(target_dir)
                self.log_window.append_log(f"保存用フォルダを作成しました: {target_dir}")
            except Exception as e:
                self.log_window.append_log(f"フォルダ作成エラー: {e}")
                target_dir = os.getcwd()
        
        # フルパスを作成
        save_path = os.path.join(target_dir, filename)
        
        try:
            with open(save_path, "w", encoding="utf-8") as f:
                # --- ヘッダー情報の書き込み ---
                f.write("==================================================\n")
                f.write(f" リズム実験データログ\n")
                f.write(f" 実験開始日時: {getattr(self, 'experiment_start_time', 'Unknown')}\n")
                f.write(f" 実験終了日時: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                
                # 設定された順序情報の書き込み
                current_score_order = self.settings.get('score_order', ['test1', 'test2', 'test3'])
                f.write(f" 楽譜順序: {' -> '.join(current_score_order)}\n")

                current_method_order = self.settings.get('experiment_order', ['linear', 'passthrough', 'metronome'])
                f.write(f" 手法順序: {' -> '.join(current_method_order)}\n")
                
                f.write("==================================================\n\n")
                
                current_set = -1
                pad_labels = {'top': '左', 'bottom': '右'} 
                
                # --- 各ログデータの書き込み ---
                for log in self.experiment_logs:
                    set_idx = log['set_index']
                    step_idx = log['step_index']
                    
                    # セットの区切り
                    if set_idx != current_set:
                        f.write(f"\n##################################################\n")
                        f.write(f" 実験セット {set_idx} (楽譜: {log['score_file']})\n")
                        f.write(f"##################################################\n")
                        current_set = set_idx
                    
                    step_name = ["事前テスト (Test 1)", "練習 (Practice)", "事後テスト (Test 2)"][step_idx - 1]
                    f.write(f"\n--- ステップ {step_idx}: {step_name} ---\n")
                    f.write(f"手法: {log['method']}\n")
                    f.write(f"日時: {log['timestamp']}\n")
                    
                    # --- ステップ全体の統計 ---
                    stats = log['stats']
                    f.write(f"【全体】 Acc: {stats.get('accuracy', 0):.1f}%, Score: {stats.get('score', 0):.1f}%, Err: {stats.get('avg_error', 0):.1f}ms, Dev: {stats.get('std_dev', 0):.1f}ms\n")
                    
                    # --- 左右別の統計 ---
                    if 'pad_stats' in log:
                        for pad_key in ['top', 'bottom']:
                            if pad_key in log['pad_stats']:
                                p_s = log['pad_stats'][pad_key]
                                label = pad_labels.get(pad_key, pad_key)
                                f.write(f"  [{label}手] Acc: {p_s.get('accuracy',0):.1f}%, Score: {p_s.get('score',0):.1f}%, Err: {p_s.get('avg_error',0):.1f}ms, Dev: {p_s.get('std_dev',0):.1f}ms")
                                f.write(f" (P:{p_s['perfect']} Gr:{p_s['great']} Go:{p_s['good']} M:{p_s['dropped']})\n")
                    
                    # --- 練習ループの詳細推移 (詳細版) ---
                    if 'practice_loops' in log:
                        f.write(f"\n  [各ループの推移]\n")
                        for loop in log['practice_loops']:
                            l_stats = loop['stats']
                            l_pad_stats = loop.get('pad_stats', {}) 

                            # ループヘッダー
                            f.write(f"  > Loop {loop['loop_count']} ({loop['timestamp']})\n")
                            
                            # ループ全体統計
                            f.write(f"    【全体】 Acc: {l_stats.get('accuracy',0):.1f}%, Score: {l_stats.get('score',0):.1f}%, Err: {l_stats.get('avg_error',0):.1f}ms, Dev: {l_stats.get('std_dev',0):.1f}ms\n")

                            # ループ左右別統計
                            for pad_key in ['top', 'bottom']:
                                if pad_key in l_pad_stats:
                                    p_s = l_pad_stats[pad_key]
                                    label = pad_labels.get(pad_key, pad_key)
                                    f.write(f"      [{label}手] Acc: {p_s.get('accuracy',0):.1f}%, Score: {p_s.get('score',0):.1f}%, Err: {p_s.get('avg_error',0):.1f}ms, Dev: {p_s.get('std_dev',0):.1f}ms")
                                    f.write(f" (P:{p_s['perfect']} Gr:{p_s['great']} Go:{p_s['good']} M:{p_s['dropped']})\n")
                            
                            f.write("\n")
                    
                    # --- テストの詳細打鍵データ (変更なし) ---
                    elif 'raw_hits' in log:
                        f.write(f"\n  [打鍵詳細データ]\n")
                        
                        def sort_key_func(hit):
                            nid = hit['note_id']
                            if not nid: return ("z", 0)
                            try:
                                parts = nid.split('-')
                                return (parts[0], int(parts[1]))
                            except (ValueError, IndexError):
                                return (str(nid), 0)

                        sorted_hits = sorted(log['raw_hits'], key=sort_key_func)

                        for hit in sorted_hits:
                            note_id = hit['note_id'] if hit['note_id'] else "Unknown"
                            judgement = hit['judgement']
                            error_str = f"{hit['error_ms']:+.0f}ms" if hit['error_ms'] is not None else "---"
                            f.write(f"  Note {note_id:<10} : {judgement:<8} {error_str}\n")

                    # --- ロボット制御ログ ---
                    if 'robot_history' in log and log['robot_history']:
                        f.write(f"\n  [ロボット制御ログ] (LinearController)\n")
                        f.write(f"  {'Time':<12} | {'Track':<7} | {'Ideal(ms)':<10} | {'Offset(ms)':<11} | {'Guided(ms)':<10}\n")
                        f.write(f"  {'-'*12}-+-{'-'*7}-+-{'-'*10}-+-{'-'*11}-+-{'-'*10}\n")
                        
                        for r in log['robot_history']:
                            offset_str = f"{r['offset']:+.1f}"
                            f.write(f"  {r['timestamp']:<12} | {r['track']:<7} | {r['ideal']:<10.0f} | {offset_str:<11} | {r['guided']:<10.0f}\n")
            
            # 完了時のログ出力（ポップアップは削除済み）
            self.log_window.append_log(f"実験ログを保存しました: {save_path}")
            
        except Exception as e:
            self.log_window.append_log(f"保存エラー: {e}")
            # エラー時のみポップアップを表示
            QMessageBox.critical(self, "保存エラー", f"ファイルの保存に失敗しました。\n{e}")


    def get_stats_per_pad(self):
        """ 左右別の統計情報を計算 (上限100%制限を追加) """
        pads = ['top', 'bottom']
        results = {}

        for pad in pads:
            if not self.template_score or pad not in self.template_score:
                continue
            
            # トラック情報
            track_data = self.template_score[pad]
            total_notes = sum(1 for item in track_data.get('items', []) if item['class'] == 'note')
            
            # 判定抽出
            pad_judgements = [j for j in self.judgements if j.get('pad') == pad]
            
            stats = { 'perfect': 0, 'great': 0, 'good': 0, 'extra': 0, 'dropped': 0 }
            valid_errors = []
            
            for j in pad_judgements:
                if j['judgement'] in stats: 
                    stats[j['judgement']] += 1
                if j['judgement'] in ['perfect', 'great', 'good'] and j['error_ms'] is not None:
                    valid_errors.append(j['error_ms'])
            
            notes_judged = stats['perfect'] + stats['great'] + stats['good']
            
            # Dropped 計算 (マイナス防止)
            stats['dropped'] = max(0, total_notes - notes_judged)

            # Acc (正打率)
            raw_accuracy = (notes_judged / total_notes * 100) if total_notes > 0 else 0.0
            stats['accuracy'] = min(100.0, raw_accuracy) # ★ 修正: 100%制限
            
            # Score (得点率)
            weighted_sum = (stats['perfect'] * 1.0) + \
                           (stats['great']   * 0.7) + \
                           (stats['good']    * 0.4)
            raw_score = (weighted_sum / total_notes * 100) if total_notes > 0 else 0.0
            stats['score'] = min(100.0, raw_score) # ★ 修正: 100%制限
            # ---------------------

            stats['avg_error'] = np.mean(valid_errors) if NUMPY_AVAILABLE and valid_errors else 0.0
            stats['std_dev'] = np.std(valid_errors) if NUMPY_AVAILABLE and valid_errors else 0.0
            stats['total_notes'] = total_notes
            
            results[pad] = stats
            
        return results
    
    def closeEvent(self, event):
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
        
        # ★★★ 音声合成エンジンの停止処理 ★★★
        if hasattr(self, 'speech_manager'):
            self.speech_manager.cleanup()

        pygame.quit()
        event.accept()

    def evaluate_and_continue_loop(self):
        """
        ループ終了時の評価と、実験データ記録を行う
        """
        if not self.is_perfect_mode: return
        
        self.judgement_history.append(list(self.judgements))
        
        # --- 実験データの記録 (練習ループ) ---
        if self.state.startswith("experiment_"):
            # ... (中略: ログ記録のロジックはそのまま) ...
            current_stats = self.summarize_performance()
            pad_stats = self.get_stats_per_pad()
            
            detailed_hits = []
            for j in self.judgements:
                detailed_hits.append({
                    'note_id': j.get('note_id'),
                    'judgement': j.get('judgement'),
                    'error_ms': j.get('error_ms'),
                    'pad': j.get('pad')
                })

            loop_data = {
                'type': 'practice_loop',
                'loop_count': self.practice_loop_count,
                'timestamp': datetime.datetime.now().strftime("%H:%M:%S"),
                'stats': current_stats,
                'pad_stats': pad_stats,
                'details': detailed_hits
            }
            
            if not hasattr(self, 'current_practice_logs'):
                self.current_practice_logs = []
            self.current_practice_logs.append(loop_data)
        # ---------------------------------------------------

        if self.active_controller and hasattr(self.active_controller, 'update_performance_data'):
            log_msg = self.active_controller.update_performance_data(self.judgement_history)
            if log_msg:
                self.log_window.append_log(f"[{self.active_controller.name}] {log_msg}")
        
        stats = self.summarize_performance()
        history_entry = { 'loop': self.practice_loop_count, 'perfects': stats['perfect'], 'std_dev': stats['std_dev'] if stats['std_dev'] > 0 else 0 }
        self.perfect_practice_history.append(history_entry)
        
        # =============================================================
        # ★★★ 修正: 練習時間の設定 (チュートリアルか本番かで分岐) ★★★
        # =============================================================
        if getattr(self, 'is_tutorial_active', False):
            # チュートリアル用の練習時間 (例: 30秒)
            time_limit_seconds = 40.0 
        else:
            # 本番実験用の練習時間 (例: 4分 = 240秒)
            time_limit_seconds = 300.0
        # =============================================================

        elapsed_practice_time = time.time() - self.practice_start_time

        # 時間経過チェック
        if elapsed_practice_time >= time_limit_seconds:
            # --- 時間経過で終了 ---
            prefix = "[チュートリアル] " if getattr(self, 'is_tutorial_active', False) else ""
            self.log_window.append_log(f"{prefix}練習時間が {time_limit_seconds:.0f} 秒に達したため、練習を終了します。")
            
            self.result_stats = stats
            self.ai_feedback_text = f"規定の {time_limit_seconds:.0f}秒 に達したため練習を終了します。"
            if self.editor_window: self.editor_window.close()

        else:
            # --- 以下、PERFECT達成による早期終了判定など (既存コード) ---
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

            #if success and self.practice_loop_count_max == float('inf'): 
               # self.result_stats = stats
                #if self.editor_window: self.editor_window.close()
            if self.practice_loop_count >= self.practice_loop_count_max: 
                self.result_stats = stats
                self.ai_feedback_text = f"規定の {self.practice_loop_count}回 に達したため練習を終了します。"
                if self.editor_window: self.editor_window.close()
            else:
                # --- ループ継続 ---
                self.practice_loop_count += 1
                self.recorded_hits.clear(); self.judgements.clear(); self.judged_notes.clear()
                pygame.mixer.music.rewind()
                if self.editor_window:
                    self.editor_window.rhythm_widget.reset_for_loop()
                    current_elapsed = self.get_elapsed_time()
                    loop_dur = self.editor_window.rhythm_widget.loop_duration_ms
                    if loop_dur > 0:
                        loop_num = int(current_elapsed / loop_dur) + 1
                        self.editor_window.rhythm_widget.next_evaluation_time = loop_num * loop_dur

    def retry(self, force_reset=False):
        # (変更なし)
        if self.state.startswith("experiment_") and not force_reset:
            pass
        else:
            self.state = "waiting"

        self.recorded_hits, self.judgements = [], []
        self.judged_notes = {}  # 変更前: self.judged_notes.clear() または set()
        self.result_stats = {}; pygame.mixer.stop()
        pygame.mixer.music.stop()
        self.practice_loop_count = 0; self.is_perfect_mode = False
        self.practice_loop_count_max = float('inf')
        self.experiment_data.clear()
        self.experiment_next_state = None
        self._demo_return_state = "waiting" # ★ 復帰先もリセット

        # ★★★ 設定リセットを追加 ★★★
        if self.original_settings:
            self.settings = self.original_settings
        self.original_settings = None
        self.setting_overrides = None
        self.apply_settings() # ★ 念のため適用
        
        self.update_button_states()
        if not self.template_score and self.state == "waiting":
            self.label_template_file.setText("ファイルが読み込まれていません")
            self.label_template_file.set_style(font_size=12, weight=QFont.Weight.Normal, color_key='text_muted')

    def update_button_states(self):
        # ... (既存の分類ロジック) ...
        is_free_mode = self.state == "waiting" or self.state == "result"
        is_playing = self.state in ["recording", "demo_playback", "practice_countdown", "experiment_running"]
        is_experiment_mode = self.state.startswith("experiment_")
        # is_experiment_intro は "intro" だけでなく、ボタン操作待ちの画面全般を含める
        is_interactive_experiment = is_experiment_mode and not is_playing

        self.free_mode_panel.setVisible(is_free_mode)
        self.experiment_panel.setVisible(is_interactive_experiment)

        if is_free_mode:
            # ... (既存コード: フリーモードのボタン制御) ...
            self.btn_exp_finish.setVisible(False)
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
        
        elif is_experiment_mode:
            self.btn_exp_finish.setVisible(True)
            self.btn_settings.setVisible(False)

            if is_interactive_experiment:
                # まず全非表示
                self.btn_exp_prev.setVisible(False)
                self.btn_exp_action.setVisible(False)
                self.btn_exp_demo.setVisible(False)
                self.btn_exp_start.setVisible(False)
                self.btn_exp_next.setVisible(False)

                # --- アンケート画面の場合 ---
                if self.state == "experiment_questionnaire":
                    self.btn_exp_next.setVisible(True)
                    
                    if getattr(self, 'questionnaire_timer_active', False):
                        # タイマー待機中
                        self.btn_exp_next.setEnabled(False)
                        self.btn_exp_next.setText("回答中... (30秒待機)")
                    else:
                        # タイマー解除後
                        self.btn_exp_next.setEnabled(True)
                        self.btn_exp_next.setText("次へ ➔")

                # --- チュートリアル説明画面 ---
                elif self.state == "experiment_explanation":
                    # ... (既存コード) ...
                    page = getattr(self, 'tutorial_page_index', 0)
                    self.btn_exp_next.setVisible(True)
                    self.btn_exp_next.setText("次へ ➔")
                    self.btn_exp_next.setEnabled(True) # 明示的に有効化
                    if page > 0: self.btn_exp_prev.setVisible(True)
                    if page == 1:
                        self.btn_exp_action.setVisible(True); self.btn_exp_action.setText("▶️ メトロノーム再生")
                    elif page == 2:
                        self.btn_exp_action.setVisible(True); self.btn_exp_action.setText("▶️ 楽譜再生")
                    elif page == 3:
                        self.btn_exp_action.setVisible(True); self.btn_exp_action.setText("▶️ ロボット動作確認")
                    elif page == 4:
                        self.btn_exp_action.setVisible(True); self.btn_exp_action.setText("▶️ テスト再生")

                # --- イントロ画面 ---
                elif self.state == "experiment_intro":
                    # ... (既存コード) ...
                    is_ready = self.template_score is not None or getattr(self, 'is_tutorial_active', False)
                    is_pre_test = (self.current_experiment_step == 0)
                    if is_pre_test:
                        self.btn_exp_demo.setVisible(is_ready)
                        has_completed_demo = getattr(self, 'experiment_demo_completed', False)
                        self.btn_exp_demo.setEnabled(is_ready and not has_completed_demo)
                        if has_completed_demo: self.btn_exp_demo.setText("お手本再生済み ✅")
                        else: self.btn_exp_demo.setText("👁️ お手本再生")
                        can_start = is_ready and has_completed_demo
                        self.btn_exp_start.setVisible(is_ready)
                        self.btn_exp_start.setEnabled(can_start)
                        lock_prefix = "" if can_start else "🔒 "
                    else:
                        self.btn_exp_start.setVisible(is_ready)
                        self.btn_exp_start.setEnabled(is_ready)
                        lock_prefix = ""
                    try:
                        config = getattr(self, '_current_step_config', self.experiment_steps_config[self.current_experiment_step])
                        self.btn_exp_start.setText(lock_prefix + config['button_text'])
                        self.btn_exp_start.bg_color = config['color']
                        self.btn_exp_start.hover_color = config['color_dark']
                        self.btn_exp_start.update_style()
                    except: pass
                
                # --- 遷移画面 ---
                elif self.state in ["experiment_pre_tutorial", "experiment_pre_real"]:
                    self.btn_exp_next.setVisible(True)
                    self.btn_exp_next.setText("次へ ➔")
                    self.btn_exp_next.setEnabled(True)
                    self.btn_exp_prev.setVisible(True)

                # --- 終了画面 ---
                elif self.state == "experiment_finished":
                    pass

        elif is_playing:
            self.btn_settings.setVisible(False)
            self.btn_exp_finish.setVisible(self.state == "experiment_running")

    def process_midi_input(self):
        if not hasattr(self, 'inport') or not self.inport: return
        
        # MIDIメッセージを処理する
        for msg in self.inport.iter_pending():
            if msg.type == 'note_on' and msg.velocity >= VELOCITY_THRESHOLD:
                pad = 'top' if msg.note in PAD_MAPPING['left'] else 'bottom' if msg.note in PAD_MAPPING['right'] else None
                if not pad: continue
                current_time_ms = pygame.time.get_ticks() # アプリ起動時からのミリ秒
                if current_time_ms - self.last_input_time.get(pad, 0) < self.DEBOUNCE_TIME_MS:
                    # 前回の入力から時間が短すぎる場合は無視（スキップ）
                    continue
                
                # 有効な入力として時間を更新
                self.last_input_time[pad] = current_time_ms
                # ---------------------------------------------------------

                # ★ 修正1: 音を鳴らす判定に 'experiment_running' を追加
                if self.state in ["practice_countdown", "recording", "experiment_running"]:
                    if self.snare_sound: self.snare_sound.play()
                
                # ★ 修正2: データを記録する判定 (is_recording_state) を修正
                # 以前の experiment_test_A1_running などの代わりに experiment_running を使用
                is_recording_state = (self.state == "recording" or self.state == "experiment_running")

                if is_recording_state:
                    hit_time_ms = self.get_elapsed_time()
                    new_hit = {'time': hit_time_ms, 'pad': pad}
                    self.recorded_hits.append(new_hit)
                    
                    judgement, error_ms, note_id = self.judge_hit(new_hit)
                    
                    self.judgements.append({
                        'judgement': judgement, 
                        'error_ms': error_ms, 
                        'pad': pad, 
                        'note_id': note_id, 
                        'hit_time': hit_time_ms
                    })
                    
                    if note_id is not None:
                        self.judged_notes[note_id] = hit_time_ms
                    
                    if self.editor_window:
                        self.editor_window.rhythm_widget.add_user_hit(new_hit)
                        self.editor_window.rhythm_widget.add_feedback_animation(judgement, new_hit)
    def judge_hit(self, hit):
        pad, hit_time = hit['pad'], hit['time']; track_data = self.template_score.get(pad)
        if not track_data: return 'extra', None, None
        bpm = track_data.get('bpm', 120); ms_per_beat = 60000.0 / bpm
        
        num = track_data.get('numerator', 4); den = track_data.get('denominator', 4)
        beats_per_measure = (num / den) * 4.0; total_beats = beats_per_measure * NUM_MEASURES
        loop_duration_ms = ms_per_beat * total_beats
        if loop_duration_ms == 0: return 'extra', None, None
        
        hit_time_in_loop = hit_time % loop_duration_ms
        closest_note, min_diff = None, float('inf')
        
        for note in track_data.get('items', []):
            if note['class'] == 'note':
                note_time = note['beat'] * ms_per_beat
                
                # ループを考慮した最短距離を計算
                diffs = [
                    abs(hit_time_in_loop - note_time), 
                    abs(hit_time_in_loop - (note_time - loop_duration_ms)), 
                    abs(hit_time_in_loop - (note_time + loop_duration_ms))
                ]
                diff = min(diffs)
                
                # ★★★ 修正: 再判定の許可ロジック ★★★
                # そのノートが「まだ判定されていない」または「前回の判定からループの半分以上時間が経っている」場合、対象とする
                last_judged_time = self.judged_notes.get(note.get('id'), -1)
                is_rejudge_allowed = False
                
                if last_judged_time == -1:
                    is_rejudge_allowed = True
                else:
                    # 前回叩いた時間との差が、ループ長の50%を超えていれば、新しいループでの打撃とみなす
                    if (hit_time - last_judged_time) > (loop_duration_ms * 0.5):
                        is_rejudge_allowed = True

                # 条件を満たす場合のみ候補にする
                if is_rejudge_allowed and diff < min_diff:
                    min_diff, closest_note = diff, note

        # 1. 最も近いノートが見つかったか？
        if closest_note:
            # 2. 見つかったノートを基準に、符号付きの「正確な誤差」を計算する
            note_time = closest_note['beat'] * ms_per_beat
            # 最も近い基準時間（現在、過去ループ、未来ループ）を探す
            candidates = [note_time, note_time - loop_duration_ms, note_time + loop_duration_ms]
            actual_note_time_instance = min(candidates, key=lambda x: abs(hit_time_in_loop - x))
            
            error_ms = hit_time_in_loop - actual_note_time_instance
            
            # 3. 誤差が 'Good' (110ms) の範囲内か？
            if abs(error_ms) <= JUDGEMENT_WINDOWS['good']:
                
                # ★★★ 重要: ここで判定時間を記録する ★★★
                self.judged_notes[closest_note['id']] = hit_time

                if abs(error_ms) <= JUDGEMENT_WINDOWS['perfect']: 
                    return 'perfect', error_ms, closest_note['id']
                if abs(error_ms) <= JUDGEMENT_WINDOWS['great']: 
                    return 'great', error_ms, closest_note['id']
                
                return 'good', error_ms, closest_note['id']

        return 'extra', None, None

    def register_dropped_note(self, note_id, pad):
        # ★★★ 修正: 辞書のキーチェックに変更（機能的には同じですが型を合わせます） ★★★
        
        # まだ一度も判定されていない、あるいは
        # ここで「前回の判定から時間が経っているか」を厳密に見ることもできますが、
        # 見逃し判定は EditorRhythmWidget 側で「現在時刻」に基づいて行われているため、
        # ここでは「単純な重複登録防止」だけで十分機能します。
        
        # ただし、ループ対応のため、register_dropped_note は
        # 「今回のループでまだ判定（ヒットまたはドロップ）されていない」ことを確認すべきですが、
        # UI側で制御されているため、ここでは既存のチェック方法（キーの有無）を
        # 時間チェックに変えるのが安全です。
        
        # 簡易修正: 判定済みリストに入っていない場合のみ追加
        # (ヒットした場合は self.judged_notes に入るので、ここは「見逃し」の初回登録になります)
        # ループごとの見逃しを厳密に取るにはUI側のロジック依存になりますが、
        # このメソッドは「判定履歴に残す」ためのものなので、シンプルに追記します。
        
        self.judgements.append({'judgement': 'dropped', 'error_ms': None, 'pad': pad, 'note_id': note_id, 'hit_time': None})
        
        # ★ 見逃した場合も「判定済み」として今の時間を記録しておく（重複報告防止）
        self.judged_notes[note_id] = self.get_elapsed_time()

    def get_elapsed_time(self):
        """
        現在のアブソリュートな経過時間を返す。
        EditorWindowが開いている場合は、そちらの絶対時刻（time.timeベース）を使用し、
        ロボット・UI・判定の時間を完全に同期させる。
        """
        if hasattr(self, 'editor_window') and self.editor_window is not None:
            return self.editor_window.get_elapsed_time()
        
        # EditorWindowがない場合（フォールバック）
        if pygame.mixer.get_init():
            return pygame.mixer.music.get_pos()
        return 0

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
        if self.state in ["practice_countdown", "recording", "experiment_running"]: 
            self.process_midi_input()
        self.canvas.update()
    def summarize_performance(self):
        """ パフォーマンス統計の計算 (上限100%制限を追加) """
        stats = { 'perfect': 0, 'great': 0, 'good': 0, 'extra': 0, 'dropped': 0 }
        
        # 集計
        for j in self.judgements:
            if j['judgement'] in stats: 
                stats[j['judgement']] += 1
        
        # ヒット数計算
        notes_judged = stats['perfect'] + stats['great'] + stats['good']
        
        # 見逃し数計算 (マイナスにならないように補正)
        stats['dropped'] = max(0, self.total_notes - notes_judged)
        
        # 誤差データの抽出
        all_errors = [j['error_ms'] for j in self.judgements if j['error_ms'] is not None]
        
        # --- 1. Acc (正打率) ---
        raw_accuracy = (notes_judged / self.total_notes * 100) if self.total_notes > 0 else 0
        stats['accuracy'] = min(100.0, raw_accuracy) # ★ 100%を超えないように制限
        
        # --- 2. Score (得点率) ---
        weighted_sum = (stats['perfect'] * 1.0) + \
                       (stats['great']   * 0.7) + \
                       (stats['good']    * 0.4)
                       
        raw_score = (weighted_sum / self.total_notes * 100) if self.total_notes > 0 else 0
        stats['score'] = min(100.0, raw_score) # ★ 100%を超えないように制限
        # -----------------------------------------------

        # 誤差・標準偏差
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
        
        current_step_idx = self.current_experiment_step
        total_steps = len(self.experiment_steps_config)

        # 次のステップインデックス
        next_step = current_step_idx + 1

        # ★ 変更: ステップが最後まで完了した場合 (2 -> 3)
        if next_step >= total_steps:
            self.log_window.append_log(f"セット {self.current_experiment_set_index + 1} の全ステップ完了。アンケート画面へ移行します。")
            
            # ここで次のセットには行かず、アンケート画面へ遷移する
            # データ保存は finish_performance ですでに完了している
            self.enter_experiment_state("experiment_questionnaire")
            
        else:
            # まだセット内のステップが残っている場合 (事前テスト -> 練習 など)
            self.log_window.append_log(f"ステップ {current_step_idx + 1} が完了。次のステップ {next_step + 1} へ。")
            # 同じセットの次のステップへ
            self.enter_experiment_state("experiment_intro", set_index=self.current_experiment_set_index, step=next_step)

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
            self.experiment_start_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.experiment_logs = [] # 全体の記録リスト
            self.current_set_log = {} # 現在のセット（楽譜1つ分）の記録
            self.experiment_data.clear()
            # ★ 修正: "explanation" -> "experiment_explanation"
            self.enter_experiment_state("experiment_explanation")

    def enter_experiment_state(self, new_state, set_index=None, step=None):
        if not new_state.startswith("experiment_"):
            new_state = "experiment_" + new_state
            
        self.log_window.append_log(f"実験状態遷移: {self.state} -> {new_state}")
        self.state = new_state
        self.label_info.setText("")
        
        # --- (既存) 1. 実験説明 ---
        if new_state == "experiment_explanation":
            # ... (既存コードのまま) ...
            self.label_template_file.setText("体験モード (チュートリアル)")
            self.label_template_file.set_style(font_size=14, weight=QFont.Weight.Bold, color_key='accent')
            self.tutorial_page_index = 0
            text = self.get_tutorial_text(new_state, 0)
            self.speech_manager.speak(text)

        # --- (既存) 2. イントロ ---
        elif new_state == "experiment_intro":
            # ... (既存コードのまま) ...
            self.experiment_demo_completed = False
            if set_index is None or step is None:
                return

            self.current_experiment_set_index = set_index
            self.current_experiment_step = step
            
            try:
                if getattr(self, 'is_tutorial_active', False):
                    # チュートリアル用ロジック (省略せず既存のコードを残すこと)
                    filename = "tutorial.json"
                    if hasattr(self, 'tutorial_steps_config'):
                        config = self.tutorial_steps_config[step]
                    else:
                        config = self.experiment_steps_config[step]
                else:
                    # 本番用ロジック
                    filename = self.experiment_sets[self.current_experiment_set_index]
                    config = copy.deepcopy(self.experiment_steps_config[self.current_experiment_step])
                    
                    if step == 1: 
                        experiment_order_list = self.settings.get('experiment_order', ['linear', 'passthrough', 'metronome'])
                        try:
                            practice_type = experiment_order_list[self.current_experiment_set_index]
                        except IndexError:
                            practice_type = 'linear'
                        if practice_type in self.experiment_practice_configs:
                            practice_config = self.experiment_practice_configs[practice_type]
                            config.update(practice_config) 

                self._current_step_config = config
                filepath = os.path.join(r"C:\卒研\music", filename)
                self._load_score_from_path(filepath)
                self.label_template_file.setText(f"📄 {filename.replace('.json', '')} ({config['title']})")
                self.label_template_file.set_style(font_size=14, weight=QFont.Weight.Bold, color_key='primary')
                self.label_info.setText("") 
                self.on_controller_changed()

            except Exception as e:
                self.log_window.append_log(f"enter_experiment_state エラー: {e}")
                self.retry(force_reset=True)
                return

        # --- (新規) 5. アンケート画面 ★★★
        elif new_state == "experiment_questionnaire":
            self.label_template_file.setText("アンケート回答")
            self.label_template_file.set_style(font_size=14, weight=QFont.Weight.Bold, color_key='warning')
            self.label_info.setText("表示されたQRコードからアンケートに回答してください。")
            
            # 音声案内
            self.speech_manager.speak("このセットは終了です。画面のQRコードからアンケートに回答してください。")

            # 30秒タイマーのセット (ボタン制御は update_button_states で行うが、有効化タイミングをここで予約)
            self.questionnaire_timer_active = True
            QTimer.singleShot(30000, self._enable_questionnaire_next_button)

        # --- (既存) 3. 終了画面 ---
        elif new_state == "experiment_finished":
            # ... (既存コード) ...
            self.label_template_file.setText("実験完了")
            self.label_template_file.set_style(font_size=14, weight=QFont.Weight.Bold, color_key='success')
            self.label_info.setText("ご協力ありがとうございました。")

        # --- (既存) 4. 遷移画面 ---
        elif new_state in ["experiment_pre_tutorial", "experiment_pre_real"]:
            # ... (既存コード) ...
            text = self.get_tutorial_text(new_state)
            self.speech_manager.speak(text)

        self.update_button_states()
        self.canvas.update()

    def _enable_questionnaire_next_button(self):
        if self.state == "experiment_questionnaire":
            self.questionnaire_timer_active = False
            self.update_button_states() # ボタンの状態を更新して有効化
            self.speech_manager.speak("回答が終わりましたら、次へ進んでください。")

    # ★★★ 修正版: on_experiment_button_clicked ★★★
    def on_experiment_button_clicked(self):
        sender = self.sender()
        
        # --- [次へ] ボタン ---
        if sender == self.btn_exp_next:
            
            # ★ 追加: アンケート画面からの遷移
            if self.state == "experiment_questionnaire":
                # アンケート終了 -> 次のセットへ、または実験終了
                next_set_index = self.current_experiment_set_index + 1
                
                if next_set_index >= len(self.experiment_sets):
                    # 全セット完了
                    self.enter_experiment_state("experiment_finished")
                else:
                    # 次のセットの Step 0 (Intro) へ
                    self.enter_experiment_state("experiment_intro", set_index=next_set_index, step=0)

            # ... (既存: 説明画面、遷移画面の処理) ...
            elif self.state == "experiment_explanation":
                if self.tutorial_page_index < 4:
                    self.tutorial_page_index += 1
                    self.canvas.update()
                    self.update_button_states()
                    text = self.get_tutorial_text("experiment_explanation", self.tutorial_page_index)
                    self.speech_manager.speak(text)
                else:
                    self.enter_experiment_state("experiment_pre_tutorial")
            
            elif self.state == "experiment_pre_tutorial":
                self.speech_manager.stop()
                self.start_experiment_tutorial_flow()

            elif self.state == "experiment_pre_real":
                self.speech_manager.stop()
                self.is_tutorial_active = False
                self.apply_settings() 
                self.enter_experiment_state("experiment_intro", set_index=0, step=0)
        
        # ... (以下、前へボタンなどは変更なし) ...
        elif sender == getattr(self, 'btn_exp_prev', None):
            if self.state == "experiment_explanation":
                if self.tutorial_page_index > 0:
                    self.tutorial_page_index -= 1
                    self.canvas.update()
                    self.update_button_states()
                    text = self.get_tutorial_text("experiment_explanation", self.tutorial_page_index)
                    self.speech_manager.speak(text)
            elif self.state == "experiment_pre_tutorial":
                self.tutorial_page_index = 4
                self.enter_experiment_state("experiment_explanation")
                text = self.get_tutorial_text("experiment_explanation", 4)
                self.speech_manager.speak(text)
            elif self.state == "experiment_pre_real":
                self.speech_manager.stop()
                self.start_experiment_tutorial_flow()
        
        elif sender == self.btn_exp_demo:
            if self.template_score and self.state == "experiment_intro":
                self._demo_return_state = self.state 
                self.start_demo_playback()
                return

        elif sender == self.btn_exp_start:
            if self.state == "experiment_intro":
                try:
                    config = getattr(self, '_current_step_config', self.experiment_steps_config[self.current_experiment_step])
                except (IndexError, AttributeError):
                    self.log_window.append_log("エラー: 設定の取得に失敗しました。")
                    return
                self.experiment_next_state = "advance_step" 
                self.start_generic_practice(
                    is_perfect_mode=config['is_perfect_mode'],
                    force_robot=config['force_robot'],
                    force_controller_name=config['force_controller_name'],
                    max_loops=config['max_loops'],
                    setting_overrides=config.get('setting_overrides')
                )

        elif sender == self.btn_exp_finish:
            self.speech_manager.stop()
            self.log_window.append_log("--- 実験が手動で中止/完了されました ---")
            self.retry(force_reset=True)

    # ★★★ アクションボタン用メソッド (修正版) ★★★
    def on_experiment_action_clicked(self):
        page = self.tutorial_page_index
        
        # 共通: tutorial.json をロード
        tutorial_path = os.path.join(r"C:\卒研\music", "tutorial.json")
        if not self._load_score_from_path(tutorial_path): return

        # 設定の一時退避
        if not self.original_settings:
            self.original_settings = self.settings.copy()

        # デモ再生の設定を作成
        demo_settings = self.settings.copy()
        
        # ページごとの設定
        force_robot = False
        controller = None
        current_visual_mode = 'score'
        
        if page == 1:  # メトロノーム確認
            demo_settings.update({
                'guide_line_on': False,
                'score_blinking_on': True,
                'metronome_on': True,
                'guide_cue_on': False,
                'demo_blink_mode': 'all'  # ★ 全点滅
            })
            force_robot = False
            current_visual_mode = 'speaker'
        
        elif page == 2:  # 楽譜再生確認
            demo_settings.update({
                'guide_line_on': False,
                'score_blinking_on': True,
                'metronome_on': True,
                'guide_cue_on': False,
                'demo_blink_mode': 'all'  # ★ 全点滅
            })
            force_robot = False

        elif page == 3: # ロボット動作確認 (チュートリアル 4/5)
            demo_settings.update({
                'guide_line_on': False,
                'score_blinking_on': True,
                'metronome_on': True,
                'guide_cue_on': False,
                'demo_blink_mode': 'first' # ★★★ ここを変更: 'all' -> 'first' ★★★
            })
            force_robot = True
            controller = "介入なし (お手本通り)"

        elif page == 4: # テスト再生
            # (変更なし: score_blinking_on が False なので blink_mode は影響しません)
            demo_settings.update({
                'guide_line_on': False,
                'score_blinking_on': False,
                'metronome_on': True,
                'guide_cue_on': False
            })
            force_robot = False   # ロボットなし

        self.settings = demo_settings
        self.apply_settings()

        # ... (以下変更なし) ...

        # カウントダウン計算
        top_bpm = self.template_score['top'].get('bpm', 100)
        countdown_s = (4 * (60.0 / top_bpm))
        
        # ロボット準備時間
        robot_prep_s = 0
        if force_robot and self.robot_manager:
             robot_prep_s = self.robot_manager.get_first_move_preparation_time(self.template_score)
             
             if controller:
                 from controllers.base_controller import BaseEntrainmentController
                 ms_per_beat = 60000.0 / top_bpm
                 active_ctrl = BaseEntrainmentController(copy.deepcopy(self.template_score), ms_per_beat)
                 master_start = time.time() + countdown_s + robot_prep_s
                 self.robot_manager.start_control(self.template_score, active_ctrl, master_start)

        master_start_time = time.time() + countdown_s + robot_prep_s
        
        # 戻り先を現在の状態に保存
        self._demo_return_state = self.state 

        # EditorWindow 表示
        self.editor_window = EditorWindow(
            self.template_score, self, self.item_images, 
            is_demo=True, 
            master_start_time=master_start_time,
            visual_mode=current_visual_mode
        )
        
        # ★★★ テスト再生(Page 4)の場合は1ループで終了、それ以外は3ループ ★★★
        if page == 4:
            self.editor_window.demo_loop_limit = 1
        else:
            self.editor_window.demo_loop_limit = 3
        # -------------------------------------------------------------
        
        self.editor_window.show()

    def start_experiment_tutorial_flow(self):
        """ 実験チュートリアルの開始 """
        self.log_window.append_log("--- 体験チュートリアル開始 ---")
        
        # フラグをセット
        self.is_tutorial_active = True 
        
        # チュートリアル用の楽譜セットを設定
        self.experiment_sets = ["tutorial.json"] 
        self.current_experiment_set_index = 0
        self.current_experiment_step = 0
        
        # ステップ設定をチュートリアル用に上書き (1回限りのリスト)
        # 設定: ロボット「介入なし」、ガイド類ON
        passthrough_config = {
            'is_perfect_mode': True,
            'force_robot': True,
            'force_controller_name': "介入なし (お手本通り)", 
            'max_loops': float('inf'), # 時間制限(5分など)まで
            'setting_overrides': None # メイン設定(ON)に従う
        }
        
        self.tutorial_steps_config = [
            # 1. 事前テスト (ロボットなし)
            {
                'title': "チュートリアル: 事前テスト",
                'description': "これは「実験チュートリアル」です。\nまずは事前テストの流れを確認します。\n(実際には記録されません)",
                'button_text': "事前テスト開始",
                'is_perfect_mode': False,
                'force_robot': False, 'force_controller_name': None, 'max_loops': 1,
                'color': COLORS['danger'], 'color_dark': COLORS['danger'].darker(),
                'setting_overrides': {'guide_line_on': False, 'score_blinking_on': False} # テストなのでOFF
            },
            # 2. 練習 (ロボットあり・Passthrough)
            {
                'title': "チュートリアル: 練習",
                'description': "次に練習パートです。\nロボットと一緒に練習します。\n(チュートリアルなので時間は本番より短いです。)",
                'button_text': "練習開始",
                **passthrough_config,
                'color': COLORS['success'], 'color_dark': COLORS['success'].darker()
            },
            # 3. 事後テスト
            {
                'title': "チュートリアル: 事後テスト",
                'description': "最後に事後テストです。\nこれで1セットの流れは終了です。",
                'button_text': "事後テスト開始",
                'is_perfect_mode': False,
                'force_robot': False, 'force_controller_name': None, 'max_loops': 1,
                'color': COLORS['danger'], 'color_dark': COLORS['danger'].darker(),
                'setting_overrides': {'guide_line_on': False, 'score_blinking_on': False}
            }
        ]
        
        # イントロ画面へ遷移
        self.enter_experiment_state("experiment_intro", set_index=0, step=0)
QR_CODE_PATHS = {
    'linear': r"C:\卒研\questionnaire\practiceA.png",      # 同調あり
    'passthrough': r"C:\卒研\questionnaire\practiceB.png",  # 同調なし
    'metronome': r"C:\卒研\questionnaire\practiceC.png"     # 従来手法
}
class AnalyzerCanvas(GlowingWidget):
    def __init__(self, main_window):
        super().__init__()
        self.main = main_window
        self.setMinimumHeight(480)
        
    def paintEvent(self, event):
        # ★★★ ここで painter を初期化する必要があります ★★★
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # 背景塗りつぶし
        painter.fillRect(self.rect(), COLORS['surface'])
        painter.setPen(QPen(COLORS['border'], 1))
        painter.drawRect(self.rect().adjusted(0, 0, -1, -1))
        
        # 描画メソッドの選択
        draw_method = None
        
        if self.main.state.startswith("experiment_"):
            if self.main.state == "experiment_explanation":
                draw_method = self.draw_experiment_explanation_state
            elif self.main.state == "experiment_intro":
                draw_method = self.draw_experiment_intro_state
            elif self.main.state == "experiment_running":
                draw_method = self.draw_experiment_running_state
            elif self.main.state == "experiment_finished":
                draw_method = self.draw_experiment_finished_state
            elif self.main.state in ["experiment_pre_tutorial", "experiment_pre_real"]:
                draw_method = self.draw_experiment_message_state
            elif self.main.state == "experiment_questionnaire":
                draw_method = self.draw_experiment_questionnaire_state
            else:
                draw_method = self.draw_experiment_default_state
        else:
            # 通常モード (waiting, recording, result, etc.)
            # getattrを使って動的にメソッドを取得 (例: draw_waiting_state)
            method_name = f"draw_{self.main.state}_state"
            draw_method = getattr(self, method_name, self.draw_waiting_state)
            
        # 選択したメソッドを実行
        if draw_method:
            draw_method(painter)

    # -------------------------------------------------------
    # 各状態の描画メソッド
    # -------------------------------------------------------

    def draw_experiment_questionnaire_state(self, painter):
        """ アンケート用QRコードの描画 (レスポンシブ対応) """
        w = self.width()
        h = self.height()
        
        # --- スケール計算 (高さ800pxを基準1.0とする) ---
        scale = min(w / 1200, h / 800)
        
        # --- フォント設定 ---
        title_size = max(24, int(36 * scale))
        desc_size = max(16, int(18 * scale))
        
        # --- レイアウト定義 ---
        # タイトル領域: 上部 15%
        title_rect = QRectF(0, h * 0.05, w, h * 0.1)
        
        # 説明文領域: タイトルの下 10%
        desc_rect = QRectF(0, h * 0.15, w, h * 0.08)
        
        # QRコード領域: 残りのスペース (マージン考慮)
        qr_area_rect = QRectF(0, h * 0.25, w, h * 0.6)

        # --- 描画実行 ---
        
        # タイトル
        painter.setPen(COLORS['text_primary'])
        painter.setFont(QFont("Segoe UI", title_size, QFont.Weight.Bold))
        painter.drawText(title_rect, Qt.AlignmentFlag.AlignCenter, "アンケートにご協力ください")

        # 説明文
        painter.setFont(QFont("Segoe UI", desc_size))
        painter.drawText(desc_rect, Qt.AlignmentFlag.AlignCenter, "以下のQRコードを読み取って回答してください。")

        # QRコード処理
        exp_order = self.main.settings.get('experiment_order', ['linear', 'passthrough', 'metronome'])
        set_index = self.main.current_experiment_set_index
        
        if 0 <= set_index < len(exp_order):
            practice_type = exp_order[set_index]
        else:
            practice_type = 'linear'

        qr_path = QR_CODE_PATHS.get(practice_type, "")

        if os.path.exists(qr_path):
            pixmap = QPixmap(qr_path)
            if not pixmap.isNull():
                # QRコードを領域に合わせてスケーリング
                # 正方形を維持しつつ、エリア内に収める
                max_qr_size = min(qr_area_rect.width(), qr_area_rect.height())
                # 少し余白を持たせる (* 0.9)
                target_size = int(max_qr_size * 0.9)
                
                scaled_pixmap = pixmap.scaled(
                    target_size, target_size, 
                    Qt.AspectRatioMode.KeepAspectRatio, 
                    Qt.TransformationMode.SmoothTransformation
                )
                
                # 中央に配置
                x = qr_area_rect.center().x() - (scaled_pixmap.width() / 2)
                y = qr_area_rect.center().y() - (scaled_pixmap.height() / 2)
                
                painter.drawPixmap(int(x), int(y), scaled_pixmap)
        else:
            painter.setPen(COLORS['danger'])
            painter.drawText(qr_area_rect, Qt.AlignmentFlag.AlignCenter, f"QRコードが見つかりません:\n{qr_path}")

    def draw_experiment_explanation_state(self, painter):
        """ 実験説明画面 (レスポンシブ対応) """
        w = self.width()
        h = self.height()
        page = self.main.tutorial_page_index
        
        # --- スケール計算 ---
        scale = min(w / 1200, h / 800)
        
        # --- フォントサイズ ---
        title_font_size = max(24, int(32 * scale))
        text_font_size = max(16, int(22 * scale)) # 本文を少し大きめに確保
        
        # --- レイアウト ---
        # タイトル: 上部 15%
        title_rect = QRectF(w * 0.05, h * 0.05, w * 0.9, h * 0.15)
        
        # 本文: その下 (左右マージンを10%ずつ確保)
        content_rect = QRectF(w * 0.1, h * 0.25, w * 0.8, h * 0.6)
        
        flags = Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop | Qt.TextFlag.TextWordWrap

        titles = [
            "チュートリアル (1/5): システム概要",
            "チュートリアル (2/5): メトロノーム",
            "チュートリアル (3/5): 楽譜の見方",
            "チュートリアル (4/5): ロボットの動き",
            "チュートリアル (5/5): テスト機能"
        ]
        title = titles[page] if page < len(titles) else ""
        text = self.main.get_tutorial_text("experiment_explanation", page)

        painter.save()
        
        # タイトル描画
        painter.setFont(QFont("Segoe UI", title_font_size, QFont.Weight.Bold))
        painter.setPen(COLORS['accent'])
        painter.drawText(title_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, title)
        
        # 区切り線
        line_y = title_rect.bottom()
        painter.setPen(QPen(COLORS['border'], 2))
        painter.drawLine(int(title_rect.left()), int(line_y), int(title_rect.right()), int(line_y))
        
        # 本文描画
        painter.setFont(QFont("Segoe UI", text_font_size))
        painter.setPen(COLORS['text_primary'])
        painter.drawText(content_rect, flags, text)
        
        painter.restore()

    def draw_experiment_message_state(self, painter):
        """ チュートリアル前後などの遷移メッセージ表示 (レスポンシブ対応) """
        w = self.width()
        h = self.height()

        # --- スケール計算 ---
        # 基準サイズ(1200x800)に対する比率を計算
        scale = min(w / 1200, h / 800)

        # --- フォントサイズ (最小サイズを保証しつつスケーリング) ---
        title_size = max(28, int(42 * scale)) 
        text_size = max(18, int(24 * scale))

        # --- テキストと色の決定 ---
        title = ""
        color = COLORS['text_primary']

        if self.main.state == "experiment_pre_tutorial":
            title = "チュートリアル（模擬実験）へ"
            color = COLORS['primary']
        elif self.main.state == "experiment_pre_real":
            title = "本番へ"
            color = COLORS['danger']

        text = self.main.get_tutorial_text(self.main.state)

        # --- レイアウト定義 (ここが重要) ---
        
        # タイトル領域: 画面上部 15% の位置から、高さ 15% 分確保
        title_rect = QRectF(w * 0.05, h * 0.15, w * 0.9, h * 0.15)
        
        # 本文領域: タイトルの下 (高さ 35% の位置) から開始
        # 左右に 10% ずつマージンを取り、下部まで広く確保して折り返しに対応
        text_rect = QRectF(w * 0.1, h * 0.35, w * 0.8, h * 0.55)

        # --- 描画実行 ---
        painter.save()
        
        # タイトル
        painter.setFont(QFont("Segoe UI", title_size, QFont.Weight.Bold))
        painter.setPen(color)
        painter.drawText(title_rect, Qt.AlignmentFlag.AlignCenter, title)
        
        # 本文
        painter.setFont(QFont("Segoe UI", text_size))
        painter.setPen(COLORS['text_primary'])
        
        # 上揃え + 水平中央揃え + 自動折り返し
        flags = Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter | Qt.TextFlag.TextWordWrap
        painter.drawText(text_rect, flags, text)
        
        painter.restore()

    def draw_experiment_intro_state(self, painter):
        """ 実験ステップ待機画面 (レスポンシブ対応) """
        w = self.width()
        h = self.height()
        
        try:
            set_num = self.main.current_experiment_set_index + 1
            step_num = self.main.current_experiment_step
            
            if hasattr(self.main, '_current_step_config'):
                config = self.main._current_step_config
            else:
                config = self.main.experiment_steps_config[step_num]
            
            title = f"セット {set_num}/{len(self.main.experiment_sets)}: {config['title']}"
            description = config['description']
            color = config['color']
            
        except Exception as e:
            title = "エラー"
            description = f"データ読込失敗: {e}"
            color = COLORS['danger']

        # --- スケール計算 ---
        scale = min(w / 1200, h / 800)
        title_size = max(28, int(36 * scale))
        desc_size = max(18, int(24 * scale))

        # --- レイアウト ---
        # タイトル: 画面中央より少し上
        title_rect = QRectF(w * 0.05, h * 0.15, w * 0.9, h * 0.15)
        
        # 説明文: タイトルの下
        desc_rect = QRectF(w * 0.1, h * 0.35, w * 0.8, h * 0.5)

        # 描画
        painter.setPen(color)
        painter.setFont(QFont("Segoe UI", title_size, QFont.Weight.Bold))
        painter.drawText(title_rect, Qt.AlignmentFlag.AlignCenter, title)
        
        painter.setPen(COLORS['text_primary'])
        painter.setFont(QFont("Segoe UI", desc_size))
        flags = Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter | Qt.TextFlag.TextWordWrap
        painter.drawText(desc_rect, flags, description)

    def draw_experiment_finished_state(self, painter):
        """ 実験終了画面 """
        painter.setPen(COLORS['success'])
        painter.setFont(QFont("Segoe UI", 36, QFont.Weight.Bold))
        painter.drawText(self.rect().adjusted(0, -100, 0, 0), Qt.AlignmentFlag.AlignCenter, "🎉 実験終了")
        
        painter.setPen(COLORS['text_primary'])
        painter.setFont(QFont("Segoe UI", 16))
        text = "ご協力ありがとうございました。\n「メインメニューに戻る」ボタンを押してください。"
        painter.drawText(self.rect().adjusted(50, 20, -50, 0), Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap, text)

    def draw_experiment_running_state(self, painter):
        self.draw_recording_state(painter)

    def draw_experiment_default_state(self, painter):
        self.draw_waiting_state(painter)

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
        painter.setPen(COLORS['success'])
        painter.setFont(QFont("Segoe UI", 42, QFont.Weight.Bold))
        painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "👁️ お手本を再生中...")
        painter.setPen(COLORS['text_secondary'])
        painter.setFont(QFont("Segoe UI", 16))
        painter.drawText(self.rect().adjusted(0, 80, 0, 0), Qt.AlignmentFlag.AlignCenter, "楽譜ウィンドウをご覧ください。")

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
        painter.save(); painter.setBrush(COLORS['surface_light']); painter.setPen(QPen(COLORS['accent'], 1)); painter.drawRoundedRect(rect, 15, 15); painter.setPen(COLORS['accent'])
        painter.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold)); painter.drawText(rect.adjusted(20, 15, 0, 0), "🤖 AI講師からのアドバイス"); painter.setPen(COLORS['text_primary']); painter.setFont(QFont("Segoe UI", 12))
        text_rect = rect.adjusted(20, 45, -20, -15); flags = Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop | Qt.TextFlag.TextWordWrap
        painter.drawText(text_rect, flags, self.main.ai_feedback_text); painter.restore()

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
        self.hide_score_content = False
        
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
        
        # 2. 練習の終了判定
        if self.loop_duration_ms > 0:
            if is_demo:
                limit = self.editor_window.demo_loop_limit
                if absolute_elapsed_ms >= self.loop_duration_ms * limit:
                    self.editor_window.close()
                    return
            else:
                if main_window.is_perfect_mode:
                    if absolute_elapsed_ms >= self.next_evaluation_time:
                        main_window.evaluate_and_continue_loop()
                        return
                else:
                    if absolute_elapsed_ms >= self.loop_duration_ms:  
                        self.editor_window.close(); return
        
        # 3. メトロノーム処理 (カウントダウン中も鳴らしたいのでここは通す)
        if main_window.settings.get('metronome_on', True) and 'top' in self.score:
            top_track = self.score['top']
            top_ms_per_beat = 60000.0 / top_track.get('bpm', 120)
            if top_ms_per_beat > 0:
                current_beat_num = int(absolute_elapsed_ms / top_ms_per_beat)
                if current_beat_num != self.last_metronome_beat:
                    beats_per_measure = top_track.get('beats_per_measure', 0)
                    if beats_per_measure > 0:
                        beats_in_measure_int = int(beats_per_measure)
                        is_accent = (current_beat_num % beats_in_measure_int == 0)
                        self.editor_window.play_metronome_sound(is_accent)

                        # ビジュアライザー更新
                        if self.editor_window.beat_visualizer_top and self.editor_window.beat_visualizer_top.isVisible():
                            numerator_top = self.score.get('top', {}).get('numerator', 4)
                            beat_top = current_beat_num % numerator_top
                            self.editor_window.beat_visualizer_top.set_beat(beat_top, numerator_top)

                        if self.editor_window.beat_visualizer_bottom and self.editor_window.beat_visualizer_bottom.isVisible():
                            numerator_bottom = self.score.get('bottom', {}).get('numerator', 4)
                            beat_bottom = current_beat_num % numerator_bottom
                            self.editor_window.beat_visualizer_bottom.set_beat(beat_bottom, numerator_bottom)
                    self.last_metronome_beat = current_beat_num
        
        # ★★★ 修正箇所: カウントダウン中（0ms未満）はここでリターンして音符処理をスキップする ★★★
        if absolute_elapsed_ms < 0:
            self.update()
            return

        if self.loop_duration_ms <= 0:
            self.update()
            return 

        # 4. 全トラック共通の「マスター時間」における現在位置を計算
        current_time_in_loop = absolute_elapsed_ms % self.loop_duration_ms

        # 5. 全トラック共通の「マスター」ループ番号を計算
        current_loop_num = int(absolute_elapsed_ms / self.loop_duration_ms)
        
        last_loop_num = self.last_loop_num 

        # 6. ループが切り替わったら、全トラックのフラグをリセット
        if current_loop_num != last_loop_num:
            for track_data in self.score.values():
                if not isinstance(track_data, dict):
                    continue
                for item in track_data.get('items', []):
                    item['played_in_loop'] = False
            
            self.last_loop_num = current_loop_num 

        # 7. 全トラックを共通の `current_time_in_loop` で処理
        for track_data in self.score.values():
            if not isinstance(track_data, dict):
                continue
                
            track_ms_per_beat = 60000.0 / track_data.get('bpm', 120)
            if track_ms_per_beat <= 0: continue
            
            for item in track_data.get('items', []):
                if item.get('played_in_loop', False):
                    continue  
                
                note_start_ms = item['beat'] * track_ms_per_beat
                time_diff = current_time_in_loop - note_start_ms
                
                # ★★★ 修正箇所: 判定ロジックの強化 ★★★
                # 変更前: if -16 <= time_diff <= 50:
                # 変更後: 「判定範囲内」または「既に時間を過ぎているがまだ処理されていない（すり抜け防止）」場合
                
                # 判定ウィンドウ (標準は -16ms ~ 50ms)
                is_in_window = (-16 <= time_diff <= 50)
                
                # すり抜け救済 (過去100ms以内なら遅れても鳴らす)
                # 特にスタート直後(0ms)のノートが、次のフレームでいきなり 20ms とかになった場合に有効
                is_missed_start = (50 < time_diff <= 100) and (item['beat'] == 0.0)

                if is_in_window or is_missed_start:
                    if item.get('class') == 'note':
                        
                        # ★★★ 修正: 点滅条件のロジック変更 ★★★
                        is_first_note = (item.get('beat', -1) == 0.0)
                        should_blink = False

                        if not is_demo:
                            # 練習モード: 常に一音目のみ
                            should_blink = is_first_note
                        else:
                            # デモモード: 設定 ('demo_blink_mode') に従う
                            # 'all'なら全点灯、'first'なら一音目のみ
                            mode = main_window.settings.get('demo_blink_mode', 'all')
                            if mode == 'all':
                                should_blink = True
                            else:
                                should_blink = is_first_note
                        
                        if should_blink:
                            item['lit_start_time'] = absolute_elapsed_ms
                        
                        if main_window.settings.get('guide_cue_on', False):  
                            self.editor_window.play_note_sound()
                    
                    item['played_in_loop'] = True
            
            # 8. 見逃し(dropped)判定 
            if not is_demo:
                track_name_key = 'unknown'
                for key, value in self.score.items():
                    if value is track_data:
                        track_name_key = key
                        break

                for note in track_data.get('items', []):
                    if note['class'] == 'note' and note.get('id') not in main_window.judged_notes:
                        note_time = note['beat'] * track_ms_per_beat
                        if current_time_in_loop > note_time + DROPPED_THRESHOLD:  
                            main_window.register_dropped_note(note['id'], track_name_key)
        
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

        if hasattr(self.editor_window, 'visual_mode') and self.editor_window.visual_mode == 'speaker':
            self.draw_speaker_mode(painter)
            return

        # ★★★ 追加: 楽譜非表示設定ならここで終了（中身を描かない） ★★★
        if self.hide_score_content:
            # ユーザーに分かりやすいよう、中央にテキストだけ出す
            painter.setPen(COLORS['text_secondary'])
            painter.setFont(QFont("Segoe UI", 16))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "ロボットの動きに合わせて練習してください")
            return
        # --------------------------------------------------------
        
        if not self.score: return

        current_time_abs = self.editor_window.get_elapsed_time()
        layout_mode = self.editor_window.main_window.settings.get('score_layout', 'vertical')

        # 1. アイテムの点灯状態を更新 (全トラック共通)
        for track_data in self.score.values():
                # 安全のため辞書型チェック
                if not isinstance(track_data, dict): 
                    continue
                    
                for item in track_data.get('items', []):
                    # ★★★ 修正箇所: 判定条件を厳密化 ★★★
                    # 以前: (diff) < LIT_DURATION  -> マイナスでもTrueになっていた
                    # 修正: 0 <= (diff) < LIT_DURATION -> 時間が過ぎていない(マイナス)場合はFalseにする
                    
                    if item.get('class') == 'note' and 'lit_start_time' in item:
                        diff = current_time_abs - item['lit_start_time']
                        item['is_lit'] = (0 <= diff < LIT_DURATION)
                    else:
                        item['is_lit'] = False

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

            # ★★★ 修正: 設定がON、または「設定OFFでも助走中(0ms未満)」なら表示する ★★★
            is_guide_on = self.editor_window.main_window.settings.get('guide_line_on', True)
            is_lead_in = (current_time_abs < 0)

            if is_guide_on or is_lead_in:
            # -----------------------------------------------------------------------------

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
                cursor_progress_fraction = (current_beat + 1.0) / total_display_beats
                
                # 3. 全てのトラックコンテキストに描画
                for track_name, ctx in staff_contexts.items():
                    cursor_x = ctx['start_x'] + cursor_progress_fraction * ctx['width']
                    self.draw_glowing_cursor(painter, cursor_x, 40, self.height() - 40)

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


    def draw_speaker_mode(self, painter):
        """ 画面中央に大きなスピーカーアイコンと波紋を描画 """
        center_x = self.width() / 2
        center_y = self.height() / 2
        
        # --- スピーカー本体の描画 ---
        icon_size = 100
        path = QPainterPath()
        
        # スピーカーの形（四角形 + 台形）
        rect_w = icon_size * 0.4
        rect_h = icon_size * 0.4
        path.addRect(center_x - icon_size/2, center_y - rect_h/2, rect_w, rect_h)
        
        polygon = QPolygonF([
            QPointF(center_x - icon_size/2 + rect_w, center_y - rect_h/2), # 左上
            QPointF(center_x + icon_size/4, center_y - icon_size/2),       # 右上
            QPointF(center_x + icon_size/4, center_y + icon_size/2),       # 右下
            QPointF(center_x - icon_size/2 + rect_w, center_y + rect_h/2)  # 左下
        ])
        path.addPolygon(polygon)
        
        painter.setBrush(COLORS['text_primary'])
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawPath(path)
        
        # --- 音波（波紋）のアニメーション描画 ---
        current_ms = self.editor_window.get_elapsed_time()
        phase = (current_ms % 1000) / 1000.0 # 0.0 -> 1.0 (1秒周期)
        
        painter.setBrush(Qt.BrushStyle.NoBrush)
        pen_color = COLORS['primary']
        pen_width = 6
        
        for i in range(3):
            wave_phase = (phase + i * 0.3) % 1.0
            alpha = int(255 * (1.0 - wave_phase))
            offset = 20 + (wave_phase * 40)
            
            wave_color = QColor(pen_color)
            wave_color.setAlpha(alpha)
            painter.setPen(QPen(wave_color, pen_width, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            
            rect_size = icon_size + offset * 2
            wave_rect = QRectF(center_x - rect_size/2 + 20, center_y - rect_size/2, rect_size, rect_size)
            
            # 右半分だけの円弧を描画
            painter.drawArc(wave_rect, -45 * 16, 90 * 16)

        # --- テキスト表示 ---
        painter.setPen(COLORS['text_primary'])
        painter.setFont(QFont("Segoe UI", 24, QFont.Weight.Bold))
        text_rect = QRectF(0, center_y + 80, self.width(), 50)
        painter.drawText(text_rect, Qt.AlignmentFlag.AlignCenter, "Listen to the Metronome")

    def draw_user_hits(self, painter, staff_contexts):
        if not self.editor_window.main_window.settings.get('show_feedback_on_score', False):
            return
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
        if not self.editor_window.main_window.settings.get('show_feedback_on_score', False):
            return
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
        if total_display_beats <= 0: return
        
        # 音符の中心位置を計算（ボックスの左端ではなく中心）
        x_fraction = (item['beat'] + 1.0) / total_display_beats
        note_center_x = start_x + x_fraction * drawable_width
        
        painter.save()
        
        if item.get('class') == 'note':
            # === 音符の描画（実際の楽譜風） ===
            
            # 1. 符頭（notehead）のサイズと形状
            notehead_width = 18
            notehead_height = 12
            notehead_y = staff_y
            
            # 2. 符尾（stem）の描画
            stem_height = 50
            stem_x = note_center_x + notehead_width / 2 - 1
            stem_top_y = notehead_y - stem_height
            
            # 音符の種類によって塗りつぶしを変える
            note_type = item.get('type', 'quarter')
            is_filled = note_type not in ['half', 'whole']  # 二分音符と全音符は白抜き
            needs_stem = note_type != 'whole'  # 全音符は符尾なし
            
            # 3. 符頭を描画
            notehead_rect = QRectF(
                note_center_x - notehead_width / 2,
                notehead_y - notehead_height / 2,
                notehead_width,
                notehead_height
            )
            
            if is_filled:
                painter.setBrush(COLORS['text_primary'])
                painter.setPen(QPen(COLORS['text_primary'], 1))
            else:
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.setPen(QPen(COLORS['text_primary'], 2))
            
            # 全音符は少し大きく
            if note_type == 'whole':
                notehead_rect.adjust(-2, -1, 2, 1)
            
            painter.drawEllipse(notehead_rect)
            
            # 4. 符尾を描画（全音符以外）
            if needs_stem:
                painter.setPen(QPen(COLORS['text_primary'], 2))
                painter.drawLine(int(stem_x), int(notehead_y), int(stem_x), int(stem_top_y))
                
                # 5. 旗（flag）の描画（八分音符以降）
                if note_type in ['eighth', 'sixteenth']:
                    flag_width = 8
                    flag_height = 12
                    
                    # 旗のパス（曲線）
                    flag_path = QPainterPath()
                    flag_path.moveTo(stem_x, stem_top_y)
                    flag_path.cubicTo(
                        stem_x + flag_width * 0.5, stem_top_y + flag_height * 0.3,
                        stem_x + flag_width * 0.8, stem_top_y + flag_height * 0.7,
                        stem_x + flag_width, stem_top_y + flag_height
                    )
                    flag_path.lineTo(stem_x, stem_top_y + flag_height * 0.6)
                    flag_path.closeSubpath()
                    
                    painter.setBrush(COLORS['text_primary'])
                    painter.setPen(Qt.PenStyle.NoPen)
                    painter.drawPath(flag_path)
                    
                    # 十六分音符は旗を2つ
                    if note_type == 'sixteenth':
                        flag_path2 = QPainterPath()
                        flag_offset = flag_height * 0.5
                        flag_path2.moveTo(stem_x, stem_top_y + flag_offset)
                        flag_path2.cubicTo(
                            stem_x + flag_width * 0.5, stem_top_y + flag_offset + flag_height * 0.3,
                            stem_x + flag_width * 0.8, stem_top_y + flag_offset + flag_height * 0.7,
                            stem_x + flag_width, stem_top_y + flag_offset + flag_height
                        )
                        flag_path2.lineTo(stem_x, stem_top_y + flag_offset + flag_height * 0.6)
                        flag_path2.closeSubpath()
                        painter.drawPath(flag_path2)
            
            # 6. 付点の描画
            if item.get('dotted', False):
                dot_x = note_center_x + notehead_width / 2 + 8
                dot_y = notehead_y
                painter.setBrush(COLORS['text_primary'])
                painter.setPen(Qt.PenStyle.NoPen)
                painter.drawEllipse(QPointF(dot_x, dot_y), 3, 3)
            
            # 7. ガイドサークル（タイミング表示用）
            #guide_circle_radius = 5
            #guide_circle_y = staff_y + 25  # 音符の下に配置
            #painter.setBrush(COLORS['primary'])
            #painter.setPen(Qt.PenStyle.NoPen)
            #painter.drawEllipse(
             #   QPointF(note_center_x, guide_circle_y),
              #  guide_circle_radius,
               # guide_circle_radius
            #)
            
            # 8. 点灯エフェクト
            if self.editor_window.main_window.settings.get('score_blinking_on', True):
                if item.get('is_lit', False):
                    # グロー効果を音符の中心から
                    for radius, alpha in [(40, 20), (30, 40), (20, 60)]:
                        glow_color = QColor(COLORS['note_glow'])
                        glow_color.setAlpha(alpha)
                        painter.setBrush(glow_color)
                        painter.setPen(Qt.PenStyle.NoPen)
                        painter.drawEllipse(QPointF(note_center_x, notehead_y), radius, radius)
                    
                    # 音符自体を明るく
                    bright_color = QColor(COLORS['note_glow'])
                    painter.setBrush(bright_color)
                    painter.setPen(QPen(COLORS['primary'].lighter(150), 2))
                    painter.drawEllipse(notehead_rect.adjusted(-2, -2, 2, 2))
        
        else:
            # === 休符の描画 ===
            width_fraction = item['duration'] / total_display_beats
            width = width_fraction * drawable_width
            item_rect = QRectF(note_center_x - width/2, staff_y - 25, width, 50)
            
            painter.setBrush(QColor(COLORS['surface']).lighter(105))
            painter.setPen(QPen(COLORS['border'].lighter(130), 1))
            painter.drawRoundedRect(item_rect, 6, 6)
            
            # 休符記号の簡易表示
            image_to_draw = self.item_images.get(item['type'])
            if image_to_draw:
                draw_y = item_rect.top() + (item_rect.height() - image_to_draw.height()) / 2
                draw_point = QPointF(item_rect.left() + 8, draw_y)
                painter.drawPixmap(draw_point, image_to_draw)
            else:
                painter.setPen(COLORS['text_secondary'])
                painter.setFont(QFont("Segoe UI", 9))
                painter.drawText(item_rect, Qt.AlignmentFlag.AlignCenter, ALL_DURATIONS[item['type']]['name'])
        
        painter.restore()
# (2096行目あたり、EditorWindow の定義の直前に、以下のクラスを丸ごと追加)

# ★★★ メトロノームビジュアライザー (移植) ★★★
class BeatVisualizer(QWidget):
    """ビートを視覚的に表示するウィジェット"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.beat_position = 0
        self.numerator = 4
        self.is_active = False
        self.setMinimumHeight(100)
        self.setStyleSheet(f"background-color: {COLORS['surface_light'].name()}; border-bottom: 1px solid {COLORS['border'].name()};")
        
    def set_beat(self, position, numerator):
        """ビート位置を設定"""
        self.beat_position = position
        self.numerator = numerator
        self.is_active = True
        self.update()
        
    def reset(self):
        """リセット"""
        self.is_active = False
        self.update()
        
    def paintEvent(self, event):
        """描画イベント"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        width = self.width()
        height = self.height()
        
        # 背景
        painter.fillRect(0, 0, width, height, COLORS['surface_light'])
        
        if self.numerator == 0:
            return
            
        # ビートの円を描画
        circle_radius = 25 # 少し小さく
        spacing = width / (self.numerator + 1)
        
        for i in range(self.numerator):
            x = int(spacing * (i + 1))
            y = height // 2
            
            # 現在のビートは赤、それ以外は灰色
            if self.is_active and i == self.beat_position:
                painter.setBrush(COLORS['danger'])
                painter.setPen(QPen(COLORS['danger_dark'], 3))
            else:
                painter.setBrush(COLORS['border'])
                painter.setPen(QPen(COLORS['text_muted'], 2))
            
            painter.drawEllipse(QPointF(x, y), circle_radius, circle_radius)
            
            # 拍の数字
            painter.setPen(COLORS['text_primary' if self.is_active and i == self.beat_position else 'text_secondary'])
            painter.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
            painter.drawText(QRectF(x - circle_radius, y - circle_radius, circle_radius * 2, circle_radius * 2), 
                           Qt.AlignmentFlag.AlignCenter, str(i + 1))
# ★★★ 移植ここまで ★★★


class EditorWindow(QMainWindow):
    def __init__(self, template_data, main_window, item_images, is_demo=False, parent=None, loop_duration_ms=0, robot_prep_time_s=0, master_start_time=0, visual_mode='score', hide_score=False):
        super().__init__(parent)
        self.main_window = main_window
        self.is_demo = is_demo
        self.template_data = template_data
        
        # ★ 変数に保存
        self.visual_mode = visual_mode 
        self.hide_score = hide_score

        # 変数の保存
        self.robot_prep_time_s = robot_prep_time_s
        self.robot_triggered = False
        self.master_start_time = master_start_time
        self.demo_loop_limit = 2
        self.was_manually_stopped = False
        title = "🎼 お手本再生" if is_demo else "🥁 練習中"; self.setWindowTitle(title)

        # ★★★ ここから修正 ★★★
        # メインウィンドウの設定から現在のレイアウトモードを取得
        layout_mode = self.main_window.settings.get('score_layout', 'vertical')
        
        screen = QApplication.primaryScreen()
        screen_size = screen.availableGeometry()
        
        # ベースサイズ
        if layout_mode == 'horizontal':
            base_w, base_h = 2000, 650
        else:
            base_w, base_h = 1500, 750
            
        # 画面の90%に収まるようにスケーリング係数を計算
        width_ratio = (screen_size.width() * 0.9) / base_w
        height_ratio = (screen_size.height() * 0.9) / base_h
        scale_factor = min(1.0, width_ratio, height_ratio) # 最大でも1.0倍
        
        self.resize(int(base_w * scale_factor), int(base_h * scale_factor))

        scale_factor = 1.0  # ← ここを調整 (0.7 = 元の70%の大きさ)

        if layout_mode == 'horizontal':
            # 元: 2000 x 650
            w, h = 2000, 650
            self.resize(int(w * scale_factor), int(h * scale_factor))
        else:
            # 元: 1500 x 750 (縦並び)
            w, h = 1500, 750
            self.resize(int(w * scale_factor), int(h * scale_factor))
        
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
        #再生停止ボタンのコメントアウト
        #self.stop_button = ModernButton("⏹️ " + ("再生停止" if is_demo else "練習中止"), "danger"); self.stop_button.clicked.connect(self.force_stop_practice)
        #header_layout.addWidget(self.stop_button); layout.addWidget(header_widget)
        self.visualizer_container = QWidget()
        visualizer_layout = QHBoxLayout(self.visualizer_container)
        visualizer_layout.setContentsMargins(0, 0, 0, 0)
        visualizer_layout.setSpacing(5) # 左右の間にわずかな隙間

        # layout_mode に応じて Top と Bottom の BeatVisualizer を作成
        layout_mode = self.main_window.settings.get('score_layout', 'vertical')
        is_two_track_mode = 'top' in self.template_data and 'bottom' in self.template_data

        self.beat_visualizer_top = None
        self.beat_visualizer_bottom = None

        if 'top' in self.template_data:
            self.beat_visualizer_top = BeatVisualizer(self)
            self.beat_visualizer_top.hide() 
            visualizer_layout.addWidget(self.beat_visualizer_top)

        # 横並びモード (horizontal) で2トラックある場合は、中央に線を入れる
        if layout_mode == 'horizontal' and is_two_track_mode:
            line = QWidget()
            line.setFixedWidth(2)
            line.setStyleSheet(f"background-color: {COLORS['border'].name()};")
            visualizer_layout.addWidget(line)

        if 'bottom' in self.template_data:
            self.beat_visualizer_bottom = BeatVisualizer(self)
            self.beat_visualizer_bottom.hide() 
            visualizer_layout.addWidget(self.beat_visualizer_bottom)

            # 1トラック (bottomのみ) の場合、Topのスペーサーを追加して中央寄せ
            if not 'top' in self.template_data:
                visualizer_layout.insertWidget(0, QWidget())

        # 1トラック (topのみ) の場合、Bottomのスペーサーを追加して中央寄せ
        elif 'top' in self.template_data and not 'bottom' in self.template_data:
            visualizer_layout.addWidget(QWidget())

        VBoxA = (self.beat_visualizer_top and not self.beat_visualizer_top.isHidden()) or \
            (self.beat_visualizer_bottom and not self.beat_visualizer_bottom.isHidden())
        if not VBoxA:
            self.visualizer_container.hide() # 両方非表示ならコンテナごと隠す

        layout.addWidget(self.visualizer_container) # ヘッダーの下に追加
        if self.visual_mode == 'speaker':
            self.visualizer_container.hide()
        # ★★★ 変更ここまで ★★★
        self.rhythm_widget = EditorRhythmWidget(item_images, self)
        layout.addWidget(self.rhythm_widget)
        self.rhythm_widget.set_data(copy.deepcopy(template_data), loop_duration_ms)
        self.rhythm_widget.hide_score_content = self.hide_score
        self.countdown_label = QLabel(self)
        self.countdown_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.countdown_label.setStyleSheet(f"color: {COLORS['text_primary'].name()}; background-color: rgba(248, 249, 250, 0.8); border-radius: 20px;")
        self.countdown_label.setFont(QFont("Segoe UI", 150, QFont.Weight.Bold))
        #if self.is_demo:
            #self.countdown_label.hide(); self.start_actual_playback()
        #else:
            #self.countdown_timer = QTimer(self); self.countdown_timer.timeout.connect(self.update_countdown); self.countdown_timer.start(50)
            
        self.countdown_timer = QTimer(self)
        self.countdown_timer.timeout.connect(self.update_countdown)
        self.countdown_timer.start(50)

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

        # ★★★ 問題2対応: ビジュアライザーをリセット ★★★
        if self.beat_visualizer_top:
            self.beat_visualizer_top.reset()
            self.beat_visualizer_top.hide()
        if self.beat_visualizer_bottom:
            self.beat_visualizer_bottom.reset()
            self.beat_visualizer_bottom.hide()
        self.visualizer_container.hide()
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
        """
        ロボットと同じ「絶対時刻(time.time)」を基準にした経過時間を返す。
        これにより、ロボットとUI/ガイド音のズレを解消する。
        """
        # 現在時刻 - 開始予定時刻 = 経過時間(秒)
        # これをミリ秒に変換
        elapsed_sec = time.time() - self.master_start_time
        return elapsed_sec * 1000.0

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