import mido
import pygame
import sys
import os

# --- 設定 ---

# 1. パッドとノート番号の対応
PAD_MAPPING = {
    'left': [47, 56],
    'right': [48, 29]
}

# 2. 感度の閾値
VELOCITY_THRESHOLD = 30

# 3. UIに関する設定
# 【変更点】背景色を明るい灰色に変更しました
WINDOW_WIDTH = 600
WINDOW_HEIGHT = 400
BACKGROUND_COLOR = (245, 245, 245)  # 明るい灰色
# 【変更点】背景色に合わせて、太鼓の色も見やすいように調整しました
DRUM_COLOR = (200, 180, 170)      # 少し明るい茶色
DRUM_LIT_COLOR = (255, 180, 0)      # 光った時のオレンジ色
LIT_DURATION = 100  # 光る時間（ミリ秒）

# --- メインのプログラム ---

def main():
    inport = None  # finallyブロックで参照できるよう、外で初期化

    # 【変更点】try...finallyブロックを追加し、どんな終了の仕方をしても必ず終了処理が実行されるようにします
    try:
        # PygameとMIDIポートの初期化
        pygame.init()
        try:
            inport = mido.open_input()
            print("MIDIポートを正常に開きました。")
        except OSError:
            print("エラー: MIDI入力ポートが見つかりません。")
            print("MIDI機器がPCに正しく接続されているか確認してください。")
            return # finallyブロックを実行して終了

        # ウィンドウの作成
        screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
        pygame.display.set_caption("太鼓シミュレーター")
        clock = pygame.time.Clock()

        # 画像の読み込み
        def load_image(path):
            if os.path.exists(path):
                return pygame.image.load(path).convert_alpha()
            return None

        images = {
            'left': load_image('left_drum.png'),
            'left_lit': load_image('left_drum_lit.png'),
            'right': load_image('right_drum.png'),
            'right_lit': load_image('right_drum_lit.png'),
        }

        lit_timers = {'left': 0, 'right': 0}

        # メインループ
        running = True
        while running:
            # イベント処理 (ウィンドウの閉じるボタン)
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False # ループを抜けて正常終了へ

            # MIDI入力のチェック
            for msg in inport.iter_pending():
                if msg.type == 'note_on' and msg.velocity >= VELOCITY_THRESHOLD:
                    note = msg.note
                    if note in PAD_MAPPING['left']:
                        lit_timers['left'] = pygame.time.get_ticks()
                    elif note in PAD_MAPPING['right']:
                        lit_timers['right'] = pygame.time.get_ticks()

            # 画面の描画
            screen.fill(BACKGROUND_COLOR)
            current_time = pygame.time.get_ticks()
            draw_drum(screen, 'left', (current_time - lit_timers['left'] < LIT_DURATION), images)
            draw_drum(screen, 'right', (current_time - lit_timers['right'] < LIT_DURATION), images)
            pygame.display.flip()

            clock.tick(60)

    except KeyboardInterrupt:
        # 【変更点】ターミナルで Ctrl+C が押された時の処理
        print("\nCtrl+Cが押されました。プログラムを終了します。")
    
    finally:
        # 【変更点】終了処理をここにまとめる
        print("終了処理を実行します...")
        if inport:
            inport.close()
            print("MIDIポートを閉じました。")
        pygame.quit()
        print("Pygameを終了しました。")
        sys.exit()

def draw_drum(screen, side, is_lit, images):
    """太鼓を描画する関数"""
    image_key = f"{side}_lit" if is_lit else side
    image_to_draw = images[image_key]

    if side == 'left':
        pos_x = WINDOW_WIDTH * 0.25
    else:
        pos_x = WINDOW_WIDTH * 0.75
    
    pos_y = WINDOW_HEIGHT / 2

    if image_to_draw:
        rect = image_to_draw.get_rect(center=(pos_x, pos_y))
        screen.blit(image_to_draw, rect)
    else:
        color = DRUM_LIT_COLOR if is_lit else DRUM_COLOR
        rect = pygame.Rect(0, 0, 150, 150)
        rect.center = (pos_x, pos_y)
        pygame.draw.ellipse(screen, color, rect)

if __name__ == '__main__':
    main()