from PyQt6.QtGui import QColor

# --- UIカラーテーマ ---
# 複数のモジュールで共有される色の定義
COLORS = {
    'background': QColor(248, 249, 250), 'surface': QColor(255, 255, 255), 'surface_light': QColor(241, 243, 245),
    'primary': QColor(59, 130, 246), 'primary_dark': QColor(37, 99, 235), 'success': QColor(25, 135, 84),
    'success_dark': QColor(21, 115, 71), 'danger': QColor(220, 53, 69), 'danger_dark': QColor(187, 45, 59),
    'warning': QColor(255, 193, 7), 'warning_dark': QColor(217, 164, 6), 'note_glow': QColor(59, 130, 246, 80),
    'rest_bg': QColor(233, 236, 239, 150), 'staff_line': QColor(173, 181, 189), 'cursor': QColor(214, 51, 132),
    'text_primary': QColor(33, 37, 41), 'text_secondary': QColor(108, 117, 125), 'text_muted': QColor(173, 181, 189),
    'border': QColor(222, 226, 230), 'perfect': QColor(255, 193, 7), 'great': QColor(25, 135, 84),
    'good': QColor(59, 130, 246), 'miss': QColor(108, 117, 125), 'extra': QColor(220, 53, 69),
    'accent': QColor(102, 16, 242), 'glow': QColor(59, 130, 246, 30),
}

