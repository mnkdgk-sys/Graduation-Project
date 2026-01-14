import sys
import openai
import os
import json
import pygame
from collections import Counter
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                               QPushButton, QListWidget, QMenuBar, QFileDialog, QMessageBox,
                               QLabel, QSpinBox, QRadioButton, QGridLayout, QButtonGroup, QComboBox, QCheckBox, QGroupBox, QScrollArea)
from PySide6.QtGui import (QPainter, QColor, QPen, QAction, QFont, QPixmap, QIcon, QLinearGradient, QCursor)
from PySide6.QtCore import Qt, QTimer, QRectF, QPointF, QSize
from PySide6.QtCore import QThread, Signal, Slot 
from PySide6.QtWidgets import QDoubleSpinBox 

try:
    import numpy as np
    NUMPY_AVAILABLE = True
except ImportError:
    NUMPY_AVAILABLE = False

# --- 定数と設定 ---
WINDOW_WIDTH, WINDOW_HEIGHT = 1280, 720

# モダンUIのカラーテーマ
COLORS = {
    'background': QColor(245, 245, 245),
    'surface': QColor(255, 255, 255),
    'surface_light': QColor(238, 238, 238),
    'primary': QColor(0, 123, 255),
    'primary_dark': QColor(0, 105, 217),
    'success': QColor(40, 167, 69),
    'warning': QColor(255, 193, 7),
    'danger': QColor(220, 53, 69),
    'text_primary': QColor(33, 37, 41),
    'text_secondary': QColor(108, 117, 125),
    'text_muted': QColor(170, 170, 170),
    'border': QColor(221, 221, 221),
    'note_glow': QColor(0, 123, 255, 100),
    'rest_bg': QColor(230, 230, 230, 200),
    'staff_line': QColor(50, 50, 50),
    'cursor': QColor(255, 0, 100),
}

NUM_MEASURES = 2
NOTE_DURATIONS = {
    'whole': {'duration': 4.0, 'name': "全音符"},
    'half': {'duration': 2.0, 'name': "2分音符"},
    'quarter': {'duration': 1.0, 'name': "4分音符"},
    'eighth': {'duration': 0.5, 'name': "8分音符"},
    'sixteenth': {'duration': 0.25, 'name': "16分音符"},
}
REST_DURATIONS = {
    'quarter_rest': {'duration': 1.0, 'name': "4分休符"},
    'eighth_rest': {'duration': 0.5, 'name': "8分休符"},
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

LIT_DURATION = 150

def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_path, relative_path)

# --- モダンUIコンポーネントクラス (変更なし) ---
class ModernButton(QPushButton):
    def __init__(self, text, button_type="primary", parent=None):
        super().__init__(text, parent)
        self.button_type = button_type
        self.setMinimumHeight(36)
        self.setFont(QFont("Segoe UI", 10, QFont.Weight.Medium))
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.apply_style()

    def apply_style(self):
        color_map = {
            "primary": (COLORS['primary'], COLORS['primary_dark'], "white"),
            "success": (COLORS['success'], COLORS['success'].darker(120), "white"),
            "warning": (COLORS['warning'], COLORS['warning'].darker(120), "black"),
            "danger": (COLORS['danger'], COLORS['danger'].darker(120), "white"),
            "secondary": (COLORS['surface_light'], COLORS['surface_light'].lighter(120), COLORS['text_primary'])
        }
        bg_color, hover_color, text_color = color_map.get(self.button_type, color_map["secondary"])
        self.setStyleSheet(f"""
            QPushButton {{
                background-color: {bg_color.name()};
                border: 1px solid {COLORS['border'].name()};
                border-radius: 6px;
                color: {text_color.name() if isinstance(text_color, QColor) else text_color};
                padding: 8px 12px;
            }}
            QPushButton:hover {{
                background-color: {hover_color.name()};
            }}
            QPushButton:pressed {{
                background-color: {hover_color.darker(110).name()};
            }}""")

class ModernGroupBox(QGroupBox):
    def __init__(self, title, parent=None):
        super().__init__(title, parent)
        self.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        self.setStyleSheet(f"""
            QGroupBox {{
                border: 1px solid {COLORS['border'].name()};
                border-radius: 8px; margin-top: 10px;
                background-color: {COLORS['surface'].name()};
            }}
            QGroupBox::title {{
                subcontrol-origin: margin; subcontrol-position: top left;
                padding: 0 10px; margin-left: 10px;
                background-color: {COLORS['surface'].name()};
                color: {COLORS['primary'].name()};
            }}""")

class ModernSpinBox(QSpinBox):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFont(QFont("Segoe UI", 10))
        self.setStyleSheet(f"""
            QSpinBox {{
                background-color: {COLORS['surface_light'].name()};
                border: 1px solid {COLORS['border'].name()};
                border-radius: 4px; padding: 6px;
                color: {COLORS['text_primary'].name()};
            }}
            QSpinBox:focus {{ border: 1px solid {COLORS['primary'].name()}; }}
            QSpinBox::up-button, QSpinBox::down-button {{ background: transparent; }}
            QSpinBox::up-arrow {{ image: url({resource_path('images/chevron-up.svg')}); }}
            QSpinBox::down-arrow {{ image: url({resource_path('images/chevron-down.svg')}); }}
            """)

class ModernComboBox(QComboBox):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFont(QFont("Segoe UI", 10))
        self.setStyleSheet(f"""
            QComboBox {{
                background-color: {COLORS['surface_light'].name()};
                border: 1px solid {COLORS['border'].name()};
                border-radius: 4px; padding: 6px;
                color: {COLORS['text_primary'].name()};
            }}
            QComboBox:focus {{ border: 1px solid {COLORS['primary'].name()}; }}
            QComboBox::drop-down {{ border: none; }}
            QComboBox::down-arrow {{ image: url({resource_path('images/chevron-down.svg')}); }}
            QComboBox QAbstractItemView {{
                background-color: {COLORS['surface'].name()};
                border: 1px solid {COLORS['border'].name()};
                color: {COLORS['text_primary'].name()};
                selection-background-color: {COLORS['primary'].name()};
            }}""")



class ModernCheckBox(QCheckBox):
    def __init__(self, text, parent=None):
        super().__init__(text, parent)
        self.setFont(QFont("Segoe UI", 10, QFont.Weight.Medium))
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        
        # アニメーション用の変数
        self._animation_progress = 0.0  # 0.0 (オフ) から 1.0 (オン)
        self._animation_timer = QTimer(self)
        self._animation_timer.timeout.connect(self._update_animation)
        self._animation_timer.setInterval(16)  # 約60fps
        self._is_hovered = False
        
        # 初期状態を設定
        if self.isChecked():
            self._animation_progress = 1.0
        
        # スタイルシートで標準のインジケータを非表示にし、テキスト色のみ設定
        self.setStyleSheet(f"""
            QCheckBox {{
                color: {COLORS['text_primary'].name()};
                spacing: 14px;
            }}
            QCheckBox::indicator {{
                width: 0px;
                height: 0px;
            }}
        """)
        
        # 状態変更時のアニメーション開始
        self.stateChanged.connect(self._on_state_changed)
    
    def _on_state_changed(self, state):
        """チェック状態が変わったときにアニメーションを開始"""
        self._animation_timer.start()
    
    def _update_animation(self):
        """アニメーションの進行を更新"""
        target = 1.0 if self.isChecked() else 0.0
        diff = target - self._animation_progress
        
        if abs(diff) < 0.01:
            self._animation_progress = target
            self._animation_timer.stop()
        else:
            # スムーズなイージング（減速）
            self._animation_progress += diff * 0.2
        
        self.update()
    
    def enterEvent(self, event):
        """マウスが入ったとき"""
        self._is_hovered = True
        self.update()
        super().enterEvent(event)
    
    def leaveEvent(self, event):
        """マウスが出たとき"""
        self._is_hovered = False
        self.update()
        super().leaveEvent(event)
    
    def sizeHint(self):
        """推奨サイズを返す"""
        fm = self.fontMetrics()
        text_width = fm.horizontalAdvance(self.text())
        base_size = super().sizeHint()
        return QSize(42 + 12 + text_width, 28)
    
    def paintEvent(self, event):
        """カスタム描画"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # スイッチのサイズと位置
        switch_width = 42
        switch_height = 22
        switch_x = 0
        switch_y = (self.height() - switch_height) / 2
        
        # 背景色（アニメーション進行度に応じて変化）
        if self._animation_progress < 0.5:
            # オフ寄り
            if self._is_hovered:
                bg_color = QColor(180, 200, 230, int(40 + self._animation_progress * 60))
            else:
                bg_color = QColor(180, 180, 180, int(30 + self._animation_progress * 50))
        else:
            # オン寄り
            progress_adjusted = (self._animation_progress - 0.5) * 2
            if self._is_hovered:
                bg_color = QColor(int(180 - 180 * progress_adjusted), 
                                int(200 - 20 * progress_adjusted), 
                                int(230 + 25 * progress_adjusted), 
                                int(100 + 155 * progress_adjusted))
            else:
                bg_color = QColor(int(180 - 180 * progress_adjusted), 
                                int(180 - 20 * progress_adjusted), 
                                int(180 + 75 * progress_adjusted), 
                                int(80 + 145 * progress_adjusted))
        
        # 背景を描画
        painter.setBrush(bg_color)
        border_alpha = int(100 + self._animation_progress * 155)
        if self._animation_progress > 0.5:
            border_color = QColor(0, 123, 255, border_alpha)
        else:
            border_color = QColor(160, 160, 160, border_alpha)
        painter.setPen(QPen(border_color, 1))
        painter.drawRoundedRect(QRectF(switch_x, switch_y, switch_width, switch_height), 11, 11)
        
        # ハンドルの位置（アニメーション）
        handle_size = 16
        handle_margin = 3
        max_travel = switch_width - handle_size - 2 * handle_margin
        handle_x = switch_x + handle_margin + max_travel * self._animation_progress
        handle_y = switch_y + handle_margin
        
        # ハンドルのグロー効果
        if self._animation_progress > 0.3:
            glow_color = QColor(0, 160, 255, int(80 * self._animation_progress))
            for i in range(3):
                glow_size = handle_size + (3 - i) * 3
                painter.setBrush(glow_color)
                painter.setPen(Qt.PenStyle.NoPen)
                painter.drawEllipse(QRectF(handle_x - (glow_size - handle_size) / 2, 
                                          handle_y - (glow_size - handle_size) / 2, 
                                          glow_size, glow_size))
                glow_color.setAlpha(int(glow_color.alpha() * 0.5))
        
        # ハンドルを描画
        handle_gradient = QLinearGradient(handle_x, handle_y, handle_x, handle_y + handle_size)
        handle_gradient.setColorAt(0, QColor(255, 255, 255))
        handle_gradient.setColorAt(1, QColor(240, 240, 240))
        painter.setBrush(handle_gradient)
        painter.setPen(QPen(QColor(200, 200, 200, 150), 1))
        painter.drawEllipse(QRectF(handle_x, handle_y, handle_size, handle_size))
        
        # テキストを描画
        painter.setPen(COLORS['text_primary'])
        painter.setFont(self.font())
        text_x = switch_width + 12
        text_rect = QRectF(text_x, 0, self.width() - text_x, self.height())
        painter.drawText(text_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, self.text())
        
        painter.end()
        

class ModernRadioButton(QRadioButton):
    def __init__(self, text, parent=None):
        super().__init__(text, parent)
        self.setFont(QFont("Segoe UI", 10))

        self.setStyleSheet(f"""
            QRadioButton {{ 
                color: {COLORS['text_primary'].name()}; 
                spacing: 8px; /* テキストとボタンの間隔 */
            }}
            
            /* オフ状態のインジケータ (円) */
            QRadioButton::indicator {{
                width: 16px; 
                height: 16px;
                border: 2px solid {COLORS['border'].name()}; /* 灰色の枠線 */
                border-radius: 10px; /* 完全に丸くする (width/2 + 2) */
                background-color: {COLORS['surface'].name()}; /* 中は白 */
            }}

            /* ホバー状態 */
            QRadioButton::indicator:hover {{
                border: 2px solid {COLORS['text_secondary'].name()}; /* ホバーで枠線を濃く */
            }}

            /* オン (チェック済み) の状態 */
            QRadioButton::indicator:checked {{
                border: 2px solid {COLORS['primary'].name()}; /* 枠線が青に */
                
                /* 中に青い点を描画 */
                background-color: qradialgradient(
                    cx:0.5, cy:0.5, radius: 0.4, fx:0.5, fy:0.5,
                    stop:0 {COLORS['primary'].name()}, /* 中心の点 (青) */
                    stop:0.8 {COLORS['primary'].name()},
                    stop:1 {COLORS['surface'].name()} /* 外側 (白) */
                );
            }}
            
            /* オン状態でホバー */
            QRadioButton::indicator:checked:hover {{
                border: 2px solid {COLORS['primary_dark'].name()}; /* 枠線が濃い青に */
                background-color: qradialgradient(
                    cx:0.5, cy:0.5, radius: 0.4, fx:0.5, fy:0.5,
                    stop:0 {COLORS['primary_dark'].name()}, /* 中心の点 (濃い青) */
                    stop:0.8 {COLORS['primary_dark'].name()},
                    stop:1 {COLORS['surface'].name()}
                );
            }}
        """)

class ModernLabel(QLabel):
    def __init__(self, text, label_type="primary", parent=None):
        super().__init__(text, parent)
        color = COLORS['text_primary']
        if label_type == "secondary": color = COLORS['text_secondary']
        elif label_type == "muted": color = COLORS['text_muted']
        self.setFont(QFont("Segoe UI", 10))
        self.setStyleSheet(f"color: {color.name()}; background: transparent;")

class ModernListWidget(QListWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFont(QFont("Segoe UI", 10))
        self.setStyleSheet(f"""
            QListWidget {{
                background-color: {COLORS['surface'].name()};
                border: 1px solid {COLORS['border'].name()};
                border-radius: 6px;
                color: {COLORS['text_primary'].name()};
                padding: 4px;
            }}
            QListWidget::item {{
                padding: 8px; border-radius: 4px; margin: 1px;
            }}
            QListWidget::item:selected {{
                background: {COLORS['primary'].name()}; color: white;
            }}
            QListWidget::item:hover:!selected {{
                background: {COLORS['surface_light'].name()};
            }}""")


# --- アプリケーションのメインクラス ---
class GenerationWorker(QThread):
    """OpenAI APIとの通信を非同期で行うワーカー"""
    pattern_generated = Signal(str, list)
    generation_failed = Signal(str)

    def __init__(self, conversation_history, parent=None):
        super().__init__(parent)
        self.history = conversation_history
        # __init__でのクライアント初期化を削除（run()内で行う）

    def run(self):
        try:
            # APIキーのチェック
            api_key = os.environ.get("OPENAI_API_KEY")
            if not api_key:
                self.generation_failed.emit("OPENAI_API_KEYが設定されていません。")
                return
            
            # クライアントの初期化をスレッド内で行う
            client = openai.OpenAI(api_key=api_key)
            
            # APIコールを実行
            response = client.chat.completions.create(
                model="gpt-4o",
                messages=self.history,
                response_format={"type": "json_object"},
                temperature=0.7,
            )
            
            json_response_str = response.choices[0].message.content
            new_history = self.history + [{"role": "assistant", "content": json_response_str}]
            
            self.pattern_generated.emit(json_response_str, new_history)
        
        except openai.OpenAIError as e:
            self.generation_failed.emit(f"OpenAI APIエラー: {e}")
        except Exception as e:
            self.generation_failed.emit(f"不明なエラー: {e}")

class RhythmWidget(QWidget):
    # (このクラスに変更なし)
    def __init__(self, item_images, main_window, parent=None):
        super().__init__(parent)
        self.main_window = main_window
        self.setMinimumHeight(200)
        self.item_images = item_images
        self.score = {}
        self.is_playing = False
        self.playback_start_time = 0
        self.playback_timer = QTimer(self)
        self.playback_timer.timeout.connect(self.update_playback)
        self.metronome_enabled = False
        self.last_metronome_beat = -1
        self.margin = 50

    def get_master_loop_duration_ms(self):
        if 'top' not in self.score: return 0
        top_track = self.score['top']
        top_bpm = top_track.get('bpm', 120)
        top_total_beats = top_track.get('total_beats', 0)
        if top_bpm <= 0 or top_total_beats <= 0: return 0
        return (60000.0 / top_bpm) * top_total_beats

    def update_playback(self):
        if not self.is_playing or not self.score: return
        absolute_elapsed_ms = self.main_window.get_elapsed_time() - self.playback_start_time
        if self.metronome_enabled and 'top' in self.score:
            top_track = self.score['top']
            top_loop_ms = (60000.0 / top_track.get('bpm', 120)) * top_track.get('total_beats', 1)
            if top_loop_ms > 0:
                top_current_ms = absolute_elapsed_ms % top_loop_ms
                top_ms_per_beat = 60000.0 / top_track.get('bpm', 120)
                if top_ms_per_beat > 0:
                    current_beat_num = int(top_current_ms / top_ms_per_beat)
                    if current_beat_num != self.last_metronome_beat:
                        beats_per_measure = top_track.get('beats_per_measure', 0)
                        if beats_per_measure > 0:
                            is_accent = (current_beat_num % int(beats_per_measure) == 0)
                            self.main_window.play_metronome_sound(is_accent)
                        self.last_metronome_beat = current_beat_num
        for track_data in self.score.values():
            track_loop_ms = (60000.0 / track_data.get('bpm', 120)) * track_data.get('total_beats', 1)
            if track_loop_ms <= 0: continue
            track_current_ms = absolute_elapsed_ms % track_loop_ms
            last_ms = track_data.get('last_elapsed_ms', 0)
            if last_ms > track_current_ms:
                for item in track_data.get('items', []):
                    item['played_in_loop'] = False
            track_data['last_elapsed_ms'] = track_current_ms
            track_ms_per_beat = 60000.0 / track_data.get('bpm', 120)
            if track_ms_per_beat <= 0: continue
            for item in track_data.get('items', []):
                note_start_ms = item['beat'] * track_ms_per_beat
                if not item.get('played_in_loop', False) and track_current_ms >= note_start_ms:
                    if item.get('class') == 'note':
                        item['lit_start_time'] = self.main_window.get_elapsed_time()
                        self.main_window.play_note_sound()
                    item['played_in_loop'] = True
        self.update()

    def set_data(self, score_data):
        self.score = score_data
        self.update()

    def start_playback(self):
        if not self.is_playing:
            self.is_playing = True
            self.playback_start_time = self.main_window.get_elapsed_time()
            for track_data in self.score.values():
                for item in track_data.get('items', []): item['played_in_loop'] = False
                track_data['last_elapsed_ms'] = -1
            self.last_metronome_beat = -1
            self.playback_timer.start(16)
            self.update()

    def stop_playback(self):
        if self.is_playing:
            self.is_playing = False
            self.playback_timer.stop()
            self.update()

    def set_metronome_enabled(self, enabled):
        self.metronome_enabled = enabled
        if not enabled: self.last_metronome_beat = -1

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # 1. 常に背景を描画する
        gradient = QLinearGradient(0, 0, 0, self.height())
        gradient.setColorAt(0, COLORS['background'])
        gradient.setColorAt(1, COLORS['surface'])
        painter.fillRect(self.rect(), gradient)

        start_x = self.margin
        drawable_width = self.width() - (self.margin * 2)

        # 2. 描画可能な場合のみ中身を実行するifブロックで囲む
        if drawable_width > 0 and self.score: 
            
            current_time = self.main_window.get_elapsed_time()
            if 'top' in self.score:
                painter.save()
                painter.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
                painter.setPen(COLORS['text_secondary'])
                bpm_text = f"メトロノーム BPM: {self.score['top'].get('bpm', 120):.0f}"
                painter.drawText(10, 20, bpm_text)
                painter.restore()

            for track_data in self.score.values():
                for item in track_data.get('items', []):
                    item['is_lit'] = item.get('class') == 'note' and 'lit_start_time' in item and (current_time - item['lit_start_time']) < LIT_DURATION

            staff_y_positions = {}
            is_two_track_mode = 'top' in self.score and 'bottom' in self.score
            if is_two_track_mode:
                staff_y_positions['top'] = self.height() * 0.35
                staff_y_positions['bottom'] = self.height() * 0.65
            elif 'top' in self.score:
                staff_y_positions['top'] = self.height() * 0.5

            for track_name, staff_y in staff_y_positions.items():
                self.draw_staff(painter, self.score[track_name], staff_y, start_x, drawable_width, is_two_track_mode)

            if self.is_playing:
                is_synced = self.main_window.sync_checkbox.isChecked()
                absolute_elapsed_ms = self.main_window.get_elapsed_time() - self.playback_start_time
                if not is_two_track_mode or is_synced:
                    master_loop_ms = self.get_master_loop_duration_ms()
                    if master_loop_ms > 0:
                        progress = (absolute_elapsed_ms % master_loop_ms) / master_loop_ms
                        cursor_x = start_x + progress * drawable_width
                        self.draw_glowing_line(painter, cursor_x, 30, self.height() - 30)
                else:
                    for track_name, staff_y in staff_y_positions.items():
                        track = self.score[track_name]
                        track_duration_ms = (60000.0 / track.get('bpm', 120)) * track.get('total_beats', 1)
                        if track_duration_ms > 0:
                            track_progress = (absolute_elapsed_ms % track_duration_ms) / track_duration_ms
                            cursor_x = start_x + track_progress * drawable_width
                            self.draw_glowing_line(painter, cursor_x, staff_y - 40, staff_y + 40, 4)

        # --- ▼▼▼ ここが修正点 ▼▼▼ ---
        # 3. painter を明示的に終了させる
        painter.end()

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
        denominator = track_data.get('denominator', 4)
        painter.save()
        if is_two_track_mode:
            painter.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
            painter.setPen(COLORS['primary'])
            label = "L" if staff_y < self.height() / 2 else "R"
            painter.drawText(QRectF(5, staff_y - 35, 40, 30), Qt.AlignmentFlag.AlignCenter, label)
        
        # 拍子記号を大きく見やすく
        painter.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        painter.setPen(COLORS['text_primary'])
        numerator = track_data.get('numerator', 4)
        ts_text = f"{numerator}/{denominator}"
        painter.drawText(QRectF(5, staff_y + 5, 40, 30), Qt.AlignmentFlag.AlignCenter, ts_text)
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
        
        is_lit = item.get('is_lit', False)
        
        if item.get('class') == 'note':
            if is_lit:
                # 外側のグロー効果（複数レイヤー）
                for i in range(3):
                    glow_alpha = 40 - (i * 10)
                    glow_expand = 6 + (i * 3)
                    glow_color = QColor(COLORS['primary'])
                    glow_color.setAlpha(glow_alpha)
                    painter.setBrush(glow_color)
                    painter.setPen(Qt.PenStyle.NoPen)
                    painter.drawRoundedRect(item_rect.adjusted(-glow_expand, -glow_expand, glow_expand, glow_expand), 10, 10)
                
                # 内側の明るい塗りつぶし
                bright_fill = QColor(COLORS['primary'])
                bright_fill.setAlpha(120)
                painter.setBrush(bright_fill)
                painter.setPen(Qt.PenStyle.NoPen)
                painter.drawRoundedRect(item_rect.adjusted(-1, -1, 1, 1), 7, 7)
            else:
                painter.setBrush(Qt.BrushStyle.NoBrush)
            
            # 枠線
            pen_width = 5 if is_lit else 2
            pen_color = COLORS['primary'] if not is_lit else QColor(255, 255, 255)
            pen = QPen(pen_color, pen_width)
            painter.setPen(pen)
            painter.drawRoundedRect(item_rect.adjusted(-pen_width/2, -pen_width/2, pen_width/2, pen_width/2), 6 + pen_width/2, 6 + pen_width/2)

        else: # 休符の場合
            painter.setBrush(COLORS['rest_bg']); painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(item_rect, 6, 6)
        painter.restore()
        
        image_to_draw = self.item_images.get(item['type'])
        if image_to_draw:
            padding_x, draw_y = 5, item_rect.top() + (item_rect.height() - image_to_draw.height()) / 2
            draw_point = QPointF(item_rect.left() + padding_x, draw_y)
            painter.drawPixmap(draw_point, image_to_draw)
            if item.get('dotted', False):
                dot_x, dot_y = draw_point.x() + image_to_draw.width() + 4, staff_y + 15
                painter.save()
                painter.setBrush(COLORS['text_primary']); painter.setPen(Qt.PenStyle.NoPen)
                painter.drawEllipse(QPointF(dot_x, dot_y), 3, 3)
                painter.restore()
        else:
            painter.setPen(COLORS['text_primary']); painter.drawText(item_rect, Qt.AlignmentFlag.AlignCenter, ALL_DURATIONS[item['type']]['name'])

    def mousePressEvent(self, event):
        if event.button() != Qt.MouseButton.RightButton or self.is_playing: return
        track_name_to_check = 'top'
        if 'top' in self.score and 'bottom' in self.score and event.position().y() > self.height() / 2:
            track_name_to_check = 'bottom'
        if track_name_to_check not in self.score: return
        total_beats = self.score[track_name_to_check].get('total_beats', 1)
        clicked_beat = ((event.position().x() - self.margin) / (self.width() - 2 * self.margin)) * total_beats
        item_to_remove = None
        for item in reversed(self.score[track_name_to_check]['items']):
            if item['beat'] <= clicked_beat < item['beat'] + item['duration']:
                item_to_remove = item; break
        if item_to_remove:
            self.score[track_name_to_check]['items'].remove(item_to_remove)
            self.update()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.note_sound, self.metronome_click, self.metronome_accent_click = None, None, None
        self._is_changing_ts = False
        
        # --- ▼▼▼ 修正点 1 (変数名を score_directory に変更) ▼▼▼ ---
        self.score_directory = r"C:\卒研\music"
        # --- ▲▲▲ 修正点 1 ▲▲▲ ---

        self.generation_worker = None
        self.ai_conversation_history = []
        self.ai_current_iteration = 0
        self.ai_max_iterations = 5 # 採点ループの最大回数
        self.ai_target_difficulty = 5.0
        self.ai_target_track = 'top'
        self.original_items_backup = []
        self.original_bpm_backup = 120
        self.original_num_backup = 4
        self.original_den_backup = 4
        self.is_ai_running = False

        try:
            pygame.mixer.pre_init(44100, -16, 2, 1024)
            pygame.init()
            pygame.mixer.set_num_channels(32)
            if pygame.mixer.get_init() is None: raise RuntimeError("Pygameミキサーを初期化できませんでした。")
            if not NUMPY_AVAILABLE: raise ImportError("'numpy' が見つかりません。")
            self.note_sound = self._generate_sound(880, 100)
            self.metronome_click = self._generate_sound(1500, 50)
            self.metronome_accent_click = self._generate_sound(2500, 50)
        except Exception as e:
            QMessageBox.critical(self, "初期化エラー", f"オーディオを初期化できませんでした:\n{e}")

        self.setWindowTitle("リズムエディター"); self.resize(WINDOW_WIDTH, WINDOW_HEIGHT)
        self.setStyleSheet(f"background-color: {COLORS['background'].name()}; color: {COLORS['text_primary'].name()};")
        try: self.setWindowIcon(QIcon(resource_path("icon.icns")))
        except: print("警告: icon.icns が見つかりません。")
        self.current_filepath, self.app_start_time = None, pygame.time.get_ticks()
        self.item_images = self._load_item_images()
        self.setup_ui()
        self.refresh_file_list()

    def _backup_track_data(self, track_name):
        """指定されたトラックの現在の状態をバックアップする"""
        if track_name not in self.rhythm_widget.score:
            return
        track_data = self.rhythm_widget.score[track_name]
        self.original_items_backup = [item.copy() for item in track_data.get('items', [])]
        self.original_bpm_backup = track_data.get('bpm', 120)
        self.original_num_backup = track_data.get('numerator', 4)
        self.original_den_backup = track_data.get('denominator', 4)

    def _restore_track_data(self, track_name):
        """バックアップからトラックの状態を復元する"""
        if track_name not in self.rhythm_widget.score:
            return
        track_data = self.rhythm_widget.score[track_name]
        track_data['items'] = self.original_items_backup
        track_data['bpm'] = self.original_bpm_backup
        track_data['numerator'] = self.original_num_backup
        track_data['denominator'] = self.original_den_backup
        
        self.recalculate_beats(track_name)
        self._update_spinners_from_track(track_name)

    def _update_spinners_from_track(self, track_name):
        """トラックデータからUIのスピナー類を更新する"""
        if track_name not in self.rhythm_widget.score:
            return
        
        track_data = self.rhythm_widget.score[track_name]
        
        # on_time_signature_changedが発火しないように一時的にブロック
        self._is_changing_ts = True
        try:
            getattr(self, f"{track_name}_bpm_spinner").setValue(track_data['bpm'])
            getattr(self, f"{track_name}_numerator_spinner").setValue(track_data['numerator'])
            getattr(self, f"{track_name}_denominator_combo").setCurrentText(str(track_data['denominator']))
        except Exception as e:
            print(f"UIスピナーの更新に失敗: {e}")
        finally:
            self._is_changing_ts = False

    def _get_system_prompt(self, bpm, numerator, denominator):
        """AIに指示を出すためのシステムプロンプトを生成する"""

        # AIに難易度計算ロジックを平易な言葉で説明する
        difficulty_hint = """
        難易度のヒント:
        - 4分音符(duration: 1.0)が基本です。
        - 8分音符(0.5)や16分音符(0.25)のように、音符が短くなるほど難易度が上がります。
        - 付点音符(dotted: true)も難易度を上げます。
        - 16分休符(0.25)のような短い休符は、難易度を少し上げます。
        - シンコペーション（拍の裏から始まる音符）は難易度を上げます。
        - BPMが高いほど難易度が上がりますが、BPMは今回固定({bpm})です。
        - 多様な音符を組み合わせると難易度が上がります。
        """

        # --- ▼▼▼ 変更 ▼▼▼ ---
        # AIが自身で拍子を決めるため、引数の値は使わない
        # (ただし、AIへのヒントとして渡す)
        
        # AIに提案させるBPMと拍子の範囲を指定
        bpm_rule = "BPMは 10 から 120 の間で整数値を選んでください。"
        ts_rule = """
        拍子は以下のいずれかから選んでください:
        - { "numerator": 4, "denominator": 4 } (4/4拍子)
        - { "numerator": 3, "denominator": 4 } (3/4拍子)
        - { "numerator": 6, "denominator": 8 } (6/8拍子)
        - { "numerator": 5, "denominator": 4 } (5/4拍子)
        """

        # 2小節分のビート数をAIに計算させる
        return f"""
        あなたはリズムパターンの専門家です。
        ユーザーの指示に従い、リズムパターンを生成してください。

        ステップ1: 拍子(numerator, denominator)を決める。
        {ts_rule}

        ステップ2: BPMを決める。
        {bpm_rule}

        ステップ3: 決めた拍子で**2小節分**のリズムパターン(`items`)を生成する。
        - 1小節のビート数 = (numerator / denominator) * 4.0
        - 生成する合計ビート数 = (1小節のビート数) * 2
        
        `items`リスト内のビートの合計 (beat + duration) は、必ず上記で計算した「生成する合計ビート数」に一致させてください。

        必ず以下のJSON形式で、`bpm`, `numerator`, `denominator`, `items`の4つのキーを持つ辞書を返してください。

        必須フォーマット:
        {{
            "bpm": 120,
            "numerator": 4,
            "denominator": 4,
            "items": [
                {{
                    "beat": 0.0, 
                    "type": "quarter", 
                    "duration": 1.0, 
                    "class": "note", 
                    "dotted": false
                }},
                // ... (合計ビート数分のアイテム) ...
                {{
                    "beat": 7.0, 
                    "type": "quarter_rest", 
                    "duration": 1.0, 
                    "class": "rest", 
                    "dotted": false
                }}
            ]
        }}

        {difficulty_hint}
        JSONオブジェクトのみを返し、前後に説明文を付けないでください。
        """
    @Slot()
    def _clear_worker_reference(self):
        """
        Slot to clear the self.generation_worker reference when the
        thread is finished, preventing RuntimeError.
        """
        # C++オブジェクトの削除はdeleteLaterに任せ、
        # ここではPythonからの参照をNoneにリセットする
        self.generation_worker = None

    @Slot()
    def start_ai_generation(self):
        """AI生成ボタンが押されたときの処理"""
        # 既存のスレッドが実行中なら待機
        if self.generation_worker and self.generation_worker.isRunning():
            QMessageBox.warning(self, "処理中", "既にAI生成が実行中です。完了までお待ちください。")
            return
        
        self.ai_generate_button.setEnabled(False)
        self.ai_status_label.setText("生成を開始します...")
        self.is_ai_running = True

        self.ai_target_difficulty = self.ai_target_difficulty_spinbox.value()
        self.ai_target_track = 'top' if self.ai_target_track_combo.currentIndex() == 0 else 'bottom'

        if self.ai_target_track == 'bottom' and not self.mode_2_track_rb.isChecked():
            self.ai_target_track = 'top'
            self.ai_target_track_combo.setCurrentIndex(0)

        self._backup_track_data(self.ai_target_track)
        
        # プロンプト生成に現在の設定を渡す（AIへのヒントとして）
        system_prompt = self._get_system_prompt(
            self.original_bpm_backup, 
            self.original_num_backup, 
            self.original_den_backup
        )
        user_prompt = f"目標難易度 {self.ai_target_difficulty:.2f} で1小節のリズムパターンを生成してください。"

        self.ai_conversation_history = [ 
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        self.ai_current_iteration = 0
        self.run_generation_step()

    def run_generation_step(self):
        """APIワーカーを起動して、AIに楽譜をリクエストする"""
        if self.generation_worker and self.generation_worker.isRunning():
            return

        self.ai_status_label.setText(f"AIが思考中... ({self.ai_current_iteration + 1}/{self.ai_max_iterations}回目)")
        
        # 新しいワーカーを作成
        self.generation_worker = GenerationWorker(self.ai_conversation_history, self)
        self.generation_worker.pattern_generated.connect(self.on_ai_pattern_received)
        self.generation_worker.generation_failed.connect(self.on_generation_failed)
        self.generation_worker.finished.connect(self._clear_worker_reference)
        self.generation_worker.finished.connect(self.generation_worker.deleteLater)
        
        self.generation_worker.start()

    @Slot(str, list)
    def on_ai_pattern_received(self, json_response_str, new_history):
        """AIからのJSONレスポンスを受け取り、採点する"""
        self.ai_conversation_history = new_history

        try:
            data = json.loads(json_response_str)
            
            new_bpm = data.get('bpm', self.original_bpm_backup)
            new_num = data.get('numerator', self.original_num_backup)
            new_den = data.get('denominator', self.original_den_backup)
            
            if 'items' not in data or not isinstance(data['items'], list):
                raise ValueError("JSONの形式が不正です ('items'キーがありません)")
            
            new_items = data['items']

            # --- ▼▼▼ ここから変更 ▼▼▼ ---
            
            # --- ここで2小節分の採点＆検証 ---
            track_data = self.rhythm_widget.score[self.ai_target_track]
            
            # 1. 一時的に楽譜をAIが生成したBPM/拍子/アイテムに入れ替える
            track_data['bpm'] = new_bpm
            track_data['numerator'] = new_num
            track_data['denominator'] = new_den
            track_data['items'] = new_items # 2小節分の全アイテムを入れる
            
            beats_per_measure = (new_num / new_den) * 4.0
            total_beats_required = beats_per_measure * 2.0 # 2小節分
            
            if beats_per_measure == 0:
                raise ValueError("拍子記号が無効です (beats_per_measureが0)")

            # 1b. 【検証】AIが2小節分を埋めているかチェック
            last_beat = max([item['beat'] + item['duration'] for item in new_items], default=0.0)
            
            if last_beat < (total_beats_required - 0.01):
                # ビート数が足りない場合
                feedback_prompt = f"楽譜が2小節分埋まっていませんでした。合計ビート数が {total_beats_required:.2f} になるようにしてください。(現在の合計: {last_beat:.2f})"
                self._restore_track_data(self.ai_target_track) 
                self.ai_conversation_history.append({"role": "user", "content": feedback_prompt})
                self.ai_current_iteration += 1
                if self.ai_current_iteration >= self.ai_max_iterations:
                     self.on_generation_failed("AIが指定回数内に有効な楽譜を生成できませんでした。")
                else:
                     self.ai_status_label.setText(f"AIが再試行中 (ビート数不足)...")
                     self.run_generation_step()
                return

            # 2. 【採点】新しいヘルパー関数で2小節の平均点を計算
            # (この時点で track_data は AI の提案内容になっている)
            actual_score = self._get_2_measure_average_score(self.ai_target_track)

            # 3. 楽譜を採点前の状態（バックアップ）に戻す
            self._restore_track_data(self.ai_target_track)
            # --- ▲▲▲ 採点＆検証ロジックここまで ▲▲▲ ---

            self.ai_status_label.setText(f"AI採点結果: {actual_score:.2f} (目標: {self.ai_target_difficulty:.2f})")

            # 許容誤差 (例: ±0.5点)
            tolerance = 0.5
            if abs(actual_score - self.ai_target_difficulty) <= tolerance:
                # 成功！
                self.load_generated_pattern(new_items, new_bpm, new_num, new_den, actual_score)
                return

            self.ai_current_iteration += 1
            if self.ai_current_iteration >= self.ai_max_iterations:
                # 試行回数上限。一番近かったものを採用
                self.load_generated_pattern(new_items, new_bpm, new_num, new_den, actual_score)
                QMessageBox.information(self, "AI生成", f"試行回数の上限に達しました。\n最終スコア: {actual_score:.2f} の楽譜を読み込みます。")
                return

            # --- フィードバックして再挑戦 ---
            feedback_prompt = ""
            if actual_score < self.ai_target_difficulty:
                feedback_prompt = f"あなたの楽譜(BPM:{new_bpm}, {new_num}/{new_den})のスコアは {actual_score:.2f} でした。目標は {self.ai_target_difficulty:.2f} です。もっと難しくしてください。"
            else:
                feedback_prompt = f"あなたの楽譜(BPM:{new_bpm}, {new_num}/{new_den})のスコアは {actual_score:.2f} でした。目標は {self.ai_target_difficulty:.2f} です。もっと簡単にしてください。"

            self.ai_conversation_history.append({"role": "user", "content": feedback_prompt})
            self.run_generation_step() # 次のステップを実行

        except json.JSONDecodeError:
            self.on_generation_failed("AIが不正なJSONを返しました。")
        except ValueError as e:
            self.on_generation_failed(f"AIが返したJSONの形式が不正です: {e}")
        except Exception as e:
            self.on_generation_failed(f"採点中に不明なエラー: {e}")


    def load_generated_pattern(self, items, bpm, num, den, final_score):
        """最終的に決定した楽譜と設定をウィジェットに読み込む"""
        track_data = self.rhythm_widget.score[self.ai_target_track]

        # --- ▼▼▼ 変更・追加 ▼▼▼ ---
        # 1. 2小節分のアイテムをそのまま設定（マージしない）
        track_data['items'] = items
        
        # 2. BPMと拍子も設定
        track_data['bpm'] = bpm
        track_data['numerator'] = num
        track_data['denominator'] = den
        
        # 3. UIのスピナーとコンボボックスを更新
        self._update_spinners_from_track(self.ai_target_track)

        # 4. total_beats などを再計算
        self.recalculate_beats(self.ai_target_track)
        # --- ▲▲▲ 変更 ▲▲▲ ---

        self.rhythm_widget.update()
        self.ai_generate_button.setEnabled(True)
        self.ai_status_label.setText(f"完了！ (スコア: {final_score:.2f})")

        # 難易度表示を更新
        if self.ai_target_track == 'top':
            self.top_difficulty_label.setText(f"上段(L)難易度: {final_score:.2f}")
        else:
            self.bottom_difficulty_label.setText(f"下段(R)難易度: {final_score:.2f}")
            
        self.combined_difficulty_label.setText("総合難易度: -")

        self.is_ai_running = False


    @Slot(str)
    def on_generation_failed(self, error_message):
        """AI生成が失敗したときの処理"""
        QMessageBox.critical(self, "AI 生成エラー", error_message)
        
        # --- ▼▼▼ 変更 ▼▼▼ ---
        # バックアップから楽譜とUIを復元
        self._restore_track_data(self.ai_target_track)
        # --- ▲▲▲ 変更 ▲▲▲ ---
        
        self.ai_generate_button.setEnabled(True)
        self.ai_status_label.setText("エラーが発生しました。")
        self.is_ai_running = False

    def _generate_sound(self, frequency, duration_ms):
        sample_rate = pygame.mixer.get_init()[0]; n_samples = int(round(duration_ms/1000*sample_rate))
        buf = np.zeros((n_samples, 2), dtype=np.int16); max_val = 2**15-1; amp = max_val*0.5
        period = int(sample_rate/frequency)
        for i in range(n_samples):
            val = amp if (i//(period/2))%2==0 else -amp
            buf[i,:]=val
        fade_out = np.linspace(1,0,n_samples)**2
        buf[:,0] = np.int16(buf[:,0]*fade_out); buf[:,1] = np.int16(buf[:,1]*fade_out)
        return pygame.sndarray.make_sound(buf)

    def _load_item_images(self):
        images, all_files = {}, {**NOTE_IMAGE_FILES, **REST_IMAGE_FILES}
        for item_type, filename in all_files.items():
            path = resource_path(filename)
            if os.path.exists(path):
                pixmap = QPixmap(path)
                h = 20 if item_type in ['eighth_rest', 'sixteenth_rest'] else 40
                images[item_type] = pixmap.scaledToHeight(h, Qt.TransformationMode.SmoothTransformation)
            else: print(f"警告: '{path}'が見つかりません。")
        return images

    def setup_ui(self):
        menu_bar = self.menuBar()
        menu_bar.setStyleSheet(f"""
            QMenuBar {{ background-color: {COLORS['surface'].name()}; color: {COLORS['text_primary'].name()}; }}
            QMenuBar::item:selected {{ background-color: {COLORS['primary'].name()}; }}
            QMenu {{ background-color: {COLORS['surface'].name()}; color: {COLORS['text_primary'].name()}; }}
            QMenu::item:selected {{ background-color: {COLORS['primary'].name()}; }}
        """)
        file_menu = menu_bar.addMenu("ファイル")
        actions = {"新規作成": self.new_score, "開く...": self.open_score, "保存": self.save_score, "名前を付けて保存...": self.save_score_as, "終了": self.close}
        for name, func in actions.items():
            if name == "終了": file_menu.addSeparator()
            action = QAction(name, self); action.triggered.connect(func); file_menu.addAction(action)
        main_widget = QWidget(); self.setCentralWidget(main_widget)
        main_layout = QHBoxLayout(main_widget); main_layout.setContentsMargins(10,10,10,10); main_layout.setSpacing(10)
        left_panel = QWidget(); left_layout = QVBoxLayout(left_panel)
        left_layout.addWidget(ModernLabel("保存済みファイル:", "secondary"))
        self.file_list_widget = ModernListWidget()
        self.file_list_widget.itemDoubleClicked.connect(self.load_from_list)
        left_layout.addWidget(self.file_list_widget)
        self.rhythm_widget = RhythmWidget(self.item_images, self, self)
        right_panel = QWidget(); right_layout = QVBoxLayout(right_panel)
        playback_controls = ModernGroupBox("再生コントロール"); playback_layout = QHBoxLayout()
        self.start_button = ModernButton("再生", "success"); self.start_button.clicked.connect(self.rhythm_widget.start_playback)
        self.stop_button = ModernButton("停止", "danger"); self.stop_button.clicked.connect(self.rhythm_widget.stop_playback)
        self.reset_button = ModernButton("リセット", "warning"); self.reset_button.clicked.connect(lambda: self.new_score(ask_confirm=True))
        playback_layout.addWidget(self.start_button); playback_layout.addWidget(self.stop_button); playback_layout.addWidget(self.reset_button)
        playback_controls.setLayout(playback_layout); right_layout.addWidget(playback_controls)
        
        difficulty_controls = ModernGroupBox("難易度評価")
        difficulty_layout = QGridLayout()

        self.top_difficulty_label = ModernLabel("上段(L)難易度: -")
        self.top_difficulty_label.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        self.bottom_difficulty_label = ModernLabel("下段(R)難易度: -")
        self.bottom_difficulty_label.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        self.combined_difficulty_label = ModernLabel("総合難易度: -")
        self.combined_difficulty_label.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        self.combined_difficulty_label.setStyleSheet(f"color: {COLORS['success'].name()};")

        self.calculate_all_button = ModernButton("難易度を総合判定", "primary")
        self.calculate_all_button.clicked.connect(self.evaluate_all_difficulties)

        difficulty_layout.addWidget(self.top_difficulty_label, 0, 0, 1, 2)
        difficulty_layout.addWidget(self.bottom_difficulty_label, 1, 0, 1, 2)
        difficulty_layout.addWidget(self.combined_difficulty_label, 2, 0, 1, 2)
        difficulty_layout.addWidget(self.calculate_all_button, 3, 0, 1, 2)

        difficulty_controls.setLayout(difficulty_layout)
        right_layout.addWidget(difficulty_controls)

        ai_controls = ModernGroupBox("AI 楽譜生成")
        ai_layout = QGridLayout()

        ai_layout.addWidget(ModernLabel("対象:"), 0, 0)
        self.ai_target_track_combo = ModernComboBox()
        self.ai_target_track_combo.addItems(["上段 (top)", "下段 (bottom)"])
        ai_layout.addWidget(self.ai_target_track_combo, 0, 1)

        ai_layout.addWidget(ModernLabel("目標難易度:"), 1, 0)
        self.ai_target_difficulty_spinbox = QDoubleSpinBox() # DoubleSpinBoxに変更
        self.ai_target_difficulty_spinbox.setRange(1.0, 10.0)
        self.ai_target_difficulty_spinbox.setValue(5.0)
        self.ai_target_difficulty_spinbox.setSingleStep(0.1)
        self.ai_target_difficulty_spinbox.setStyleSheet(ModernSpinBox().styleSheet()) # スタイルを拝借
        ai_layout.addWidget(self.ai_target_difficulty_spinbox, 1, 1)

        self.ai_generate_button = ModernButton("AIで生成", "primary")
        self.ai_generate_button.clicked.connect(self.start_ai_generation)
        ai_layout.addWidget(self.ai_generate_button, 2, 0, 1, 2)

        self.ai_status_label = ModernLabel("待機中...", "muted")
        ai_layout.addWidget(self.ai_status_label, 3, 0, 1, 2)

        ai_controls.setLayout(ai_layout)
        right_layout.addWidget(ai_controls)

        general_settings = ModernGroupBox("全体設定"); general_layout = QVBoxLayout()
        self.metronome_checkbox = ModernCheckBox("メトロノーム (上段トラック基準)"); self.metronome_checkbox.toggled.connect(self.rhythm_widget.set_metronome_enabled)
        general_layout.addWidget(self.metronome_checkbox)
        mode_layout = QHBoxLayout(); self.mode_1_track_rb = ModernRadioButton("1トラック"); self.mode_2_track_rb = ModernRadioButton("2トラック")
        self.mode_group = QButtonGroup(self); self.mode_group.addButton(self.mode_1_track_rb); self.mode_group.addButton(self.mode_2_track_rb)
        self.mode_1_track_rb.toggled.connect(self.on_track_mode_changed); self.mode_2_track_rb.toggled.connect(self.on_track_mode_changed)
        mode_layout.addWidget(self.mode_1_track_rb); mode_layout.addWidget(self.mode_2_track_rb)
        general_layout.addLayout(mode_layout); general_settings.setLayout(general_layout); right_layout.addWidget(general_settings)
        self.top_track_settings = self._create_track_settings_group("上段 (L) トラック", "top")
        right_layout.addWidget(self.top_track_settings)
        self.sync_checkbox = ModernCheckBox("BPMを同期"); self.sync_checkbox.toggled.connect(self.on_sync_toggled)
        right_layout.addWidget(self.sync_checkbox)
        self.bottom_track_settings = self._create_track_settings_group("下段 (R) トラック", "bottom")
        right_layout.addWidget(self.bottom_track_settings)
        item_palette_content = ModernGroupBox("アイテムパレット")
        palette_layout = QGridLayout()

        self.dotted_checkbox = ModernCheckBox("付点")
        palette_layout.addWidget(self.dotted_checkbox, 0, 0, 1, 2)
        palette_layout.addWidget(ModernLabel("音符"), 1, 0)
        palette_layout.addWidget(ModernLabel("休符"), 1, 1)

        for i, (key, val) in enumerate(NOTE_DURATIONS.items()):
            btn = ModernButton(val['name'], "secondary")
            btn.clicked.connect(lambda c=False, k=key: self.add_item_to_score(k))
            palette_layout.addWidget(btn, i + 2, 0)

        for i, (key, val) in enumerate(REST_DURATIONS.items()):
            btn = ModernButton(val['name'], "secondary")
            btn.clicked.connect(lambda c=False, k=key: self.add_item_to_score(k))
            palette_layout.addWidget(btn, i + 2, 1)

        item_palette_content.setLayout(palette_layout)
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setStyleSheet("QScrollArea { border: none; }")
        scroll_area.setWidget(item_palette_content)
        right_layout.addWidget(scroll_area)
        right_layout.addStretch()
        main_layout.addWidget(left_panel, 1); main_layout.addWidget(self.rhythm_widget, 4); main_layout.addWidget(right_panel, 1)
        self.mode_2_track_rb.setChecked(True)
        self.new_score(ask_confirm=False)

    def _create_track_settings_group(self, title, track_name):
        group_box = ModernGroupBox(title); layout = QGridLayout()
        layout.addWidget(ModernLabel("編集:"), 0, 0); radio = ModernRadioButton(""); radio.setProperty("track_name", track_name); layout.addWidget(radio, 0, 1)
        if track_name == "top": self.top_track_rb = radio; self.track_group = QButtonGroup(self); self.track_group.addButton(radio); radio.setChecked(True)
        else: self.bottom_track_rb = radio; self.track_group.addButton(radio)
        layout.addWidget(ModernLabel("拍子:"), 1, 0); num = ModernSpinBox(); num.setRange(1, 16); den = ModernComboBox(); den.addItems(["2", "4", "8", "16"])
        ts_layout = QHBoxLayout(); ts_layout.addWidget(num); ts_layout.addWidget(ModernLabel("/")); ts_layout.addWidget(den); layout.addLayout(ts_layout, 1, 1)
        layout.addWidget(ModernLabel("BPM:"), 2, 0); bpm = ModernSpinBox(); bpm.setRange(10, 300); layout.addWidget(bpm, 2, 1)
        setattr(self, f"{track_name}_numerator_spinner", num); setattr(self, f"{track_name}_denominator_combo", den); setattr(self, f"{track_name}_bpm_spinner", bpm)
        num.valueChanged.connect(lambda v, tn=track_name: self.on_time_signature_changed(tn))
        den.currentTextChanged.connect(lambda t, tn=track_name: self.on_time_signature_changed(tn))
        bpm.valueChanged.connect(lambda v, tn=track_name: self.on_bpm_changed(tn, v))
        group_box.setLayout(layout); return group_box

    def play_note_sound(self):
        if self.note_sound: self.note_sound.play()

    def play_metronome_sound(self, is_accent):
        if is_accent and self.metronome_accent_click: self.metronome_accent_click.play()
        elif not is_accent and self.metronome_click: self.metronome_click.play()

    def recalculate_beats(self, track_name):
        if track_name not in self.rhythm_widget.score: return
        d = self.rhythm_widget.score[track_name]
        d['beats_per_measure'] = (d.get('numerator',4)/d.get('denominator',4))*4.0
        d['total_beats'] = d['beats_per_measure'] * NUM_MEASURES
        self.rhythm_widget.update()
        if self.sync_checkbox.isChecked(): self.sync_bpms()

    def on_bpm_changed(self, track_name, value):
        if track_name in self.rhythm_widget.score:
            self.rhythm_widget.score[track_name]['bpm'] = value
            self.rhythm_widget.update()
            if track_name == 'top' and self.sync_checkbox.isChecked(): self.sync_bpms()

    def on_time_signature_changed(self, track_name):
        if self._is_changing_ts: return
        track_data = self.rhythm_widget.score.get(track_name)
        if not track_data or not track_data.get('items'):
            num_spinner = getattr(self, f"{track_name}_numerator_spinner"); den_combo = getattr(self, f"{track_name}_denominator_combo")
            track_data['numerator'] = num_spinner.value(); track_data['denominator'] = int(den_combo.currentText())
            self.recalculate_beats(track_name); return
        reply = QMessageBox.question(self, '変更の確認', '拍子を変更すると、このトラックの楽譜はリセットされます。\nよろしいですか？', QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            track_data['items'] = []
            num_spinner = getattr(self, f"{track_name}_numerator_spinner"); den_combo = getattr(self, f"{track_name}_denominator_combo")
            track_data['numerator'] = num_spinner.value(); track_data['denominator'] = int(den_combo.currentText())
            self.recalculate_beats(track_name)
        else:
            self._is_changing_ts = True
            getattr(self, f"{track_name}_numerator_spinner").setValue(track_data['numerator'])
            getattr(self, f"{track_name}_denominator_combo").setCurrentText(str(track_data['denominator']))
            self._is_changing_ts = False

    def on_track_mode_changed(self, checked):
        if not checked: return
        is_2_track = self.mode_2_track_rb.isChecked()
        self.bottom_track_settings.setVisible(is_2_track); self.sync_checkbox.setVisible(is_2_track)
        
        self.bottom_difficulty_label.setVisible(is_2_track)
        self.combined_difficulty_label.setVisible(is_2_track)

        if any(d.get('items') for d in self.rhythm_widget.score.values()):
            reply = QMessageBox.question(self, '変更の確認', 'モードを変更すると楽譜全体がリセットされます。\nよろしいですか？', QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
            if reply == QMessageBox.StandardButton.No:
                self.mode_1_track_rb.blockSignals(True); self.mode_2_track_rb.blockSignals(True)
                if self.sender() is self.mode_1_track_rb: self.mode_2_track_rb.setChecked(True)
                else: self.mode_1_track_rb.setChecked(True)
                self.mode_1_track_rb.blockSignals(False); self.mode_2_track_rb.blockSignals(False)
                
                is_2_track_after_revert = self.mode_2_track_rb.isChecked()
                self.bottom_track_settings.setVisible(is_2_track_after_revert)
                self.sync_checkbox.setVisible(is_2_track_after_revert)
                self.bottom_difficulty_label.setVisible(is_2_track_after_revert)
                self.combined_difficulty_label.setVisible(is_2_track_after_revert)
                return
        self.new_score(ask_confirm=False)

    def add_item_to_score(self, item_type):
        active_button = self.track_group.checkedButton()
        if not active_button: QMessageBox.warning(self, "エラー", "編集トラックを選択してください。"); return
        target_name = active_button.property("track_name")
        if target_name not in self.rhythm_widget.score: return
        track = self.rhythm_widget.score[target_name]
        items = track['items']
        next_beat = max([i['beat'] + i['duration'] for i in items], default=0.0)
        duration = ALL_DURATIONS[item_type]['duration'] * (1.5 if self.dotted_checkbox.isChecked() else 1.0)
        if next_beat + 0.001 >= track['total_beats']: QMessageBox.warning(self,"エラー","トラックがいっぱいです。"); return
        if track['beats_per_measure'] > 0:
            measure_end = (int(next_beat / track['beats_per_measure']) + 1) * track['beats_per_measure']
            if next_beat + duration > measure_end + 0.001: QMessageBox.warning(self, "エラー", "小節をまたげません。"); return
        new_item = {'beat':next_beat, 'type':item_type, 'duration':duration, 'class':'note' if item_type in NOTE_DURATIONS else 'rest', 'dotted':self.dotted_checkbox.isChecked()}
        items.append(new_item); items.sort(key=lambda x: x['beat']); self.rhythm_widget.update()

    def get_elapsed_time(self): return pygame.time.get_ticks() - self.app_start_time

    # --- ▼▼▼ 修正点 2 (self.score_directory を参照し、ディレクトリ作成機能を追加) ▼▼▼ ---
    def refresh_file_list(self):
        self.file_list_widget.clear()
        score_dir = self.score_directory # __init__ で設定したパス
        try:
            if not os.path.exists(score_dir):
                print(f"警告: 楽譜ディレクトリ '{score_dir}' が見つかりません。")
                os.makedirs(score_dir) # 存在しない場合は作成する
                print(f"'{score_dir}' を作成しました。")
            
            for f in sorted(os.listdir(score_dir)):
                if f.endswith(".json"): self.file_list_widget.addItem(f)
        except FileNotFoundError: 
            print(f"楽譜ディレクトリ '{score_dir}' が見つかりません。")
    # --- ▲▲▲ 修正点 2 ▲▲▲ ---

    def new_score(self, ask_confirm=True):
        if ask_confirm and any(d.get('items') for d in self.rhythm_widget.score.values()):
            if QMessageBox.question(self,'確認','楽譜を破棄しますか？',QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No,QMessageBox.StandardButton.No) == QMessageBox.StandardButton.No: return
        is_2_track = self.mode_2_track_rb.isChecked()
        self.bottom_track_settings.setVisible(is_2_track); self.sync_checkbox.setVisible(is_2_track)
        self.top_track_settings.setTitle("上段 (L) トラック" if is_2_track else "トラック")
        
        self.bottom_difficulty_label.setVisible(is_2_track)
        self.combined_difficulty_label.setVisible(is_2_track)

        def create_track_data(bpm=120, num=4, den=4):
            data = {'bpm': bpm, 'numerator': num, 'denominator': den, 'items': []}
            data['beats_per_measure'] = (data['numerator']/data['denominator'])*4.0
            data['total_beats'] = data['beats_per_measure']*NUM_MEASURES
            return data
        score = {'top': create_track_data()}
        if is_2_track: score['bottom'] = create_track_data()
        self.rhythm_widget.set_data(score); self._update_ui_from_score_data()
        self.current_filepath = None; self.setWindowTitle("新規の楽譜 - リズムエディター")
        
        self.top_difficulty_label.setText("上段(L)難易度: -")
        self.bottom_difficulty_label.setText("下段(R)難易度: -")
        self.combined_difficulty_label.setText("総合難易度: -")

    def open_score(self):
        fp, _ = QFileDialog.getOpenFileName(self, "楽譜を開く", "", "JSON (*.json)")
        if fp: self.load_score(fp)

    # --- ▼▼▼ 修正点 3 (self.score_directory を参照) ▼▼▼ ---
    def load_from_list(self, item):
        full_path = os.path.join(self.score_directory, item.text())
        self.load_score(full_path)
    # --- ▲▲▲ 修正点 3 ▲▲▲ ---

    def _update_ui_from_score_data(self):
        self._is_changing_ts = True
        score = self.rhythm_widget.score
        is_2_track = 'bottom' in score
        self.mode_2_track_rb.setChecked(is_2_track); self.mode_1_track_rb.setChecked(not is_2_track)
        self.bottom_track_settings.setVisible(is_2_track); self.sync_checkbox.setVisible(is_2_track)
        self.top_track_settings.setTitle("上段 (L) トラック" if is_2_track else "トラック")

        self.bottom_difficulty_label.setVisible(is_2_track)
        self.combined_difficulty_label.setVisible(is_2_track)

        for name in ['top', 'bottom']:
            if name in score:
                getattr(self,f"{name}_bpm_spinner").setValue(score[name].get('bpm',120))
                getattr(self,f"{name}_numerator_spinner").setValue(score[name].get('numerator',4))
                getattr(self,f"{name}_denominator_combo").setCurrentText(str(score[name].get('denominator',4)))
        self._is_changing_ts = False
        
        self.top_difficulty_label.setText("上段(L)難易度: -")
        self.bottom_difficulty_label.setText("下段(R)難易度: -")
        self.combined_difficulty_label.setText("総合難易度: -")

    def load_score(self, filepath):
        try:
            with open(filepath, 'r', encoding='utf-8') as f: data = json.load(f)
            self.rhythm_widget.set_data(data)
            self._update_ui_from_score_data()
            for track_name in self.rhythm_widget.score: self.recalculate_beats(track_name)
            self.current_filepath = filepath
            self.setWindowTitle(f"{os.path.basename(filepath)} - リズムエディター")
        except Exception as e:
            QMessageBox.critical(self, "エラー", f"ファイル読み込み失敗:\n{e}")

    def save_score(self):
        if not self.current_filepath: self.save_score_as()
        else: self.perform_save(self.current_filepath)

    # --- ▼▼▼ 修正点 4 (self.score_directory を参照) ▼▼▼ ---
    def save_score_as(self):
        default_path = self.current_filepath or os.path.join(self.score_directory, "無題.json")
        fp, _ = QFileDialog.getSaveFileName(self, "名前を付けて保存", default_path, "JSON (*.json)")
        if fp: self.perform_save(fp)
    # --- ▲▲▲ 修正点 4 ▲▲▲ ---

    def perform_save(self, filepath):
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(self.rhythm_widget.score, f, indent=4, ensure_ascii=False)
            self.current_filepath = filepath; self.setWindowTitle(f"{os.path.basename(filepath)} - リズムエディター")
            self.refresh_file_list()
        except Exception as e:
            QMessageBox.critical(self, "エラー", f"ファイル保存失敗:\n{e}")

    def on_sync_toggled(self, checked):
        self.bottom_bpm_spinner.setEnabled(not checked)
        if checked: self.sync_bpms()
        self.rhythm_widget.update()

    def sync_bpms(self):
        if 'top' in self.rhythm_widget.score and 'bottom' in self.rhythm_widget.score:
            top = self.rhythm_widget.score['top']; bottom = self.rhythm_widget.score['bottom']
            if top['total_beats'] > 0 and bottom['total_beats'] > 0:
                new_bottom_bpm = top['bpm'] * (bottom['total_beats'] / top['total_beats'])
                self.bottom_bpm_spinner.setValue(int(round(new_bottom_bpm)))
                

    def _get_2_measure_average_score(self, track_name):
        """
        指定されたトラックの2小節分の平均難易度スコアを計算します。
        (内部で _calculate_single_track_difficulty を2回呼び出します)
        """
        if track_name not in self.rhythm_widget.score:
            return 0.0
            
        track_data = self.rhythm_widget.score[track_name]
        
        beats_per_measure = track_data.get('beats_per_measure', 4.0)
        if beats_per_measure == 0:
            return 0.0 # ゼロ除算を回避

        all_items = track_data.get('items', [])
        
        # 1. 1小節目と2小節目のアイテムに分割
        items_m1 = [item for item in all_items if item['beat'] < beats_per_measure]
        items_m2_original = [item for item in all_items if item['beat'] >= beats_per_measure]
        
        # 2. 2小節目のアイテムの 'beat' を 0 始まりにシフトする
        items_m2_shifted = []
        for item in items_m2_original:
            shifted_item = item.copy()
            shifted_item['beat'] -= beats_per_measure
            items_m2_shifted.append(shifted_item)

        # 3. 採点
        # _calculate_single_track_difficulty が参照できるように、
        # track_data の items を一時的に書き換える
        
        original_items = track_data['items'] # バックアップ
        
        try:
            # 4. 1小節目を採点
            track_data['items'] = items_m1
            score_m1 = self._calculate_single_track_difficulty(track_name)

            # 5. 2小節目を採点
            track_data['items'] = items_m2_shifted
            score_m2 = self._calculate_single_track_difficulty(track_name) if items_m2_shifted else 0.0
        
        finally:
            # 6. 必ず元のアイテムリストに戻す
            track_data['items'] = original_items

        # 7. 平均スコアを計算 (2小節とも空の場合は 0.0)
        average_score = (score_m1 + score_m2) / 2.0 if (items_m1 or items_m2_shifted) else 0.0
        
        return average_score
                
    # ### ▼▼▼ 変更・追加箇所 ▼▼▼ (難易度評価ロジックを全面的に更新)
    
    def evaluate_all_difficulties(self):
        # --- ▼▼▼ 変更 ▼▼▼ ---
        # 1小節だけではなく、2小節の平均点を計算する
        d_top = self._get_2_measure_average_score('top')
        self.top_difficulty_label.setText(f"上段(L)難易度: {d_top:.2f}")

        if self.mode_2_track_rb.isChecked():
            d_bottom = self._get_2_measure_average_score('bottom')
            self.bottom_difficulty_label.setText(f"下段(R)難易度: {d_bottom:.2f}")
            # --- ▲▲▲ 変更 ▲▲▲ ---

            track_top = self.rhythm_widget.score['top']
            track_bottom = self.rhythm_widget.score['bottom']
            
            base_difficulty = (d_top + d_bottom) / 2.0
            
            polymeter_penalty = 0.0
            if (track_top.get('numerator') != track_bottom.get('numerator') or
                track_top.get('denominator') != track_bottom.get('denominator')):
                polymeter_penalty = 2.5
            
            # --- 新しい総合難易度ロジック ---
            interaction_modifier = 0.0
            profile_top = self._get_rhythm_profile('top')
            profile_bottom = self._get_rhythm_profile('bottom')

            # 拍子が異なり、小節の長さが違う場合は比較しない
            if len(profile_top) == len(profile_bottom) and profile_top:
                interaction_score = 0.0
                for i in range(len(profile_top)):
                    slot_top = profile_top[i]
                    slot_bottom = profile_bottom[i]

                    # 両方S(tart) -> 最も簡単
                    if slot_top == 'S' and slot_bottom == 'S':
                        interaction_score += 2
                    # 両方同じ状態 (H-H or ---) -> 安定
                    elif slot_top == slot_bottom:
                        interaction_score += 1
                    # SとH -> 抑えながら叩く
                    elif (slot_top == 'S' and slot_bottom == 'H') or (slot_top == 'H' and slot_bottom == 'S'):
                        interaction_score += 0
                    # Sと- -> ポリリズム
                    elif (slot_top == 'S' and slot_bottom == '-') or (slot_top == '-' and slot_bottom == 'S'):
                        interaction_score -= 2
                    # Hと- -> 抑えながら休む
                    elif (slot_top == 'H' and slot_bottom == '-') or (slot_top == '-' and slot_bottom == 'H'):
                        interaction_score -= 1
                
                max_score = len(profile_top) * 2.0
                normalized_score = interaction_score / max_score if max_score > 0 else 0
                # -2.0 (簡単) から +2.5 (難しい) の補正値に変換
                interaction_modifier = (1.0 - normalized_score) * 2.25 - 2.0

            combined_difficulty = base_difficulty + interaction_modifier + polymeter_penalty
            final_score = max(1.0, min(10.0, combined_difficulty))
            self.combined_difficulty_label.setText(f"総合難易度: {final_score:.2f}")
        else:
            self.bottom_difficulty_label.setText("下段(R)難易度: -")
            self.combined_difficulty_label.setText("総合難易度: -")

    def _get_rhythm_profile(self, track_name):
        """小節のリズム状態を16分音符単位の文字列で返すヘルパー関数"""
        track_data = self.rhythm_widget.score[track_name]
        beats_per_measure = track_data.get('beats_per_measure', 4.0)
        
        # 16分音符を基準としたスロット数を計算
        num_slots = int(beats_per_measure / 0.25)
        if num_slots == 0: return []

        profile = ['-'] * num_slots
        
        measure_items = [item for item in track_data.get('items', []) if item['beat'] < beats_per_measure]
        
        for item in measure_items:
            start_slot = int(item['beat'] / 0.25)
            duration_slots = int(item['duration'] / 0.25)
            
            if start_slot < num_slots and item['class'] == 'note':
                profile[start_slot] = 'S' # Start
                for i in range(1, duration_slots):
                    if start_slot + i < num_slots:
                        profile[start_slot + i] = 'H' # Hold
        return profile

    def _calculate_single_track_difficulty(self, track_name):
        track_data = self.rhythm_widget.score[track_name]
        beats_per_measure = track_data.get('beats_per_measure', 4.0)
        measure_items = [item for item in track_data.get('items', []) if item['beat'] < beats_per_measure]
        bpm = track_data.get('bpm', 120)

        if not measure_items: return 0.0
            
        W1_REST, W2_OFF_BEAT = 0.15, 1.5
        DIFFICULTY_VALUES = {
            2.0: 2, 3.0: 2, 4.0: 2, 6.0: 2,
            1.0: 4, 1.5: 5, 0.5: 6, 0.75: 6,
            0.25: 8, 0.375: 8,
        }
        
        notes = [item for item in measure_items if item['class'] == 'note']
        if not notes: return 1.0
            
        note_durations = [n['duration'] for n in notes]
        duration_counts = Counter(note_durations)
        
        most_common = duration_counts.most_common(1)[0]
        L_list = [d for d, c in duration_counts.items() if c == most_common[1]]
        
        Dp = sum(DIFFICULTY_VALUES.get(d, 9) for d in L_list) / len(L_list)
        N = sum(c for d, c in duration_counts.items() if d not in L_list)
        
        D1 = Dp
        if N > 0:
            Amax, Smax = (10 - Dp) / N, (Dp - 1) / N
            A, S = 0.0, 0.0
            for dur, count in duration_counts.items():
                if dur in L_list: continue
                Dc_curr = DIFFICULTY_VALUES.get(dur, 9)
                if Dc_curr > Dp: A += ((Dc_curr - Dp) / Dp) * Amax * count
                else: S += ((Dp - Dc_curr) / Dp) * Smax * count
            D1 += (A - S)

        rest_penalty = 0.0
        rests = sorted([i for i in measure_items if i['class'] == 'rest'], key=lambda x: x['duration'])
        if rests:
            shortest_rest = rests[0]
            is_adjacent = any(
                abs(n['beat'] - (shortest_rest['beat'] + shortest_rest['duration'])) < 0.01 or \
                abs((n['beat'] + n['duration']) - shortest_rest['beat']) < 0.01
                for n in notes
            )
            if is_adjacent:
                rest_Dc = DIFFICULTY_VALUES.get(shortest_rest['duration'], 9)
                rest_penalty = W1_REST * rest_Dc
        
        off_beat_penalty = 0.0
        beat_unit = 4.0 / track_data.get('denominator', 4)
        has_off_beat = False
        sorted_notes = sorted(notes, key=lambda x: x['beat'])

        for i, note in enumerate(sorted_notes):
            if note['beat'] % beat_unit > 0.01:
                if i > 0:
                    prev_note = sorted_notes[i-1]
                    if abs(prev_note['beat'] + prev_note['duration'] - note['beat']) < 0.01:
                       if abs((note['duration'] + prev_note['duration']) - beat_unit) < 0.01:
                           continue 
                has_off_beat = True
                break
        
        if has_off_beat:
            off_beat_penalty = W2_OFF_BEAT
            
        base_score = D1 + rest_penalty + off_beat_penalty
        
        bpm_modifier = 1.0 + (bpm - 120) * 0.005
        
        final_score = base_score * bpm_modifier
        return max(1.0, min(10.0, final_score))

    def closeEvent(self, event):
        """ウィンドウを閉じる際のイベント"""
        if self.generation_worker and self.generation_worker.isRunning():
            reply = QMessageBox.question(
                self, "確認",
                "AIによる生成が実行中です。\n強制終了しますか？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            
            if reply == QMessageBox.StandardButton.Yes:
                # スレッドの終了を待つ
                self.generation_worker.terminate()
                self.generation_worker.wait(3000)  # 最大3秒待機
                event.accept()
            else:
                event.ignore()
        else:
            event.accept()


def run_editor():
    app = QApplication.instance() or QApplication(sys.argv)
    window = MainWindow()

    try:
        screen = QApplication.screenAt(QCursor.pos())
        if not screen:
            screen = QApplication.primaryScreen()
        center_point = screen.availableGeometry().center()
        window.move(center_point.x() - window.width() / 2,
                    center_point.y() - window.height() / 2)
    except Exception as e:
        print(f"ウィンドウの中央配置中にエラーが発生しました: {e}")
        window.move(100, 100)

    window.showMaximized()
    return app.exec()

if __name__ == '__main__':
    run_editor()