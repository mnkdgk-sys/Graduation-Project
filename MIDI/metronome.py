import sys
import json
import math
from pathlib import Path
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QPushButton, QLabel, QSlider, QFileDialog,
                             QComboBox, QGroupBox)
from PyQt6.QtCore import QTimer, Qt, pyqtSignal
from PyQt6.QtGui import QPainter, QColor, QPen
from PyQt6.QtMultimedia import QAudioOutput, QMediaPlayer
from PyQt6.QtCore import QUrl
import numpy as np
import wave
import tempfile


class MetronomeEngine:
    """メトロノームのコアエンジン"""
    
    def __init__(self):
        self.bpm = 120
        self.numerator = 4
        self.denominator = 4
        self.is_playing = False
        self.beat_count = 0
        self.current_beat_position = 0.0
        self.items = []
        self.total_beats = 0.0
        
    def set_bpm(self, bpm):
        """BPMを設定"""
        self.bpm = max(40, min(240, bpm))
        
    def set_time_signature(self, numerator, denominator):
        """拍子を設定"""
        self.numerator = numerator
        self.denominator = denominator
        
    def get_interval(self):
        """ビート間隔をミリ秒で取得（4分音符基準）"""
        return int(60000 / self.bpm)
    
    def load_from_json(self, json_path, part='top'):
        """
        JSONファイルからBPM情報を読み込む
        
        Args:
            json_path: JSONファイルのパス
            part: 'top' または 'bottom'
        """
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
                if part in data:
                    part_data = data[part]
                    
                    if 'bpm' in part_data:
                        self.set_bpm(part_data['bpm'])
                    
                    if 'numerator' in part_data and 'denominator' in part_data:
                        self.set_time_signature(
                            part_data['numerator'], 
                            part_data['denominator']
                        )
                    
                    if 'items' in part_data:
                        self.items = part_data['items']
                    
                    if 'total_beats' in part_data:
                        self.total_beats = part_data['total_beats']
                    
                    return True
                else:
                    print(f"パート '{part}' が見つかりません")
                    return False
                    
        except Exception as e:
            print(f"JSONファイル読み込みエラー: {e}")
            return False
    
    def start(self):
        """メトロノーム開始"""
        self.is_playing = True
        self.beat_count = 0
        self.current_beat_position = 0.0
        
    def stop(self):
        """メトロノーム停止"""
        self.is_playing = False
        self.beat_count = 0
        self.current_beat_position = 0.0
        
    def tick(self):
        """1ビート進める"""
        if self.is_playing:
            self.beat_count = (self.beat_count + 1) % self.numerator
            self.current_beat_position += 1.0
            
            # total_beatsを超えたらループ
            if self.total_beats > 0 and self.current_beat_position >= self.total_beats:
                self.current_beat_position = 0.0
                
            return True
        return False


class BeatVisualizer(QWidget):
    """ビートを視覚的に表示するウィジェット"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.beat_position = 0
        self.numerator = 4
        self.is_active = False
        self.setMinimumHeight(100)
        
    def set_beat(self, position, numerator):
        """ビート位置を設定"""
        self.beat_position = position
        self.numerator = numerator
        self.is_active = True
        self.update()
        
    def reset(self):
        """リセット"""
        self.is_active = False
        self.update()
        
    def paintEvent(self, event):
        """描画イベント"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        width = self.width()
        height = self.height()
        
        # 背景
        painter.fillRect(0, 0, width, height, QColor(240, 240, 240))
        
        if self.numerator == 0:
            return
            
        # ビートの円を描画
        circle_radius = 30
        spacing = width / (self.numerator + 1)
        
        for i in range(self.numerator):
            x = int(spacing * (i + 1))
            y = height // 2
            
            # 現在のビートは赤、それ以外は灰色
            if self.is_active and i == self.beat_position:
                painter.setBrush(QColor(255, 80, 80))
                painter.setPen(QPen(QColor(200, 50, 50), 3))
            else:
                painter.setBrush(QColor(200, 200, 200))
                painter.setPen(QPen(QColor(150, 150, 150), 2))
            
            painter.drawEllipse(x - circle_radius, y - circle_radius, 
                              circle_radius * 2, circle_radius * 2)


class MetronomeUI(QMainWindow):
    """メトロノームのUIメインウィンドウ"""
    
    beat_signal = pyqtSignal(int, float)  # (beat_in_measure, total_beat_position)
    
    def __init__(self, engine=None):
        super().__init__()
        self.engine = engine if engine else MetronomeEngine()
        self.timer = QTimer()
        self.timer.timeout.connect(self.on_beat)
        
        # 音声生成
        self.temp_dir = tempfile.mkdtemp()
        self.sound_file_high = self._generate_beep(880, 0.05)  # 高音
        self.sound_file_low = self._generate_beep(440, 0.05)   # 低音
        
        # メディアプレイヤー
        self.audio_output = QAudioOutput()
        self.media_player = QMediaPlayer()
        self.media_player.setAudioOutput(self.audio_output)
        self.audio_output.setVolume(0.7)
        
        self.current_json_path = None
        
        self.init_ui()
        
    def init_ui(self):
        """UIの初期化"""
        self.setWindowTitle('メトロノーム')
        self.setGeometry(100, 100, 600, 500)
        
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        
        # ファイル情報グループ
        file_group = QGroupBox('ファイル情報')
        file_layout = QVBoxLayout()
        
        self.file_label = QLabel('ファイル: 未読込')
        file_layout.addWidget(self.file_label)
        
        # パート選択
        part_layout = QHBoxLayout()
        part_layout.addWidget(QLabel('パート:'))
        self.part_combo = QComboBox()
        self.part_combo.addItems(['top', 'bottom'])
        self.part_combo.currentTextChanged.connect(self.on_part_changed)
        part_layout.addWidget(self.part_combo)
        part_layout.addStretch()
        file_layout.addLayout(part_layout)
        
        file_group.setLayout(file_layout)
        layout.addWidget(file_group)
        
        # ビジュアライザー
        self.visualizer = BeatVisualizer()
        layout.addWidget(self.visualizer)
        
        # 拍子とBPM表示
        info_layout = QHBoxLayout()
        
        self.time_signature_label = QLabel(f'{self.engine.numerator}/{self.engine.denominator}')
        self.time_signature_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.time_signature_label.setStyleSheet('font-size: 28px; font-weight: bold;')
        info_layout.addWidget(self.time_signature_label)
        
        self.bpm_label = QLabel(f'BPM: {self.engine.bpm}')
        self.bpm_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.bpm_label.setStyleSheet('font-size: 28px; font-weight: bold;')
        info_layout.addWidget(self.bpm_label)
        
        layout.addLayout(info_layout)
        
        # 現在位置表示
        self.position_label = QLabel('位置: 0.0 / 0.0')
        self.position_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.position_label.setStyleSheet('font-size: 16px;')
        layout.addWidget(self.position_label)
        
        # BPMスライダー
        slider_layout = QHBoxLayout()
        slider_layout.addWidget(QLabel('40'))
        
        self.bpm_slider = QSlider(Qt.Orientation.Horizontal)
        self.bpm_slider.setMinimum(40)
        self.bpm_slider.setMaximum(240)
        self.bpm_slider.setValue(self.engine.bpm)
        self.bpm_slider.valueChanged.connect(self.on_bpm_changed)
        slider_layout.addWidget(self.bpm_slider)
        
        slider_layout.addWidget(QLabel('240'))
        layout.addLayout(slider_layout)
        
        # コントロールボタン
        button_layout = QHBoxLayout()
        
        self.play_button = QPushButton('再生')
        self.play_button.clicked.connect(self.toggle_playback)
        self.play_button.setStyleSheet('font-size: 16px; padding: 10px;')
        button_layout.addWidget(self.play_button)
        
        self.load_button = QPushButton('JSONを読込')
        self.load_button.clicked.connect(self.load_json)
        self.load_button.setStyleSheet('font-size: 16px; padding: 10px;')
        button_layout.addWidget(self.load_button)
        
        layout.addLayout(button_layout)
        
    def _generate_beep(self, frequency, duration):
        """ビープ音を生成"""
        sample_rate = 44100
        samples = int(sample_rate * duration)
        
        # サイン波を生成
        t = np.linspace(0, duration, samples)
        audio = np.sin(2 * np.pi * frequency * t)
        
        # エンベロープ適用(クリック音を防ぐ)
        envelope = np.ones_like(audio)
        fade_samples = int(sample_rate * 0.01)
        envelope[:fade_samples] = np.linspace(0, 1, fade_samples)
        envelope[-fade_samples:] = np.linspace(1, 0, fade_samples)
        audio = audio * envelope
        
        # 16ビット整数に変換
        audio = (audio * 32767).astype(np.int16)
        
        # WAVファイルとして保存
        temp_file = Path(self.temp_dir) / f'beep_{frequency}.wav'
        with wave.open(str(temp_file), 'w') as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(sample_rate)
            wav_file.writeframes(audio.tobytes())
        
        return str(temp_file)
    
    def on_bpm_changed(self, value):
        """BPM変更時"""
        self.engine.set_bpm(value)
        self.bpm_label.setText(f'BPM: {self.engine.bpm}')
        
        if self.engine.is_playing:
            self.timer.setInterval(self.engine.get_interval())
    
    def toggle_playback(self):
        """再生/停止切り替え"""
        if self.engine.is_playing:
            self.stop()
        else:
            self.start()
    
    def start(self):
        """再生開始"""
        self.engine.start()
        self.play_button.setText('停止')
        self.timer.start(self.engine.get_interval())
        self.visualizer.set_beat(0, self.engine.numerator)
        self.update_position_label()
        
    def stop(self):
        """停止"""
        self.engine.stop()
        self.play_button.setText('再生')
        self.timer.stop()
        self.visualizer.reset()
        self.update_position_label()
        
    def on_beat(self):
        """ビート発生時"""
        self.engine.tick()
        
        # 音を鳴らす(1拍目は高音、それ以外は低音)
        if self.engine.beat_count == 0:
            sound_file = self.sound_file_high
        else:
            sound_file = self.sound_file_low
            
        self.media_player.setSource(QUrl.fromLocalFile(sound_file))
        self.media_player.play()
        
        # ビジュアライザー更新
        self.visualizer.set_beat(self.engine.beat_count, self.engine.numerator)
        
        # 位置表示更新
        self.update_position_label()
        
        # シグナル発行
        self.beat_signal.emit(self.engine.beat_count, self.engine.current_beat_position)
    
    def update_position_label(self):
        """位置ラベルを更新"""
        self.position_label.setText(
            f'位置: {self.engine.current_beat_position:.1f} / {self.engine.total_beats:.1f}'
        )
        
    def load_json(self):
        """JSONファイルを読み込む"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, 'JSONファイルを選択', '', 'JSON Files (*.json)'
        )
        
        if file_path:
            self.current_json_path = file_path
            self.load_current_part()
            
    def on_part_changed(self, part):
        """パート変更時"""
        if self.current_json_path:
            was_playing = self.engine.is_playing
            if was_playing:
                self.stop()
                
            self.load_current_part()
            
            if was_playing:
                self.start()
    
    def load_current_part(self):
        """現在選択されているパートを読み込む"""
        if not self.current_json_path:
            return
            
        part = self.part_combo.currentText()
        
        if self.engine.load_from_json(self.current_json_path, part):
            self.bpm_slider.setValue(self.engine.bpm)
            self.bpm_label.setText(f'BPM: {self.engine.bpm}')
            self.time_signature_label.setText(
                f'{self.engine.numerator}/{self.engine.denominator}'
            )
            self.visualizer.numerator = self.engine.numerator
            self.file_label.setText(f'ファイル: {Path(self.current_json_path).name} ({part})')
            self.update_position_label()
    
    def closeEvent(self, event):
        """ウィンドウクローズ時のクリーンアップ"""
        self.stop()
        # 一時ファイル削除
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
        event.accept()


def create_metronome(bpm=120, numerator=4, denominator=4):
    """
    メトロノームインスタンスを作成する関数
    
    Args:
        bpm: 初期BPM値
        numerator: 拍子の分子
        denominator: 拍子の分母
        
    Returns:
        MetronomeEngine, MetronomeUI: エンジンとUIのタプル
    """
    engine = MetronomeEngine()
    engine.set_bpm(bpm)
    engine.set_time_signature(numerator, denominator)
    ui = MetronomeUI(engine)
    return engine, ui


if __name__ == '__main__':
    app = QApplication(sys.argv)
    engine, ui = create_metronome(120, 4, 4)
    ui.show()
    sys.exit(app.exec())