import mido
import time

# --- 設定 ---

# 1. パッドとノート番号の対応を設定します
#    'パッドの表示名': [対応するノート番号のリスト]
PAD_MAPPING = {
    '左パッド': [47, 56],
    '右パッド': [48, 29]
}

# 2. 感度の閾値を設定します (この値以上の強さの時だけ反応)
VELOCITY_THRESHOLD = 30

def run():
    print("MIDI入力を待っています...")
    print(f"強さが {VELOCITY_THRESHOLD} 以上の時のみメッセージを表示します。")
    print("プログラムを終了するには Ctrl+C を押してください。")

    try:
        # デバイス名を指定せず、接続されている全てのMIDIポートを開きます
        with mido.open_input() as inport:
            for msg in inport:
                
                # メッセージが 'note_on' で、かつ強さが設定した閾値以上の場合のみ処理
                if msg.type == 'note_on' and msg.velocity >= VELOCITY_THRESHOLD:
                    note = msg.note
                    velocity = msg.velocity
                    
                    # 叩かれたノート番号がどのパッドに属するかを調べる
                    detected_pad = None
                    for pad_name, notes in PAD_MAPPING.items():
                        if note in notes:
                            detected_pad = pad_name
                            break  # 対応するパッドが見つかったらループを抜ける

                    # 結果を出力
                    if detected_pad:
                        print(f"{detected_pad}が叩かれました: ノート番号={note}, 強さ={velocity}")
                    else:
                        # PAD_MAPPINGに登録されていないノート番号が来た場合（デバッグ用）
                        print(f"未登録のパッドが叩かれました: ノート番号={note}, 強さ={velocity}")

    except OSError:
        print("エラー: MIDI入力ポートが見つかりません。")
        print("MIDI機器がPCに正しく接続されているか確認してください。")
    except KeyboardInterrupt:
        print("\nプログラムを終了します。")

if __name__ == '__main__':
    run()