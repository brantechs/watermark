from __future__ import annotations

from pathlib import Path

import numpy as np  # type: ignore
from PIL import Image, ImageSequence  # type: ignore


def overlay_images(
    base_frame: Image.Image,
    overlay_image: Image.Image,
    transparency: float,
) -> Image.Image:
    """
    ベース画像へ透かし画像を合成する。
    ベース画像の完全透過部分には透かしを乗せない。
    """

    base_rgba = base_frame.convert("RGBA")
    overlay_rgba = overlay_image.convert("RGBA").resize(
        base_rgba.size,
        Image.Resampling.LANCZOS,
    )

    if "A" in base_rgba.mode:
        base_alpha_np = np.array(base_rgba.getchannel("A"))
        transparent_mask = base_alpha_np == 0
    else:
        transparent_mask = None

    overlay_with_alpha = overlay_rgba.copy()
    overlay_alpha = overlay_with_alpha.getchannel("A").point(
        lambda p: int(p * transparency)
    )
    overlay_with_alpha.putalpha(overlay_alpha)

    if transparent_mask is not None:
        overlay_np = np.array(overlay_with_alpha)
        overlay_np[transparent_mask] = [0, 0, 0, 0]
        overlay_with_alpha = Image.fromarray(overlay_np, "RGBA")

    return Image.alpha_composite(base_rgba, overlay_with_alpha)


def _build_output_path(
    base_image_path: Path,
    output_folder: Path,
    transparency: float,
) -> Path:
    ext = base_image_path.suffix.lower()
    opacity = int(transparency * 100)
    return output_folder / f"{base_image_path.stem}_{opacity}pct{ext}"


def _save_static_image(
    combined_image: Image.Image,
    output_path: Path,
    ext: str,
) -> None:
    if ext in {".jpg", ".jpeg", ".bmp"}:
        combined_image = combined_image.convert("RGB")

    combined_image.save(output_path)


def _save_animated_image(
    base_image: Image.Image,
    overlay_image: Image.Image,
    output_path: Path,
    transparency: float,
) -> None:
    frames: list[Image.Image] = []
    durations: list[int] = []

    for frame in ImageSequence.Iterator(base_image):
        duration = frame.info.get("duration", base_image.info.get("duration", 100))
        durations.append(duration)

        combined_frame = overlay_images(frame, overlay_image, transparency)
        frames.append(combined_frame)

    if not frames:
        raise ValueError("No frames found in animated image.")

    first_frame = frames[0]
    append_frames = frames[1:]

    first_frame.save(
        output_path,
        save_all=True,
        append_images=append_frames,
        duration=durations,
        loop=base_image.info.get("loop", 0),
        disposal=2,
    )


def process_images(
    base_image_path: Path,
    overlay_image_path: Path,
    output_folder: Path,
    transparency: float = 0.15,
) -> Path:
    """
    入力画像にウォーターマークを適用し、出力ファイルのパスを返す。
    """

    base_image_path = Path(base_image_path)
    overlay_image_path = Path(overlay_image_path)
    output_folder = Path(output_folder)

    if not base_image_path.exists():
        raise FileNotFoundError(f"Base image not found: {base_image_path.resolve()}")

    if not overlay_image_path.exists():
        raise FileNotFoundError(f"Overlay image not found: {overlay_image_path.resolve()}")

    if not (0 < transparency <= 1):
        raise ValueError("transparency must be greater than 0 and less than or equal to 1.")

    output_folder.mkdir(parents=True, exist_ok=True)

    ext = base_image_path.suffix.lower()
    output_path = _build_output_path(base_image_path, output_folder, transparency)

    with Image.open(base_image_path) as base_image:
        with Image.open(overlay_image_path) as overlay_image:
            if getattr(base_image, "is_animated", False):
                _save_animated_image(
                    base_image=base_image,
                    overlay_image=overlay_image,
                    output_path=output_path,
                    transparency=transparency,
                )
            else:
                combined_image = overlay_images(base_image, overlay_image, transparency)
                _save_static_image(combined_image, output_path, ext)

    return output_path
