import pygame
import pygame.midi
import sys
import math
import time
import os
# モジュール化した2つのプログラムをインポート
import rhythm_editor_module_v2 
import training_module_v2

# --- 設定 ---
WINDOW_WIDTH, WINDOW_HEIGHT = 800, 600
C_WHITE = (255, 255, 255)
C_BLACK = (0, 0, 0)
C_BLUE = (50, 100, 200)
C_GREEN = (0, 180, 80)
C_DARK_BLUE = (20, 40, 80)
C_LIGHT_BLUE = (100, 150, 255)
C_DARK_GREEN = (0, 120, 50)
C_LIGHT_GREEN = (50, 220, 130)
C_PURPLE = (120, 80, 200)
C_ORANGE = (255, 140, 50)
C_GRAY = (128, 128, 128)
C_LIGHT_GRAY = (200, 200, 200)

# --- UIコンポーネントと描画関数 ---

class ModernButton:
    def __init__(self, text, pos, font, primary_color, secondary_color, text_color=C_WHITE, width=300, height=80):
        self.text = text
        self.pos = pos
        self.font = font
        self.primary_color = primary_color
        self.secondary_color = secondary_color
        self.text_color = text_color
        self.width = width
        self.height = height
        self.hover_scale = 1.0
        self.target_scale = 1.0
        self.glow_intensity = 0.0
        self.target_glow = 0.0
        self.rect = pygame.Rect(0, 0, width, height)
        self.rect.center = pos
        self.text_surface = self.font.render(self.text, True, self.text_color)

    def update(self, dt):
        self.hover_scale += (self.target_scale - self.hover_scale) * dt * 8
        self.glow_intensity += (self.target_glow - self.glow_intensity) * dt * 10

    def handle_event(self, event):
        if event.type == pygame.MOUSEMOTION:
            if self.rect.collidepoint(event.pos):
                self.target_scale = 1.05
                self.target_glow = 20
            else:
                self.target_scale = 1.0
                self.target_glow = 0
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.rect.collidepoint(event.pos):
                return True
        return False

    def draw(self, surface):
        scaled_width = int(self.width * self.hover_scale)
        scaled_height = int(self.height * self.hover_scale)
        scaled_rect = pygame.Rect(0, 0, scaled_width, scaled_height)
        scaled_rect.center = self.pos

        if self.glow_intensity > 0:
            glow_surface = pygame.Surface((scaled_width + int(self.glow_intensity * 2),
                                         scaled_height + int(self.glow_intensity * 2)), pygame.SRCALPHA)
            glow_rect = glow_surface.get_rect(center=self.pos)
            for i in range(int(self.glow_intensity)):
                alpha = int(255 * (1 - i / self.glow_intensity) * 0.3)
                color = (*self.primary_color, alpha)
                pygame.draw.rect(glow_surface, color,
                               (i, i, scaled_width + (int(self.glow_intensity) - i) * 2,
                                scaled_height + (int(self.glow_intensity) - i) * 2),
                               border_radius=20 + i)
            surface.blit(glow_surface, glow_rect)

        gradient_surface = pygame.Surface((scaled_width, scaled_height), pygame.SRCALPHA)
        for y in range(scaled_height):
            ratio = y / scaled_height
            r = int(self.primary_color[0] * (1 - ratio) + self.secondary_color[0] * ratio)
            g = int(self.primary_color[1] * (1 - ratio) + self.secondary_color[1] * ratio)
            b = int(self.primary_color[2] * (1 - ratio) + self.secondary_color[2] * ratio)
            pygame.draw.line(gradient_surface, (r, g, b), (0, y), (scaled_width, y))
        
        mask = pygame.Surface((scaled_width, scaled_height), pygame.SRCALPHA)
        pygame.draw.rect(mask, (255, 255, 255, 255), (0, 0, scaled_width, scaled_height), border_radius=20)
        gradient_surface.blit(gradient_surface, (0, 0), special_flags=pygame.BLEND_ALPHA_SDL2)

        surface.blit(gradient_surface, scaled_rect)
        pygame.draw.rect(surface, C_WHITE, scaled_rect, 2, border_radius=20)
        text_rect = self.text_surface.get_rect(center=self.pos)
        surface.blit(self.text_surface, text_rect)

class ParticleEffect:
    def __init__(self):
        self.particles = []

    def add_particle(self, x, y):
        self.particles.append({
            'x': x, 'y': y,
            'vx': (pygame.time.get_ticks() % 100 - 50) / 25.0,
            'vy': (pygame.time.get_ticks() % 100 - 50) / 25.0,
            'life': 1.0, 'size': pygame.time.get_ticks() % 5 + 2
        })

    def update(self, dt):
        for particle in self.particles[:]:
            particle['x'] += particle['vx'] * dt * 60
            particle['y'] += particle['vy'] * dt * 60
            particle['life'] -= dt * 2
            if particle['life'] <= 0:
                self.particles.remove(particle)

    def draw(self, surface):
        for particle in self.particles:
            alpha = int(255 * particle['life'])
            color = (100, 150, 255, alpha)
            pos = (int(particle['x']), int(particle['y']))
            particle_surface = pygame.Surface((particle['size'] * 2, particle['size'] * 2), pygame.SRCALPHA)
            pygame.draw.circle(particle_surface, color, (particle['size'], particle['size']), particle['size'])
            surface.blit(particle_surface, (pos[0] - particle['size'], pos[1] - particle['size']))

def draw_animated_background(surface, time_elapsed):
    for y in range(WINDOW_HEIGHT):
        ratio = y / WINDOW_HEIGHT
        wave1 = math.sin(time_elapsed * 0.5 + ratio * 2) * 0.3 + 0.7
        wave2 = math.cos(time_elapsed * 0.3 + ratio * 3) * 0.2 + 0.8
        r = int(20 * wave1 + 15 * wave2)
        g = int(30 * wave1 + 25 * wave2)
        b = int(60 * wave1 + 80 * wave2)
        pygame.draw.line(surface, (r, g, b), (0, y), (WINDOW_WIDTH, y))

    for i in range(3):
        offset_x = math.sin(time_elapsed * 0.4 + i * 2) * 100
        offset_y = math.cos(time_elapsed * 0.3 + i * 1.5) * 50
        x = WINDOW_WIDTH // 4 + offset_x + i * WINDOW_WIDTH // 4
        y = WINDOW_HEIGHT // 3 + offset_y
        alpha = int(30 + math.sin(time_elapsed * 0.6 + i) * 15)
        circle_surface = pygame.Surface((200, 200), pygame.SRCALPHA)
        pygame.draw.circle(circle_surface, (100, 150, 255, alpha), (100, 100), 80)
        pygame.draw.circle(circle_surface, (150, 200, 255, alpha // 2), (100, 100), 60)
        surface.blit(circle_surface, (x - 100, y - 100))

def draw_title(surface, font, time_elapsed):
    title_text = "リズム練習システム"
    colors = [
        (255, 100, 150), (255, 150, 100), (255, 255, 100),
        (150, 255, 100), (100, 255, 150), (100, 255, 255),
        (100, 150, 255), (150, 100, 255), (255, 100, 255),
    ]
    x_offset = 0
    title_width = sum(font.render(char, True, (0,0,0)).get_width() for char in title_text)
    start_x = (WINDOW_WIDTH - title_width) // 2
    for i, char in enumerate(title_text):
        color_index = int((time_elapsed * 2 + i * 0.5) % len(colors))
        color = colors[color_index]
        char_surface = font.render(char, True, color)
        y_offset = math.sin(time_elapsed * 3 + i * 0.5) * 5
        surface.blit(char_surface, (start_x + x_offset, 100 + y_offset))
        x_offset += char_surface.get_width()

def is_midi_device_connected():
    pygame.midi.init()
    device_count = pygame.midi.get_count()
    pygame.midi.quit()
    return device_count > 0

def show_popup_message(screen, font, title, message):
    popup_width, popup_height = 450, 200
    popup_rect = pygame.Rect((WINDOW_WIDTH - popup_width) // 2, (WINDOW_HEIGHT - popup_height) // 2, popup_width, popup_height)
    ok_button = ModernButton("OK", (popup_rect.centerx, popup_rect.bottom - 40), font, C_BLUE, C_LIGHT_BLUE, width=120, height=50)
    clock = pygame.time.Clock()

    # メッセージを複数行に分割
    message_lines = message.split('\n')
    message_surfaces = [font.render(line, True, C_BLACK) for line in message_lines]

    while True:
        dt = clock.tick(60) / 1000.0
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            if ok_button.handle_event(event):
                return

        draw_animated_background(screen, time.time())
        
        # ポップアップ背景（半透明にするためのSurface）
        popup_bg_surface = pygame.Surface((popup_width, popup_height), pygame.SRCALPHA)
        pygame.draw.rect(popup_bg_surface, (*C_WHITE, 230), popup_bg_surface.get_rect(), border_radius=12)
        screen.blit(popup_bg_surface, popup_rect)
        pygame.draw.rect(screen, C_GRAY, popup_rect, 2, border_radius=12)

        title_surface = font.render(title, True, C_PURPLE)
        title_rect = title_surface.get_rect(midtop=(popup_rect.centerx, popup_rect.top + 20))
        screen.blit(title_surface, title_rect)
        
        # 複数行メッセージの描画
        for i, msg_surface in enumerate(message_surfaces):
            msg_rect = msg_surface.get_rect(center=(popup_rect.centerx, popup_rect.centery - 15 + i * 30))
            screen.blit(msg_surface, msg_rect)

        ok_button.update(dt)
        ok_button.draw(screen)
        pygame.display.flip()

# --- メイン画面 ---
def home_screen():
    pygame.init()
    screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
    pygame.display.set_caption("リズム練習システム")
    clock = pygame.time.Clock()

    try:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        font_path = os.path.join(script_dir, "NotoSansJP-Regular.ttf")
        title_font = pygame.font.Font(font_path, 40)
        button_font = pygame.font.Font(font_path, 24)
        
    except pygame.error: 
        print(f"日本語フォント 'NotoSansJP-Regular.ttf' が見つかりません。システムフォントで代替します。")
        title_font = pygame.font.SysFont("sans-serif", 42)
        button_font = pygame.font.SysFont("sans-serif", 24)

    def reload_fonts():
        try:
            # font_path はこのスコープ内で利用可能
            return pygame.font.Font(font_path, 40), pygame.font.Font(font_path, 24)
        except pygame.error:
            return pygame.font.SysFont("sans-serif", 42), pygame.font.SysFont("sans-serif", 24)

    btn_editor = ModernButton("♪ 楽譜を編集する", (WINDOW_WIDTH / 2, WINDOW_HEIGHT * 0.45), button_font, C_BLUE, C_LIGHT_BLUE)
    btn_analyzer = ModernButton("♫ リズムを練習する", (WINDOW_WIDTH / 2, WINDOW_HEIGHT * 0.65), button_font, C_GREEN, C_LIGHT_GREEN)
    particles = ParticleEffect()
    start_time = time.time()
    
    while True:
        dt = clock.tick(60) / 1000.0
        time_elapsed = time.time() - start_time
        
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()

            # 楽譜エディタを起動する際の処理
            if btn_editor.handle_event(event):
                print("エディタを起動します...")
                rhythm_editor_module_v2.run_editor() 

                # --- ここから修正 ---
                print("--- ホーム画面に戻りました ---")
                pygame.quit()  # Pygameを完全に終了
                pygame.init()  # Pygameを再初期化
                screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT)) # 画面を再作成
                pygame.display.set_caption("リズム練習システム")
                title_font, button_font = reload_fonts() # フォントを再読み込み！
                start_time = time.time()
                # ★★★ 重要：溜まった経過時間をリセットする ★★★
                clock.tick() 
                # --- 修正ここまで ---

            # リズム練習ツールを起動する際の処理
            if btn_analyzer.handle_event(event):
                if not is_midi_device_connected():
                    print("MIDI機器が接続されていません。")
                    show_popup_message(screen, button_font, "MIDI接続エラー", "練習を開始するには\nMIDI機器を接続してください。")
                    continue
                
                print("練習ツールを起動します...")
                training_module_v2.run_analyzer() # この関数の実行後に問題が起きる

                # --- こちらも同様に修正 ---
                print("--- ホーム画面に戻りました ---")
                pygame.quit()
                pygame.init()
                screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
                pygame.display.set_caption("リズム練習システム")
                title_font, button_font = reload_fonts()
                start_time = time.time()
                # ★★★ 重要：溜まった経過時間をリセットする ★★★
                clock.tick()
        btn_editor.update(dt)
        btn_analyzer.update(dt)
        particles.update(dt)

        draw_animated_background(screen, time_elapsed)
        particles.draw(screen)
        draw_title(screen, title_font, time_elapsed)
        btn_editor.draw(screen)
        btn_analyzer.draw(screen)

        pygame.display.flip()

if __name__ == '__main__':
    home_screen()