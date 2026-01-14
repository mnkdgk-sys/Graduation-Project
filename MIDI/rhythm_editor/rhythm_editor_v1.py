import pygame
import sys

# --- 初期設定と定義 ---
WINDOW_WIDTH, WINDOW_HEIGHT = 800, 300
C_WHITE = (255, 255, 255)
C_BLACK = (0, 0, 0)
C_GRAY = (150, 150, 150)

# 前回作成した音符の定義
NOTE_DURATIONS = {
    'whole':    [4.0, "全音符"],
    'half':     [2.0, "2分音符"],
    'quarter':  [1.0, "4分音符"],
    'eighth':   [0.5, "8分音符"],
    'sixteenth':[0.25, "16分音符"],
}

# --- 音符を描画するための関数 ---
# 今は円や線で描画しますが、後にこの部分を画像に差し替えます
def draw_note(surface, note_type, pos):
    """指定された位置に、指定された種類の音符を描画する"""
    note_head_radius = 10
    stem_height = 40
    
    # 符頭（たま）
    if note_type == 'half' or note_type == 'whole':
        pygame.draw.circle(surface, C_BLACK, pos, note_head_radius, 2) # 白抜き
    else:
        pygame.draw.circle(surface, C_BLACK, pos, note_head_radius) # 黒塗り

    # 符幹（ぼう）
    if note_type != 'whole':
        stem_start = (pos[0] + note_head_radius, pos[1])
        stem_end = (pos[0] + note_head_radius, pos[1] - stem_height)
        pygame.draw.line(surface, C_BLACK, stem_start, stem_end, 2)

# --- メイン処理 ---
def main():
    pygame.init()
    screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
    pygame.display.set_caption("リズムエディター v1 - 静的表示")
    font = pygame.font.SysFont("sans-serif", 30)

    # --- 表示する楽譜のデータを定義 ---
    # これは仮のデータです。最終的にはユーザーがこれを作成します。
    # 'beat': 小節の何拍目に始まるか
    # 'type': 音符の種類
    score = [
        {'beat': 0, 'type': 'quarter'},
        {'beat': 1, 'type': 'quarter'},
        {'beat': 2, 'type': 'quarter'},
        {'beat': 3, 'type': 'quarter'},
    ]
    
    # 1小節あたりの拍数（今は4/4拍子で固定）
    beats_per_measure = 4

    # 描画エリアの設定
    measure_width = 600
    start_x = (WINDOW_WIDTH - measure_width) / 2
    staff_y = WINDOW_HEIGHT / 2

    # --- メインループ ---
    while True:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()

        # 画面を白で塗りつぶし
        screen.fill(C_WHITE)

        # 拍子記号の表示
        time_sig_text = font.render("4/4", True, C_BLACK)
        screen.blit(time_sig_text, (start_x - 50, staff_y - 25))

        # 一線譜と小節線を描画
        pygame.draw.line(screen, C_BLACK, (start_x, staff_y), (start_x + measure_width, staff_y), 2)
        pygame.draw.line(screen, C_BLACK, (start_x, staff_y - 20), (start_x, staff_y + 20), 2)
        pygame.draw.line(screen, C_BLACK, (start_x + measure_width, staff_y - 20), (start_x + measure_width, staff_y + 20), 2)

        # 楽譜データに基づいて音符を描画
        for note in score:
            # 音符のX座標を計算
            note_x = start_x + (note['beat'] / beats_per_measure) * measure_width
            # 音符を描画
            draw_note(screen, note['type'], (note_x, staff_y))
            
        # 画面を更新
        pygame.display.flip()


if __name__ == '__main__':
    main()