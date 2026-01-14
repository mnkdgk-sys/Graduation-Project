#S利用可能なMIDI入力ポートの名前を一覧表示
import mido
print("利用可能なMIDI入力ポート:", mido.get_input_names())