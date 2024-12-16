import discord
import shutil  # ファイル削除用
from pathlib import Path
from discord.ext import commands
from discord import app_commands
from PIL import Image
from utils.config_loader import load_env, ensure_base_dir, ConfigLoader
from utils.watermark_processor import process_images

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
BASE_DIR = ensure_base_dir(env["BASE_DIR"])

# Initialize ConfigLoader
config_loader = ConfigLoader(BASE_DIR)

# Set up intents and bot instance
intents = discord.Intents.default()
intents.messages = True       # メッセージ関連Intentを有効化
intents.message_content = True  # メッセージ内容Intentを有効化
intents.guilds = True  # サーバー情報の取得を有効化

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
    guide_message = (
        "こんにちは！私は投稿された画像にウォーターマークを透過処理するBotです🤖\n"
        "使い方は簡単！`/wm_set`と一緒にウォーターマークを設定した状態で、このチャンネルに画像ファイルを送るだけ！\n"
        "以下のコマンドからお試しください：\n\n"
        "📌 `/wm_set` - コマンドを送信する際にウォーターマークを一緒に送ってください！更新もこちら！\n"
        "📌 `/wm_check` - 現在有効なウォーターマークを確認できます\n"
        "📌 `/wm_clear` - 現在のウォーターマークを削除\n\n"
        "チャンネルごとに異なるウォーターマークを設定できます\n"
        "何か質問があれば、ぶらんちにお問い合わせください！"
    )

    # システムチャンネルがある場合はそこに送信
    if guild.system_channel:  # デフォルトのシステムチャンネル
        try:
            await guild.system_channel.send(guide_message)
        except discord.Forbidden:
            print(f"{guild.name}のシステムチャンネルにメッセージを送信できませんでした。")
    else:
        # 送信可能なテキストチャンネルを探す
        for channel in guild.text_channels:
            if channel.permissions_for(guild.me).send_messages:
                try:
                    await channel.send(guide_message)
                    break
                except discord.Forbidden:
                    continue

@bot.command()
async def hello(ctx):
    await ctx.send("hello from discord")

@bot.command(aliases=['wm_set', 'uw'])
async def upload_watermark(ctx):
    if not ctx.message.attachments:
        await ctx.send("Please attach an image to set as the watermark.")
        return

    attachment = ctx.message.attachments[0]
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
    await ctx.send(f"Watermark uploaded and set to: {attachment.filename}")

@bot.command(aliases=['wm_check', 'sw'])
async def show_watermark(ctx):
    server_id = ctx.guild.id
    channel_id = ctx.channel.id
    channel_settings = config_loader.get_channel_settings(server_id, channel_id)

    active_watermark = channel_settings.get("active_watermark")
    if active_watermark:
        file = discord.File(active_watermark, filename="watermark.png")
        await ctx.send("Current active watermark:", file=file)
    else:
        await ctx.send("No active watermark is set for this channel.")


@bot.command(aliases=['wm_clear', 'cw'])
async def clear_watermark(ctx):
    server_id = ctx.guild.id
    channel_id = ctx.channel.id

    # 設定をクリア
    config_loader.delete_channel_settings(server_id, channel_id)
    await ctx.send("Active watermark has been cleared.")

# Pillowがサポートする拡張子一覧
supported_extensions = list(Image.registered_extensions().keys())

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

    server_id = message.guild.id
    channel_id = message.channel.id
    
    # チャンネルごとのウォーターマークを取得
    channel_settings = config_loader.get_channel_settings(server_id, channel_id)
    active_watermark = channel_settings.get("active_watermark")

    if not active_watermark:
        await message.channel.send("No active watermark is set for this channel.")
        await bot.process_commands(message)
        return

    # 必要なディレクトリを定義
    temp_dir = Path("temp")
    error_files_dir = Path("logs/error_files")
    temp_dir.mkdir(exist_ok=True)  # 一時ディレクトリ
    error_files_dir.mkdir(parents=True, exist_ok=True)  # エラー用ディレクトリ

    # 添付ファイルを保存してウォーターマーク処理
    for attachment in message.attachments:
        # 添付ファイルの拡張子を取得
        extension = Path(attachment.filename).suffix.lower()

        if extension not in supported_extensions:
            await message.channel.send(f"Unsupported file type: {attachment.filename}")
            continue

        try:
            # 一時的な保存パス
            input_path = temp_dir / attachment.filename
            output_file_name = f"{attachment.filename.split('.')[0]}_15％{extension}" # 一時的に保存する出力先
            output_path = temp_dir / output_file_name

            # 添付ファイルを保存
            await attachment.save(input_path)

            # ウォーターマークを適用
            process_images(
                base_image_path=str(input_path),
                overlay_image_path=active_watermark,
                output_folder=str(temp_dir),
                transparencies=[0.15],  # デフォルトの透過率
            )

            # 処理後の画像を送信
            await message.channel.send(file=discord.File(str(output_path)))

            # 正常に処理できたら一時ファイルを削除
            input_path.unlink(missing_ok=True)  # 元の添付ファイル
            output_path.unlink(missing_ok=True)  # 処理後のファイル

        except Exception as e:
            # エラー時にファイルを保存
            error_file_path = error_files_dir / attachment.filename
            shutil.copy(input_path, error_file_path)  # エラー時に一時ファイルを保存
            error_log_path = error_files_dir / "error_log.txt"
            with open(error_log_path, "a") as log_file:
                log_file.write(f"Error processing {attachment.filename}: {e}\n")

            await message.channel.send(f"An error occurred while processing {attachment.filename}: {e}")

    # 他のコマンドが処理されるようにする
    await bot.process_commands(message)

# Run the bot
if __name__ == "__main__":
    bot.run(TOKEN)
