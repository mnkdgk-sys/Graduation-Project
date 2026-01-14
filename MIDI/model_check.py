import os
from openai import OpenAI

# APIキーを取得（環境変数 OPENAI_API_KEY が必要）
api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    print("OPENAI_API_KEY が設定されていません。")
    exit()

client = OpenAI(api_key=api_key)

# 利用可能なモデルを取得
models = client.models.list()

print("=== 利用可能なモデル一覧 ===")
for model in models.data:
    print(model.id)
