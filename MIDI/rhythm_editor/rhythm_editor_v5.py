import pygame
import sys
import os

# --- (初期設定、色の定義、NOTE_DURATIONSは変更なし) ---
WINDOW_WIDTH, WINDOW_HEIGHT = 800, 400
C_WHITE = (255, 255, 255); C_BLACK = (0, 0, 0); C_GRAY = (150, 150, 150)
C_LIGHT_GRAY = (220, 220, 220); C_RED = (255, 0, 0); C_BLUE = (0, 0, 255)
C_PALE_BLUE = (170, 170, 255); C_NOTE_BG = (230, 230, 250)
NOTE_DURATIONS = {
    'whole':    {'duration': 4.0, 'name': "全"}, 'half':     {'duration': 2.0, 'name': "2分"},
    'quarter':  {'duration': 1.0, 'name': "4分"}, 'eighth':   {'duration': 0.5, 'name': "8分"},
    'sixteenth':{'duration': 0.25, 'name': "16分"},
}
BPM = 120.0; LIT_DURATION = 100

# --- (Buttonクラス、draw_note関数は変更なし) ---
class Button:
    def __init__(self, text, pos, font, bg_color=C_BLUE, text_color=C_WHITE, padding=10):
        self.text = text; self.pos = pos; self.font = font; self.bg_color = bg_color
        self.text_color = text_color; self.padding = padding; self.set_rect()
    def set_rect(self):
        self.text_surface = self.font.render(self.text, True, self.text_color)
        self.rect = self.text_surface.get_rect(center=self.pos); self.rect.width += self.padding * 2
        self.rect.height += self.padding * 2
    def draw(self, surface, is_selected=False):
        color = C_PALE_BLUE if is_selected else self.bg_color
        pygame.draw.rect(surface, color, self.rect, border_radius=8)
        surface.blit(self.text_surface, self.text_surface.get_rect(center=self.rect.center))
    def is_clicked(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            return self.rect.collidepoint(event.pos)
        return False

def draw_note(surface, note, measure_info, font):
    start_x, measure_width, staff_y, beats_per_measure = measure_info
    x = start_x + (note['beat'] / beats_per_measure) * measure_width
    width = (note['duration'] / beats_per_measure) * measure_width
    note_rect = pygame.Rect(x, staff_y - 25, width, 50)
    pygame.draw.rect(surface, C_NOTE_BG, note_rect)
    pygame.draw.rect(surface, C_GRAY, note_rect, 1)
    color = C_RED if note.get('is_lit', False) else C_BLACK
    note_head_radius = 8
    pygame.draw.circle(surface, color, (x + note_head_radius + 5, staff_y), note_head_radius)
    pygame.draw.line(surface, color, (x + note_head_radius*2 + 5, staff_y), (x + note_head_radius*2+5, staff_y - 25), 2)

# --- メイン処理 ---
def main():
    pygame.init(); pygame.mixer.init()
    screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
    pygame.display.set_caption("リズムエディター v5 - リセット機能")
    clock = pygame.time.Clock()
    
    font_path = "NotoSansJP-Regular.ttf"
    try:
        font = pygame.font.Font(font_path, 20)
        font_small = pygame.font.Font(font_path, 14)
    except FileNotFoundError:
        font = pygame.font.SysFont("sans-serif", 20)
        font_small = pygame.font.SysFont("sans-serif", 14)

    try: click_sound = pygame.mixer.Sound("click.wav")
    except FileNotFoundError: click_sound = None

    score = []
    beats_per_measure = 4
    
    # --- UI要素の準備 ---
    btn_start = Button("Start", (60, 40), font); btn_stop = Button("Stop", (160, 40), font)
    btn_reset = Button("リセット", (270, 40), font, bg_color=C_GRAY) # 【追加】リセットボタン

    palette_buttons = {}
    x_offset, y_offset = 60, 120
    for i, (note_type, props) in enumerate(NOTE_DURATIONS.items()):
        button = Button(props['name'], (x_offset, y_offset + i * 50), font_small, padding=8)
        palette_buttons[note_type] = button
    
    selected_note_type = 'quarter'
    is_playing = False; playback_start_time = 0
    
    measure_width = 600
    start_x = 150
    staff_y = WINDOW_HEIGHT / 2
    staff_rect = pygame.Rect(start_x, staff_y - 30, measure_width, 60)

    while True:
        for event in pygame.event.get():
            if event.type == pygame.QUIT: pygame.quit(); sys.exit()
            
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                palette_clicked = False
                for note_type, button in palette_buttons.items():
                    if button.is_clicked(event):
                        selected_note_type = note_type
                        palette_clicked = True
                        break 
                
                if not palette_clicked:
                    if btn_start.is_clicked(event) and not is_playing:
                        is_playing = True; playback_start_time = pygame.time.get_ticks()
                    elif btn_stop.is_clicked(event) and is_playing:
                        is_playing = False
                    # --- 【ここから追加】リセットボタンの処理 ---
                    elif btn_reset.is_clicked(event) and not is_playing:
                        score = [] # 楽譜データを空にする
                        print("楽譜をリセットしました。")
                    # --- 【ここまで追加】
                    elif not is_playing and staff_rect.collidepoint(event.pos):
                        note_info = NOTE_DURATIONS[selected_note_type]
                        new_note_duration = note_info['duration']
                        relative_x = event.pos[0] - start_x
                        progress = max(0, relative_x / measure_width)
                        clicked_beat = progress * beats_per_measure
                        quantize_unit = 0.25
                        new_note_beat = round(clicked_beat / quantize_unit) * quantize_unit
                        
                        can_place = True
                        if new_note_beat + new_note_duration > beats_per_measure:
                            can_place = False
                        
                        if can_place:
                            for existing_note in score:
                                if not (new_note_beat + new_note_duration <= existing_note['beat'] or \
                                        new_note_beat >= existing_note['beat'] + existing_note['duration']):
                                    can_place = False; break
                        
                        if can_place:
                            new_note = {'beat': new_note_beat, 'type': selected_note_type, 'duration': new_note_duration}
                            score.append(new_note)
                            score.sort(key=lambda x: x['beat'])

        # --- 描画処理 ---
        screen.fill(C_WHITE)
        btn_start.draw(screen); btn_stop.draw(screen)
        btn_reset.draw(screen) # 【追加】リセットボタンを描画
        bpm_text = font.render(f"BPM: {BPM}", True, C_BLACK); screen.blit(bpm_text, (380, 30)) # BPM表示位置を調整
        for note_type, button in palette_buttons.items():
            button.draw(screen, is_selected=(note_type == selected_note_type))
        pygame.draw.line(screen, C_BLACK, (start_x, staff_y), (start_x + measure_width, staff_y), 2)
        for i in range(beats_per_measure * 4 * 4 + 1):
            line_color = C_GRAY if i % 4 == 0 else C_LIGHT_GRAY
            x = start_x + (i / (beats_per_measure * 4)) * measure_width
            pygame.draw.line(screen, line_color, (x, staff_y - 30), (x, staff_y + 30), 1)
        
        # --- (再生処理と音符描画処理は変更なし) ---
        for note in score: note['is_lit'] = False
        if is_playing and score:
            ms_per_beat = 60000.0 / BPM
            measure_duration_ms = beats_per_measure * ms_per_beat
            time_in_loop = (pygame.time.get_ticks() - playback_start_time) % measure_duration_ms
            current_beat = (time_in_loop / measure_duration_ms) * beats_per_measure
            cursor_x = start_x + (time_in_loop / ms_per_beat) * (measure_width / beats_per_measure)
            pygame.draw.line(screen, C_RED, (cursor_x, staff_y - 40), (cursor_x, staff_y + 40), 2)
            if current_beat < 0.1: 
                for note in score: note['played_in_loop'] = False
            for note in score:
                if not note.get('played_in_loop', False) and current_beat >= note['beat']:
                    if click_sound: click_sound.play()
                    note['played_in_loop'] = True
                    note['lit_start_time'] = pygame.time.get_ticks()
        current_time = pygame.time.get_ticks()
        for note in score:
            if 'lit_start_time' in note and (current_time - note['lit_start_time']) < LIT_DURATION:
                note['is_lit'] = True
            draw_note(screen, note, (start_x, measure_width, staff_y, beats_per_measure), font_small)
            
        pygame.display.flip()
        clock.tick(60)

if __name__ == '__main__':
    main()