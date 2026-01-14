# controllers/base_controller.py

class BaseEntrainmentController:
    """
    全ての同調制御コントローラーの基底クラス。
    新しいコントローラーは必ずこのクラスを継承してください。
    """
    def __init__(self, score_data, ms_per_beat):
        self.score_data = score_data
        self.ms_per_beat = ms_per_beat

    @property
    def name(self):
        """UIに表示されるコントローラーの名前"""
        raise NotImplementedError

    def update_performance_data(self, full_judgement_history):
        """
        メインウィンドウから毎ループの終わりに最新の演奏データを受け取るメソッド。
        このメソッド内で、学習者の演奏を分析し、次のループの戦略を立てます。
        
        Args:
            full_judgement_history (list): これまでの全ループの判定結果のリスト
        
        Returns:
            str or None: 分析結果のサマリーログ。ログがない場合はNone。
        """
        # 継承先が実装しない場合は、ログなし(None)を返す
        return None

    def get_guided_timing(self, track_name, ideal_note_time_ms):
        """
        シミュレーターから毎フレーム呼び出されるメソッド。
        理想のタイミングを基に、誘導後のタイミングを計算して返す。
        
        Args:
            track_name (str): 'top' または 'bottom'
            ideal_note_time_ms (float): お手本楽譜上のノートの理想的なタイミング(ms)
        
        Returns:
            tuple (float, str or None): 
                - (0) 制御が適用された後のタイミング(ms)
                - (1) 介入ログ。ログがない場合はNone。
        """
        # 継承先が実装しない場合は、(元の時間, ログなし) をタプルで返す
        return ideal_note_time_ms, None

    def reset(self):
        """練習がリセットされたときに内部状態を初期化するメソッド"""
        pass