import pydobot
import time

def main():
    """
    2台のDobot Magicianをキーボードから入力された座標に移動させるメイン関数
    """
    # 2台のDobotが接続されているCOMポートを指定
    port1 = 'COM3'
    port2 = 'COM4'
    bot1 = None
    bot2 = None

    try:
        # Dobotに接続
        print(f"Dobot 1 ({port1}) に接続しています...")
        bot1 = pydobot.Dobot(port=port1, verbose=False)
        print("✅ Dobot 1 に接続しました。")

        print(f"Dobot 2 ({port2}) に接続しています...")
        bot2 = pydobot.Dobot(port=port2, verbose=False)
        print("✅ Dobot 2 に接続しました。")

        # 2台のDobotの速度と加速度を設定
        print("ロボットの速度・加速度を設定しています...")
        bot1.speed(100, 100)
        bot2.speed(100, 100)
        print("✅ 設定が完了しました。")

    except Exception as e:
        print(f"❌ 初期設定中にエラーが発生しました: {e}")
        print("COMポートが正しいか、Dobotの電源が入っているか確認してください。")
        # 万が一、片方だけ接続成功した場合に備えて閉じる処理
        if bot1:
            bot1.close()
        if bot2:
            bot2.close()
        return

    # ユーザーから座標を入力
    while True:
        try:
            coord_input = input("\n👉 目標座標を (x, y, z) の形式で入力してください (例: 250, 0, 50): ")
            x, y, z = [float(val.strip()) for val in coord_input.split(',')]
            break
        except ValueError:
            print("⚠️ 入力形式が正しくありません。数値を3つ、カンマで区切って入力してください。")

    # ヘッドの回転角度(r)は0に固定
    r = 0

    print(f"\n🚀 2台のDobotを座標 ({x}, {y}, {z}) に移動します...")

    try:
        # 1台目のDobotを移動 (wait=Trueで移動完了を待つ)
        bot1.move_to(x, y, z, r, wait=True)
        print("Dobot 1 の移動が完了しました。")

        # 2台目のDobotを移動
        bot2.move_to(x, y, z, r, wait=True)
        print("Dobot 2 の移動が完了しました。")

        print("\n🎉 全ての移動が完了しました！")

    except Exception as e:
        print(f"❌ 移動中にエラーが発生しました: {e}")

    finally:
        # Dobotとの接続を閉じる 【ここを修正しました】
        # is_connected()メソッドは存在しないため、オブジェクトがあるかどうかだけで判断します。
        if bot1:
            bot1.close()
            print(f"\nDobot 1 ({port1}) との接続を閉じました。")
        if bot2:
            bot2.close()
            print(f"Dobot 2 ({port2}) との接続を閉じました。")

if __name__ == '__main__':
    main()