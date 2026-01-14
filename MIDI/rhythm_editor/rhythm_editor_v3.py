import pygame
import sys
import os

# --- 初期設定と定義 ---
WINDOW_WIDTH, WINDOW_HEIGHT = 800, 300
C_WHITE = (255, 255, 255); C_BLACK = (0, 0, 0); C_GRAY = (150, 150, 150)
C_LIGHT_GRAY = (220, 220, 220); C_RED = (255, 0, 0); C_BLUE = (0, 0, 255)
NOTE_DURATIONS = {'quarter': [1.0, "4分音符"]}
BPM = 120.0; LIT_DURATION = 100

# --- Buttonクラス ---
class Button:
    def __init__(self, text, pos, font, bg_color=C_BLUE, text_color=C_WHITE, padding=10):
        self.text = text; self.pos = pos; self.font = font; self.bg_color = bg_color
        self.text_color = text_color; self.padding = padding; self.set_rect()
    def set_rect(self):
        self.text_surface = self.font.render(self.text, True, self.text_color)
        self.rect = self.text_surface.get_rect(center=self.pos); self.rect.width += self.padding * 2
        self.rect.height += self.padding * 2
    def draw(self, surface):
        pygame.draw.rect(surface, self.bg_color, self.rect, border_radius=8)
        surface.blit(self.text_surface, self.text_surface.get_rect(center=self.rect.center))
    def is_clicked(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            return self.rect.collidepoint(event.pos)
        return False

# --- draw_note関数 ---
def draw_note(surface, note_type, pos, is_lit):
    note_head_radius = 10; stem_height = 40
    color = C_RED if is_lit else C_BLACK
    pygame.draw.circle(surface, color, pos, note_head_radius)
    stem_start = (pos[0] + note_head_radius, pos[1]); stem_end = (pos[0] + note_head_radius, pos[1] - stem_height)
    pygame.draw.line(surface, color, stem_start, stem_end, 2)

# --- メイン処理 ---
def main():
    pygame.init(); pygame.mixer.init()
    screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
    pygame.display.set_caption("リズムエディター v3 - 配置機能")
    
    # --- 【修正点】この一行が抜けていました ---
    clock = pygame.time.Clock()
    
    font = pygame.font.SysFont("sans-serif", 30)
    
    try:
        click_sound = pygame.mixer.Sound("click.wav")
    except FileNotFoundError:
        print("警告: click.wav が見つかりません。メトロノーム音なしで実行します。")
        click_sound = None

    score = []
    beats_per_measure = 4
    
    btn_start = Button("Start", (60, 40), font)
    btn_stop = Button("Stop", (160, 40), font)

    is_playing = False; playback_start_time = 0
    note_lit_times = []
    next_click_beat = 0

    measure_width = 500
    start_x = (WINDOW_WIDTH - measure_width) / 2
    staff_y = WINDOW_HEIGHT / 2
    staff_rect = pygame.Rect(start_x, staff_y - 20, measure_width, 40)

    while True:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if not is_playing and staff_rect.collidepoint(event.pos):
                    relative_x = event.pos[0] - start_x
                    progress = relative_x / measure_width
                    clicked_beat = progress * beats_per_measure
                    quantize_unit = 0.25
                    quantized_beat = round(clicked_beat / quantize_unit) * quantize_unit
                    
                    is_existing = any(note['beat'] == quantized_beat for note in score)
                    if not is_existing:
                        new_note = {'beat': quantized_beat, 'type': 'quarter'}
                        score.append(new_note)
                        score.sort(key=lambda x: x['beat'])
                        note_lit_times = [0] * len(score)
                        print(f"音符を配置しました: {quantized_beat}拍目")

            if btn_start.is_clicked(event) and not is_playing:
                is_playing = True; playback_start_time = pygame.time.get_ticks(); next_click_beat = 0
            if btn_stop.is_clicked(event) and is_playing:
                is_playing = False

        screen.fill(C_WHITE)
        btn_start.draw(screen); btn_stop.draw(screen)
        bpm_text = font.render(f"BPM: {BPM}", True, C_BLACK); screen.blit(bpm_text, (260, 30))
        pygame.draw.line(screen, C_BLACK, (start_x, staff_y), (start_x + measure_width, staff_y), 2)
        pygame.draw.line(screen, C_BLACK, (start_x, staff_y - 20), (start_x, staff_y + 20), 2)
        pygame.draw.line(screen, C_BLACK, (start_x + measure_width, staff_y - 20), (start_x + measure_width, staff_y + 20), 2)

        if is_playing and score:
            ms_per_beat = 60000.0 / BPM
            measure_duration_ms = beats_per_measure * ms_per_beat
            elapsed_time = pygame.time.get_ticks() - playback_start_time
            time_in_loop = elapsed_time % measure_duration_ms
            
            progress = time_in_loop / measure_duration_ms
            cursor_x = start_x + progress * measure_width
            pygame.draw.line(screen, C_RED, (cursor_x, staff_y - 30), (cursor_x, staff_y + 30), 2)
            
            current_beat_in_loop = (time_in_loop / measure_duration_ms) * beats_per_measure
            
            # 再生ロジックの調整
            if time_in_loop < ms_per_beat and next_click_beat != 0:
                next_click_beat = 0

            if current_beat_in_loop >= next_click_beat:
                if click_sound: click_sound.play()
                next_click_beat += 1
            
            for i, note in enumerate(score):
                if note['beat'] <= current_beat_in_loop < note['beat'] + 0.1:
                     note_lit_times[i] = pygame.time.get_ticks()

        current_time_for_lit = pygame.time.get_ticks()
        for i, note in enumerate(score):
            note_x = start_x + (note['beat'] / beats_per_measure) * measure_width
            is_lit = (current_time_for_lit - note_lit_times[i]) < LIT_DURATION
            draw_note(screen, note['type'], (note_x, staff_y), is_lit)

        pygame.display.flip()
        
        # この命令が、変数`clock`を必要としていました
        clock.tick(60)

if __name__ == '__main__':
    main()