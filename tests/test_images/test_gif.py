from PIL import Image
from pathlib import Path

def create_gif_with_fixed_palette(frames_folder: Path, output_gif_path: Path, duration=170):
    """
    各フレームのパレットサイズを固定し、正しい透過設定でGIFを生成します。

    引数:
        - frames_folder: フレーム画像が保存されたフォルダ
        - output_gif_path: 出力GIFファイルのパス
        - duration: 各フレームの表示時間 (ミリ秒)
    """
    frames = [Image.open(frame_path).convert("RGBA") for frame_path in sorted(frames_folder.glob("*.png"))]

    if not frames:
        raise ValueError(f"指定されたフォルダにフレームが存在しません: {frames_folder.resolve()}")

    palette_frames = []
    transparency_index = 254

    for frame in frames:
        # # パレットモードに変換し、透明部分を設定
        # p_frame = frame.convert("P", palette=Image.ADAPTIVE, colors=256)
        # alpha = frame.getchannel("A")
        # mask = Image.eval(alpha, lambda a: 255 if a < 128 else 0)
        # p_frame.paste(transparency_index, mask=mask)
        # palette_frames.append(p_frame)

        # RGBA → P (最大255色) に変換
        p_frame = frame.convert("P", palette=Image.ADAPTIVE, colors=255)

        # アルファチャネルからマスクを作り、インデックス254を塗り込む
        alpha = frame.getchannel("A")
        mask = Image.eval(alpha, lambda a: 255 if a < 128 else 0)
        p_frame.paste(transparency_index, mask=mask)

        palette_frames.append(p_frame)

    durations = [duration] * len(palette_frames)

    # GIFを生成
    palette_frames[0].save(
        output_gif_path,
        save_all=True,
        append_images=palette_frames[1:],
        duration=durations,
        loop=0,
        transparency=transparency_index,
        disposal=3,  # 前フレームを破棄
        optimize=False
    )
    print(f"GIFを生成しました: {output_gif_path}")

def check_frame_images(frames_folder: Path):
    """
    フレーム画像のサイズやモードを確認します。

    引数:
        - frames_folder: フレーム画像が保存されたフォルダ
    """
    frames = list(sorted(frames_folder.glob("*.png")))

    if not frames:
        print(f"指定されたフォルダにフレームが存在しません: {frames_folder.resolve()}")
        return

    for i, frame_path in enumerate(frames):
        with Image.open(frame_path) as img:
            print(f"Frame {i}: Path={frame_path}, Size={img.size}, Mode={img.mode}")

if __name__ == "__main__":
    # テスト用ディレクトリと出力先
    frames_folder = Path("tests/test_images/test_output/frames/")
    output_gif_path = Path("tests/test_images/test_output/output_fixed_palette.gif")

    check_frame_images(frames_folder)

    # GIF作成関数を実行
    try:
        create_gif_with_fixed_palette(frames_folder, output_gif_path, duration=170)
    except Exception as e:
        print(f"GIF作成中にエラーが発生しました: {e}")
