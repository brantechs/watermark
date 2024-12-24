from pathlib import Path
from PIL import Image # type: ignore
import sys

# プロジェクトのルートディレクトリを取得し、モジュール検索パスに追加
project_root = Path(__file__).resolve().parent.parent
sys.path.append(str(project_root))

from src.utils.watermark_processor import (
    apply_watermark_to_frames_strict,
    create_gif_pil_isolated,
    process_images
)

def main():
    """
    メイン関数:
    1. 静止画の透かし処理を検証します。
        - ベース画像とオーバーレイ画像の存在を確認します。
        - 透かし処理を実行し、結果を出力フォルダに保存します。
    2. フレームごとの透かし処理を検証します。
        - フレームフォルダとオーバーレイ画像の存在を確認します。
        - 各フレームに透かしを適用し、結果を出力フォルダに保存します。
    3. GIF作成処理を検証します。
        - フレームフォルダからGIFを作成し、出力フォルダに保存します。
    4. 結果の検証:
        - 出力フォルダの存在を確認し、フォルダ内のファイルをリスト表示します。

    Raises:
        FileNotFoundError: 指定されたファイルやフォルダが見つからない場合に発生します。
        Exception: その他の処理中に発生した例外をキャッチして表示します。
    """
    # 基本パス設定
    ## テスト用のベースディレクトリ
    TEST_BASE_DIR = Path("./tests/test_images")
    base_image_path = TEST_BASE_DIR / "src/1309159-2.gif"
    overlay_image_path = TEST_BASE_DIR / "src/watermark.png"
    output_folder = TEST_BASE_DIR / "test_output"
    frames_folder = output_folder / "frames"
    output_gif_path = output_folder / "output.gif"

    # 出力フォルダの作成
    if not output_folder.exists():
        output_folder.mkdir(parents=True, exist_ok=True)

    # === 1. 静止画の処理検証 ===
    print("静止画の透かし処理をテスト中...")
    try:
        if not base_image_path.exists():
            raise FileNotFoundError(f"ベース画像が見つかりません: {base_image_path}")
        if not overlay_image_path.exists():
            raise FileNotFoundError(f"オーバーレイ画像が見つかりません: {overlay_image_path}")
        process_images(base_image_path, overlay_image_path, output_folder, transparency=0.2)
        print("静止画の透かし処理テストに合格しました。")
    except Exception as e:
        print(f"静止画の透かし処理テストに失敗しました: {e}")

    # === 2. フレームごとの透かし処理検証 ===
    print("\nフレームごとの透かし処理をテスト中...")
    try:
        if not frames_folder.exists():
            raise FileNotFoundError(f"フレームフォルダが見つかりません: {frames_folder}")
        if not overlay_image_path.exists():
            raise FileNotFoundError(f"オーバーレイ画像が見つかりません: {overlay_image_path}")
        apply_watermark_to_frames_strict(frames_folder, overlay_image_path, output_folder, transparency=0.2)
        print("フレームごとの透かし処理テストに合格しました。")
    except Exception as e:
        print(f"フレームごとの透かし処理テストに失敗しました: {e}")

    # === 3. GIF作成処理検証 ===
    print("\nフレームからGIF作成をテスト中...")
    try:
        create_gif_pil_isolated(frames_folder, output_gif_path, duration=100)
        print("GIF作成テストに合格しました。")
    except Exception as e:
        print(f"GIF作成テストに失敗しました: {e}")

    print("\n結果の検証:")
    if output_folder.exists():
        print(f"出力フォルダ: {output_folder.resolve()}")
        for output_file in output_folder.iterdir():
            print(f"- {output_file.name}")
    else:
        print(f"出力フォルダが存在しません: {output_folder.resolve()}")
    for output_file in output_folder.iterdir():
        print(f"- {output_file.name}")

if __name__ == "__main__":
    main()
