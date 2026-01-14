import pygame
import pygame.midi
import sys
import math
import time
import os
import random
import webbrowser
from typing import List, Tuple
import colorsys
import multiprocessing 

# モジュール化した2つのプログラムをインポート
import rhythm_editor_module_v4
import training_module_v3

def run_in_process(target_func):
    """指定された関数を別のプロセスで実行し、その終了を待ちます。"""
    multiprocessing.freeze_support() 
    process = multiprocessing.Process(target=target_func)
    process.start()
    process.join()

# --- 拡張設定 ---
WINDOW_WIDTH, WINDOW_HEIGHT = 1280, 670
FPS = 30

# --- プロ級カラーパレット（Material Design 3 + Future Tech） ---
class ProColorTheme:
    # プライマリーカラー（AI/ロボティクス）
    ELECTRIC_BLUE = (0, 122, 255)        # iOS/Apple Blue
    ROBOT_CYAN = (0, 188, 212)           # Cyan 500
    NEURAL_PURPLE = (103, 58, 183)       # Deep Purple 500
    AI_GREEN = (76, 175, 80)             # Green 500
    RHYTHM_ORANGE = (255, 152, 0)        # Orange 500
    
    # アクセントカラー
    NEON_ACCENT = (0, 229, 255)          # Bright Cyan
    PULSE_PINK = (233, 30, 99)           # Pink A400
    ENERGY_YELLOW = (255, 235, 59)       # Yellow 500
    
    # ニュートラル（高品質グレースケール）
    SURFACE_00 = (242, 242, 247)      # 明るい背景 (Almost White)
    SURFACE_01 = (255, 255, 255)      # カードなどの表面 (Pure White)
    SURFACE_02 = (249, 249, 249)      # 少しだけ影のある表面
    SURFACE_03 = (239, 239, 244)      # やや濃いグレーの表面
    
    # テキスト階層
    ON_SURFACE = (20, 20, 20)          # メインの文字 (Almost Black)
    ON_SURFACE_VARIANT = (99, 99, 102) # サブの文字 (Medium Gray)
    OUTLINE = (209, 209, 214)          # 薄い境界線 (Light Gray)
    OUTLINE_VARIANT = (199, 199, 204)  # 区切り線 (Slightly Darker Gray)
    
    # 機能色 (変更なしでも良いですが、見やすさのために調整するのも手です)
    SUCCESS = (40, 167, 69)            # Success Green
    WARNING = (255, 149, 0)            # Warning Orange
    ERROR = (255, 59, 48)              # Error Red
    INFO = (0, 122, 255)               # Info Blue
    
    # グラス/ブラー効果用
    GLASS_OVERLAY = (0, 0, 0, 20)      # 暗い色のオーバーレイに変更
    GLASS_HIGHLIGHT = (255, 255, 255, 40)
    GLASS_SHADOW = (0, 0, 0, 60)
   

# --- 高度なパーティクルシステム ---
class ProParticle:
    def __init__(self, x: float, y: float, particle_type: str = "default"):
        self.x = max(0, min(WINDOW_WIDTH, x))
        self.y = max(0, min(WINDOW_HEIGHT, y))
        self.type = particle_type
        
        if particle_type == "neural":
            self.vx = random.uniform(-1, 1)
            self.vy = random.uniform(-1, 1)
            self.size = random.uniform(2, 4)
            self.color = ProColorTheme.NEURAL_PURPLE
            self.connection_range = 120
        elif particle_type == "rhythm":
            self.vx = random.uniform(-2, 2)
            self.vy = random.uniform(-3, -1)
            self.size = random.uniform(3, 8)
            self.color = ProColorTheme.RHYTHM_ORANGE
            self.pulse_speed = random.uniform(2, 5)
        elif particle_type == "robot":
            self.vx = random.uniform(-0.5, 0.5)
            self.vy = random.uniform(-0.5, 0.5)
            self.size = random.uniform(1, 3)
            self.color = ProColorTheme.ROBOT_CYAN
            self.circuit_pattern = random.randint(0, 3)
        else:
            self.vx = random.uniform(-1, 1)
            self.vy = random.uniform(-1, 1)
            self.size = random.uniform(2, 6)
            self.color = ProColorTheme.ELECTRIC_BLUE
            
        self.life = random.uniform(3, 8)
        self.max_life = self.life
        self.rotation = random.uniform(0, 360)
        self.rotation_speed = random.uniform(-30, 30)

    def update(self, dt: float):
        self.x += self.vx * dt * 60
        self.y += self.vy * dt * 60
        self.life -= dt
        self.rotation += self.rotation_speed * dt
        
        # 境界処理
        if self.x < 0 or self.x > WINDOW_WIDTH:
            self.vx *= -0.8
            self.x = max(0, min(WINDOW_WIDTH, self.x))
        if self.y < 0 or self.y > WINDOW_HEIGHT:
            self.vy *= -0.8
            self.y = max(0, min(WINDOW_HEIGHT, self.y))
            
        return self.life > 0

    def draw(self, surface: pygame.Surface):
        if self.life <= 0:
            return
            
        alpha = int(255 * (self.life / self.max_life))
        
        if self.type == "neural":
            # ニューラルネットワーク風の点
            glow_size = int(self.size * 3)
            glow_surf = pygame.Surface((glow_size * 2, glow_size * 2), pygame.SRCALPHA)
            
            # グラデーション付きグロー
            for i in range(glow_size, 0, -1):
                glow_alpha = int(alpha * (glow_size - i) / glow_size * 0.3)
                pygame.draw.circle(glow_surf, (*self.color, glow_alpha), 
                                 (glow_size, glow_size), i)
            
            # コア
            pygame.draw.circle(glow_surf, (*self.color, alpha), 
                             (glow_size, glow_size), int(self.size))
            
            surface.blit(glow_surf, (int(self.x) - glow_size, int(self.y) - glow_size))
            
        elif self.type == "rhythm":
            # リズム波形風のパーティクル
            pulse = math.sin(time.time() * self.pulse_speed) * 0.5 + 0.5
            current_size = int(self.size * (0.8 + pulse * 0.4))
            
            # パルス効果
            pulse_surf = pygame.Surface((current_size * 4, current_size * 4), pygame.SRCALPHA)
            center = (current_size * 2, current_size * 2)
            
            for ring in range(3):
                ring_alpha = int(alpha * (1 - ring * 0.3) * pulse)
                ring_size = current_size + ring * current_size
                pygame.draw.circle(pulse_surf, (*self.color, ring_alpha), 
                                 center, ring_size, max(1, ring_size // 4))
            
            surface.blit(pulse_surf, (int(self.x) - current_size * 2, 
                                    int(self.y) - current_size * 2))
            
        elif self.type == "robot":
            # ロボット回路風のパーティクル
            circuit_surf = pygame.Surface((int(self.size * 6), int(self.size * 6)), pygame.SRCALPHA)
            center = (int(self.size * 3), int(self.size * 3))
            
            # 回転する四角形
            angle_rad = math.radians(self.rotation)
            cos_a, sin_a = math.cos(angle_rad), math.sin(angle_rad)
            
            # 四角形の頂点を計算
            points = []
            for dx, dy in [(-1, -1), (1, -1), (1, 1), (-1, 1)]:
                x = center[0] + (dx * self.size * cos_a - dy * self.size * sin_a)
                y = center[1] + (dx * self.size * sin_a + dy * self.size * cos_a)
                points.append((x, y))
            
            # 回路パターン描画
            pygame.draw.polygon(circuit_surf, (*self.color, alpha), points)
            pygame.draw.polygon(circuit_surf, (*self.color, alpha // 2), points, 1)
            
            # 接続線
            if self.circuit_pattern % 2 == 0:
                pygame.draw.line(circuit_surf, (*self.color, alpha // 3),
                               (0, center[1]), (circuit_surf.get_width(), center[1]), 1)
            if self.circuit_pattern // 2 == 1:
                pygame.draw.line(circuit_surf, (*self.color, alpha // 3),
                               (center[0], 0), (center[0], circuit_surf.get_height()), 1)
            
            surface.blit(circuit_surf, (int(self.x) - self.size * 3, 
                                      int(self.y) - self.size * 3))

class ProParticleSystem:
    def __init__(self):
        self.particles: List[ProParticle] = []
        self.neural_connections = []

    def emit_neural_burst(self, x: float, y: float, count: int = 30):
        for _ in range(min(count, 50)):
            particle = ProParticle(
                x + random.uniform(-50, 50),
                y + random.uniform(-50, 50),
                "neural"
            )
            self.particles.append(particle)

    def emit_rhythm_pulse(self, x: float, y: float, count: int = 15):
        for _ in range(min(count, 25)):
            particle = ProParticle(
                x + random.uniform(-30, 30),
                y + random.uniform(-30, 30),
                "rhythm"
            )
            self.particles.append(particle)

    def emit_robot_pattern(self, x: float, y: float, count: int = 20):
        for _ in range(min(count, 30)):
            particle = ProParticle(
                x + random.uniform(-40, 40),
                y + random.uniform(-40, 40),
                "robot"
            )
            self.particles.append(particle)

    def update(self, dt: float):
        pass
        

    def draw(self, surface: pygame.Surface):
        pass

# --- プロ級ボタンコンポーネント ---
class MaterialButton:
    def __init__(self, text: str, pos: Tuple[int, int], font: pygame.font.Font,
                 width: int = 280, height: int = 64, button_type: str = "elevated"):
        self.text = text
        self.pos = pos
        self.font = font
        self.width = width
        self.height = height
        self.type = button_type  # "elevated", "filled", "outlined", "text"
        
        self.rect = pygame.Rect(0, 0, width, height)
        self.rect.center = pos
        
        # アニメーション状態
        self.elevation = 3 if button_type == "elevated" else 0
        self.target_elevation = self.elevation
        self.hover_progress = 0.0
        self.press_progress = 0.0
        self.focus_progress = 0.0
        self.ripple_effects = []
        
        # Material Design状態
        self.is_hovered = False
        self.is_pressed = False
        self.is_focused = False
        
        # パーティクルシステム
        self.particles = ProParticleSystem()
        
        # カラー設定
        self._setup_colors()

    def _setup_colors(self):
        if self.type == "elevated":
            self.bg_color = ProColorTheme.SURFACE_01
            self.text_color = ProColorTheme.ON_SURFACE
            self.accent_color = ProColorTheme.ELECTRIC_BLUE
        elif self.type == "filled":
            self.bg_color = ProColorTheme.ELECTRIC_BLUE
            self.text_color = ProColorTheme.ON_SURFACE
            self.accent_color = ProColorTheme.NEON_ACCENT
        elif self.type == "outlined":
            # 透明色ではなく、薄い背景色を使用
            self.bg_color = ProColorTheme.SURFACE_01
            self.text_color = ProColorTheme.ELECTRIC_BLUE
            self.accent_color = ProColorTheme.ELECTRIC_BLUE

    def update(self, dt: float):
        # スムーズなアニメーション
        target_hover = 1.0 if self.is_hovered else 0.0
        target_press = 1.0 if self.is_pressed else 0.0
        target_focus = 1.0 if self.is_focused else 0.0
        
        self.hover_progress += (target_hover - self.hover_progress) * dt * 8
        self.press_progress += (target_press - self.press_progress) * dt * 12
        self.focus_progress += (target_focus - self.focus_progress) * dt * 6
        
        # エレベーション計算
        if self.type == "elevated":
            self.target_elevation = 3 + self.hover_progress * 5 - self.press_progress * 2
        elif self.type == "filled":
            self.target_elevation = 1 + self.hover_progress * 2
        
        self.elevation += (self.target_elevation - self.elevation) * dt * 10
        
        # パーティクル更新
        self.particles.update(dt)
        
        # リップル効果更新
        self.ripple_effects = [(x, y, t + dt, max_t) for x, y, t, max_t in self.ripple_effects if t < max_t]
        
        # ホバー時のパーティクル放出
        if self.is_hovered and random.random() < 0.1:
            particle_type = random.choice(["neural", "robot"])
            if particle_type == "neural":
                self.particles.emit_neural_burst(self.pos[0], self.pos[1], 5)
            else:
                self.particles.emit_robot_pattern(self.pos[0], self.pos[1], 3)

    def handle_event(self, event: pygame.event.Event) -> bool:
        if event.type == pygame.MOUSEMOTION:
            self.is_hovered = self.rect.collidepoint(event.pos)
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.rect.collidepoint(event.pos):
                self.is_pressed = True
                # リップル効果を追加
                rel_x = event.pos[0] - self.rect.left
                rel_y = event.pos[1] - self.rect.top
                self.ripple_effects.append((rel_x, rel_y, 0.0, 0.6))
                # パーティクルバースト
                self.particles.emit_rhythm_pulse(event.pos[0], event.pos[1], 20)
        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            if self.is_pressed and self.rect.collidepoint(event.pos):
                self.is_pressed = False
                return True
            self.is_pressed = False
        return False

    def draw_shadow(self, surface: pygame.Surface):
        if self.elevation <= 0:
            return
            
        shadow_offset = int(self.elevation * 0.5)
        shadow_blur = int(self.elevation * 1.5)
        shadow_alpha = int(min(80, self.elevation * 10))
        
        # 複数の影を重ねてブラー効果を近似
        for i in range(shadow_blur):
            alpha = int(shadow_alpha / (i + 1))
            shadow_rect = self.rect.copy()
            shadow_rect.x += shadow_offset + i
            shadow_rect.y += shadow_offset + i
            
            shadow_surf = pygame.Surface((shadow_rect.width, shadow_rect.height), pygame.SRCALPHA)
            pygame.draw.rect(shadow_surf, (0, 0, 0, alpha), 
                           (0, 0, shadow_rect.width, shadow_rect.height), 
                           border_radius=12)
            surface.blit(shadow_surf, shadow_rect)

    def draw_background(self, surface: pygame.Surface):
        # ベース背景
        bg_surf = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
        
        if self.type == "outlined":
            # アウトライン背景
            pygame.draw.rect(bg_surf, (*ProColorTheme.SURFACE_01, int(50 + self.hover_progress * 30)),
                           (0, 0, self.width, self.height), border_radius=12)
            pygame.draw.rect(bg_surf, (*self.accent_color, int(150 + self.hover_progress * 105)),
                           (0, 0, self.width, self.height), width=2, border_radius=12)
        else:
            # フィル背景
            # ホバー時の色の変化（安全な計算）
            hover_overlay = int(self.hover_progress * 20)
            press_overlay = int(self.press_progress * 40)
            
            base_color = self.bg_color
            # 色の値を安全な範囲に制限
            modified_color = (
                max(0, min(255, base_color[0] + hover_overlay - press_overlay)),
                max(0, min(255, base_color[1] + hover_overlay - press_overlay)), 
                max(0, min(255, base_color[2] + hover_overlay - press_overlay))
            )
            
            # アルファチャンネルがある場合の処理
            if len(base_color) == 4:
                modified_color = (*modified_color, max(0, min(255, base_color[3])))
            
            pygame.draw.rect(bg_surf, modified_color, (0, 0, self.width, self.height), 
                           border_radius=12)
        
        # ステート層（Material Design）
        state_alpha = int(self.hover_progress * 8 + self.press_progress * 12)
        if state_alpha > 0:

            pygame.draw.rect(bg_surf, (*ProColorTheme.ON_SURFACE, state_alpha),
                           (0, 0, self.width, self.height), border_radius=12)
        
        surface.blit(bg_surf, self.rect)

    def draw_ripples(self, surface: pygame.Surface):
        for rel_x, rel_y, t, max_t in self.ripple_effects:
            progress = t / max_t
            max_radius = math.sqrt(self.width**2 + self.height**2)
            current_radius = int(max_radius * progress)
            alpha = int(40 * (1 - progress))
            
            if alpha > 0:
                ripple_surf = pygame.Surface((current_radius * 2, current_radius * 2), pygame.SRCALPHA)
                pygame.draw.circle(ripple_surf, (*ProColorTheme.ON_SURFACE, alpha),
                                 (current_radius, current_radius), current_radius)
                
                # クリップ
                clipped_surf = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
                clipped_surf.blit(ripple_surf, (rel_x - current_radius, rel_y - current_radius))
                
                mask_surf = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
                pygame.draw.rect(mask_surf, (255, 255, 255, 255),
                               (0, 0, self.width, self.height), border_radius=12)
                
                result_surf = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
                result_surf.blit(clipped_surf, (0, 0))
                result_surf.blit(mask_surf, (0, 0), special_flags=pygame.BLEND_ALPHA_SDL2)
                
                surface.blit(result_surf, self.rect)

    def draw_focus_ring(self, surface: pygame.Surface):
        if self.focus_progress > 0:
            focus_alpha = int(self.focus_progress * 60)
            focus_rect = self.rect.inflate(8, 8)
            
            focus_surf = pygame.Surface((focus_rect.width, focus_rect.height), pygame.SRCALPHA)
            pygame.draw.rect(focus_surf, (*self.accent_color, focus_alpha),
                           (0, 0, focus_rect.width, focus_rect.height),
                           width=3, border_radius=15)
            surface.blit(focus_surf, focus_rect)

    def draw(self, surface: pygame.Surface):
        # 影
        self.draw_shadow(surface)
        
        # フォーカスリング
        self.draw_focus_ring(surface)
        
        # 背景
        self.draw_background(surface)
        
        # リップル効果
        self.draw_ripples(surface)
        
        # パーティクル
        self.particles.draw(surface)
        
        # テキスト
        text_surf = self.font.render(self.text, True, self.text_color)
        text_rect = text_surf.get_rect(center=self.pos)
        surface.blit(text_surf, text_rect)

    def set_text(self, new_text: str):
        self.text = new_text

# --- プロ仕様の背景システム ---
class ProBackground:
    def __init__(self):
        self.time = 0
        self.grid_animation = 0
        self.neural_networks = []
        self.robot_circuits = []
        self.rhythm_waves = []
        
        # ニューラルネットワーク風の背景要素
        for _ in range(8):
            self.neural_networks.append({
                'nodes': [(random.randint(100, WINDOW_WIDTH-100), 
                          random.randint(100, WINDOW_HEIGHT-100)) for _ in range(random.randint(4, 8))],
                'connections': [],
                'pulse_phase': random.uniform(0, math.pi * 2),
                'pulse_speed': random.uniform(0.5, 2.0)
            })
        
        # ロボット回路パターン
        for _ in range(12):
            self.robot_circuits.append({
                'x': random.randint(0, WINDOW_WIDTH),
                'y': random.randint(0, WINDOW_HEIGHT),
                'pattern': random.randint(0, 3),
                'size': random.uniform(20, 60),
                'rotation': random.uniform(0, 360),
                'rotation_speed': random.uniform(-20, 20),
                'alpha': random.uniform(10, 30)
            })
        
        # リズム波形
        self.rhythm_frequencies = [random.uniform(0.5, 3.0) for _ in range(6)]
        self.rhythm_phases = [random.uniform(0, math.pi * 2) for _ in range(6)]

    def update(self, dt: float):
        self.time += dt
        self.grid_animation = (self.time * 0.2) % 1.0
        
        # ニューラルネットワークの更新
        for network in self.neural_networks:
            # ノードの軽微な移動
            for i, (x, y) in enumerate(network['nodes']):
                offset = math.sin(self.time * 0.5 + i) * 5
                network['nodes'][i] = (x + offset, y + math.cos(self.time * 0.3 + i) * 3)
            
            # 接続の再計算
            network['connections'].clear()
            nodes = network['nodes']
            for i, node1 in enumerate(nodes):
                for j, node2 in enumerate(nodes[i+1:], i+1):
                    distance = math.sqrt((node1[0] - node2[0])**2 + (node1[1] - node2[1])**2)
                    if distance < 150:
                        network['connections'].append((i, j, distance))
        
        # ロボット回路の更新
        for circuit in self.robot_circuits:
            circuit['rotation'] += circuit['rotation_speed'] * dt
            circuit['alpha'] = 15 + math.sin(self.time * 2 + circuit['x'] * 0.01) * 10

    def draw_grid(self, surface: pygame.Surface):
        surface.fill(ProColorTheme.SURFACE_00)

    def draw_neural_networks(self, surface: pygame.Surface):
        for network in self.neural_networks:
            pulse = math.sin(self.time * network['pulse_speed'] + network['pulse_phase']) * 0.5 + 0.5
            
            # 接続線
            for i, j, distance in network['connections']:
                strength = 1 - (distance / 150)
                alpha = int(30 * strength * pulse)
                if alpha > 0:
                    pygame.draw.line(surface, (*ProColorTheme.NEURAL_PURPLE, alpha),
                                   network['nodes'][i], network['nodes'][j], 1)
            
            # ノード
            for i, (x, y) in enumerate(network['nodes']):
                node_pulse = math.sin(self.time * 3 + i) * 0.3 + 0.7
                size = int(4 * node_pulse)
                alpha = int(100 * pulse)
                
                if size > 0 and alpha > 0:
                    node_surf = pygame.Surface((size * 4, size * 4), pygame.SRCALPHA)
                    center = (size * 2, size * 2)
                    
                    # グロー効果
                    for glow_size in range(size * 2, size, -1):
                        glow_alpha = int(alpha * (size * 2 - glow_size) / size)
                        pygame.draw.circle(node_surf, (*ProColorTheme.NEURAL_PURPLE, glow_alpha),
                                         center, glow_size)
                    
                    # コア
                    pygame.draw.circle(node_surf, (*ProColorTheme.NEURAL_PURPLE, alpha),
                                     center, size)
                    
                    surface.blit(node_surf, (int(x) - size * 2, int(y) - size * 2))

    def draw_robot_circuits(self, surface: pygame.Surface):
        for circuit in self.robot_circuits:
            circuit_surf = pygame.Surface((int(circuit['size'] * 2), int(circuit['size'] * 2)), pygame.SRCALPHA)
            center = (int(circuit['size']), int(circuit['size']))
            
            # 回転角度
            angle_rad = math.radians(circuit['rotation'])
            cos_a, sin_a = math.cos(angle_rad), math.sin(angle_rad)
            
            # 回路パターン
            if circuit['pattern'] == 0:
                # 十字パターン
                size = circuit['size'] * 0.8
                # 水平線
                start_h = (center[0] + (-size * cos_a), center[1] + (-size * sin_a))
                end_h = (center[0] + (size * cos_a), center[1] + (size * sin_a))
                pygame.draw.line(circuit_surf, (*ProColorTheme.ROBOT_CYAN, int(circuit['alpha'])),
                               start_h, end_h, 2)
                
                # 垂直線
                start_v = (center[0] + (-size * sin_a), center[1] + (size * cos_a))
                end_v = (center[0] + (size * sin_a), center[1] + (-size * cos_a))
                pygame.draw.line(circuit_surf, (*ProColorTheme.ROBOT_CYAN, int(circuit['alpha'])),
                               start_v, end_v, 2)
                
            elif circuit['pattern'] == 1:
                # 六角形パターン
                points = []
                for i in range(6):
                    angle = angle_rad + i * math.pi / 3
                    x = center[0] + math.cos(angle) * circuit['size'] * 0.6
                    y = center[1] + math.sin(angle) * circuit['size'] * 0.6
                    points.append((x, y))
                
                if len(points) >= 3:
                    pygame.draw.polygon(circuit_surf, (*ProColorTheme.ROBOT_CYAN, int(circuit['alpha'] * 0.5)), points)
                    pygame.draw.polygon(circuit_surf, (*ProColorTheme.ROBOT_CYAN, int(circuit['alpha'])), points, 2)
                    
            elif circuit['pattern'] == 2:
                # 回路基板パターン
                size = circuit['size'] * 0.7
                # L字パターン
                points = [
                    (center[0] + (-size * cos_a), center[1] + (-size * sin_a)),
                    (center[0] + (0 * cos_a - size * sin_a), center[1] + (0 * sin_a + size * cos_a)),
                    (center[0] + (size * cos_a - size * sin_a), center[1] + (size * sin_a + size * cos_a)),
                    (center[0] + (size * cos_a), center[1] + (size * sin_a))
                ]
                
                for i in range(len(points) - 1):
                    pygame.draw.line(circuit_surf, (*ProColorTheme.ROBOT_CYAN, int(circuit['alpha'])),
                                   points[i], points[i + 1], 2)
                    
            else:
                # 菱形パターン
                points = []
                for i in range(4):
                    angle = angle_rad + i * math.pi / 2 + math.pi / 4
                    x = center[0] + math.cos(angle) * circuit['size'] * 0.5
                    y = center[1] + math.sin(angle) * circuit['size'] * 0.5
                    points.append((x, y))
                
                if len(points) >= 3:
                    pygame.draw.polygon(circuit_surf, (*ProColorTheme.ROBOT_CYAN, int(circuit['alpha'])), points, 2)
            
            surface.blit(circuit_surf, (int(circuit['x'] - circuit['size']), 
                                      int(circuit['y'] - circuit['size'])))

    def draw_rhythm_waves(self, surface: pygame.Surface):
        wave_height = 80
        base_y = WINDOW_HEIGHT - 150
        
        for wave_idx, (freq, phase) in enumerate(zip(self.rhythm_frequencies, self.rhythm_phases)):
            points = []
            alpha = int(40 - wave_idx * 5)
            color = [ProColorTheme.RHYTHM_ORANGE, ProColorTheme.ELECTRIC_BLUE, 
                    ProColorTheme.NEON_ACCENT][wave_idx % 3]
            
            for x in range(0, WINDOW_WIDTH, 4):
                y = base_y + math.sin(self.time * freq + x * 0.01 + phase) * wave_height / (wave_idx + 1)
                points.append((x, int(y)))
            
            if len(points) > 2:
                for i in range(len(points) - 1):
                    pygame.draw.line(surface, (*color, alpha), points[i], points[i + 1], 1)

    def draw(self, surface: pygame.Surface):
        # ベースグラデーション
        for y in range(WINDOW_HEIGHT):
            progress = y / WINDOW_HEIGHT
            wave = math.sin(self.time * 0.3 + progress * 2) * 0.05 + 0.95
            
            r_val = ProColorTheme.SURFACE_00[0] * wave
            g_val = ProColorTheme.SURFACE_00[1] * wave + progress * 8
            b_val = ProColorTheme.SURFACE_00[2] * wave + progress * 12
            
            # 0から255の範囲に値を制限してから整数に変換
            r = max(0, min(255, int(r_val)))
            g = max(0, min(255, int(g_val)))
            b = max(0, min(255, int(b_val)))
            
            pygame.draw.line(surface, (r, g, b), (0, y), (WINDOW_WIDTH, y))
        
        # 各レイヤーを描画
        self.draw_grid(surface)
        self.draw_neural_networks(surface)
        self.draw_robot_circuits(surface)
        self.draw_rhythm_waves(surface)


# --- プロ級タイトルシステム ---
class ProTitle:
    def __init__(self, font: pygame.font.Font):
        self.font = font
        # フォントのパスを取得してより大きなサイズのフォントを作成
        try:
            # フォントファイルのパスを取得
            if hasattr(font, 'get_name'):
                font_name = font.get_name()
                self.large_font = pygame.font.SysFont(font_name, 72)
            else:
                # システムフォントを使用
                self.large_font = pygame.font.SysFont("arial", 72, bold=True)
        except:
            # フォールバック: デフォルトフォント
            self.large_font = pygame.font.Font(None, 72)
        
        self.time = 0
        self.particles = ProParticleSystem()
        
        # タイトルテキスト
        self.main_title = "Rhythm Trauning System"
        self.subtitle = "Training with Dobot Magician"
        
        # アニメーション要素
        self.title_glow = 0
        self.letter_animations = []
        for i in range(len(self.main_title)):
            self.letter_animations.append({
                'offset_y': 0,
                'scale': 1.0,
                'hue_shift': i * 0.1,
                'pulse_phase': i * 0.3
            })

    def update(self, dt: float):
        self.time += dt
        self.particles.update(dt)
        
        # タイトル文字のアニメーション
        for i, anim in enumerate(self.letter_animations):
            anim['offset_y'] = math.sin(self.time * 2 + anim['pulse_phase']) * 8
            anim['scale'] = 1.0 + math.sin(self.time * 3 + anim['pulse_phase']) * 0.1
            anim['hue_shift'] = (self.time * 0.1 + i * 0.1) % 1.0
        
        # グロー強度
        self.title_glow = 30 + math.sin(self.time * 2) * 20
        
        # パーティクル放出
        if random.random() < 0.3:
            self.particles.emit_neural_burst(WINDOW_WIDTH // 2, 120, 3)
        if random.random() < 0.2:
            self.particles.emit_robot_pattern(WINDOW_WIDTH // 2 + random.uniform(-200, 200), 120, 2)

    def draw_holographic_text(self, surface: pygame.Surface, text: str, font: pygame.font.Font, 
                             center_pos: Tuple[int, int], use_animation: bool = True):
        total_width = font.size(text)[0]
        start_x = center_pos[0] - total_width // 2
        current_x = start_x
        
        for i, char in enumerate(text):
            if use_animation and i < len(self.letter_animations):
                anim = self.letter_animations[i]
                
                # HSV色空間での色生成（安全な範囲）
                hue = max(0.0, min(1.0, anim['hue_shift']))
                rgb = tuple(int(max(0, min(255, c * 255))) for c in colorsys.hsv_to_rgb(hue, 0.8, 1.0))
                
                # 3Dエフェクト用の複数レイヤー
                for layer in range(3):
                    layer_offset_x = math.sin(self.time * 1.5 + i * 0.2 + layer * 0.5) * (3 - layer)
                    layer_offset_y = math.cos(self.time * 1.2 + i * 0.3 + layer * 0.5) * (2 - layer)
                    
                    layer_alpha = max(50, 200 - layer * 50)  # アルファも安全な範囲に
                    layer_color = (
                        max(0, min(255, rgb[0] + layer * 20)),
                        max(0, min(255, rgb[1] + layer * 15)), 
                        max(0, min(255, rgb[2] + layer * 25))
                    )
                    
                    # スケール適用
                    scaled_font = font  # フォントスケーリングは複雑なので一旦無効化
                    
                    char_surf = scaled_font.render(char, True, layer_color)
                    
                    # グロー効果
                    if layer == 0 and self.title_glow > 0:
                        glow_size = max(10, int(self.title_glow))
                        glow_surf = pygame.Surface((char_surf.get_width() + glow_size, 
                                                  char_surf.get_height() + glow_size), pygame.SRCALPHA)
                        
                        # グローレイヤー（安全な範囲で）
                        for glow_layer in range(min(5, glow_size // 5)):
                            glow_alpha = max(10, min(100, 60 // (glow_layer + 1)))
                            glow_color = (*rgb, glow_alpha)
                            glow_char = scaled_font.render(char, True, rgb)  # アルファ付き色は避ける
                            glow_offset = glow_layer * 2
                            glow_surf.blit(glow_char, (glow_offset, glow_offset))
                        
                        surface.blit(glow_surf, (current_x + layer_offset_x - glow_size // 2, 
                                               center_pos[1] + anim['offset_y'] + layer_offset_y - glow_size // 2))
                    
                    surface.blit(char_surf, (current_x + layer_offset_x, 
                                           center_pos[1] + anim['offset_y'] + layer_offset_y))
            else:
                # 通常の描画
                char_surf = font.render(char, True, ProColorTheme.ON_SURFACE)
                surface.blit(char_surf, (current_x, center_pos[1]))
            
            current_x += font.size(char)[0]

    def draw(self, surface: pygame.Surface):
        title_surf = self.large_font.render(self.main_title, True, ProColorTheme.ON_SURFACE)
        title_rect = title_surf.get_rect(center=(WINDOW_WIDTH // 2, 120))
        surface.blit(title_surf, title_rect)

        # サブタイトル
        subtitle_surf = self.font.render(self.subtitle, True, ProColorTheme.ON_SURFACE_VARIANT)
        subtitle_rect = subtitle_surf.get_rect(center=(WINDOW_WIDTH // 2, 180))
        surface.blit(subtitle_surf, subtitle_rect)

# --- 次世代ポップアップ ---
class ProPopup:
    def __init__(self, font: pygame.font.Font, title: str, message: str, popup_type: str = "warning"):
        self.title = title
        self.message = message
        self.font = font
        self.type = popup_type  # "warning", "error", "info", "success"
        
        # サイズ計算
        self.width = 480
        self.height = 320
        self.rect = pygame.Rect((WINDOW_WIDTH - self.width) // 2, 
                               (WINDOW_HEIGHT - self.height) // 2, 
                               self.width, self.height)
        
        # ボタン
        self.ok_button = MaterialButton("OK", 
                                      (self.rect.centerx, self.rect.bottom - 50), 
                                      font, width=120, height=48, button_type="filled")
        
        # アニメーション
        self.scale = 0.0
        self.target_scale = 1.0
        self.backdrop_alpha = 0.0
        self.time = 0.0
        
        # エフェクト
        self.particles = ProParticleSystem()
        self.icon_particles = ProParticleSystem()
        
        # 色設定
        self.setup_colors()
        
        # 初期エフェクト
        self.particles.emit_neural_burst(self.rect.centerx, self.rect.centery, 50)

    def setup_colors(self):
        if self.type == "warning":
            self.accent_color = ProColorTheme.WARNING
            self.icon_color = ProColorTheme.WARNING
        elif self.type == "error":
            self.accent_color = ProColorTheme.ERROR
            self.icon_color = ProColorTheme.ERROR
        elif self.type == "info":
            self.accent_color = ProColorTheme.INFO
            self.icon_color = ProColorTheme.INFO
        else:  # success
            self.accent_color = ProColorTheme.SUCCESS
            self.icon_color = ProColorTheme.SUCCESS

    def update(self, dt: float):
        self.time += dt
        
        # スムーズアニメーション
        self.scale += (self.target_scale - self.scale) * dt * 8
        self.backdrop_alpha = min(0.7, self.backdrop_alpha + dt * 3)
        
        # エフェクト更新
        self.particles.update(dt)
        self.icon_particles.update(dt)
        self.ok_button.update(dt)
        
        # アイコン周辺のエフェクト
        if random.random() < 0.3:
            self.icon_particles.emit_rhythm_pulse(self.rect.centerx, self.rect.top + 80, 3)

    def handle_event(self, event: pygame.event.Event) -> bool:
        return self.ok_button.handle_event(event)

    def draw_backdrop(self, surface: pygame.Surface):
        # プロ級背景ブラー
        backdrop_surf = pygame.Surface((WINDOW_WIDTH, WINDOW_HEIGHT), pygame.SRCALPHA)
        
        # 放射状グラデーション
        center_x, center_y = WINDOW_WIDTH // 2, WINDOW_HEIGHT // 2
        max_radius = math.sqrt(center_x**2 + center_y**2)
        
        for radius in range(int(max_radius), 0, -20):
            alpha = int(self.backdrop_alpha * 180 * (1 - radius / max_radius))
            pygame.draw.circle(backdrop_surf, (*ProColorTheme.SURFACE_00, alpha), 
                             (center_x, center_y), radius)
        
        surface.blit(backdrop_surf, (0, 0))

    def draw_icon(self, surface: pygame.Surface):
        icon_size = 48
        icon_center = (self.rect.centerx, self.rect.top + 80)
        
        # アイコンのパルス効果
        pulse = math.sin(self.time * 4) * 0.2 + 0.8
        current_size = int(icon_size * pulse)
        
        # 背景円
        circle_surf = pygame.Surface((current_size * 3, current_size * 3), pygame.SRCALPHA)
        center = (current_size * 1.5, current_size * 1.5)
        
        # グラデーション円
        for i in range(current_size, 0, -2):
            alpha = int(100 * (current_size - i) / current_size)
            pygame.draw.circle(circle_surf, (*self.icon_color, alpha), center, i)
        
        surface.blit(circle_surf, (icon_center[0] - current_size * 1.5, 
                                 icon_center[1] - current_size * 1.5))
        
        # アイコンシンボル
        if self.type == "warning":
            # 警告三角形
            triangle_height = current_size
            points = [
                (icon_center[0], icon_center[1] - triangle_height // 2),
                (icon_center[0] - triangle_height // 2, icon_center[1] + triangle_height // 2),
                (icon_center[0] + triangle_height // 2, icon_center[1] + triangle_height // 2)
            ]
            pygame.draw.polygon(surface, ProColorTheme.ON_SURFACE, points)
            pygame.draw.polygon(surface, self.icon_color, points, 3)
            
            # 感嘆符
            exclamation_font = pygame.font.Font(None, int(current_size * 0.6))
            exclamation_surf = exclamation_font.render("!", True, self.icon_color)
            exclamation_rect = exclamation_surf.get_rect(center=icon_center)
            surface.blit(exclamation_surf, exclamation_rect)

    def draw_content(self, surface: pygame.Surface):
        if self.scale < 0.3:
            return
            
        # メインコンテナ
        container_surf = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
        
        # Material Design カード背景
        # 複数レイヤーでグラスモーフィズム効果
        for layer in range(3):
            layer_alpha = 60 - layer * 15
            layer_surf = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
            
            # グラデーション背景
            for y in range(self.height):
                progress = y / self.height
                wave = math.sin(self.time + progress * 2 + layer) * 0.1 + 0.9
                
                r_val = (ProColorTheme.SURFACE_02[0] + layer * 5) * wave
                g_val = (ProColorTheme.SURFACE_02[1] + layer * 7) * wave
                b_val = (ProColorTheme.SURFACE_02[2] + layer * 10) * wave

                r = max(0, min(255, int(r_val)))
                g = max(0, min(255, int(g_val)))
                b = max(0, min(255, int(b_val)))
                
                pygame.draw.line(layer_surf, (r, g, b, layer_alpha), (0, y), (self.width, y))
        
        container_surf.blit(layer_surf, (0, 0))
        # ボーダー
        pygame.draw.rect(container_surf, (*self.accent_color, 150), 
                        (0, 0, self.width, self.height), width=2, border_radius=16)
        
        # スケール適用
        if self.scale != 1.0:
            scaled_width = int(self.width * self.scale)
            scaled_height = int(self.height * self.scale)
            container_surf = pygame.transform.smoothscale(container_surf, (scaled_width, scaled_height))
            draw_rect = container_surf.get_rect(center=self.rect.center)
        else:
            draw_rect = self.rect
        
        surface.blit(container_surf, draw_rect)

    def draw_text(self, surface: pygame.Surface):
        if self.scale < 0.7:
            return
            
        # タイトル
        title_surf = self.font.render(self.title, True, self.accent_color)
        title_rect = title_surf.get_rect(center=(self.rect.centerx, self.rect.top + 140))
        surface.blit(title_surf, title_rect)
        
        # メッセージ（複数行対応）
        lines = self.message.split('\n')
        line_height = self.font.get_height() + 8
        total_height = len(lines) * line_height
        start_y = self.rect.centery - total_height // 2 + 50
        
        for i, line in enumerate(lines):
            # 文字ごとのカラーバリエーション
            line_surf = pygame.Surface(self.font.size(line), pygame.SRCALPHA)
            x_offset = 0
            
            for j, char in enumerate(line):
                char_time = self.time * 2 + i * 0.5 + j * 0.1
                brightness = 0.7 + math.sin(char_time) * 0.2
                
                char_color = (
                    int(ProColorTheme.ON_SURFACE_VARIANT[0] * brightness),
                    int(ProColorTheme.ON_SURFACE_VARIANT[1] * brightness),
                    int(ProColorTheme.ON_SURFACE_VARIANT[2] * brightness)
                )
                
                char_surf = self.font.render(char, True, char_color)
                line_surf.blit(char_surf, (x_offset, 0))
                x_offset += char_surf.get_width()
            
            line_rect = line_surf.get_rect(center=(self.rect.centerx, start_y + i * line_height))
            surface.blit(line_surf, line_rect)

    def draw(self, surface: pygame.Surface):
        # 背景
        self.draw_backdrop(surface)
        
        # パーティクル
        self.particles.draw(surface)
        
        # メインコンテンツ
        self.draw_content(surface)
        
        # アイコン
        if self.scale > 0.5:
            self.icon_particles.draw(surface)
            self.draw_icon(surface)
        
        # テキスト
        self.draw_text(surface)
        
        # ボタン
        if self.scale > 0.9:
            self.ok_button.draw(surface)

# --- MIDI接続チェック ---
def is_midi_device_connected():
    pygame.midi.init()
    found_input_device = False
    for i in range(pygame.midi.get_count()):
        info = pygame.midi.get_device_info(i)
        if info[2] == 1:
            print(f"MIDI入力デバイスが見つかりました: {info[1].decode()}")
            found_input_device = True
            break
    pygame.midi.quit()
    return found_input_device

# --- メイン関数 ---
def home_screen_enhanced():
    """次世代リズム練習システム ホーム画面"""
    pygame.init()
    screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
    pygame.display.set_caption("リズム練習システム - AI-Powered Rhythm Training System")
    clock = pygame.time.Clock()
    
    # フォント設定
    try:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        font_path = os.path.join(script_dir, "NotoSansJP-Regular.ttf")
        if os.path.exists(font_path):
            title_font = pygame.font.Font(font_path, 36)
            button_font = pygame.font.Font(font_path, 20)
            small_font = pygame.font.Font(font_path, 16)
            print("日本語フォントを読み込みました。")
        else:
            raise FileNotFoundError("フォントファイルが見つかりません")
    except (pygame.error, FileNotFoundError):
        print("日本語フォントが見つかりません。システムフォントを使用します。")
        # Windows用の綺麗なフォントを優先的に試す
        font_candidates = ["Yu Gothic UI", "Meiryo UI", "MS Gothic", "arial", "calibri", "segoeui"]
        title_font = None
        
        for font_name in font_candidates:
            try:
                 # スクリプトと同じフォルダにあるフォントファイルを直接指定します
                script_dir = os.path.dirname(os.path.abspath(__file__))
                font_path = os.path.join(script_dir, "NotoSansJP-Regular.ttf")
                
                title_font = pygame.font.Font(font_path, 36)
                button_font = pygame.font.Font(font_path, 20)
                small_font = pygame.font.Font(font_path, 16)
                print("NotoSansJP-Regular.ttf を読み込みました。")
                
            except pygame.error:
                print("エラー: NotoSansJP-Regular.ttf が見つかりません！")
                print("スクリプトと同じフォルダにフォントファイルがあるか確認してください。")
                # フォントがない場合はPygameのデフォルトフォントで続行します
                title_font = pygame.font.Font(None, 38)
                button_font = pygame.font.Font(None, 22)
                small_font = pygame.font.Font(None, 18)
            except:
                continue
        
        # フォールバック
        if title_font is None:
            title_font = pygame.font.Font(None, 38)
            button_font = pygame.font.Font(None, 22)
            small_font = pygame.font.Font(None, 18)

    # UI要素初期化
    background = ProBackground()
    title = ProTitle(title_font)
    
    # モダンボタン
    btn_instructions = MaterialButton("説明書を開く",
                                      (WINDOW_WIDTH // 2, WINDOW_HEIGHT * 0.5), # Y座標を調整
                                      button_font, width=320, height=72, button_type="outlined") # スタイルを変更
    
    # 既存のボタンのY座標を下にずらす
    btn_editor = MaterialButton("リズムを編集する",
                                (WINDOW_WIDTH // 2 - 220, WINDOW_HEIGHT * 0.7), # X, Y座標を調整
                                button_font, width=320, height=72, button_type="elevated")
    
    btn_analyzer = MaterialButton("リズム練習をする",
                                  (WINDOW_WIDTH // 2 + 220, WINDOW_HEIGHT * 0.7), # X, Y座標を調整
                                  button_font, width=320, height=72, button_type="filled")
    # 状態管理
    editor_launch_time = None
    analyzer_launch_time = None
    popup_instance = None

    # メインループ
    while True:
        dt = clock.tick(FPS) / 1000.0
        
        # イベント処理
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            
            if popup_instance:
                if popup_instance.handle_event(event):
                    popup_instance = None
            elif editor_launch_time is None and analyzer_launch_time is None:
                if btn_editor.handle_event(event):
                    print("エディタの起動を1.5秒後に予約しました。")
                    editor_launch_time = time.time()
                    btn_editor.set_text("" \
                    "起動中...")
                    
                if btn_analyzer.handle_event(event):
                    if not is_midi_device_connected():
                        print("MIDI機器が接続されていません。")
                        popup_instance = ProPopup(button_font, 
                                                "MIDI機器が接続されていません", 
                                                "PCにMIDI機器を接続してから\n練習を開始してください", 
                                                "warning")
                    else:
                        print("練習ツールの起動を1.5秒後に予約しました。")
                        analyzer_launch_time = time.time()
                        btn_analyzer.set_text("起動中...")

        # 遅延起動チェック
        if editor_launch_time and (time.time() - editor_launch_time >= 1.5):
            print("楽譜エディタを起動します...")
            run_in_process(rhythm_editor_module_v4.run_editor)
            print("--- ホーム画面に戻りました ---")
            screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))

            editor_launch_time = None
            btn_editor.set_text("楽譜を編集する")
            clock.tick()

        if analyzer_launch_time and (time.time() - analyzer_launch_time >= 1.5):
            print("リズム練習を開始します...")
            run_in_process(training_module_v3.run_drum_trainer)
            print("--- ホーム画面に戻りました ---")

            screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))

            analyzer_launch_time = None
            btn_analyzer.set_text("リズム練習をする")
            clock.tick()

        # 更新
        background.update(dt)
        title.update(dt)
        btn_editor.update(dt)
        btn_analyzer.update(dt)
        
        if popup_instance:
            popup_instance.update(dt)

        # 描画
        background.draw(screen)
        title.draw(screen)
        
        # フィーチャーカード風の情報表示
        info_y = WINDOW_HEIGHT * 0.8
        info_surf = small_font.render(" AI-powered rhythm analysis •  Real-time feedback •  Adaptive learning", 
                                    True, ProColorTheme.ON_SURFACE_VARIANT)
        info_rect = info_surf.get_rect(center=(WINDOW_WIDTH // 2, info_y))
        screen.blit(info_surf, info_rect)
        
        btn_editor.draw(screen)
        btn_analyzer.draw(screen)
        
        if popup_instance:
            popup_instance.draw(screen)
            
        pygame.display.flip()

if __name__ == '__main__':
    home_screen_enhanced()