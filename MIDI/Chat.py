#chatgptと対話するプログラム
import os
import openai
from openai import OpenAI

def main():
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("環境変数 OPENAI_API_KEY が設定されていません。")
        return

    client = OpenAI(api_key=api_key)

    messages = [
        {"role": "system", "content": "あなたは親切で知識豊富なアシスタントです。"}
    ]

    print("ChatGPTと対話を開始します（'exit'で終了）。")

    while True:
        user_input = input("あなた > ")
        if user_input.lower() in {"exit", "quit"}:
            print("終了します。")
            break

        messages.append({"role": "user", "content": user_input})

        try:
            response = client.chat.completions.create(
                model="gpt-4o",  # または "gpt-3.5-turbo"
                messages=messages
            )
            reply = response.choices[0].message.content.strip()
            print("アシスタント >", reply)
            messages.append({"role": "assistant", "content": reply})
        except Exception as e:
            print("エラー:", e)

if __name__ == "__main__":
    main()
