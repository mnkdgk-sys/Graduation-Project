import mido
import sys

# --- 設定 ---
# この値以上の強さで叩かれた信号のみを表示します
VELOCITY_THRESHOLD = 25 


def check_zones():
    """
    接続されたMIDIデバイスからの入力を待ち受け、メッセージをコンソールに表示します。
    """
    print("--- ドラムパッド ゾーンチェッカー (感度調整版) ---")
    print("MIDIデバイスを接続し、パッドの異なるゾーンを叩いてください。")
    print(f"ベロシティが {VELOCITY_THRESHOLD} 未満の弱い入力は無視されます。")
    print("終了するには Ctrl+C を押してください。")
    print("-" * 45)

    try:
        # PCに接続されている全てのMIDIデバイスからの入力を受け付けます
        with mido.open_input() as inport:
            print("MIDI入力を待っています...")
            
            # メッセージを受信したら、その内容をそのまま表示します
            for msg in inport:
                # 【変更点】note_on かつ、ベロシティが閾値以上の場合のみ表示
                if msg.type == 'note_on' and msg.velocity >= VELOCITY_THRESHOLD:
                    print(msg)

    except OSError:
        print("\nエラー: MIDI入力ポートが見つかりませんでした。")
        print("MIDIデバイスがPCに正しく接続されているか確認してください。")
    except KeyboardInterrupt:
        print("\n診断を終了します。")

if __name__ == '__main__':
    check_zones()