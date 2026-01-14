# robot_control_module.py (同調制御ロジック統合版)

#-----------ライブラリのインポート-----------
import time
import threading
from PyQt6.QtCore import QObject, pyqtSignal, QThread

try:
    from pydobot import Dobot
    PYDOBOT_AVAILABLE = True
except ImportError:
    PYDOBOT_AVAILABLE = False
#-------------------------------------------

# --- ロボット設定 ---
ROBOT1_CONFIG = {
    "port": "COM3", #ロボットがコンピュータに接続されている通信ポートを指定
    "ready_pos": (234, 15, 60, 0),  #ロボットが演奏を待っている間の「待機位置」の座標
    "strike_pos": (222, 11, -5, 0), #ロボットがドラムパッドを「叩く瞬間」の位置座標
}
ROBOT2_CONFIG = {
    "port": "COM4",
    "ready_pos": (234, 15, 60, 0),
    "strike_pos": (222, 11, -5, 0),
}

# --- 動作パラメータ ---
LATENCY_COMPENSATION_S = 0.050  #遅延補正（秒）。コンピュータが命令を送ってから、実際にロボットが動き出すまでには、ごくわずかな時間差（遅延）があり、その差を見越して、0.05秒だけ早く命令を送ることで、目的の時刻に寸分違わず叩けるように調整。

# 振り上げる高さの計算パラメータ
MAX_BACKSWING_HEIGHT = 35.0 #スティックを振り上げる高さ（バックスイング）の最大値
MIN_BACKSWING_HEIGHT = 5.0  #バックスイングの最小値です。非常に速いフレーズを叩くときに使う
TIME_TO_HEIGHT_NORMALIZATION_S = 0.5    #バックスイングの高さを計算するための基準時間。次の音符までの時間がこの値（0.5秒）より長ければ最大まで振り上げ、短ければその時間に応じて振り上げる高さを滑らかに変化させる。

class RobotController(QObject): #1体のロボットを操縦する「操縦士」の役割を担い、演奏開始前に全ての動きを計画する。
    log_message = pyqtSignal(str)   #QObjectを継承し、pyqtSignalを持つことで、このクラス（バックグラウンドで動作する）からメインアプリ（UIスレッド）へ、処理の状況 (log_message) や完了 (finished) を安全に通知
    finished = pyqtSignal()
    
    # ★★★ 変更点1: __init__ に track_name と controller を追加 ★★★
    def __init__(self, config, note_items, bpm, loop_duration, start_event, stop_event, device_list, track_name, controller):   #動作に必要な情報をすべて受け取ってインスタンス変数（self.xxx）に保存
        super().__init__()
        self.config = config    ## ロボットの物理設定 (ポート番号, 座標)
        self.note_items = note_items    # このロボットが演奏する楽譜
        self.bpm = bpm  #曲のテンポ
        self.loop_duration = loop_duration  #曲1ループの時間
        self.start_event = start_event  #全ロボット共通の「開始」合図
        self.stop_event = stop_event    #全ロボット共通の「停止」合図
        self.device_list = device_list  #アクティブなデバイスのリスト
        self.track_name = track_name      # 'top'か'bottom'か
        self.controller = controller      # 同調制御コントローラー
        
        self.motion_plan = self._create_motion_plan()   #け取った情報をもとに、ただちに_create_motion_planメソッドを呼び出し、「モーションプラン（動作計画）」の作成を開始

    def _create_motion_plan(self):  #ボットが演奏すべきすべての動きを、演奏開始前に計算・リスト化
        notes_only = sorted([item for item in self.note_items if item.get("class") == "note"], key=lambda x: x['beat']) #渡された楽譜 (self.note_items) の中から、休符などを除いた音符 ("class" == "note") のみを抽出し、演奏順に並べ替え。
        if not notes_only:  #もしnotes_onlyリストが空っぽだったら
            return []   #演奏すべき音符がないので、空の動作計画（空のリスト）を返して、このメソッドの処理を終了

        motion_plan = []    #これから作成する一連の動作計画を格納するための、空のリストmotion_planを用意
        seconds_per_beat = 60.0 / self.bpm  #曲のテンポ（self.bpm、1分あたりの拍数）をもとに、1拍あたりの時間（秒）を計算
        
        for i, current_note in enumerate(notes_only):   #抽出した音符を一つずつループ処理し、各音符に対する動きを計画
            is_last_note = (i == len(notes_only) - 1)   #現在処理している音符が、リストの最後の音符であるかどうかを判定し、結果をis_last_noteという変数にTrueかFalseで保存
            next_note = notes_only[0] if is_last_note else notes_only[i + 1]    #もし最後の音符なら、次の音符は「ループしてリストの最初に戻った音符 (notes_only[0])」とする。そうでなければ、単純に「リストの次の音符 (notes_only[i + 1])」とする。
            
            current_strike_time = current_note.get("beat", 0) * seconds_per_beat    #現在の音符を叩くべき正確な時刻（ループ開始から何秒後か）を計算し、current_strike_timeに保存
            
            interval = 0    #次の音符までの時間を格納する変数intervalを、一旦0で初期化
            if is_last_note:    #もし現在の音符が最後の音符だった場合
                interval = self.loop_duration - current_strike_time + (next_note.get("beat", 0) * seconds_per_beat) #最後の音符から、次のループの最初の音符までの時間を計算。（現在の打刻時刻からループ終了までの時間）＋（次のループの最初の音符の打刻時刻）
            else:   #最後の音符でなかった場合
                interval = (next_note.get("beat", 0) - current_note.get("beat", 0)) * seconds_per_beat  #次の音符の打刻時刻と現在の音符の打刻時刻の差を計算して、intervalに保存
            
            if interval <= 0.02: continue   #もし音符間の時間が0.02秒以下と非常に短い場合は、バックスイングの時間が確保できないため、この音符に対する動作計画はスキップして、次の音符のループに移る。
            #計算したインターバルの半分を使ってスティックを振り上げると仮定し、振り上げ動作のタイミング (upstroke_target_time) を決定
            upstroke_duration = interval / 2.0  #音符間の時間の半分を、スティックを振り上げる（アップストロークする）ための時間と仮定
            upstroke_target_time = current_strike_time + upstroke_duration  #スティックを振り上げ終わるべき目標時刻を計算

            height_ratio = min(upstroke_duration / TIME_TO_HEIGHT_NORMALIZATION_S, 1.0) #振り上げに使える時間（upstroke_duration）を基準時間。TIME_TO_HEIGHT_NORMALIZATION_S）で割り、振り上げる高さの比率（0.0～1.0）を計算
            backswing_z = MIN_BACKSWING_HEIGHT + (MAX_BACKSWING_HEIGHT - MIN_BACKSWING_HEIGHT) * height_ratio   #上で計算した比率を使って、バックスイングの最終的なZ座標（高さ）を算出。時間が長ければ高く、短ければ低くなる。
            
            ready_x, ready_y, _, ready_r = self.config["ready_pos"] #設定から待機位置のX, Y座標と回転角を取得。Z座標は使わないので_で無視。
            backswing_pos = (ready_x, ready_y, backswing_z, ready_r)    #算出した高さ（backswing_z）と、元のX, Y, 回転角を組み合わせて、バックスイング完了時の最終的な座標を作成
            #1つの音符に対して、2つの動作を計画リスト (motion_plan) に追加
            motion_plan.append({"target_time": current_strike_time, "position": self.config["strike_pos"]}) #音符を叩く（ストライク）動作
            motion_plan.append({"target_time": upstroke_target_time, "position": backswing_pos})    #スティックを振り上げる（バックスイング）動作

        return sorted(motion_plan, key=lambda x: x['target_time'])  #すべての音符のストライクとバックスイングの計画がリストに入ったら、最後に全体を時間順に並べ替えて、完成したモーションプランを返す。

    def run(self):  #1体のロボットの接続から演奏実行、そして安全な終了までの全プロセスを担当
        device = None   #ロボットとの接続情報を格納するための変数deviceを用意し初期化
        port = self.config["port"]  #このロボットが接続されている通信ポート名（例：「COM3」）を設定情報から取り出し、portという変数に保存
        try:    #tryブロックで囲ってエラー処理に備える
            if not PYDOBOT_AVAILABLE: raise ImportError("pydobotライブラリが見つかりません。")  #もしpydobotライブラリが利用不可（PYDOBOT_AVAILABLEがFalse）であれば、意図的にエラーを発生させ、この後の処理を中止してexceptブロックに処理を移す。

            # 物理的なロボットに接続
            device = Dobot(port=port, verbose=False)    #ここで物理的なロボットアームに接続。Dobotクラスを使って、指定したportに接続するためのdeviceオブジェクトを作成。
            self.device_list.append(device) #作成したdeviceオブジェクトを、現在アクティブなデバイスの共有リストに追加
            self.log_message.emit(f"ロボット [{port}] 接続完了")    #emitを使って、メインアプリの画面に「ロボット [COM3] 接続完了」といったメッセージを送信し、ユーザーに進捗を伝える。

            self.log_message.emit(f"ロボット [{port}] キャリブレーションを初期化・再設定します...") #同様に、「キャリブレーション（位置調整）を開始します」というメッセージを画面に送る。
            
            ## 速度や加速度を設定
            device.speed(velocity=2000, acceleration=2000)  #ロボットアームが動く際の速度（velocity）と加速度（acceleration）の最大値を設定する命令。
            
            # 待機位置へ移動 (完了まで待つ)
            device.move_to(*self.config["ready_pos"], wait=True)    #ロボットに、設定された「待機位置」へ移動するよう命令。wait=Trueで、ロボットがその位置への移動を完全に終えるまで、プログラムの次の行に進まない。
            self.log_message.emit(f"ロボット [{port}] 準備完了")    #待機位置への移動が完了したことを、メッセージでユーザーに知らせる。

            # 最初の音を叩くための準備位置(バックスイング)へ移動
            if self.motion_plan:    #事前に作成した動作計画 (motion_plan) が空でない（＝演奏すべき音符がある）かどうかを確認
                initial_backswing_pos = self.motion_plan[1]["position"] #動作計画の2番目 ([1]) の動作、つまり最初の音を叩くためのバックスイングの位置を取り出す。（1番目([0])は最初の打撃動作）


                device.move_to(*initial_backswing_pos, wait=True)   #最初の音を叩く直前の「振りかぶった」状態の位置まで、ロボットを移動させる。wait=Trueで移動完了を待つ。
                self.log_message.emit(f"ロボット [{port}] 最初の打撃準備完了")  #これでいつでも叩き始められる状態になったことを、ユーザーに通知。

            # Goサインが出るまでここで待機
            self.start_event.wait() #プログラムはここで一時停止。司令官であるRobotManagerからGoサイン (start_event) が送られてくるまで、ここで待機。
            if self.stop_event.is_set(): return #Goサインを待っている間に「停止」命令が来た場合に備えた安全確認。もし停止命令が来ていれば、演奏を開始せずにこのrunメソッドの処理を終了。

            master_start_time = time.time() #time.time()で演奏が開始された正確な絶対時刻を取得し、すべてのタイミング計算の基準点となるmaster_start_time変数に保存
            loop_count = 0  #音楽のフレーズを何回繰り返したかを数えるためのカウンターloop_countを0で初期化
            
            while not self.stop_event.is_set(): #メインアプリから「停止」の合図 (self.stop_event) が来るまで、このwhileブロック内の処理を無限に繰り返す。
                current_loop_start_time = master_start_time + (loop_count * self.loop_duration) #現在の繰り返し回 (loop_count) の開始絶対時刻を計算。全体の開始時刻に、これまでの繰り返し回数分の時間を足し合わせる。
                
                start_index = 0 #常にstart_indexを0に設定
                if loop_count == 0:
                    start_index = 0
                
                for motion in self.motion_plan[start_index:]:   #事前に作成した動作計画 (self.motion_plan) の中身を、motionという変数に一つずつ取り出しながらループ処理
                    if self.stop_event.is_set(): break  #作のループの途中でも、常に「停止」命令が来ていないかを確認し、もし来ていればこのforループを直ちに中断

                    # コントローラーにタイミングを問い合わせる 
                    # モーションプランの理想的なタイミング(秒)をミリ秒に変換
                    ideal_time_ms = motion["target_time"] * 1000
                    
                    # コントローラーに問い合わせて、介入後のタイミング(ミリ秒)を取得
                    guided_time_ms = self.controller.get_guided_timing(self.track_name, ideal_time_ms)  #理想のタイミングをそのまま使わず、メインアプリの「頭脳」であるself.controllerに本当に動くべき時刻はいつか問い合わせ、介入後の「導かれた」タイミング (guided_time_ms) を受け取る。
                    
                    # 実行のために秒に戻す
                    guided_time_s_in_loop = guided_time_ms / 1000.0 #「頭脳」から受け取ったミリ秒単位の時刻を、計算しやすいように秒単位に戻す。
                    
                    target_time = current_loop_start_time + guided_time_s_in_loop   #現在のループの開始時刻に、「導かれた」時刻を足し合わせることで、この動作が実行されるべき最終的な絶対時刻 (target_time) を算出
                    
                    send_command_time = target_time - LATENCY_COMPENSATION_S    #ロボットへの命令の伝達遅延を見越して、実際に命令を送信すべき時刻 (send_command_time) を、目標時刻よりLATENCY_COMPENSATION_S（例: 0.05秒）だけ早く設定

                    while time.time() < send_command_time:  #命令を送信すべき時刻になるまで、ここで超高速で時間を確認しながら待機 
                        if self.stop_event.is_set(): break  #時間待ちの最中でも「停止」命令を常に確認し、即座に中断できる
                        time.sleep(0.001)   #CPUに過度な負荷をかけないよう、時間待ちループの中で1ミリ秒だけ処理を止める。これにより、精密なタイミングとCPU負荷のバランスを取る。
                    if self.stop_event.is_set(): break  #時間待ちループを抜けた直後にも、念のため「停止」命令を確認
                    
                    if not self.stop_event.is_set():    #最終的に停止命令が来ていないことを確認した上で、次の行を実行
                        device.move_to(*motion["position"], wait=False) #時刻ぴったりに、ロボットに[動け]という命令を送る。wait=Falseで、ロボットの動きの完了を待たずに、プログラムはすぐに次の動作の準備（次のループ）に進む。



                if self.stop_event.is_set(): break  #1フレーズ分の動作がすべて終わった後にも「停止」命令を確認し、来ていればwhileループを抜ける
                loop_count += 1 #1フレーズ分の演奏が完了したので、繰り返し回数のカウンターを1つ増やす。

        except Exception as e:  #もし、try:ブロック内のどこかで、予期せぬエラー（断線、物理的な衝突など、あらゆる種類のエラー）が発生した場合、プログラムはクラッシュせずにこのexceptブロックにジャンプ。発生したエラーの詳細はeという変数に格納
            self.log_message.emit(f"ロボット [{port}] エラー: {e}") #捕まえたエラーの詳細（e）を含んだメッセージを、メインアプリの画面に送信
        finally:    #このブロック内のコードは、エラーが起きても起きなくても、処理が正常に完了しても、どんな状況でも必ず最後に実行
            if device:  #ロボットとの接続 (device) が確立されていたかどうかを確認
                try:    #後片付けの処理自体がエラーになる可能性（例: エラー発生時にUSBケーブルが抜かれた）もあるため、ここでもtry...exceptを使う。passは「エラーが起きても何もしないで次に進む」という意味で、後片付けを最後までやり遂げるための安全策。
                    if device in self.device_list: self.device_list.remove(device)
                    device.move_to(230, 15, 60, 0, wait=True)    #ロボットアームを、あらかじめ決められた安全な退避位置へ移動
                except: pass
                try: device.close() #ロボットとの通信ポートを正式に切断
                except: pass
                self.log_message.emit(f"ロボット [{port}] 接続解除")
            self.finished.emit()    #このロボットコントローラー（スレッド）の全タスクが完全に終了したことを、司令官であるRobotManagerに通知

class RobotManager(QObject):    #PyQtのQObjectを継承して、シグナルなどのUI連携機能を使えるようにする。
    log_message = pyqtSignal(str)   #UI画面にメッセージを伝えるための「通信路（シグナル）」を定義

    def __init__(self, parent=None):    #このクラスの初期化メソッド
        super().__init__(parent)    #親クラスであるQObjectの初期化処理を呼び出す。
        self.threads = []   #これから作成するバックグラウンド処理用のスレッドと、その上で動くワーカー（RobotController）を管理するための空のリストを用意
        self.workers = []   
        self.start_event = threading.Event()    #全てのロボットが一斉に動き出したり止まったりするための、共有の「合図（イベント）」を作成。start_eventが「スタート」、stop_eventが「停止命令」の役割を果たす。
        self.stop_event = threading.Event()
        self.active_devices = []    #現在接続中のロボットデバイスを管理するためのリスト

    # ★★★ 変更点3: start_control が active_controller を受け取る ★★★
    def start_control(self, score_data, active_controller): #演奏すべきscore_data（楽譜）と、ロボットの「頭脳」であるactive_controllerを受け取る。
        self.stop_control() #新しい演奏を始める前に、もし前回の演奏が残っていれば、まずそれを完全に停止
        self.stop_event.clear() #「停止」と「開始」の合図を、まだ送られていない初期状態（クリア状態）に戻す。
        self.start_event.clear()

        top_score = score_data.get("top", {}); bottom_score = score_data.get("bottom", {})  #この一連の処理で、受け取ったscore_dataから左手（top）と右手（bottom）それぞれの楽譜、BPM、演奏時間などを解析・抽出
        top_bpm = top_score.get("bpm", 120); bottom_bpm = bottom_score.get("bpm", 120)
        
        top_items = top_score.get("items", [])
        bottom_items = bottom_score.get("items", [])
        
        top_beats = top_score.get("total_beats", 8); bottom_beats = bottom_score.get("total_beats", 8)
        top_duration = top_beats * (60.0 / top_bpm)
        bottom_duration = bottom_beats * (60.0 / bottom_bpm)
        loop_duration_sec = max(top_duration, bottom_duration)
        
        # track_nameを渡すためにタプルの内容を更新
        configs = [ #左手用ロボットと右手用ロボット、それぞれに必要な情報（物理設定、楽譜、BPM、担当パート名）をまとめたリストを作成
            (ROBOT1_CONFIG, top_items, top_bpm, 'top'), 
            (ROBOT2_CONFIG, bottom_items, bottom_bpm, 'bottom')
        ]

        self.log_message.emit("🎼 楽譜分析とモーションプランニング開始...")
        
        for config, items, bpm, track_name in configs:  #上で作成したconfigsリストを使い、ロボット1台分ずつループ処理（計2回ループ）
            thread = QThread()  #このロボットをバックグラウンドで動かすための、空のQThreadオブジェクトを作成
            # ★★★ 変更点4: RobotController に track_name と active_controller を渡す ★★★
            worker = RobotController(config, items, bpm, loop_duration_sec, self.start_event, self.stop_event, self.active_devices, track_name, active_controller)  #ロボット1体を専門に操縦するRobotController（ワーカー）を生成。このとき、ロボットの物理設定、楽譜、共有の開始/停止合図、そして最も重要な「頭脳」であるactive_controllerを渡す。
            worker.moveToThread(thread) #作成したworkerを、バックグラウンドで動くthreadに移動させる。これにより、workerの処理がUIを固まらせるのを防ぐ。
            worker.log_message.connect(self.log_message.emit)   #workerからのメッセージを、このRobotManager経由でUIに中継するように接続
            thread.started.connect(worker.run)  #スレッドが開始されたら、自動的にworkerのrunメソッドを実行するように接続
            worker.finished.connect(thread.quit)    #処理が終わった後の後片付けを設定。workerが終わったらthreadを終了させ、threadが終わったらworkerとthreadをメモリから削除するように接続
            worker.finished.connect(worker.deleteLater)
            thread.finished.connect(thread.deleteLater)
            thread.finished.connect(lambda t=thread, w=worker: self._on_thread_finished(t, w))
            thread.start()  #バックグラウンドスレッドを起動します。これにより、すぐにworker.runメソッドの実行が始まる。
            self.threads.append(thread) #管理リストに、今作成したthreadとworkerを追加
            self.workers.append(worker)

    def stop_control(self): #全てのロボットの動作を停止させるためのメソッド
        if not self.threads: return #停止させるべきスレッドがなければ、何もせずに処理を終了
        self.log_message.emit("🛑 演奏停止中...")   #「停止中です」というメッセージをUIに送る。
        self.stop_event.set()   #共有の「停止」合図をONにする。全てのworkerはこの合図を常に監視しており、ONになったことを検知してループを抜け、処理を終了。
        self.start_event.set()  #もしworkerが開始合図を待って停止している場合、この行で合図を送って待ち状態から解放し、すぐに停止命令を検知できるようにする。

    def trigger_start(self):    #カウントダウンの後など、任意のタイミングで演奏を開始させるためのメソッド
        self.log_message.emit("🎬 演奏開始！")
        self.start_event.set()  #共有の「開始」合図をONにします。workerのrunメソッド内でこの合図を待っていた全ロボットが、この瞬間、一斉に動き出す。

    def _on_thread_finished(self, thread_obj, worker_obj):
        if thread_obj in self.threads: self.threads.remove(thread_obj)  #終了したスレッドとワーカーを、管理リストから安全に削除
        if worker_obj in self.workers: self.workers.remove(worker_obj)