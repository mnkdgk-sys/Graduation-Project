import pygame
import sys
import os

# --- 初期設定と定義 ---
WINDOW_WIDTH, WINDOW_HEIGHT = 800, 400
# 色の定義
C_WHITE = (255, 255, 255); C_BLACK = (0, 0, 0); C_GRAY = (150, 150, 150)
C_LIGHT_GRAY = (220, 220, 220); C_RED = (255, 0, 0); C_BLUE = (0, 0, 255)
C_PALE_BLUE = (170, 170, 255); C_NOTE_BG = (230, 230, 250); C_LIT_GLOW = (255, 255, 0, 150)
C_REST_BG = (180, 180, 180, 150) # 【追加】休符ブロックの色（半透明グレー）

# 音符と休符の定義
NOTE_DURATIONS = {
    'whole':    {'duration': 4.0, 'name': "全音符"}, 'half':     {'duration': 2.0, 'name': "2分音符"},
    'quarter':  {'duration': 1.0, 'name': "4分音符"}, 'eighth':   {'duration': 0.5, 'name': "8分音符"},
    'sixteenth':{'duration': 0.25, 'name': "16分音符"},
}
REST_DURATIONS = { # 【追加】
    'quarter_rest':  {'duration': 1.0, 'name': "4分休符"},
    'eighth_rest':   {'duration': 0.5, 'name': "8分休符"},
    'sixteenth_rest':{'duration': 0.25, 'name': "16分休符"},
}
NOTE_IMAGE_FILES = {
    'whole': 'whole_note.PNG', 'half': 'half_note.PNG', 'quarter': 'quarter_note.PNG',
    'eighth': 'eighth_note.PNG', 'sixteenth':'sixteenth_note.PNG',
}
REST_IMAGE_FILES = { # 【追加】
    'quarter_rest': 'quarter_rest.PNG', 'eighth_rest': 'eighth_rest.PNG',
    'sixteenth_rest': 'sixteenth_rest.PNG',
}
BPM = 120.0; LIT_DURATION = 150

class Button:
    # ... (変更なし) ...
    def __init__(self, text, pos, font, bg_color=C_BLUE, text_color=C_WHITE, padding=10):
        self.text = text; self.pos = pos; self.font = font; self.bg_color = bg_color; self.text_color = text_color; self.padding = padding; self.set_rect()
    def set_rect(self):
        self.text_surface = self.font.render(self.text, True, self.text_color); self.rect = self.text_surface.get_rect(center=self.pos); self.rect.width += self.padding * 2; self.rect.height += self.padding * 2
    def draw(self, surface, is_selected=False):
        color = C_PALE_BLUE if is_selected else self.bg_color; pygame.draw.rect(surface, color, self.rect, border_radius=8); surface.blit(self.text_surface, self.text_surface.get_rect(center=self.rect.center))
    def is_clicked(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1: return self.rect.collidepoint(event.pos)
        return False

# --- 【変更】draw_note から draw_item に関数名を変更 ---
def draw_item(surface, item, measure_info, images):
    start_x, measure_width, staff_y, beats_per_measure = measure_info
    x = start_x + (item['beat'] / beats_per_measure) * measure_width
    width = (item['duration'] / beats_per_measure) * measure_width
    item_block_rect = pygame.Rect(x, staff_y - 25, width, 50)
    
    # 【変更】アイテムの種類によって背景色を変える
    if item['class'] == 'note':
        if item.get('is_lit', False):
            glow_surface = pygame.Surface(item_block_rect.size, pygame.SRCALPHA); glow_surface.fill(C_LIT_GLOW); surface.blit(glow_surface, item_block_rect.topleft)
        pygame.draw.rect(surface, C_GRAY, item_block_rect, 1) # 音符は細い枠線
    elif item['class'] == 'rest':
        rest_surface = pygame.Surface(item_block_rect.size, pygame.SRCALPHA); rest_surface.fill(C_REST_BG); surface.blit(rest_surface, item_block_rect.topleft)

    item_image = images.get(item['type'])
    if item_image:
        img_rect = item_image.get_rect(center=item_block_rect.center); surface.blit(item_image, img_rect)

def main():
    pygame.init(); pygame.mixer.init()
    screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
    pygame.display.set_caption("リズムエディター Final - 休符対応")
    clock = pygame.time.Clock()
    
    try: font = pygame.font.Font("NotoSansJP-Regular.ttf", 20); font_small = pygame.font.Font("NotoSansJP-Regular.ttf", 14)
    except FileNotFoundError: font = pygame.font.SysFont("sans-serif", 20); font_small = pygame.font.SysFont("sans-serif", 14)
    
    try: click_sound = pygame.mixer.Sound("click.wav")
    except FileNotFoundError: click_sound = None

    # 【変更】音符と休符の画像をまとめて読み込む
    item_images = {}
    all_image_files = {**NOTE_IMAGE_FILES, **REST_IMAGE_FILES}
    NOTE_IMAGE_MAX_HEIGHT = 40
    for item_type, filename in all_image_files.items():
        try:
            image = pygame.image.load(filename).convert_alpha(); original_width, original_height = image.get_rect().size
            if original_height == 0: continue
            aspect_ratio = original_width / original_height; new_height = NOTE_IMAGE_MAX_HEIGHT; new_width = int(new_height * aspect_ratio)
            image = pygame.transform.smoothscale(image, (new_width, new_height)); item_images[item_type] = image
        except FileNotFoundError: print(f"警告: 画像ファイル '{filename}' が見つかりません。")
    
    # 【変更】音符と休符の定義をまとめる
    ALL_DURATIONS = {**NOTE_DURATIONS, **REST_DURATIONS}

    score = []; beats_per_measure = 4
    bpm = 120.0
    
    btn_start = Button("Start", (60, 40), font); btn_stop = Button("Stop", (200, 40), font); btn_reset = Button("リセット", (340, 40), font, bg_color=C_GRAY)
    btn_bpm_minus = Button("-", (650, 40), font, padding=5); btn_bpm_plus = Button("+", (750, 40), font, padding=5)

    # 【変更】パレットを2列に
    palette_buttons = {}
    note_x, rest_x, y_offset = 60, 160, 120
    for i, (note_type, props) in enumerate(NOTE_DURATIONS.items()):
        button = Button(props['name'], (note_x, y_offset + i * 50), font_small, padding=5); palette_buttons[note_type] = button
    for i, (rest_type, props) in enumerate(REST_DURATIONS.items()):
        button = Button(props['name'], (rest_x, y_offset + i * 50), font_small, padding=5); palette_buttons[rest_type] = button
    
    is_playing = False; playback_start_time = 0
    measure_width = 500; start_x = 250; staff_y = WINDOW_HEIGHT / 2
    feedback_msg = ""; feedback_time = 0; FEEDBACK_DURATION = 2000

    while True:
        for event in pygame.event.get():
            if event.type == pygame.QUIT: pygame.quit(); sys.exit()
            if event.type == pygame.MOUSEBUTTONDOWN:
                if not is_playing:
                    if event.button == 3: # 右クリック削除
                        mouse_pos = event.pos; item_to_delete = None
                        for item in score:
                            x = start_x + (item['beat'] / beats_per_measure) * measure_width; width = (item['duration'] / beats_per_measure) * measure_width
                            item_rect = pygame.Rect(x, staff_y - 25, width, 50)
                            if item_rect.collidepoint(mouse_pos): item_to_delete = item; break
                        if item_to_delete: score.remove(item_to_delete)
                    
                    elif event.button == 1: # 左クリック
                        if btn_start.is_clicked(event): is_playing = True; playback_start_time = pygame.time.get_ticks()
                        elif btn_reset.is_clicked(event): score = []
                        elif btn_bpm_minus.is_clicked(event): bpm = max(30, bpm - 5)
                        elif btn_bpm_plus.is_clicked(event): bpm = min(240, bpm + 5)
                        else:
                            item_type_to_add = None
                            for item_type, button in palette_buttons.items():
                                if button.is_clicked(event): item_type_to_add = item_type; break
                            
                            if item_type_to_add:
                                if not score: next_beat = 0.0
                                else: last_item = score[-1]; next_beat = last_item['beat'] + last_item['duration']
                                
                                item_info = ALL_DURATIONS[item_type_to_add]; new_item_duration = item_info['duration']
                                if next_beat + new_item_duration <= beats_per_measure:
                                    item_class = 'note' if item_type_to_add in NOTE_DURATIONS else 'rest'
                                    new_item = {'beat': next_beat, 'type': item_type_to_add, 'duration': new_item_duration, 'class': item_class}
                                    score.append(new_item); score.sort(key=lambda x: x['beat'])
                                else: feedback_msg = "配置不可: 小節の容量を超えます。"; feedback_time = pygame.time.get_ticks()

                elif is_playing and btn_stop.is_clicked(event): is_playing = False
        
        screen.fill(C_WHITE)
        btn_start.draw(screen); btn_stop.draw(screen); btn_reset.draw(screen)
        bpm_text = font.render(f"BPM: {bpm:.0f}", True, C_BLACK); screen.blit(bpm_text, bpm_text.get_rect(center=(700, 40)))
        btn_bpm_minus.draw(screen); btn_bpm_plus.draw(screen)
        for item_type, button in palette_buttons.items(): button.draw(screen)
        
        pygame.draw.line(screen, C_BLACK, (start_x, staff_y), (start_x + measure_width, staff_y), 2)
        for i in range(beats_per_measure * 4 + 1):
            line_color = C_GRAY if i % 4 == 0 else C_LIGHT_GRAY; x = start_x + (i / beats_per_measure) * measure_width
            pygame.draw.line(screen, line_color, (x, staff_y - 30), (x, staff_y + 30), 1)

        for item in score: item['is_lit'] = False
        if is_playing and score:
            ms_per_beat = 60000.0 / bpm; measure_duration_ms = beats_per_measure * ms_per_beat
            if measure_duration_ms == 0: measure_duration_ms = 1
            time_in_loop = (pygame.time.get_ticks() - playback_start_time) % measure_duration_ms
            progress = time_in_loop / measure_duration_ms; cursor_x = start_x + progress * measure_width
            pygame.draw.line(screen, C_RED, (cursor_x, staff_y - 40), (cursor_x, staff_y + 40), 2)
            current_beat = (time_in_loop / measure_duration_ms) * beats_per_measure
            if current_beat < 0.1:
                for item in score: item['played_in_loop'] = False
            for item in score:
                if not item.get('played_in_loop', False) and current_beat >= item['beat']:
                    # 【変更点】アイテムが'note'の場合のみ音を鳴らす
                    if item['class'] == 'note':
                        if click_sound: click_sound.play()
                        item['lit_start_time'] = pygame.time.get_ticks()
                    item['played_in_loop'] = True
        
        current_time = pygame.time.get_ticks()
        for item in score:
            if item.get('class') == 'note' and 'lit_start_time' in item and (current_time - item['lit_start_time']) < LIT_DURATION:
                item['is_lit'] = True
            draw_item(screen, item, (start_x, measure_width, staff_y, beats_per_measure), item_images)

        if feedback_msg and current_time - feedback_time < FEEDBACK_DURATION:
            msg_surface = font.render(feedback_msg, True, C_RED)
            screen.blit(msg_surface, msg_surface.get_rect(center=(WINDOW_WIDTH/2 + 125, WINDOW_HEIGHT - 30)))
        
        pygame.display.flip()
        clock.tick(60)

if __name__ == '__main__':
    main()