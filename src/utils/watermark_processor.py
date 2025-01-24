from PIL import Image
import numpy as np
from pathlib import Path
import logging

# ログ設定
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Pillowでサポートされている拡張子一覧
PIL_SUPPORTED_EXT = list(Image.registered_extensions().keys())

# アルファチャンネル対応の拡張子
ALPHA_SUPPORTED_EXT = {
    ".png", ".apng", ".tiff", ".tif", ".webp", ".ico", ".icns", ".dds",
    ".jp2", ".j2k", ".jpx", ".j2c", ".sgi", ".rgb", ".tga"
}

# アルファチャンネル非対応の拡張子
ALPHA_NOT_SUPPORTED_EXT = {".jpg", ".jpeg", ".bmp", ".gif", ".ppm", ".pgm", ".pbm"}

# アルファチャンネルを持つか確認する関数
def has_alpha_channel(image: Image.Image) -> bool:
    """
    指定された画像がアルファチャンネルを持っているかを確認します。

    引数:
        image (Image.Image): チェックするPillow画像オブジェクト

    戻り値:
        bool: アルファチャンネルを持っている場合はTrue
    """
    return "A" in image.mode

# 画像を透過マスクを考慮して合成する関数
def overlay_images(base_frame: Image.Image, overlay_image: Image.Image, transparency: float) -> Image.Image:
    """
    ベース画像にオーバーレイ画像を透過マスクを考慮して重ねる。

    引数:
        base_frame (Image.Image): ベースとなる画像
        overlay_image (Image.Image): 重ねるオーバーレイ画像
        transparency (float): 透明度 (0.0～1.0)

    戻り値:
        Image.Image: 合成後の画像
    """
    # ベース画像がアルファチャンネルを持つ場合、透過領域をマスクとして抽出
    if has_alpha_channel(base_frame):
        base_alpha = base_frame.getchannel("A")  # アルファチャンネルを取得
        base_alpha_np = np.array(base_alpha)    # NumPy配列に変換
        mask = base_alpha_np == 0               # 完全に透過した領域のマスクを作成
    else:
        mask = None

    # オーバーレイ画像に透明度を適用
    overlay_with_alpha = overlay_image.copy()
    alpha = overlay_with_alpha.getchannel("A").point(lambda p: int(p * transparency))
    overlay_with_alpha.putalpha(alpha)

    # マスクがある場合は、透過領域を無効化
    if mask is not None:
        overlay_np = np.array(overlay_with_alpha)  # オーバーレイ画像をNumPy配列に変換
        overlay_np[mask] = [0, 0, 0, 0]            # 完全に透過した領域を無効化
        overlay_with_alpha = Image.fromarray(overlay_np, "RGBA")

    # ベース画像とオーバーレイ画像を合成
    return Image.alpha_composite(base_frame.convert("RGBA"), overlay_with_alpha)

# 画像処理のメイン関数
def process_images(base_image_path: Path, overlay_image_path: Path, output_folder: Path, transparency=0.15):
    """
    静止画やアニメーション画像に透かしを適用し、結果を出力フォルダに保存します。

    引数:
        base_image_path (Path): ベース画像のパス
        overlay_image_path (Path): オーバーレイ画像のパス
        output_folder (Path): 出力フォルダのパス
        transparency (float): 透かしの透明度 (0.0～1.0)
    """
    logging.info(f"ベース画像: {base_image_path}")
    logging.info(f"オーバーレイ画像: {overlay_image_path}")
    logging.info(f"出力フォルダ: {output_folder}")
    logging.info(f"透明度: {transparency}")

    # 入力ファイルと出力フォルダの存在チェック
    if not base_image_path.exists():
        raise FileNotFoundError(f"ベース画像が見つかりません: {base_image_path}")
    if not overlay_image_path.exists():
        raise FileNotFoundError(f"オーバーレイ画像が見つかりません: {overlay_image_path}")
    output_folder.mkdir(parents=True, exist_ok=True)  # フォルダがない場合は作成

    # ベース画像とオーバーレイ画像を読み込み
    base_image = Image.open(base_image_path)
    overlay_image = Image.open(overlay_image_path).convert("RGBA")
    overlay_image = overlay_image.resize(base_image.size, Image.Resampling.LANCZOS)

    # 拡張子に応じた処理
    ext = base_image_path.suffix.lower()
    if ext in ALPHA_NOT_SUPPORTED_EXT:
        base_frame = base_image.convert("RGB")  # アルファチャンネルがない場合はRGBに変換
    elif ext in ALPHA_SUPPORTED_EXT:
        base_frame = base_image.convert("RGBA")  # アルファチャンネルがある場合はRGBAに変換
    else:
        raise ValueError(f"サポートされていない拡張子: {ext}")

    # 透かし適用処理
    combined_image = overlay_images(base_frame, overlay_image, transparency)

    # 結果を保存
    output_image_path = output_folder / f"{base_image_path.stem}_watermarked{ext}"
    try:
        combined_image.save(output_image_path)
        logging.info(f"透かし適用済み画像を保存しました: {output_image_path}")
    except Exception as e:
        logging.error(f"画像の保存に失敗しました: {e}")
        raise