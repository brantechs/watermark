from PIL import Image  # type: ignore
import imageio.v3 as iio  # type: ignore
from pathlib import Path
import numpy as np  # type: ignore

# ファイル拡張子を判定する関数
def get_file_extension(file_path: Path) -> str:
    return file_path.suffix.lower()

# オーバーレイ処理を行う関数
def overlay_images(base_frame: Image.Image, overlay_image: Image.Image, transparency: float) -> Image.Image:
    """
    透過情報を考慮しながらウォーターマークを重ねる。
    - 元の透過部分にはウォーターマークを適用しない。
    """
    if "A" in base_frame.mode:
        base_alpha = base_frame.split()[3]
        base_alpha_np = np.array(base_alpha)
        mask = base_alpha_np == 0  # 完全に透過している部分をマスク
    else:
        base_alpha = None
        mask = None

    overlay_with_alpha = overlay_image.copy()
    alpha = overlay_with_alpha.split()[3].point(lambda p: int(p * transparency))
    overlay_with_alpha.putalpha(alpha)

    if mask is not None:
        overlay_with_alpha_np = np.array(overlay_with_alpha)
        overlay_with_alpha_np[mask] = [0, 0, 0, 0]
        overlay_with_alpha = Image.fromarray(overlay_with_alpha_np, "RGBA")

    combined = Image.alpha_composite(base_frame, overlay_with_alpha)

    return combined

# gifのフレーム数を正確に判定し、各フレームを返す関数
def get_gif_frames(image: Image.Image) -> list[Image.Image]:
    frames = []
    try:
        while True:
            frames.append(image.copy())
            image.seek(image.tell() + 1)
    except EOFError:
        pass
    return frames

# メイン処理
def process_images(base_image_path: Path, overlay_image_path: Path, output_folder: Path, transparencies=[0.15]):
    """
    入力画像にウォーターマークを適用し、指定されたフォルダに保存する。
    """
    if not base_image_path.exists():
        raise FileNotFoundError(f"Base image not found: {base_image_path.resolve()}")
    if not overlay_image_path.exists():
        raise FileNotFoundError(f"Overlay image not found: {overlay_image_path.resolve()}")

    output_folder.mkdir(parents=True, exist_ok=True)

    base_name = base_image_path.stem
    ext = base_image_path.suffix.lower()
    base_image = Image.open(base_image_path)
    overlay_image = Image.open(overlay_image_path).convert("RGBA")
    overlay_image = overlay_image.resize(base_image.size, Image.Resampling.LANCZOS)

    if ext in [".gif", ".png"] and getattr(base_image, "is_animated", False):
        for transparency in transparencies:
            frames = get_gif_frames(base_image)
            processed_frames = []

            for frame in frames:
                base_frame = frame.convert("RGBA")
                combined_frame = overlay_images(base_frame, overlay_image, transparency)
                processed_frames.append(np.array(combined_frame))

            output_file_path = output_folder / f"{base_name}_{int(transparency * 100)}％{ext}"
            iio.imwrite(
                str(output_file_path),
                processed_frames,
                duration=base_image.info.get("duration", 100),
                loop=base_image.info.get("loop", 0),
                plugin="pillow" if ext == ".png" else None
            )
    else:
        base_frame = base_image.convert("RGBA")
        for transparency in transparencies:
            combined_image = overlay_images(base_frame, overlay_image, transparency)

            # 保存前に非透過形式の場合はRGBに変換
            if ext in [".jpg", ".jpeg", ".bmp"]:
                print(f"Converting image to RGB for format: {ext}")
                combined_image = combined_image.convert("RGB")

            # 出力ファイルを保存
            output_image_path = output_folder / f"{base_name}_{int(transparency * 100)}％{ext}"
            try:
                print(f"Saving image to: {output_image_path}")
                combined_image.save(output_image_path)
            except Exception as e:
                raise IOError(f"Failed to save image: {output_image_path}. Error: {e}")
