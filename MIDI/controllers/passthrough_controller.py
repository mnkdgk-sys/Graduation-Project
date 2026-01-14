# controllers/passthrough_controller.py

from .base_controller import BaseEntrainmentController

class PassthroughController(BaseEntrainmentController):
    """
    同調制御を行わず、お手本のリズムをそのまま返すコントローラー。
    比較対象やデフォルトとして使用します。
    """
    @property
    def name(self):
        return "介入なし (お手本通り)"

    # このコントローラーは何もしないので、他のメソッドは基底クラスの実装のまま