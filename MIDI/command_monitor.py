import sys
import time
import copy
import math
from PyQt6.QtWidgets import (
    QApplication, QDialog, QWidget, QVBoxLayout, QSizePolicy,
    QGridLayout, QLabel, QGroupBox, QToolTip # ★ Import QToolTip
)
from PyQt6.QtCore import Qt, QTimer, QRectF, QPointF, pyqtSlot
from PyQt6.QtGui import QPainter, QColor, QFont, QPen, QBrush

# ui_theme.py から色をインポート (メインアプリと共通)
try:
    from ui_theme import COLORS
except ImportError:
    # フォールバック
    print("Warning: ui_theme.py not found, using fallback colors for command_monitor.")
    COLORS = {'background': QColor(248, 249, 250), 'surface': QColor(255, 255, 255),
              'primary': QColor(59, 130, 246), 'danger': QColor(220, 53, 69),
              'text_primary': QColor(33, 37, 41), 'text_secondary': QColor(108, 117, 125),
              'text_muted': QColor(173, 181, 189), 'border': QColor(222, 226, 230),
              'cursor': QColor(214, 51, 132), 'success': QColor(25, 135, 84),
              'surface_light': QColor(241, 243, 245)}

# --- グラフ設定 ---
GRAPH_START_SEC = -2.0 # ★ Start time axis before 0
Z_AXIS_MIN = 0.0
Z_AXIS_MAX = 100.0
Z_AXIS_RANGE = Z_AXIS_MAX - Z_AXIS_MIN
HOVER_RADIUS_SQ = 25 # ★ Pixel radius (squared) for tooltip activation

# --- GraphWidget (描画ウィジェット) ---
class GraphWidget(QWidget):
    """
    時系列グラフを描画するウィジェット (全体表示版, ツールチップ付き)
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMinimumHeight(300)
        self.setMouseTracking(True) # ★ Enable mouse tracking for tooltips

        self.score_data = None
        self.master_start_time = 0
        self.is_monitoring = False
        self.total_duration_sec = 8.0 # Default, updated later
        self.loop_duration_sec = 8.0  # Default, updated later

        self.template_notes = [] # 楽譜 (目標)
        self.command_log = []    # 送信されたコマンド

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update)

        self.font_small = QFont("Segoe UI", 8)
        self.font_bold = QFont("Segoe UI", 10, QFont.Weight.Bold)

        self.pen_grid = QPen(COLORS['border'], 1, Qt.PenStyle.DashLine)
        self.pen_axis = QPen(COLORS['text_secondary'], 1, Qt.PenStyle.SolidLine)
        self.pen_template = QPen(COLORS['text_muted'], 2)
        self.brush_template = QBrush(COLORS['text_muted'])
        self.pen_command_top = QPen(COLORS['primary'], 2)
        self.brush_command_top = QBrush(COLORS['primary'])
        self.pen_command_bottom = QPen(COLORS['success'], 2)
        self.brush_command_bottom = QBrush(COLORS['success'])

    def start_monitoring(self, score_data, master_start_time, motion_plan_data):
        self.score_data = copy.deepcopy(score_data)
        self.master_start_time = master_start_time
        self.command_log.clear()
        self.template_notes.clear()

        # ★ Calculate total and loop duration
        max_time = 0.0
        if motion_plan_data:
            for track_plan in motion_plan_data.values():
                if track_plan:
                     max_time = max(max_time, max(m['target_time'] for m in track_plan if 'target_time' in m)) # Safety check

        # Add padding, ensure minimum duration
        self.total_duration_sec = max(8.0, math.ceil(max_time) + 1.0)

        # Calculate loop duration (use 'top' track as reference)
        top_score = score_data.get("top", {})
        top_bpm = top_score.get("bpm", 120)
        top_beats = top_score.get("total_beats", 8)
        if top_bpm > 0:
             self.loop_duration_sec = top_beats * (60.0 / top_bpm)
        else:
             self.loop_duration_sec = 8.0 # Fallback
        # ---

        self.parse_template_notes(motion_plan_data)
        self.is_monitoring = True
        if not self.timer.isActive():
            self.timer.start(50)

    def stop_monitoring(self):
        self.is_monitoring = False
        if self.timer.isActive():
             self.timer.stop()
        self.update() # Trigger one final redraw

    def parse_template_notes(self, motion_plan_data):
        if not motion_plan_data:
            print("Monitor Error: No motion plan data received for parsing.")
            return
        for track_name, plan in motion_plan_data.items():
            if plan is None: continue
            for motion in plan:
                 # ★ Add safety check for required keys
                 if all(k in motion for k in ['target_time', 'position', 'action']):
                    self.template_notes.append({
                        'track': track_name,
                        'time_sec': motion['target_time'],
                        'z': motion['position'][2],
                        'action': motion['action']
                    })
                 else:
                     print(f"Monitor Warning: Skipping incomplete motion data in track {track_name}")

        self.template_notes.sort(key=lambda x: x['time_sec'])

    @pyqtSlot(str, dict)
    def update_command(self, track_name, motion):
        send_time_sec = time.time() - self.master_start_time
        # ★ Ensure details dictionary is populated safely
        details = {
            'pos': motion.get("position", ("N/A",)*4),
            'vel': motion.get("velocity", "N/A"),
            'acc': motion.get("acceleration", "N/A"),
            'action': motion.get("action", "N/A")
        }
        self.command_log.append({
            'time_sec': send_time_sec,
            'track': track_name,
            'z': motion.get("position", (0,0,0))[2], # Default Z to 0 if missing
            'details': details
        })
        if not self.is_monitoring:
             self.update()

    # --- Coordinate Conversion ---
    def _to_pixel(self, time_sec, z_coord, graph_rect, time_start, time_duration):
        """ Converts graph coordinates (time, z) to widget pixel coordinates """
        if time_duration <= 0 or Z_AXIS_RANGE <= 0: return QPointF(0,0) # Avoid division by zero

        x_ratio = (time_sec - time_start) / time_duration
        x = graph_rect.left() + (x_ratio * graph_rect.width())

        clamped_z = max(Z_AXIS_MIN, min(Z_AXIS_MAX, z_coord))
        y_ratio = (clamped_z - Z_AXIS_MIN) / Z_AXIS_RANGE
        y = graph_rect.bottom() - (y_ratio * graph_rect.height()) # Y is inverted

        return QPointF(x, y)

    def _from_pixel(self, point, graph_rect, time_start, time_duration):
        """ Converts widget pixel coordinates to graph coordinates (time, z) """
        if graph_rect.width() <= 0 or graph_rect.height() <= 0 or time_duration <= 0 or Z_AXIS_RANGE <= 0:
            return None, None # Invalid dimensions

        x_ratio = (point.x() - graph_rect.left()) / graph_rect.width()
        time_sec = time_start + (x_ratio * time_duration)

        y_ratio = (graph_rect.bottom() - point.y()) / graph_rect.height()
        z_coord = Z_AXIS_MIN + (y_ratio * Z_AXIS_RANGE)

        return time_sec, z_coord


    # --- Drawing ---
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), COLORS['surface'])

        if self.master_start_time == 0:
             painter.setPen(COLORS['text_muted'])
             painter.setFont(self.font_bold)
             painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "練習開始待機中...")
             return

        # --- Coordinates and Time Calculation ---
        margin_left, margin_right, margin_top, margin_bottom = 50, 20, 20, 40
        graph_rect = QRectF(margin_left, margin_top,
                            self.width() - margin_left - margin_right,
                            self.height() - margin_top - margin_bottom)

        if graph_rect.width() <= 0 or graph_rect.height() <= 0: return

        # ★ Time axis starts at GRAPH_START_SEC
        time_start_sec = GRAPH_START_SEC
        time_end_sec = self.total_duration_sec
        current_graph_duration = time_end_sec - time_start_sec

        # --- Grid and Axes ---
        painter.setFont(self.font_small)
        # Z-axis
        painter.setPen(self.pen_axis)
        painter.drawLine(int(graph_rect.left()), int(graph_rect.top()), int(graph_rect.left()), int(graph_rect.bottom()))
        for i in range(6):
            z = Z_AXIS_MIN + (Z_AXIS_RANGE * i / 5.0)
            p = self._to_pixel(time_start_sec, z, graph_rect, time_start_sec, current_graph_duration)
            painter.setPen(self.pen_grid)
            painter.drawLine(int(graph_rect.left()), int(p.y()), int(graph_rect.right()), int(p.y()))
            painter.setPen(self.pen_axis)
            painter.drawText(QRectF(0, p.y() - 8, margin_left - 5, 16),
                             Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, f"{z:.0f}mm")
        # Time-axis
        p_bottom = self._to_pixel(time_start_sec, Z_AXIS_MIN, graph_rect, time_start_sec, current_graph_duration)
        painter.setPen(self.pen_axis)
        painter.drawLine(int(graph_rect.left()), int(p_bottom.y()), int(graph_rect.right()), int(p_bottom.y()))
        # Time grid lines and labels (every 1 second, starting from negative if needed)
        grid_time = math.floor(time_start_sec) # ★ Start from floor(GRAPH_START_SEC)
        while grid_time <= time_end_sec:
            p = self._to_pixel(grid_time, Z_AXIS_MIN, graph_rect, time_start_sec, current_graph_duration)
            if p.x() >= graph_rect.left() -1 : # Allow drawing at the very start
                painter.setPen(self.pen_grid)
                painter.drawLine(int(p.x()), int(graph_rect.top()), int(p.x()), int(graph_rect.bottom()))
                # Draw label only for integer seconds
                # if abs(grid_time % 1.0) < 0.01 or abs(grid_time % 1.0 - 1.0) < 0.01: # No need for float check anymore
                painter.setPen(self.pen_axis)
                painter.drawText(QRectF(p.x() - 25, p_bottom.y() + 5, 50, 20),
                                    Qt.AlignmentFlag.AlignCenter, f"{grid_time:.0f}s")
            grid_time += 1.0 # Increment by 1 second

        # --- Template Notes (Target) ---
        painter.setPen(self.pen_template)
        painter.setBrush(self.brush_template)
        for note in self.template_notes:
            if time_start_sec <= note['time_sec'] <= time_end_sec:
                p = self._to_pixel(note['time_sec'], note['z'], graph_rect, time_start_sec, current_graph_duration)
                if note['action'] == 'strike': painter.drawEllipse(p, 4, 4)
                else:
                    painter.setBrush(Qt.BrushStyle.NoBrush)
                    painter.drawLine(int(p.x()), int(p.y() - 4), int(p.x() - 4), int(p.y() + 4))
                    painter.drawLine(int(p.x() - 4), int(p.y() + 4), int(p.x() + 4), int(p.y() + 4))
                    painter.drawLine(int(p.x() + 4), int(p.y() + 4), int(p.x()), int(p.y() - 4))
                    painter.setBrush(self.brush_template)

        # --- Commands (Sent) ---
        for cmd in self.command_log:
            if time_start_sec <= cmd['time_sec'] <= time_end_sec:
                p = self._to_pixel(cmd['time_sec'], cmd['z'], graph_rect, time_start_sec, current_graph_duration)
                if cmd['track'] == 'top':
                    painter.setPen(self.pen_command_top); painter.setBrush(self.brush_command_top)
                else:
                    painter.setPen(self.pen_command_bottom); painter.setBrush(self.brush_command_bottom)
                painter.drawRect(QRectF(p.x() - 3, p.y() - 3, 6, 6))

        # --- Status Message ---
        if not self.is_monitoring:
             painter.setPen(COLORS['danger'])
             painter.setFont(self.font_bold)
             finished_text_rect = QRectF(graph_rect.left(), graph_rect.top(), graph_rect.width(), 30)
             painter.drawText(finished_text_rect.translated(0, 5), Qt.AlignmentFlag.AlignCenter, "--- 練習終了 ---")

    # --- Tooltip Handling ---
    def mouseMoveEvent(self, event):
        """ Handles mouse movement to show tooltips over command and template points """
        # ★ Hide tooltip initially
        QToolTip.hideText()

        # ★ Check if data is available
        if not self.command_log and not self.template_notes:
            return

        mouse_pos = event.pos()

        # Define graph area based on current widget size
        margin_left, margin_right, margin_top, margin_bottom = 50, 20, 20, 40
        graph_rect = QRectF(margin_left, margin_top,
                            self.width() - margin_left - margin_right,
                            self.height() - margin_top - margin_bottom)

        if not graph_rect.contains(QPointF(mouse_pos)):
             return # Mouse is outside graph area

        # Time range of the visible graph
        time_start_sec = GRAPH_START_SEC
        time_end_sec = self.total_duration_sec
        current_graph_duration = time_end_sec - time_start_sec

        hover_found = False
        tooltip_text = ""
        tooltip_pos = event.globalPosition().toPoint() # Use global position for tooltip

        # --- 1. Check Command Points (□) first (higher priority) ---
        min_dist_sq_cmd = HOVER_RADIUS_SQ # Use squared distance
        closest_cmd = None

        # Check only commands potentially visible
        visible_commands = [cmd for cmd in self.command_log if time_start_sec <= cmd['time_sec'] <= time_end_sec]

        for cmd in visible_commands:
            cmd_pixel_pos = self._to_pixel(cmd['time_sec'], cmd['z'], graph_rect, time_start_sec, current_graph_duration)
            dx = mouse_pos.x() - cmd_pixel_pos.x()
            dy = mouse_pos.y() - cmd_pixel_pos.y()
            dist_sq = dx*dx + dy*dy

            if dist_sq < min_dist_sq_cmd:
                min_dist_sq_cmd = dist_sq
                closest_cmd = cmd
                hover_found = True # Found a command hover

        if hover_found and closest_cmd:
            details = closest_cmd['details']
            pos = details['pos']
            vel = details['vel']
            acc = details['acc']
            action = details['action'].capitalize()
            cmd_time = closest_cmd['time_sec']
            time_in_loop = f"{(cmd_time % self.loop_duration_sec):.3f}s (Loop)" if self.loop_duration_sec > 0 else "N/A"
            pos_text = f"({pos[0]:.0f}, {pos[1]:.0f}, {pos[2]:.0f})" if isinstance(pos, (list, tuple)) and len(pos) >= 3 and all(isinstance(p, (int, float)) for p in pos[:3]) else "N/A"
            vel_text = f"{vel:.0f}" if isinstance(vel, (int, float)) else "N/A"
            acc_text = f"{acc:.0f}" if isinstance(acc, (int, float)) else "N/A"

            tooltip_text = (
                f"COMMAND\n" # ★ Indicate type
                f"Track: {closest_cmd['track'].upper()}\n"
                f"Action: {action}\n"
                f"Send Time: {cmd_time:.3f}s\n"
                f"Loop Time: {time_in_loop}\n"
                f"Target Z: {closest_cmd['z']:.1f}mm\n"
                f"Pos: {pos_text}\n"
                f"Vel: {vel_text} Acc: {acc_text}"
            )
            QToolTip.showText(tooltip_pos, tooltip_text, self)
            # Command found, don't check template notes
            super().mouseMoveEvent(event)
            return

        # --- 2. Check Template Note Points (○/△) if no command hover ---
        min_dist_sq_note = HOVER_RADIUS_SQ
        closest_note = None
        hover_found = False # Reset for template notes

        visible_notes = [note for note in self.template_notes if time_start_sec <= note['time_sec'] <= time_end_sec]

        for note in visible_notes:
            note_pixel_pos = self._to_pixel(note['time_sec'], note['z'], graph_rect, time_start_sec, current_graph_duration)
            dx = mouse_pos.x() - note_pixel_pos.x()
            dy = mouse_pos.y() - note_pixel_pos.y()
            dist_sq = dx*dx + dy*dy

            if dist_sq < min_dist_sq_note:
                min_dist_sq_note = dist_sq
                closest_note = note
                hover_found = True # Found a template note hover

        if hover_found and closest_note:
            note_time = closest_note['time_sec']
            time_in_loop = f"{(note_time % self.loop_duration_sec):.3f}s (Loop)" if self.loop_duration_sec > 0 else "N/A"
            action = closest_note['action'].capitalize()

            tooltip_text = (
                f"TEMPLATE NOTE\n" # ★ Indicate type
                f"Track: {closest_note['track'].upper()}\n"
                f"Action: {action}\n"
                f"Target Time: {note_time:.3f}s\n"
                f"Loop Time: {time_in_loop}\n"
                f"Target Z: {closest_note['z']:.1f}mm"
            )
            QToolTip.showText(tooltip_pos, tooltip_text, self)
            # Template note found
            super().mouseMoveEvent(event)
            return

        # --- No hover found on either ---
        # QToolTip.hideText() is called at the beginning

        super().mouseMoveEvent(event) # Pass event along

    def leaveEvent(self, event):
        """ Hide tooltip when mouse leaves the widget """
        QToolTip.hideText()
        super().leaveEvent(event)


# --- CommandInfoDisplay remains the same ---
class CommandInfoDisplay(QGroupBox):
    # ... (Paste the CommandInfoDisplay class code from the previous answer here) ...
    def __init__(self, title, color=COLORS['primary'], parent=None):
        super().__init__(title, parent)
        self.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        self.setStyleSheet(f"""
            QGroupBox {{
                background-color: {COLORS['surface_light'].name()};
                border: 1px solid {color.name()}; /* Use track color for border */
                border-radius: 8px;
                margin-top: 10px;
                padding-top: 5px; /* Add padding inside */
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 0 5px;
                margin-left: 10px;
                color: {color.name()}; /* Use track color for title */
                background-color: {COLORS['surface_light'].name()};
            }}
            QLabel {{
                background-color: transparent; /* Ensure labels have transparent background */
                padding: 1px;
            }}
        """)

        self.labels = {
            "Action": QLabel("-"),
            "Pos (X,Y,Z)": QLabel("-"),
            "Velocity": QLabel("-"),
            "Accel": QLabel("-")
        }

        layout = QGridLayout(self)
        layout.setContentsMargins(10, 5, 10, 10) # Adjust margins
        layout.setSpacing(2) # Reduce spacing
        for i, (key, label) in enumerate(self.labels.items()):
            key_label = QLabel(f"{key}:")
            key_label.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
            key_label.setStyleSheet(f"color: {COLORS['text_secondary'].name()};")
            label.setFont(QFont("Segoe UI", 9))
            label.setMinimumWidth(150) # Ensure enough space for values
            layout.addWidget(key_label, i, 0, alignment=Qt.AlignmentFlag.AlignRight)
            layout.addWidget(label, i, 1)

    def update_info(self, motion):
        # ★ Add safety checks using .get() with defaults
        action = motion.get("action", "N/A").capitalize()
        pos = motion.get("position", ("N/A",)*4)
        vel = motion.get("velocity", "N/A")
        acc = motion.get("acceleration", "N/A")

        # Check if values are available before formatting
        pos_text = f"{pos[0]:.0f}, {pos[1]:.0f}, {pos[2]:.0f}" if isinstance(pos, (list, tuple)) and len(pos) >= 3 and all(isinstance(p, (int, float)) for p in pos[:3]) else "N/A"
        vel_text = f"{vel:.0f}" if isinstance(vel, (int, float)) else "N/A"
        acc_text = f"{acc:.0f}" if isinstance(acc, (int, float)) else "N/A"

        self.labels["Action"].setText(action)
        self.labels["Pos (X,Y,Z)"].setText(pos_text)
        self.labels["Velocity"].setText(vel_text)
        self.labels["Accel"].setText(acc_text)

    def clear_info(self):
         for label in self.labels.values():
             label.setText("-")


# --- CommandVizWindow remains the same ---
class CommandVizWindow(QDialog):
    # ... (Paste the CommandVizWindow class code from the previous answer here) ...
    """
    グラフウィジェットとコマンド詳細表示を配置するメインのモニターウィンドウ
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("コマンドモニター (全体表示)") # ★ Update title
        self.setMinimumSize(800, 550)
        self.setStyleSheet(f"QDialog {{ background-color: {COLORS['background'].name()}; }}")

        self.graph_widget = GraphWidget(self)
        self.top_info = CommandInfoDisplay("Top (L) Last Command", COLORS['primary'])
        self.bottom_info = CommandInfoDisplay("Bottom (R) Last Command", COLORS['success'])

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.addWidget(self.graph_widget) # Graph takes most space

        info_layout = QGridLayout()
        info_layout.addWidget(self.top_info, 0, 0)
        info_layout.addWidget(self.bottom_info, 0, 1)
        layout.addLayout(info_layout)

        self.setLayout(layout)

    def start_monitoring(self, score_data, master_start_time, motion_plan_data):
        """
        MainWindowから呼ばれ、グラフウィジェットのモニターを開始する
        """
        self.top_info.clear_info()
        self.bottom_info.clear_info()
        self.graph_widget.start_monitoring(score_data, master_start_time, motion_plan_data)

    def stop_monitoring(self):
        """
        MainWindowから呼ばれ、グラフウィジェットのモニターを停止する
        """
        self.graph_widget.stop_monitoring()

    @pyqtSlot(str, dict)
    def update_command(self, track_name, motion):
        """
        MainWindow経由でRobotManagerからのシグナルを受け取り、
        グラフウィジェットにデータを渡し、コマンド詳細表示を更新する
        """
        self.graph_widget.update_command(track_name, motion) # Pass to graph
        # Update info display
        if track_name == 'top':
            self.top_info.update_info(motion)
        elif track_name == 'bottom':
            self.bottom_info.update_info(motion)

    def closeEvent(self, event):
        """
        ウィンドウが閉じられたときの処理
        """
        self.stop_monitoring()
        event.ignore()
        self.hide()