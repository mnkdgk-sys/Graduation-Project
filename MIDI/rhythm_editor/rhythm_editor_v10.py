import pygame
import sys
import os
import json
import tkinter as tk
from tkinter import filedialog

# --- 初期設定と定義 ---
WINDOW_WIDTH, WINDOW_HEIGHT = 1200, 500
# 色の定義
C_WHITE = (255, 255, 255); C_BLACK = (0, 0, 0); C_GRAY = (150, 150, 150)
C_DARK_GRAY = (80, 80, 80) 
C_LIGHT_GRAY = (220, 220, 220); C_RED = (255, 0, 0); C_BLUE = (0, 0, 255)
C_PALE_BLUE = (170, 170, 255); C_NOTE_BG = (230, 230, 250); C_LIT_GLOW = (255, 255, 0, 150)
C_REST_BG = (180, 180, 180, 150); C_GREEN = (0, 180, 80)

# 音符と休符の定義
NOTE_DURATIONS = {
    'whole':    {'duration': 4.0, 'name': "全音符"}, 'half':     {'duration': 2.0, 'name': "2分音符"},
    'quarter':  {'duration': 1.0, 'name': "4分音符"}, 'eighth':   {'duration': 0.5, 'name': "8分音符"},
    'sixteenth':{'duration': 0.25, 'name': "16分音符"},
}
REST_DURATIONS = {
    'quarter_rest':  {'duration': 1.0, 'name': "4分休符"}, 'eighth_rest':   {'duration': 0.5, 'name': "8分休符"},
    'sixteenth_rest':{'duration': 0.25, 'name': "16分休符"},
}
NOTE_IMAGE_FILES = {
    'whole': 'whole_note.PNG', 'half': 'half_note.PNG', 'quarter': 'quarter_note.PNG',
    'eighth': 'eighth_note.PNG', 'sixteenth':'sixteenth_note.PNG',
}
REST_IMAGE_FILES = {
    'quarter_rest': 'quarter_rest.PNG', 'eighth_rest': 'eighth_rest.PNG', 'sixteenth_rest': 'sixteenth_rest.PNG',
}
BPM = 120.0; LIT_DURATION = 150
BEATS_PER_MEASURE = 4; NUM_MEASURES = 2; TOTAL_BEATS = BEATS_PER_MEASURE * NUM_MEASURES

class Button:
    def __init__(self, text, pos, font, bg_color=C_BLUE, text_color=C_WHITE, padding=10):
        self.text = text; self.pos = pos; self.font = font; self.bg_color = bg_color; self.text_color = text_color; self.padding = padding; self.set_rect()
    def set_rect(self):
        self.text_surface = self.font.render(self.text, True, self.text_color); self.rect = self.text_surface.get_rect(center=self.pos); self.rect.width += self.padding * 2; self.rect.height += self.padding * 2
    def draw(self, surface, is_selected=False):
        color = C_PALE_BLUE if is_selected else self.bg_color; pygame.draw.rect(surface, color, self.rect, border_radius=8); surface.blit(self.text_surface, self.text_surface.get_rect(center=self.rect.center))
    def is_clicked(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1: return self.rect.collidepoint(event.pos)
        return False

def draw_item(surface, item, measure_info, images):
    start_x, score_width, staff_y, total_beats = measure_info
    x = start_x + (item['beat'] / total_beats) * score_width; width = (item['duration'] / total_beats) * score_width
    item_block_rect = pygame.Rect(x, staff_y - 25, width, 50)
    if item['class'] == 'note':
        if item.get('is_lit', False):
            glow_surface = pygame.Surface(item_block_rect.size, pygame.SRCALPHA); glow_surface.fill(C_LIT_GLOW); surface.blit(glow_surface, item_block_rect.topleft)
        pygame.draw.rect(surface, C_GRAY, item_block_rect, 1)
    elif item['class'] == 'rest':
        rest_surface = pygame.Surface(item_block_rect.size, pygame.SRCALPHA); rest_surface.fill(C_REST_BG); surface.blit(rest_surface, item_block_rect.topleft)
    item_image = images.get(item['type'])
    if item_image:
        img_rect = item_image.get_rect(center=item_block_rect.center); surface.blit(item_image, img_rect)

def handle_file_action(state, filename, current_score, current_bpm):
    if not filename: return current_score, current_bpm
    filepath = filename if filename.endswith(".json") else filename + ".json"

    if state == "saving":
        data_to_save = {"bpm": current_bpm, "score": current_score}
        try:
            with open(filepath, 'w', encoding='utf-8') as f: json.dump(data_to_save, f, indent=4)
            print(f"楽譜を保存しました: {filepath}")
        except Exception as e: print(f"ファイルの保存中にエラーが発生しました: {e}")
        return current_score, current_bpm
    
    elif state == "loading":
        try:
            with open(filepath, 'r', encoding='utf-8') as f: loaded_data = json.load(f)
            if "bpm" in loaded_data and "score" in loaded_data:
                print(f"楽譜を読み込みました: {filepath}")
                return loaded_data["score"], loaded_data["bpm"]
            else: print(f"エラー: 無効な楽譜ファイルです: {filepath}")
        except FileNotFoundError: print(f"エラー: ファイルが見つかりません: {filepath}")
        except Exception as e: print(f"ファイルの読み込み中にエラーが発生しました: {e}")
        return current_score, current_bpm

def main():
    pygame.init(); pygame.mixer.init()
    screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
    pygame.display.set_caption("リズムエディター 完成版")
    clock = pygame.time.Clock()
    
    try: font = pygame.font.Font("NotoSansJP-Regular.ttf", 20); font_small = pygame.font.Font("NotoSansJP-Regular.ttf", 14); font_large = pygame.font.Font("NotoSansJP-Regular.ttf", 50)
    except FileNotFoundError: font = pygame.font.SysFont("sans-serif", 20); font_small = pygame.font.SysFont("sans-serif", 14); font_large = pygame.font.SysFont("sans-serif", 50)
    
    try: click_sound = pygame.mixer.Sound("click.wav")
    except (FileNotFoundError, pygame.error): click_sound = None

    item_images = {}; all_image_files = {**NOTE_IMAGE_FILES, **REST_IMAGE_FILES}
    NOTE_IMAGE_MAX_HEIGHT = 40
    for item_type, filename in all_image_files.items():
        try:
            image = pygame.image.load(filename).convert_alpha(); original_width, original_height = image.get_rect().size
            if original_height == 0: continue
            aspect_ratio = original_width / original_height; new_height = NOTE_IMAGE_MAX_HEIGHT; new_width = int(new_height * aspect_ratio)
            image = pygame.transform.smoothscale(image, (new_width, new_height)); item_images[item_type] = image
        except (FileNotFoundError, pygame.error): print(f"警告: 画像ファイル '{filename}' が見つかりません。")
    
    ALL_DURATIONS = {**NOTE_DURATIONS, **REST_DURATIONS}
    score = {'top': [], 'bottom': []}; bpm = 120.0
    
    btn_start = Button("Start", (80, 40), font); btn_stop = Button("Stop", (220, 40), font); btn_reset = Button("リセット", (360, 40), font, bg_color=C_GRAY)
    btn_save = Button("保存", (800, 40), font, bg_color=C_GREEN); btn_load = Button("読込", (900, 40), font, bg_color=C_GREEN)
    btn_bpm_minus = Button("-", (970, 40), font, padding=5); btn_bpm_plus = Button("+", (1070, 40), font, padding=5)
    btn_track_top = Button("上段", (80, 100), font_small); btn_track_bottom = Button("下段", (180, 100), font_small)
    
    palette_buttons = {}
    note_x, rest_x, y_offset = 80, 180, 180
    for i, (note_type, props) in enumerate(NOTE_DURATIONS.items()):
        button = Button(props['name'], (note_x, y_offset + i * 50), font_small, padding=5); palette_buttons[note_type] = button
    for i, (rest_type, props) in enumerate(REST_DURATIONS.items()):
        button = Button(props['name'], (rest_x, y_offset + i * 50), font_small, padding=5); palette_buttons[rest_type] = button
    
    app_state = "editing"; input_text = ""; input_box_rect = pygame.Rect(WINDOW_WIDTH/2 - 200, WINDOW_HEIGHT/2 - 25, 400, 50)
    btn_confirm = Button("決定", (WINDOW_WIDTH/2 - 80, WINDOW_HEIGHT/2 + 50), font)
    btn_cancel = Button("キャンセル", (WINDOW_WIDTH/2 + 80, WINDOW_HEIGHT/2 + 50), font, bg_color=C_GRAY)

    is_playing = False; playback_start_time = 0; active_track = 'top'
    score_width = 800; start_x = 350
    staff_y_top = WINDOW_HEIGHT * 0.35; staff_y_bottom = WINDOW_HEIGHT * 0.65
    feedback_msg = ""; feedback_time = 0; FEEDBACK_DURATION = 2000

    while True:
        events = pygame.event.get()
        for event in events:
            if event.type == pygame.QUIT: pygame.quit(); sys.exit()

            if app_state == "editing":
                if event.type == pygame.MOUSEBUTTONDOWN:
                    if not is_playing:
                        if event.button == 3:
                            mouse_pos = event.pos
                            for track_name in ['top', 'bottom']:
                                staff_y = staff_y_top if track_name == 'top' else staff_y_bottom; item_to_delete = None
                                for item in score[track_name]:
                                    x = start_x + (item['beat'] / TOTAL_BEATS) * score_width; width = (item['duration'] / TOTAL_BEATS) * score_width
                                    item_rect = pygame.Rect(x, staff_y - 25, width, 50)
                                    if item_rect.collidepoint(mouse_pos): item_to_delete = item; break
                                if item_to_delete: score[track_name].remove(item_to_delete); break
                        elif event.button == 1:
                            if btn_save.is_clicked(event): app_state = "saving"; input_text = "my_rhythm"
                            elif btn_load.is_clicked(event): app_state = "loading"; input_text = ""
                            elif btn_start.is_clicked(event): is_playing = True; playback_start_time = pygame.time.get_ticks()
                            elif btn_reset.is_clicked(event): score = {'top': [], 'bottom': []}
                            elif btn_bpm_minus.is_clicked(event): bpm = max(30, bpm - 5)
                            elif btn_bpm_plus.is_clicked(event): bpm = min(240, bpm + 5)
                            elif btn_track_top.is_clicked(event): active_track = 'top'
                            elif btn_track_bottom.is_clicked(event): active_track = 'bottom'
                            else:
                                item_type_to_add = None
                                for item_type, button in palette_buttons.items():
                                    if button.is_clicked(event): item_type_to_add = item_type; break
                                if item_type_to_add:
                                    target_track = score[active_track]
                                    if not target_track: next_beat = 0.0
                                    else: last_item = target_track[-1]; next_beat = last_item['beat'] + last_item['duration']
                                    item_info = ALL_DURATIONS[item_type_to_add]; new_item_duration = item_info['duration']
                                    if next_beat + new_item_duration <= TOTAL_BEATS:
                                        item_class = 'note' if item_type_to_add in NOTE_DURATIONS else 'rest'
                                        new_item = {'beat': next_beat, 'type': item_type_to_add, 'duration': new_item_duration, 'class': item_class}
                                        target_track.append(new_item); target_track.sort(key=lambda x: x['beat'])
                                    else: feedback_msg = "配置不可: 小節の容量を超えます。"; feedback_time = pygame.time.get_ticks()
                    elif is_playing and btn_stop.is_clicked(event): is_playing = False
            
            elif app_state in ["saving", "loading"]:
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_RETURN:
                        score, bpm = handle_file_action(app_state, input_text, score, bpm); app_state = "editing"
                    elif event.key == pygame.K_BACKSPACE: input_text = input_text[:-1]
                    else: input_text += event.unicode
                elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    if btn_confirm.is_clicked(event):
                        score, bpm = handle_file_action(app_state, input_text, score, bpm); app_state = "editing"
                    elif btn_cancel.is_clicked(event): app_state = "editing"
        
        screen.fill(C_WHITE)
        if app_state == "editing":
            btn_start.draw(screen); btn_stop.draw(screen); btn_reset.draw(screen); btn_save.draw(screen); btn_load.draw(screen)
            bpm_text = font.render(f"BPM: {bpm:.0f}", True, C_BLACK); screen.blit(bpm_text, bpm_text.get_rect(center=(620, 40)))
            btn_bpm_minus.draw(screen); btn_bpm_plus.draw(screen)
            btn_track_top.draw(screen, is_selected=(active_track == 'top')); btn_track_bottom.draw(screen, is_selected=(active_track == 'bottom'))
            for item_type, button in palette_buttons.items(): button.draw(screen)
            for staff_y in [staff_y_top, staff_y_bottom]:
                pygame.draw.line(screen, C_BLACK, (start_x, staff_y), (start_x + score_width, staff_y), 2)
                for i in range(TOTAL_BEATS * 4 + 1):
                    line_color = C_GRAY if i % 4 == 0 else C_LIGHT_GRAY; x = start_x + (i / TOTAL_BEATS) * score_width
                    pygame.draw.line(screen, line_color, (x, staff_y - 30), (x, staff_y + 30), 1)
                for i in range(1, NUM_MEASURES):
                    x = start_x + (i * BEATS_PER_MEASURE / TOTAL_BEATS) * score_width
                    pygame.draw.line(screen, C_BLACK, (x, staff_y - 30), (x, staff_y + 30), 2)

            if is_playing:
                ms_per_beat = 60000.0 / bpm; total_duration_ms = TOTAL_BEATS * ms_per_beat
                if total_duration_ms == 0: total_duration_ms = 1
                time_in_loop = (pygame.time.get_ticks() - playback_start_time) % total_duration_ms
                progress = time_in_loop / total_duration_ms; cursor_x = start_x + progress * score_width
                pygame.draw.line(screen, C_RED, (cursor_x, 50), (cursor_x, WINDOW_HEIGHT - 50), 2)
                current_beat = (time_in_loop / total_duration_ms) * TOTAL_BEATS
                if current_beat < 0.2:
                    for track_name in ['top', 'bottom']:
                        for item in score[track_name]: item['played_in_loop'] = False
                for track_name in ['top', 'bottom']:
                    for item in score[track_name]:
                        if not item.get('played_in_loop', False) and current_beat >= item['beat']:
                            if item['class'] == 'note':
                                if click_sound: click_sound.play()
                                item['lit_start_time'] = pygame.time.get_ticks()
                            item['played_in_loop'] = True
            
            current_time = pygame.time.get_ticks()
            for track_name in ['top', 'bottom']:
                staff_y = staff_y_top if track_name == 'top' else staff_y_bottom
                for item in score[track_name]:
                    if item.get('class') == 'note' and 'lit_start_time' in item and (current_time - item['lit_start_time']) < LIT_DURATION:
                        item['is_lit'] = True
                    else: item['is_lit'] = False
                    draw_item(screen, item, (start_x, score_width, staff_y, TOTAL_BEATS), item_images)

            if feedback_msg and current_time - feedback_time < FEEDBACK_DURATION:
                msg_surface = font.render(feedback_msg, True, C_RED)
                screen.blit(msg_surface, msg_surface.get_rect(center=(WINDOW_WIDTH/2 + 125, WINDOW_HEIGHT - 30)))
        
        elif app_state in ["saving", "loading"]:
            title_text = "ファイル名を入力して保存" if app_state == "saving" else "ファイル名を入力して読み込み"
            title_surface = font_large.render(title_text, True, C_DARK_GRAY)
            screen.blit(title_surface, title_surface.get_rect(center=(WINDOW_WIDTH/2, WINDOW_HEIGHT/2 - 100)))
            pygame.draw.rect(screen, C_WHITE, input_box_rect); pygame.draw.rect(screen, C_BLACK, input_box_rect, 2)
            input_surface = font.render(input_text, True, C_BLACK)
            screen.blit(input_surface, (input_box_rect.x + 10, input_box_rect.y + 10))
            btn_confirm.draw(screen); btn_cancel.draw(screen)

        pygame.display.flip()
        clock.tick(60)

if __name__ == '__main__':
    main()