import discord # type: ignore
import shutil  # ファイル削除用
import logging
import asyncio
from pathlib import Path
from discord.ext import commands # type: ignore
from discord import app_commands # type: ignore
from PIL import Image # type: ignore
from utils.config_loader import load_env, ensure_base_dir, ConfigLoader
from utils.watermark_processor import process_images, overlay_images


# create watermark class
class Watermark(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.watermark_group = app_commands.Group(name="watermark", description="Watermark related commands")

    @app_commands.command(name="show", description="Show the active watermark")
    async def show_watermark(self, interaction: discord.Interaction):
        await interaction.response.send_message("Showing watermark...")

    @app_commands.command(name="upload", description="Upload a new watermark")
    async def upload_watermark(self, interaction: discord.Interaction):
        await interaction.response.send_message("Uploading watermark...")

    @app_commands.command(name="clear", description="Clear the active watermark")
    async def clear_watermark(self, interaction: discord.Interaction):
        await interaction.response.send_message("Clearing watermark...")

# Load environment variables
env = load_env()
TOKEN = env["DISCORD_TOKEN"]
PREFIX = env["COMMAND_PREFIX"]
# BASE_DIR = ensure_base_dir(env["BASE_DIR"])
BASE_DIR = Path("data/guilds")

# Pillowがサポートする拡張子一覧を取得
PIL_SUPPORTED_EXT = list(Image.registered_extensions().keys())

# アルファチャンネルを持ちうる拡張子
ALPHA_SUPPORTED_EXT = {".png", ".tiff", ".tif", ".webp", ".ico", ".dds", ".jp2", ".j2k", ".jpx", ".j2c", ".sgi", ".rgb", ".tga"}

# アルファチャンネルを持たない拡張子（例外的な対応が必要なもの）
ALPHA_NOT_SUPPORTED_EXT = {".jpg", ".jpeg", ".bmp", ".gif", ".ppm", ".pgm", ".pbm"}

# Initialize ConfigLoader
config_loader = ConfigLoader(BASE_DIR)

# Initialize logger
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Set up intents and bot instance
intents = discord.Intents.default()
intents.messages = True       # メッセージ関連Intentを有効化
intents.message_content = True  # メッセージ内容Intentを有効化
intents.guilds = True  # サーバー情報の取得を有効化

# lock instance
lock = asyncio.Lock()

# bot instance
bot = commands.Bot(command_prefix=PREFIX, intents=intents)

@bot.event
async def on_ready():
    bot.tree.add_command(Watermark(bot).watermark_group)
    await bot.tree.sync()
    print("Watermark commands synced!")

@bot.event
async def on_guild_join(guild):
    """
    新しいサーバーに追加されたときのイベント。
    """
    intro_path = Path("intro.md")
    if intro_path.exists():
        with open(intro_path, "r", encoding="utf-8") as file:
            intro_content = file.read()

    # システムチャンネルがある場合はそこに送信
    if guild.system_channel:  # デフォルトのシステムチャンネル
        try:
            await guild.system_channel.send(intro_content)
        except discord.Forbidden:
            print(f"{guild.name}のシステムチャンネルにメッセージを送信できませんでした。")
    else:
        # 送信可能なテキストチャンネルを探す
        for channel in guild.text_channels:
            if channel.permissions_for(guild.me).send_messages:
                try:
                    await channel.send(intro_content)
                    break
                except discord.Forbidden:
                    continue

@bot.command()
async def hello(ctx):
    await ctx.send("hello from discord")

@bot.command(aliases=['wm_set', 'uw'])
async def upload_watermark(ctx):
    def check(msg):
        return msg.attachments and msg.channel == ctx.channel and msg.author == ctx.author

    # 画像が添付されていない場合
    if not ctx.message.attachments:

        # await ctx.send("Please attach an image to set as the watermark. You have 60 seconds to upload an image.")
        await ctx.send("ウォーターマークとして設定する画像を添付してください。60秒以内に画像をアップロードしてください。")

        try:
            # 画像の添付を待機
            msg = await bot.wait_for('message', timeout=60.0, check=check)

        # 添付されなかった場合はそのまま終了
        except asyncio.TimeoutError:
            # await ctx.send("No image was uploaded within 60 seconds. Command timed out.")
            await ctx.send("60秒以内に画像がアップロードされませんでした。コマンドがタイムアウトしました。")
            return

        # 画像が添付された場合はそれを取得
        attachment = msg.attachments[0]

    # 画像が添付されていた場合
    else:
        attachment = ctx.message.attachments[0]
        # 画像の拡張子を確認
        extension = Path(attachment.filename).suffix.lower()
        if extension not in PIL_SUPPORTED_EXT:
            # await ctx.send(f"Unsupported file format: {attachment.filename}")
            await ctx.send(f"サポートされていないファイル形式です: {attachment.filename}")
            return

    server_id = ctx.guild.id
    channel_id = ctx.channel.id

    # 保存パスの生成
    channel_dir = config_loader.get_server_dir(server_id) / str(channel_id)
    channel_dir.mkdir(parents=True, exist_ok=True)
    watermark_path = channel_dir / attachment.filename

    # 既存のウォーターマークを削除
    channel_settings = config_loader.get_channel_settings(server_id, channel_id)
    if "active_watermark" in channel_settings:
        try:
            Path(channel_settings["active_watermark"]).unlink()
        except FileNotFoundError:
            pass

    # 新しいウォーターマークを保存
    await attachment.save(watermark_path)

    # 設定を更新
    config_loader.set_channel_settings(server_id, channel_id, {"active_watermark": str(watermark_path)})
    # await ctx.send(f"Watermark uploaded and set to: {attachment.filename}")
    await ctx.send(f"ウォーターマークが設定されました: {attachment.filename}")

# 透過度を変更する関数
@bot.command(aliases=['wm_settp'])
async def set_watermark_transparency(ctx, transparency: int = None):
    """
    チャンネルごとの透過度を設定するコマンド
    """
    # 現在の設定値を確認
    server_id = ctx.guild.id
    channel_id = ctx.channel.id
    try:
        channel_settings = config_loader.get_channel_settings(server_id, channel_id)
    except Exception as e:
        await ctx.send(f"Error loading settings: {e}")
        return

    if transparency is None:
        # await ctx.send(f"Please specify a transparency value between 1 and 100. Current setting value is {str(transparency)}e.g.: `/wm_settp 50`.")
        await ctx.send(f"透過度を1から100の半角数字で指定してください。現在の設定値は{str(transparency)}です。例： `/wm_settp 50`.")
        return

    try:
        # 引数を整数に変換
        transparency = int(transparency)
    except ValueError:
        # await ctx.send("Invalid transparency value. Please provide a valid number between 1 and 100.")
        await ctx.send("不正な値です。1から100の間で有効な数値を指定してください。")
        return

    if not (1 <= transparency <= 100):
        # await ctx.send("Invalid transparency value. Please provide a number between 1 and 100.")
        await ctx.send("無効な値です。1から100の間で有効な数値を指定してください。")
        return

    try:
        # 透過度を設定
        await config_loader.set_transparency(server_id, channel_id, transparency)
        # await ctx.send(f"Transparency has been set to {transparency}% for this channel.")
        await ctx.send(f"このチャンネルでの透過度は {transparency}% に設定されました。")
    except Exception as e:
        # await ctx.send(f"An error occurred while setting transparency: {e}")
        await ctx.send(f"透過度の設定中にエラーが発生しました。 {e}")

@bot.command(aliases=['wm_check', 'sw'])
async def show_watermark(ctx):
    server_id = ctx.guild.id
    channel_id = ctx.channel.id
    try:
        channel_settings = config_loader.get_channel_settings(server_id, channel_id)
    except Exception as e:
        # await ctx.send(f"Error loading settings: {e}")
        await ctx.send(f"設定が読み込めませんでした: {e}")
        return

    active_watermark = channel_settings.get("active_watermark")
    transparency = channel_settings.get("transparency", 15)  # デフォルト透過度

    if active_watermark and Path(active_watermark).exists():
        file = discord.File(active_watermark, filename="watermark.png")
        # await ctx.send(f"Current active watermark with transparency {transparency}:", file=file)
        await ctx.send(f"現在の透過度は {transparency}% です。", file=file)
    else:
        # await ctx.send("No active watermark is set for this channel. We may help you by `wm_help` command.")
        await ctx.send("こちらのチャンネルではウォーターマークが設定されていません。`wm_help`から使用方法をご確認ください。")
        # デバッグ用ログ
        print(f"No active watermark for channel : {channel_settings}")

@bot.command(aliases=['wm_clear', 'cw'])
async def clear_watermark(ctx):
    server_id = ctx.guild.id
    channel_id = ctx.channel.id

    # 設定をクリア
    config_loader.delete_channel_settings(server_id, channel_id)
    # await ctx.send("Active watermark has been cleared.")
    await ctx.send("このチャンネルではウォーターマークが無効化されました。")

@bot.command(aliases=['wm_intro', 'intro', 'wm_help'])
async def self_introduce(ctx):
    intro_path = Path("intro.md")
    if intro_path.exists():
        with open(intro_path, "r", encoding="utf-8") as file:
            intro_content = file.read()
        # Discord メッセージの最大文字数は2000文字
        if len(intro_content) > 2000:
            # await ctx.send("The self is too long to display in a single message.")
            await ctx.send("メッセージが長すぎて投稿できませんでした。")
        else:
            await ctx.send(intro_content)
    else:
        # await ctx.send("Something went wrong. Please try again later.")
        await ctx.send("不明なエラーが発生しました。後ほど再度お試しください。")

@bot.command(aliases=['wm_tos', 'tos'])
async def TermsofService(ctx):
    tos_path = Path("ToS.md")
    if tos_path.exists():
        with open(tos_path, "r", encoding="utf-8") as file:
            tos_content = file.read()
        # Discord メッセージの最大文字数は2000文字
        if len(tos_content) > 2000:
            # await ctx.send("The Terms of Service is too long to display in a single message. Please check the [Google Docs](https://docs.google.com/document/d/1iZ3O5GVKic53Ymi__KP3RHifNY6JNUdpG-048czEQH4/edit?usp=sharing) directly.")
            await ctx.send("利用規約が長すぎて投稿できませんでした。")
        else:
            await ctx.send(tos_content)
    else:
        # await ctx.send("Terms of Service file (ToS.md) not found in the project directory.")
        await ctx.send("利用規約が見つかりませんでした。")

import asyncio

lock = asyncio.Lock()  # ロックを作成
# 透過度を確認する関数
async def set_transparency(server_id, channel_id, transparency):
    """
    チャンネル設定に透過度を保存
    """
    try:
        config_loader.set_channel_settings(server_id, channel_id, {"transparency": transparency})
    except Exception as e:
        logging.error(f"Failed to set transparency: {e}")

@bot.event
async def on_message(message):
    """
    メッセージが投稿された際にトリガーされるイベント。
    添付画像があればウォーターマークを適用し、返信として送信する。
    """

    # Bot自身のメッセージは無視
    if message.author.bot:
        return

    # プレフィックスコマンドが存在する場合はスキップして処理
    if message.content.startswith(PREFIX):
        await bot.process_commands(message)
        return

    # メッセージに添付ファイルがあるか確認
    if not message.attachments:
        # 他のコマンドが処理されるようにする
        await bot.process_commands(message)
        return

    # サーバー情報とチャンネル情報を取得
    server_id = message.guild.id
    channel_id = message.channel.id

    # チャンネル設定を取得
    channel_settings = config_loader.get_channel_settings(server_id, channel_id)
    transparency = channel_settings.get("transparency", 15) / 100  # 透過率を0.0~1.0に変換
    # チャンネルごとのウォーターマークを取得
    active_watermark = channel_settings.get("active_watermark")

    # ウォーターマークが設定されていないチャンネルではなにもしない
    if not active_watermark:
        return

    async with lock:  # ロックを取得して処理を直列化
        # 必要なディレクトリを定義
        temp_dir = Path("/data/temp")
        error_files_dir = Path("/data/logs/error_files")

        try:
            error_files_dir.mkdir(parents=True, exist_ok=True)  # エラー用ディレクトリ

            # ディレクトリ作成成功のログ
            logging.info(f"Temp directory created or exists: {temp_dir.resolve()}")
            logging.info(f"Error files directory created or exists: {error_files_dir.resolve()}")
        except PermissionError as perm_error:
            logging.error(f"Permission error creating directories: {perm_error}")
            return
        except Exception as dir_error:
            logging.error(f"Failed to create directories: {dir_error}")
            return

        # 添付ファイルを保存してウォーターマーク処理
        for attachment in message.attachments:
            # 添付ファイルの拡張子を取得
            extension = Path(attachment.filename).suffix.lower()

            if extension not in PIL_SUPPORTED_EXT:
                # await message.channel.send(f"Unsupported file type: {attachment.filename}")
                await message.channel.send(f"サポートされていない拡張子です: {attachment.filename}")
                continue

            try:
                # 一時的な保存パス
                input_path = temp_dir / attachment.filename
                output_file_name = f"{attachment.filename.split('.')[0]}_{str(int(transparency*100))}pct{extension}" # 一時的に保存する出力先
                output_path = temp_dir / output_file_name

                # 添付ファイルを保存
                await attachment.save(input_path)

                # 保存後に存在確認とログ出力
                if input_path.exists():
                    logging.info(f"File exists and is accessible: {input_path.resolve()}")
                else:
                    logging.error(f"File is not accessible: {input_path.resolve()}")
                    raise FileNotFoundError(f"File was not saved: {input_path}")

                logging.info(f"Base image path passed to process_images: {input_path}")
                logging.info(f"Overlay image path passed to process_images: {Path(active_watermark)}")

                # ウォーターマークを適用
                process_images(
                    base_image_path=input_path,
                    overlay_image_path=Path(active_watermark),
                    output_folder=temp_dir,
                    transparency=transparency,  # 透過率は読み出し時に0.0~1.0に変換
                )

                # 保存後に存在確認とログ出力
                if output_path.exists():
                    logging.info(f"File exists and is accessible: {output_path.resolve()}")
                else:
                    logging.error(f"File is not accessible: {output_path.resolve()}")
                    raise FileNotFoundError(f"File was not saved: {output_path}")

                logging.info(f"Processed image path passed to process_images: {output_path}")

                # 処理後の画像を送信
                await message.channel.send(file=discord.File(str(output_path)))

                # 正常に処理できたら一時ファイルを削除
                # input_path.unlink(missing_ok=True)  # 元の添付ファイル
                # output_path.unlink(missing_ok=True)  # 処理後のファイル

            except FileNotFoundError as fnf_error:
                await message.channel.send(f"File not found error: {fnf_error}")
                error_log_path = error_files_dir / "error_log.txt"
                with open(error_log_path, "a") as log_file:
                    log_file.write(f"FileNotFoundError: {fnf_error}\n")

            except Exception as e:
                await message.channel.send(f"An error occurred: {e}")
                error_log_path = error_files_dir / "error_log.txt"
                with open(error_log_path, "a") as log_file:
                    log_file.write(f"Unexpected error: {e}\n")

    # 他のコマンドが処理されるようにする
    await bot.process_commands(message)

# Run the bot
if __name__ == "__main__":
    import signal
    
    def shutdown_handler(signal, frame):
        loop = asyncio.get_event_loop()
        loop.create_task(bot.close())
    
    signal.signal(signal.SIGINT, shutdown_handler)
    signal.signal(signal.SIGTERM, shutdown_handler)
    
    bot.run(TOKEN)
