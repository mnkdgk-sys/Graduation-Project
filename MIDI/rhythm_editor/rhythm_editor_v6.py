import pygame
import sys
import os

# --- (設定やクラス定義などは変更なし) ---
WINDOW_WIDTH, WINDOW_HEIGHT = 800, 400
C_WHITE = (255, 255, 255); C_BLACK = (0, 0, 0); C_GRAY = (150, 150, 150)
C_LIGHT_GRAY = (220, 220, 220); C_RED = (255, 0, 0); C_BLUE = (0, 0, 255)
C_PALE_BLUE = (170, 170, 255); C_NOTE_BG = (230, 230, 250); C_LIT_GLOW = (255, 255, 0, 150)
NOTE_DURATIONS = {
    'whole':    {'duration': 4.0, 'name': "全"}, 'half':     {'duration': 2.0, 'name': "2分"},
    'quarter':  {'duration': 1.0, 'name': "4分"}, 'eighth':   {'duration': 0.5, 'name': "8分"},
    'sixteenth':{'duration': 0.25, 'name': "16分"},
}
NOTE_IMAGE_FILES = {
    'whole':    'whole_note.PNG', 'half':     'half_note.PNG', 'quarter':  'quarter_note.PNG',
    'eighth':   'eighth_note.PNG', 'sixteenth':'sixteenth_note.PNG',
}
BPM = 120.0; LIT_DURATION = 150

class Button:
    # ... (変更なし) ...
    def __init__(self, text, pos, font, bg_color=C_BLUE, text_color=C_WHITE, padding=10):
        self.text = text; self.pos = pos; self.font = font; self.bg_color = bg_color; self.text_color = text_color; self.padding = padding; self.set_rect()
    def set_rect(self):
        self.text_surface = self.font.render(self.text, True, self.text_color); self.rect = self.text_surface.get_rect(center=self.pos); self.rect.width += self.padding * 2; self.rect.height += self.padding * 2
    def draw(self, surface, is_selected=False):
        color = self.bg_color; pygame.draw.rect(surface, color, self.rect, border_radius=8); surface.blit(self.text_surface, self.text_surface.get_rect(center=self.rect.center))
    def is_clicked(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1: return self.rect.collidepoint(event.pos)
        return False

def draw_note(surface, note, measure_info, images):
    # ... (変更なし) ...
    start_x, measure_width, staff_y, beats_per_measure = measure_info
    x = start_x + (note['beat'] / beats_per_measure) * measure_width; width = (note['duration'] / beats_per_measure) * measure_width
    note_block_rect = pygame.Rect(x, staff_y - 25, width, 50)
    if note.get('is_lit', False):
        glow_surface = pygame.Surface(note_block_rect.size, pygame.SRCALPHA); glow_surface.fill(C_LIT_GLOW); surface.blit(glow_surface, note_block_rect.topleft)
    pygame.draw.rect(surface, C_GRAY, note_block_rect, 1)
    note_image = images.get(note['type'])
    if note_image:
        img_rect = note_image.get_rect(center=note_block_rect.center); surface.blit(note_image, img_rect)
    else:
        pygame.draw.circle(surface, C_BLACK, (x + 15, staff_y), 8); pygame.draw.line(surface, C_BLACK, (x + 23, staff_y), (x + 23, staff_y - 25), 2)

# --- メイン処理 ---
def main():
    pygame.init(); pygame.mixer.init()
    screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
    pygame.display.set_caption("リズムエディター Final")
    clock = pygame.time.Clock()
    
    try: font = pygame.font.Font("NotoSansJP-Regular.ttf", 20)
    except FileNotFoundError: font = pygame.font.SysFont("sans-serif", 20)
    
    try: click_sound = pygame.mixer.Sound("click.wav")
    except FileNotFoundError: click_sound = None

    note_images = {}
    NOTE_IMAGE_MAX_HEIGHT = 40
    for note_type, filename in NOTE_IMAGE_FILES.items():
        try:
            image = pygame.image.load(filename).convert_alpha(); original_width, original_height = image.get_rect().size
            if original_height == 0: continue
            aspect_ratio = original_width / original_height; new_height = NOTE_IMAGE_MAX_HEIGHT; new_width = int(new_height * aspect_ratio)
            image = pygame.transform.smoothscale(image, (new_width, new_height)); note_images[note_type] = image
        except FileNotFoundError: print(f"警告: 画像ファイル '{filename}' が見つかりません。")

    score = []; beats_per_measure = 4
    btn_start = Button("Start", (60, 40), font); btn_stop = Button("Stop", (160, 40), font); btn_reset = Button("リセット", (270, 40), font, bg_color=C_GRAY)
    
    palette_buttons = {}
    x_offset, y_offset = 60, 120
    for i, (note_type, props) in enumerate(NOTE_DURATIONS.items()):
        button = Button(props['name'], (x_offset, y_offset + i * 50), font, padding=8); palette_buttons[note_type] = button
    
    is_playing = False; playback_start_time = 0
    measure_width = 600; start_x = 150; staff_y = WINDOW_HEIGHT / 2
    feedback_msg = ""; feedback_time = 0; FEEDBACK_DURATION = 2000

    while True:
        for event in pygame.event.get():
            if event.type == pygame.QUIT: pygame.quit(); sys.exit()
            
            # --- 【ここから修正】マウスクリック処理のロジックを全面的に見直し ---
            if event.type == pygame.MOUSEBUTTONDOWN:
                # --- 右クリックの処理 (削除) ---
                if event.button == 3:
                    if not is_playing:
                        mouse_pos = event.pos
                        note_to_delete = None
                        for note in score:
                            x = start_x + (note['beat'] / beats_per_measure) * measure_width
                            width = (note['duration'] / beats_per_measure) * measure_width
                            note_rect = pygame.Rect(x, staff_y - 25, width, 50)
                            if note_rect.collidepoint(mouse_pos):
                                note_to_delete = note; break
                        if note_to_delete:
                            score.remove(note_to_delete)
                
                # --- 左クリックの処理 (ボタン操作 or 配置) ---
                elif event.button == 1:
                    # 最初にチェック：Start, Stop, Resetボタン
                    if btn_start.is_clicked(event) and not is_playing:
                        is_playing = True; playback_start_time = pygame.time.get_ticks()
                    elif btn_stop.is_clicked(event) and is_playing:
                        is_playing = False
                    elif btn_reset.is_clicked(event) and not is_playing:
                        score = []
                    else:
                        # 上記ボタンでなければ、パレットのボタンかチェック
                        note_type_to_add = None
                        for note_type, button in palette_buttons.items():
                            if button.is_clicked(event):
                                note_type_to_add = note_type; break
                        
                        # パレットがクリックされたら、音符を追加
                        if note_type_to_add and not is_playing:
                            if not score: next_beat = 0.0
                            else: last_note = score[-1]; next_beat = last_note['beat'] + last_note['duration']
                            
                            note_info = NOTE_DURATIONS[note_type_to_add]; new_note_duration = note_info['duration']

                            if next_beat + new_note_duration <= beats_per_measure:
                                new_note = {'beat': next_beat, 'type': note_type_to_add, 'duration': new_note_duration}
                                score.append(new_note); score.sort(key=lambda x: x['beat'])
                            else:
                                feedback_msg = "配置不可: 小節の容量を超えます。"; feedback_time = pygame.time.get_ticks()
            # --- 【修正はここまで】 ---
        
        # --- (描画、再生処理は変更なし) ---
        screen.fill(C_WHITE)
        btn_start.draw(screen); btn_stop.draw(screen); btn_reset.draw(screen)
        bpm_text = font.render(f"BPM: {BPM}", True, C_BLACK); screen.blit(bpm_text, (380, 30))
        for note_type, button in palette_buttons.items(): button.draw(screen)
        pygame.draw.line(screen, C_BLACK, (start_x, staff_y), (start_x + measure_width, staff_y), 2)
        for i in range(beats_per_measure * 4 + 1):
            line_color = C_GRAY if i % 4 == 0 else C_LIGHT_GRAY; x = start_x + (i / beats_per_measure) * measure_width
            pygame.draw.line(screen, line_color, (x, staff_y - 30), (x, staff_y + 30), 1)

        for note in score: note['is_lit'] = False
        if is_playing and score:
            ms_per_beat = 60000.0 / BPM; measure_duration_ms = beats_per_measure * ms_per_beat
            if measure_duration_ms == 0: measure_duration_ms = 1
            time_in_loop = (pygame.time.get_ticks() - playback_start_time) % measure_duration_ms
            progress = time_in_loop / measure_duration_ms
            cursor_x = start_x + progress * measure_width
            pygame.draw.line(screen, C_RED, (cursor_x, staff_y - 40), (cursor_x, staff_y + 40), 2)
            current_beat = (time_in_loop / measure_duration_ms) * beats_per_measure
            if current_beat < 0.1:
                for note in score: note['played_in_loop'] = False
            for note in score:
                if not note.get('played_in_loop', False) and current_beat >= note['beat']:
                    if click_sound: click_sound.play(); note['played_in_loop'] = True; note['lit_start_time'] = pygame.time.get_ticks()
        
        current_time = pygame.time.get_ticks()
        for note in score:
            if 'lit_start_time' in note and (current_time - note['lit_start_time']) < LIT_DURATION: note['is_lit'] = True
            draw_note(screen, note, (start_x, measure_width, staff_y, beats_per_measure), note_images)

        if feedback_msg and current_time - feedback_time < FEEDBACK_DURATION:
            msg_surface = font.render(feedback_msg, True, C_RED)
            screen.blit(msg_surface, msg_surface.get_rect(center=(WINDOW_WIDTH/2 + 75, WINDOW_HEIGHT - 30)))
        
        pygame.display.flip()
        clock.tick(60)

if __name__ == '__main__':
    main()