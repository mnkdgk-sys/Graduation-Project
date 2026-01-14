import sys
import os
import json
import pygame
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                             QPushButton, QListWidget, QMenuBar, QFileDialog, QMessageBox,
                             QLabel, QSpinBox, QRadioButton, QGridLayout, QButtonGroup)
from PySide6.QtGui import QPainter, QColor, QPen, QAction, QFont, QPixmap, QIcon
from PySide6.QtCore import Qt, QTimer, QRectF

# --- 【重要】ファイルパス解決用の関数 ---
def resource_path(relative_path):
    """ アプリとして固めた後でも、画像などのファイルを見つけられるようにする """
    try:
        # PyInstallerが作成した一時フォルダのパスを取得
        base_path = sys._MEIPASS
    except Exception:
        # スクリプトとして実行している場合は、スクリプトと同じディレクトリ
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

# --- (定数定義などは変更なし) ---
WINDOW_WIDTH, WINDOW_HEIGHT = 1600, 600
C_BLACK = QColor(0, 0, 0); C_GRAY = QColor(150, 150, 150); C_LIGHT_GRAY = QColor(220, 220, 220)
C_RED = QColor(255, 0, 0); C_NOTE_BG = QColor(230, 230, 250, 200); C_REST_BG = QColor(180, 180, 180, 150)
C_LIT_GLOW = QColor(255, 255, 0, 150)
BEATS_PER_MEASURE = 4; NUM_MEASURES = 2; TOTAL_BEATS = BEATS_PER_MEASURE * NUM_MEASURES
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
    'whole': 'whole_note.PNG', 'half': 'half_note.PNG', 'quarter': 'quarter_note.PNG',
    'eighth': 'eighth_note.PNG', 'sixteenth':'sixteenth_note.PNG',
}
REST_IMAGE_FILES = {
    'quarter_rest': 'quarter_rest.PNG', 'eighth_rest': 'eighth_rest.PNG', 'sixteenth_rest': 'sixteenth_rest.PNG',
}
LIT_DURATION = 150

# --- (RhythmWidget, Buttonクラスは変更なし) ---
class RhythmWidget(QWidget):
    # ... (内容は前回のコードと同じ) ...
    def __init__(self, item_images, parent=None):
        super().__init__(parent); self.setMinimumHeight(200); self.item_images = item_images; self.score = {'top': [], 'bottom': []}
        self.bpm = 120.0; self.is_playing = False; self.playback_start_time = 0; self.playback_timer = QTimer(self)
        self.playback_timer.timeout.connect(self.update_playback); self.current_beat = 0; self.margin = 20
    def update_playback(self):
        ms_per_beat = 60000.0 / self.bpm; total_duration_ms = TOTAL_BEATS * ms_per_beat
        if total_duration_ms == 0: total_duration_ms = 1
        time_in_loop = (self.parent().parent().get_elapsed_time() - self.playback_start_time) % total_duration_ms
        self.current_beat = (time_in_loop / total_duration_ms) * TOTAL_BEATS
        if self.current_beat < 0.2:
            for track in self.score.values():
                for item in track: item['played_in_loop'] = False
        for track in self.score.values():
            for item in track:
                if not item.get('played_in_loop', False) and self.current_beat >= item['beat']:
                    if item.get('class') == 'note':
                        item['lit_start_time'] = self.parent().parent().get_elapsed_time(); self.parent().parent().play_click_sound()
                    item['played_in_loop'] = True
        self.update()
    def set_data(self, score_data, bpm): self.score = score_data; self.bpm = bpm; self.update()
    def start_playback(self):
        if not self.is_playing:
            self.is_playing = True; self.playback_start_time = self.parent().parent().get_elapsed_time(); self.playback_timer.start(16)
            for track in self.score.values():
                for item in track: item['played_in_loop'] = False
    def stop_playback(self):
        if self.is_playing: self.is_playing = False; self.playback_timer.stop(); self.update()
    def paintEvent(self, event):
        painter = QPainter(self); painter.setRenderHint(QPainter.Antialiasing); painter.fillRect(self.rect(), Qt.white)
        staff_y_top = self.height() * 0.35; staff_y_bottom = self.height() * 0.65
        start_x = self.margin; drawable_width = self.width() - (self.margin * 2)
        current_time = self.parent().parent().get_elapsed_time()
        for track in self.score.values():
            for item in track:
                if item.get('class') == 'note' and 'lit_start_time' in item and (current_time - item['lit_start_time']) < LIT_DURATION:
                    item['is_lit'] = True
                else: item['is_lit'] = False
        for staff_y in [staff_y_top, staff_y_bottom]:
            painter.setPen(QPen(C_BLACK, 2)); painter.drawLine(start_x, staff_y, start_x + drawable_width, staff_y)
            for i in range(TOTAL_BEATS * 4 + 1):
                x = start_x + (i / (TOTAL_BEATS * 4)) * drawable_width
                painter.setPen(QPen(C_GRAY if i % 4 == 0 else C_LIGHT_GRAY, 1)); painter.drawLine(x, staff_y - 30, x, staff_y + 30)
            for i in range(1, NUM_MEASURES):
                x = start_x + (i * BEATS_PER_MEASURE / TOTAL_BEATS) * drawable_width
                painter.setPen(QPen(C_BLACK, 2)); painter.drawLine(x, staff_y - 30, x, staff_y + 30)
        for track_name, staff_y in [('top', staff_y_top), ('bottom', staff_y_bottom)]:
            for item in self.score.get(track_name, []): self.draw_item(painter, item, staff_y)
        if self.is_playing:
            ms_per_beat = 60000.0 / self.bpm; total_duration_ms = TOTAL_BEATS * ms_per_beat
            if total_duration_ms == 0: total_duration_ms = 1
            time_in_loop = (self.parent().parent().get_elapsed_time() - self.playback_start_time) % total_duration_ms
            progress = time_in_loop / total_duration_ms; cursor_x = start_x + progress * drawable_width
            painter.setPen(QPen(C_RED, 2)); painter.drawLine(cursor_x, 50, cursor_x, self.height() - 50)
    def draw_item(self, painter, item, staff_y):
        start_x = self.margin; drawable_width = self.width() - (self.margin * 2)
        x = start_x + (item['beat'] / TOTAL_BEATS) * drawable_width; width = (item['duration'] / TOTAL_BEATS) * drawable_width
        item_rect = QRectF(x, staff_y - 25, width, 50)
        if item.get('class') == 'note':
            if item.get('is_lit', False): painter.fillRect(item_rect, C_LIT_GLOW)
            painter.setPen(C_GRAY); painter.drawRect(item_rect)
        else: painter.fillRect(item_rect, C_REST_BG)
        image_to_draw = self.item_images.get(item['type'])
        if image_to_draw:
            img_rect = QRectF(image_to_draw.rect()); img_rect.moveCenter(item_rect.center())
            painter.drawPixmap(img_rect.topLeft(), image_to_draw)
        else:
            painter.setPen(C_BLACK); painter.setFont(QFont("sans-serif", 10)); text = ALL_DURATIONS[item['type']]['name']; painter.drawText(item_rect, Qt.AlignCenter, text)
    def mousePressEvent(self, event):
        if event.button() == Qt.RightButton and not self.is_playing:
            start_x = self.margin; drawable_width = self.width() - (self.margin * 2)
            target_y = event.position().y(); track_name = 'top' if target_y < self.height() / 2 else 'bottom'
            staff_y = self.height() * 0.35 if track_name == 'top' else self.height() * 0.65
            item_to_delete = None
            for item in self.score[track_name]:
                x = start_x + (item['beat'] / TOTAL_BEATS) * drawable_width; width = (item['duration'] / TOTAL_BEATS) * drawable_width
                item_rect = QRectF(x, staff_y - 25, width, 50)
                if item_rect.contains(event.position()): item_to_delete = item; break
            if item_to_delete: self.score[track_name].remove(item_to_delete); self.update()

class Button(QPushButton):
    def __init__(self, text, parent=None):
        super().__init__(text, parent)

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("高機能リズムエディター"); self.setGeometry(100, 100, 1600, 600)
        self.setWindowIcon(QIcon(resource_path("icon.icns"))) # 【修正】アイコンパス
        self.current_filepath = None; self.active_track = 'top'
        self.app_start_time = pygame.time.get_ticks()

        # 【修正】ファイルパスを resource_path で囲む
        try: self.click_sound = pygame.mixer.Sound(resource_path("click.wav"))
        except (FileNotFoundError, pygame.error): self.click_sound = None

        self.item_images = {}
        all_image_files = {**NOTE_IMAGE_FILES, **REST_IMAGE_FILES}
        IMAGE_MAX_HEIGHT = 40
        for item_type, filename in all_image_files.items():
            path = resource_path(filename) # 【修正】
            if os.path.exists(path):
                pixmap = QPixmap(path)
                if not pixmap.isNull():
                    pixmap = pixmap.scaledToHeight(IMAGE_MAX_HEIGHT, Qt.SmoothTransformation)
                    self.item_images[item_type] = pixmap
            else: print(f"警告: 画像ファイル '{filename}' が見つかりません。")

        self.setup_ui()
        self.refresh_file_list()

    def setup_ui(self):
        # ... (内容はほぼ変更なし、フォントのパス指定を修正) ...
        try:
            font = QFont(resource_path("NotoSansJP-Regular.ttf"), 12)
            small_font = QFont(resource_path("NotoSansJP-Regular.ttf"), 9)
        except:
            font = QFont("sans-serif", 12)
            small_font = QFont("sans-serif", 9)
        
        # (以降のUIセットアップは変更なし)
        menu_bar = self.menuBar(); file_menu = menu_bar.addMenu("ファイル")
        new_action = QAction("新規作成", self); new_action.triggered.connect(self.new_score)
        open_action = QAction("開く...", self); open_action.triggered.connect(self.open_score)
        save_action = QAction("保存", self); save_action.triggered.connect(self.save_score)
        save_as_action = QAction("名前を付けて保存...", self); save_as_action.triggered.connect(self.save_score_as)
        exit_action = QAction("終了", self); exit_action.triggered.connect(self.close)
        file_menu.addActions([new_action, open_action, save_action, save_as_action]); file_menu.addSeparator(); file_menu.addAction(exit_action)
        main_widget = QWidget(); main_layout = QHBoxLayout(main_widget); self.setCentralWidget(main_widget)
        left_panel = QWidget(); left_layout = QVBoxLayout(left_panel)
        self.file_list_widget = QListWidget(); self.file_list_widget.itemDoubleClicked.connect(self.load_from_list)
        left_layout.addWidget(self.file_list_widget)
        self.rhythm_widget = RhythmWidget(self.item_images, self)
        right_panel = QWidget(); right_layout = QVBoxLayout(right_panel)
        playback_layout = QHBoxLayout()
        self.start_button = Button("再生"); self.start_button.clicked.connect(self.rhythm_widget.start_playback)
        self.stop_button = Button("停止"); self.stop_button.clicked.connect(self.rhythm_widget.stop_playback)
        self.reset_button = Button("リセット"); self.reset_button.clicked.connect(self.new_score)
        playback_layout.addWidget(self.start_button); playback_layout.addWidget(self.stop_button); playback_layout.addWidget(self.reset_button)
        right_layout.addLayout(playback_layout)
        bpm_layout = QHBoxLayout(); bpm_layout.addWidget(QLabel("BPM:"))
        self.bpm_spinner = QSpinBox(); self.bpm_spinner.setRange(30, 300); self.bpm_spinner.setValue(120)
        self.bpm_spinner.valueChanged.connect(self.update_bpm)
        bpm_layout.addWidget(self.bpm_spinner); right_layout.addLayout(bpm_layout)
        track_layout = QHBoxLayout(); track_layout.addWidget(QLabel("編集トラック:"))
        self.track_group = QButtonGroup(self)
        self.top_track_rb = QRadioButton("上段"); self.top_track_rb.setChecked(True)
        self.bottom_track_rb = QRadioButton("下段")
        self.track_group.addButton(self.top_track_rb); self.track_group.addButton(self.bottom_track_rb)
        self.top_track_rb.toggled.connect(self.set_active_track)
        track_layout.addWidget(self.top_track_rb); track_layout.addWidget(self.bottom_track_rb); right_layout.addLayout(track_layout)
        palette_layout = QGridLayout(); palette_layout.addWidget(QLabel("音符"), 0, 0); palette_layout.addWidget(QLabel("休符"), 0, 1)
        for i, (key, val) in enumerate(NOTE_DURATIONS.items()):
            btn = Button(val['name']); btn.clicked.connect(lambda checked, k=key: self.add_item_to_score(k))
            palette_layout.addWidget(btn, i + 1, 0)
        for i, (key, val) in enumerate(REST_DURATIONS.items()):
            btn = Button(val['name']); btn.clicked.connect(lambda checked, k=key: self.add_item_to_score(k))
            palette_layout.addWidget(btn, i + 1, 1)
        right_layout.addLayout(palette_layout); right_layout.addStretch()
        main_layout.addWidget(left_panel, 2); main_layout.addWidget(self.rhythm_widget, 10); main_layout.addWidget(right_panel, 2)
    
    # (以降のメソッドは変更なし)
    def play_click_sound(self):
        if self.click_sound: self.click_sound.play()
    def update_bpm(self, value): self.rhythm_widget.bpm = value
    def set_active_track(self): self.active_track = 'top' if self.top_track_rb.isChecked() else 'bottom'
    def add_item_to_score(self, item_type):
        target_track = self.rhythm_widget.score[self.active_track]
        next_beat = 0.0
        if target_track: last_item = target_track[-1]; next_beat = last_item['beat'] + last_item['duration']
        item_info = ALL_DURATIONS[item_type]; new_item_duration = item_info['duration']
        if next_beat + new_item_duration <= TOTAL_BEATS:
            item_class = 'note' if item_type in NOTE_DURATIONS else 'rest'
            new_item = {'beat': next_beat, 'type': item_type, 'duration': new_item_duration, 'class': item_class}
            target_track.append(new_item); target_track.sort(key=lambda x: x['beat'])
            self.rhythm_widget.update()
        else: QMessageBox.warning(self, "エラー", "小節の容量を超えてしまうため、配置できません。")
    def get_elapsed_time(self): return pygame.time.get_ticks() - self.app_start_time
    def refresh_file_list(self):
        self.file_list_widget.clear()
        for filename in os.listdir("."):
            if filename.endswith(".json"): self.file_list_widget.addItem(filename)
    def new_score(self):
        reply = QMessageBox.question(self, '確認', '現在の楽譜を破棄しますか？', QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            self.rhythm_widget.set_data({'top': [], 'bottom': []}, 120.0); self.bpm_spinner.setValue(120)
            self.current_filepath = None; self.setWindowTitle("新規の楽譜 - 高機能リズムエディター")
    def open_score(self):
        filepath, _ = QFileDialog.getOpenFileName(self, "楽譜ファイルを開く", "", "JSON Files (*.json)")
        if filepath: self.load_score(filepath)
    def load_from_list(self, item): self.load_score(item.text())
    def load_score(self, filepath):
        try:
            with open(filepath, 'r', encoding='utf-8') as f: data = json.load(f)
            if "bpm" in data and "score" in data:
                self.rhythm_widget.set_data(data["score"], data["bpm"]); self.bpm_spinner.setValue(data["bpm"])
                self.current_filepath = filepath; self.setWindowTitle(f"{os.path.basename(filepath)} - 高機能リズムエディター")
            else: QMessageBox.warning(self, "エラー", "無効な楽譜ファイルです。")
        except Exception as e: QMessageBox.critical(self, "エラー", f"ファイルの読み込みに失敗しました:\n{e}")
    def save_score(self):
        if not self.current_filepath: self.save_score_as()
        else: self.perform_save(self.current_filepath)
    def save_score_as(self):
        filepath, _ = QFileDialog.getSaveFileName(self, "楽譜を名前を付けて保存", self.current_filepath or "untitled.json", "JSON Files (*.json)")
        if filepath: self.perform_save(filepath)
    def perform_save(self, filepath):
        data_to_save = {"bpm": self.rhythm_widget.bpm, "score": self.rhythm_widget.score}
        try:
            with open(filepath, 'w', encoding='utf-8') as f: json.dump(data_to_save, f, indent=4)
            self.current_filepath = filepath; self.setWindowTitle(f"{os.path.basename(filepath)} - 高機能リズムエディター")
            self.refresh_file_list()
        except Exception as e: QMessageBox.critical(self, "エラー", f"ファイルの保存に失敗しました:\n{e}")

if __name__ == '__main__':
    pygame.init()
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())