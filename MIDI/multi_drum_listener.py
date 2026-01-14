import mido

# --- 事前設定 ---

# 1. 接続している2つのドラムパッドのデバイス名をリストに記述します
#    (mido.get_input_names() で表示される正確な名前)
DRUM_PAD_NAMES = [
    'DTX Drums',  # 1台目のドラムパッドの名前に書き換える
    'DTX Drums'   # 2台目のドラムパッドの名前に書き換える
]

# 2. ステップ1で調べたノート番号を、分かりやすい名前で定義しておきます
#    (ご自身の環境に合わせて値を書き換えてください)
NOTE_MAPPING = {
    # 'デバイス名': {ノート番号: 'ゾーン名'}
    DRUM_PAD_NAMES[0]: {
        38: 'Head',
        40: 'Rim',
        37: 'Edge'
    },
    DRUM_PAD_NAMES[1]: {
        48: 'High Tom',
        45: 'Low Tom',
        49: 'Crash Cymbal'
    }
}

def run():
    ports = []
    try:
        # 指定された名前のポートをすべて開く
        for name in DRUM_PAD_NAMES:
            ports.append(mido.open_input(name))
        
        print("ドラムパッドからの入力を待っています...")
        print("プログラムを終了するには Ctrl+C を押してください。")

        # 複数のポートからのメッセージを同時に受信
        for msg, port_name in mido.ports.multi_receive(ports, yield_ports=True):
            
            # note_on (叩かれた) メッセージで、かつベロシティが0より大きい場合のみ処理
            if msg.type == 'note_on' and msg.velocity > 0:
                note = msg.note
                velocity = msg.velocity

                # どのパッドから来たメッセージかを表示
                print(f"[{port_name}]が叩かれました！ (Note={note}, Velocity={velocity})")

                # ノート番号からゾーンを特定する
                if port_name in NOTE_MAPPING and note in NOTE_MAPPING[port_name]:
                    zone_name = NOTE_MAPPING[port_name][note]
                    print(f"  -> ゾーン: {zone_name}")
                    
                    # --- ここにゾーンごとの処理を記述 ---
                    if port_name == DRUM_PAD_NAMES[0]: # 1台目のパッドなら
                        if zone_name == 'Head':
                            print("    (1台目のパッドのヘッドに対する処理)")
                        elif zone_name == 'Rim':
                            print("    (1台目のパッドのリムに対する処理)")
                    
                    elif port_name == DRUM_PAD_NAMES[1]: # 2台目のパッドなら
                        if zone_name == 'High Tom':
                            print("    (2台目のパッドのハイタムに対する処理)")

                else:
                    print(f"  -> ゾーン: 不明 (ノート番号 {note} は未登録です)")

    except OSError as e:
        print(f"エラー: MIDIポートを開けませんでした。 {e}")
        print("デバイス名が正しいか、接続されているかを確認してください。")
        print("利用可能なポート:", mido.get_input_names())
    except KeyboardInterrupt:
        print("\nプログラムを終了します。")
    finally:
        # プログラム終了時にすべてのポートを閉じる
        for port in ports:
            port.close()

if __name__ == '__main__':
    run()