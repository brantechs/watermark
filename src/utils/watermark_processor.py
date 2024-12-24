from PIL import Image
import imageio.v3 as iio
import numpy as np
from pathlib import Path

# ファイルの拡張子を取得する関数
def get_file_extension(file_path: Path) -> str:
    return file_path.suffix.lower()

# 透過マスクを使用して画像を厳密にオーバーレイする関数
def overlay_images_strict(base_frame: Image.Image, overlay_image: Image.Image, transparency: float) -> Image.Image:
    """
    ベース画像の非透過領域にのみ透かしを適用します。

    引数:
        - base_frame: 処理対象のベース画像
        - overlay_image: 透かし用のオーバーレイ画像
        - transparency: オーバーレイの透明度 (0.0～1.0)
    
    戻り値:
        - 合成されたImageオブジェクト
    """
    # ベース画像からアルファチャンネルを抽出
    if "A" in base_frame.mode:
        base_alpha = base_frame.split()[3]  # アルファチャンネルの取得
        base_alpha_np = np.array(base_alpha)
        mask = base_alpha_np == 0  # 完全に透過した領域のマスク作成
    else:
        mask = None

    # 透明度を調整したオーバーレイ画像を準備
    overlay_with_alpha = overlay_image.copy()
    alpha = overlay_with_alpha.split()[3].point(lambda p: int(p * transparency))
    overlay_with_alpha.putalpha(alpha)

    # マスクをオーバーレイ画像に適用
    if mask is not None:
        overlay_with_alpha_np = np.array(overlay_with_alpha)
        overlay_with_alpha_np[mask] = [0, 0, 0, 0]  # 完全に透過した領域を無効化
        overlay_with_alpha = Image.fromarray(overlay_with_alpha_np, "RGBA")

    # ベース画像とオーバーレイ画像を合成
    combined = Image.alpha_composite(base_frame, overlay_with_alpha)
    return combined

# フレームごとに透かしを適用する関数
def apply_watermark_to_frames_strict(frames_path: Path, overlay_image_path: Path, output_folder: Path, transparency=0.15):
    """
    各フレームに厳密に透かしを適用し、結果を保存します。

    引数:
        - frames_path: フレーム画像が保存されたフォルダパス
        - overlay_image_path: オーバーレイ画像のパス
        - output_folder: 処理結果を保存するフォルダ
        - transparency: 透かしの透明度
    """
    overlay_image = Image.open(overlay_image_path).convert("RGBA")
    for frame_path in frames_path.glob("*.png"):  # PNG形式のフレーム画像を処理
        frame = Image.open(frame_path).convert("RGBA")
        overlay_resized = overlay_image.resize(frame.size, Image.Resampling.LANCZOS)

        # 厳密なオーバーレイを適用
        combined_frame = overlay_images_strict(frame, overlay_resized, transparency)
        output_frame_path = frames_path / frame_path.name  # 修正: frames_path を明確に指定
        combined_frame.save(output_frame_path)

# GIFをフレームから作成する関数
def create_gif_pil_isolated(frames_folder: Path, output_gif_path: Path, duration=100):
    """
    フレーム画像を使用してGIFを作成します。

    引数:
        - frames_folder: フレーム画像が保存されたフォルダ
        - output_gif_path: 出力GIFファイルのパス
        - duration: 各フレームの表示時間 (ミリ秒)
    """
    frames = [Image.open(frame_path).copy() for frame_path in sorted(frames_folder.glob("*.png"))]

    # フレームが存在しない場合のエラーチェック
    if not frames:
        raise ValueError(f"指定されたフォルダにフレームが存在しません: {frames_folder.resolve()}")

    frames[0].save(
        output_gif_path,
        save_all=True,
        append_images=frames[1:],
        duration=duration,
        loop=0,
        disposal=2  # フレームの破棄設定 (GIFの破棄動作を制御)
    )

# メインの画像処理関数
def process_images(base_image_path: Path, overlay_image_path: Path, output_folder: Path, transparency=0.15):
    """
    静止画またはアニメーション画像に透かしを適用し、出力を保存します。

    引数:
        - base_image_path: ベース画像のパス
        - overlay_image_path: オーバーレイ画像のパス
        - output_folder: 処理結果を保存するフォルダ
        - transparency: 透かしの透明度
    """
    if not base_image_path.exists():
        raise FileNotFoundError(f"ベース画像が見つかりません: {base_image_path.resolve()}")
    if not overlay_image_path.exists():
        raise FileNotFoundError(f"オーバーレイ画像が見つかりません: {overlay_image_path.resolve()}")

    if not output_folder.exists():
        try:
            output_folder.mkdir(parents=True, exist_ok=True)
            print(f"出力フォルダを作成しました: {output_folder}")
        except PermissionError as e:
            raise PermissionError(f"出力フォルダの作成に失敗しました: {e}")

    base_name = base_image_path.stem
    ext = get_file_extension(base_image_path)
    base_image = Image.open(base_image_path)
    overlay_image = Image.open(overlay_image_path).convert("RGBA")
    overlay_image = overlay_image.resize(base_image.size, Image.Resampling.LANCZOS)

    if ext in [".gif"] and getattr(base_image, "is_animated", False):
        # GIFのフレームごとに透かしを適用
        frames = []
        frame_output_folder = output_folder / "frames"  # フレーム出力用フォルダ
        frame_output_folder.mkdir(parents=True, exist_ok=True)

        transparency_index = 255  # GIFで透明として扱うインデックス

        try:
            frame_index = 0
            while True:
                frame = base_image.copy().convert("RGBA")
                combined_frame = overlay_images_strict(frame, overlay_image, transparency)

                # RGBAからPモードに変換してGIFパレットを適用
                combined_frame_p = combined_frame.convert("P", palette=Image.ADAPTIVE, colors=256)

                # 透過ピクセルを透明インデックスとして設定
                mask = combined_frame.getchannel("A").point(lambda p: 255 if p == 0 else 0)
                combined_frame_p.paste(transparency_index, mask=mask)

                frames.append(combined_frame_p)

                # フレームをPNGとして保存
                frame_output_path = frame_output_folder / f"frame_{frame_index:03d}.png"
                combined_frame.save(frame_output_path)
                print(f"フレームを保存しました: {frame_output_path}")

                frame_index += 1
                base_image.seek(base_image.tell() + 1)
        except EOFError:
            pass

        output_file_path = output_folder / f"{base_name}_watermarked{ext}"
        try:
            # PILでGIFを保存
            frames[0].save(
                output_file_path,
                save_all=True,
                append_images=frames[1:],
                duration=base_image.info.get("duration", 100),
                loop=base_image.info.get("loop", 0),
                transparency=transparency_index,  # インデックス255を透過色として設定
                disposal=2                       # フレーム破棄設定
            )
            print(f"GIFを保存中: {output_file_path}")
        except Exception as e:
            raise RuntimeError(f"GIFの保存に失敗しました: {e}")

        if output_file_path.exists():
            print(f"GIFが正常に作成されました: {output_file_path}")
        else:
            raise FileNotFoundError(f"GIFが作成されませんでした: {output_file_path}")

    else:
        # 静止画の透かし処理
        base_frame = base_image.convert("RGBA")
        combined_image = overlay_images_strict(base_frame, overlay_image, transparency)

        if ext in [".jpg", ".jpeg", ".bmp"]:
            combined_image = combined_image.convert("RGB")

        output_image_path = output_folder / f"{base_name}_watermarked{ext}"
        try:
            combined_image.save(output_image_path)
            print(f"静止画を保存しました: {output_image_path}")
        except Exception as e:
            raise RuntimeError(f"静止画の保存に失敗しました: {e}")
