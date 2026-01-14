import sys
import os
import json
import pygame
from collections import Counter
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                               QPushButton, QListWidget, QMenuBar, QFileDialog, QMessageBox,
                               QLabel, QSpinBox, QRadioButton, QGridLayout, QButtonGroup, QComboBox, QCheckBox, QGroupBox, QScrollArea)
from PySide6.QtGui import (QPainter, QColor, QPen, QAction, QFont, QPixmap, QIcon, QLinearGradient, QCursor)
from PySide6.QtCore import Qt, QTimer, QRectF, QPointF

# numpy（サウンド生成用）が利用可能かチェック
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
        self.setFont(QFont("Segoe UI", 10))
        self.setStyleSheet(f"""
            QCheckBox {{ color: {COLORS['text_primary'].name()}; spacing: 8px; }}
            QCheckBox::indicator {{
                width: 16px; height: 16px;
                border: 2px solid {COLORS['border'].name()};
                border-radius: 4px;
                background-color: {COLORS['surface_light'].name()};
            }}
            QCheckBox::indicator:checked {{
                background-color: {COLORS['primary'].name()};
                border-color: {COLORS['primary'].name()};
                image: url({resource_path('images/check.svg')});
            }}""")

class ModernRadioButton(QRadioButton):
    def __init__(self, text, parent=None):
        super().__init__(text, parent)
        self.setFont(QFont("Segoe UI", 10))
        self.setStyleSheet(f"""
            QRadioButton {{ color: {COLORS['text_primary'].name()}; spacing: 8px; }}
            QRadioButton::indicator {{
                width: 16px; height: 16px;
                border: 2px solid {COLORS['border'].name()};
                border-radius: 9px;
                background-color: {COLORS['surface_light'].name()};
            }}
            QRadioButton::indicator:checked {{
                background-color: {COLORS['primary'].name()};
                border: 3px solid {COLORS['surface_light'].name()};
            }}""")

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
        gradient = QLinearGradient(0, 0, 0, self.height())
        gradient.setColorAt(0, COLORS['background'])
        gradient.setColorAt(1, COLORS['surface'])
        painter.fillRect(self.rect(), gradient)
        start_x = self.margin
        drawable_width = self.width() - (self.margin * 2)
        if drawable_width <= 0 or not self.score: return
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
            painter.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold)); painter.setPen(COLORS['primary'])
            label = "L" if staff_y < self.height() / 2 else "R"
            painter.drawText(QRectF(5, staff_y - 28, 40, 25), Qt.AlignmentFlag.AlignCenter, label)
        painter.setFont(QFont("Segoe UI", 10)); painter.setPen(COLORS['text_secondary'])
        ts_text = f"{track_data.get('numerator', 4)}\n─\n{denominator}"
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
            if item.get('is_lit', False):
                glow_color = COLORS['note_glow']
                painter.setBrush(glow_color)
                painter.setPen(Qt.PenStyle.NoPen)
                painter.drawRoundedRect(item_rect.adjusted(-2, -2, 2, 2), 8, 8)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            pen_width = 2
            if item.get('is_lit', False):
                pen_width = 4
            pen = QPen(COLORS['primary'], pen_width)
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
        self.script_directory = os.path.dirname(os.path.abspath(__file__))
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
        layout.addWidget(ModernLabel("BPM:"), 2, 0); bpm = ModernSpinBox(); bpm.setRange(30, 300); layout.addWidget(bpm, 2, 1)
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

    def refresh_file_list(self):
        self.file_list_widget.clear()
        script_dir = os.path.dirname(os.path.abspath(__file__))
        try:
            for f in sorted(os.listdir(script_dir)):
                if f.endswith(".json"): self.file_list_widget.addItem(f)
        except FileNotFoundError: print("カレントディレクトリが見つかりません。")

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

    def load_from_list(self, item):
        full_path = os.path.join(self.script_directory, item.text())
        self.load_score(full_path)

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

    def save_score_as(self):
        fp, _ = QFileDialog.getSaveFileName(self, "名前を付けて保存", self.current_filepath or "無題.json", "JSON (*.json)")
        if fp: self.perform_save(fp)

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
                
    # ### ▼▼▼ 変更・追加箇所 ▼▼▼ (難易度評価ロジックを全面的に更新)
    
    def evaluate_all_difficulties(self):
        d_top = self._calculate_single_track_difficulty('top')
        self.top_difficulty_label.setText(f"上段(L)難易度: {d_top:.2f}")

        if self.mode_2_track_rb.isChecked():
            d_bottom = self._calculate_single_track_difficulty('bottom')
            self.bottom_difficulty_label.setText(f"下段(R)難易度: {d_bottom:.2f}")

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

    def closeEvent(self, event): event.accept()


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

    window.show()
    return app.exec()

if __name__ == '__main__':
    run_editor()