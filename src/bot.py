from __future__ import annotations

import asyncio
import logging
import secrets
from pathlib import Path

import discord  # type: ignore
from discord import app_commands  # type: ignore
from discord.ext import commands  # type: ignore
from PIL import Image  # type: ignore

from utils.config_loader import ConfigLoader, ensure_base_dir, load_env
from utils.watermark_processor import process_images


# ------------------------------------------------------------
# Environment / paths
# ------------------------------------------------------------

env = load_env()

TOKEN = env["DISCORD_TOKEN"]
BASE_DIR = ensure_base_dir(env["BASE_DIR"])

# BASE_DIR default is data/src, so temp becomes data/temp.
TEMP_DIR = ensure_base_dir(str(BASE_DIR.parent / "temp"))
ERROR_FILES_DIR = ensure_base_dir(str(BASE_DIR.parent / "logs" / "error_files"))

config_loader = ConfigLoader(BASE_DIR)

# registered_extensions() には保存専用形式(.pdf 等)も含まれるため、
# Pillow が読み込める形式(Image.OPEN に登録済み)に限定する。
Image.init()
SUPPORTED_EXTENSIONS = {
    ext
    for ext, fmt in Image.registered_extensions().items()
    if fmt in Image.OPEN
}

DEFAULT_TRANSPARENCY = 15

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)

lock = asyncio.Lock()


# ------------------------------------------------------------
# Helpers
# ------------------------------------------------------------

def is_supported_image(filename: str) -> bool:
    return Path(filename).suffix.lower() in SUPPORTED_EXTENSIONS


def get_ids_from_interaction(interaction: discord.Interaction) -> tuple[int, int] | None:
    if interaction.guild_id is None or interaction.channel_id is None:
        return None
    return interaction.guild_id, interaction.channel_id


async def send_error_file_log(message: str) -> None:
    ERROR_FILES_DIR.mkdir(parents=True, exist_ok=True)
    error_log_path = ERROR_FILES_DIR / "error_log.txt"
    with open(error_log_path, "a", encoding="utf-8") as log_file:
        log_file.write(f"{message}\n")


def build_intro_message() -> str:
    return (
        "こんにちは！私は投稿された画像にウォーターマークを透過処理するBotです🤖\n\n"
        "このBotは、チャンネルごとに設定された透かし画像を、投稿された画像へ自動合成します。\n\n"
        "まずは `/wm set` で、このチャンネルに使う透かし画像を設定してください。\n"
        "設定後、このチャンネルに画像を投稿すると、自動で透かし入り画像を返信します。\n\n"
        "主なコマンド：\n"
        "- `/wm set` : このチャンネルの透かし画像を設定・更新\n"
        "- `/wm check` : 現在の設定を確認\n"
        "- `/wm opacity` : 透過度を変更\n"
        "- `/wm clear` : このチャンネルの設定を削除\n"
        "- `/wm help` : 使い方を表示\n\n"
        "⚠️ 透かし設定後は、このチャンネルに投稿された画像が自動加工されます。\n"
        "Bot専用チャンネルを作ることを推奨します。"
    )


# ------------------------------------------------------------
# Slash commands
# ------------------------------------------------------------

wm_group = app_commands.Group(
    name="wm",
    description="ウォーターマーク関連コマンド",
)


@wm_group.command(name="set", description="このチャンネルの透かし画像を設定・更新します")
@app_commands.describe(
    watermark="透かしとして使用する画像ファイル",
    opacity="透過度。1〜100の整数。未指定の場合は現在値または初期値15を使用します",
)
async def wm_set(
    interaction: discord.Interaction,
    watermark: discord.Attachment,
    opacity: int | None = None,
):
    ids = get_ids_from_interaction(interaction)
    if ids is None:
        await interaction.response.send_message(
            "このコマンドはサーバー内のチャンネルで使用してください。",
            ephemeral=True,
        )
        return

    if not is_supported_image(watermark.filename):
        await interaction.response.send_message(
            f"サポートされていないファイル形式です: `{watermark.filename}`",
            ephemeral=True,
        )
        return

    if opacity is not None and not (1 <= opacity <= 100):
        await interaction.response.send_message(
            "透過度は 1〜100 の整数で指定してください。",
            ephemeral=True,
        )
        return

    await interaction.response.defer(thinking=True)

    server_id, channel_id = ids
    channel_dir = config_loader.get_server_dir(server_id) / str(channel_id)
    channel_dir.mkdir(parents=True, exist_ok=True)

    channel_settings = config_loader.get_channel_settings(server_id, channel_id)

    # Remove old watermark file if exists.
    old_watermark = channel_settings.get("active_watermark")
    if old_watermark:
        try:
            Path(old_watermark).unlink(missing_ok=True)
        except Exception as e:
            logging.warning("Failed to remove old watermark: %s", e)

    ext = Path(watermark.filename).suffix.lower()
    saved_name = f"{secrets.token_hex(8)}{ext}"
    watermark_path = channel_dir / saved_name

    try:
        await watermark.save(watermark_path)

        # Verify that Pillow can open it as an image.
        with Image.open(watermark_path) as img:
            img.verify()

    except Exception as e:
        watermark_path.unlink(missing_ok=True)
        await interaction.followup.send(
            f"透かし画像の保存または検証に失敗しました: `{e}`",
            ephemeral=True,
        )
        return

    new_settings: dict[str, object] = {
        "active_watermark": str(watermark_path),
        "watermark_original_filename": watermark.filename,
    }

    if opacity is not None:
        new_settings["transparency"] = opacity

    config_loader.set_channel_settings(server_id, channel_id, new_settings)

    applied_opacity = opacity or channel_settings.get("transparency", DEFAULT_TRANSPARENCY)

    await interaction.followup.send(
        "このチャンネルの透かし画像を設定しました。\n"
        f"- ファイル名: `{watermark.filename}`\n"
        f"- 透過度: `{applied_opacity}%`"
    )


@wm_group.command(name="check", description="このチャンネルの透かし設定を確認します")
async def wm_check(interaction: discord.Interaction):
    ids = get_ids_from_interaction(interaction)
    if ids is None:
        await interaction.response.send_message(
            "このコマンドはサーバー内のチャンネルで使用してください。",
            ephemeral=True,
        )
        return

    server_id, channel_id = ids
    channel_settings = config_loader.get_channel_settings(server_id, channel_id)

    active_watermark = channel_settings.get("active_watermark")
    opacity = channel_settings.get("transparency", DEFAULT_TRANSPARENCY)
    original_filename = channel_settings.get("watermark_original_filename", "不明")

    if not active_watermark or not Path(str(active_watermark)).exists():
        await interaction.response.send_message(
            "このチャンネルには透かし画像が設定されていません。\n"
            "`/wm set` で透かし画像を設定してください。",
            ephemeral=True,
        )
        return

    await interaction.response.send_message(
        "現在の透かし設定です。\n"
        f"- 元ファイル名: `{original_filename}`\n"
        f"- 透過度: `{opacity}%`",
        file=discord.File(str(active_watermark), filename="watermark.png"),
    )


@wm_group.command(name="opacity", description="このチャンネルの透過度を変更します")
@app_commands.describe(opacity="透過度。1〜100の整数")
async def wm_opacity(interaction: discord.Interaction, opacity: int):
    ids = get_ids_from_interaction(interaction)
    if ids is None:
        await interaction.response.send_message(
            "このコマンドはサーバー内のチャンネルで使用してください。",
            ephemeral=True,
        )
        return

    if not (1 <= opacity <= 100):
        await interaction.response.send_message(
            "透過度は 1〜100 の整数で指定してください。",
            ephemeral=True,
        )
        return

    server_id, channel_id = ids
    channel_settings = config_loader.get_channel_settings(server_id, channel_id)

    if not channel_settings.get("active_watermark"):
        await interaction.response.send_message(
            "このチャンネルには透かし画像が設定されていません。\n"
            "先に `/wm set` で透かし画像を設定してください。",
            ephemeral=True,
        )
        return

    config_loader.set_transparency(server_id, channel_id, opacity)

    await interaction.response.send_message(
        f"このチャンネルの透過度を `{opacity}%` に設定しました。"
    )


@wm_group.command(name="clear", description="このチャンネルの透かし設定を削除します")
async def wm_clear(interaction: discord.Interaction):
    ids = get_ids_from_interaction(interaction)
    if ids is None:
        await interaction.response.send_message(
            "このコマンドはサーバー内のチャンネルで使用してください。",
            ephemeral=True,
        )
        return

    server_id, channel_id = ids
    channel_settings = config_loader.get_channel_settings(server_id, channel_id)

    active_watermark = channel_settings.get("active_watermark")
    if active_watermark:
        try:
            Path(str(active_watermark)).unlink(missing_ok=True)
        except Exception as e:
            logging.warning("Failed to remove watermark file: %s", e)

    config_loader.delete_channel_settings(server_id, channel_id)

    await interaction.response.send_message(
        "このチャンネルの透かし設定を削除しました。"
    )


@wm_group.command(name="help", description="Watermark Botの使い方を表示します")
async def wm_help(interaction: discord.Interaction):
    await interaction.response.send_message(build_intro_message(), ephemeral=True)


# ------------------------------------------------------------
# Bot events
# ------------------------------------------------------------

class WatermarkBot(commands.Bot):
    async def setup_hook(self):
        self.tree.add_command(wm_group)
        await self.tree.sync()
        logging.info("Slash commands synced.")


intents = discord.Intents.default()
intents.messages = True
intents.message_content = True
intents.guilds = True

bot = WatermarkBot(command_prefix="!", intents=intents)


@bot.event
async def on_ready():
    logging.info("Logged in as %s", bot.user)


@bot.event
async def on_guild_join(guild: discord.Guild):
    intro_message = build_intro_message()

    if guild.system_channel:
        try:
            await guild.system_channel.send(intro_message)
            return
        except discord.Forbidden:
            logging.warning("%s のシステムチャンネルに送信できませんでした。", guild.name)

    for channel in guild.text_channels:
        if channel.permissions_for(guild.me).send_messages:
            try:
                await channel.send(intro_message)
                return
            except discord.Forbidden:
                continue


@bot.event
async def on_message(message: discord.Message):
    """
    添付画像が投稿された際、チャンネル設定に応じて透かしを適用する。
    スラッシュコマンドは on_message では処理しない。
    """

    if message.author.bot:
        return

    if message.guild is None:
        return

    if not message.attachments:
        return

    server_id = message.guild.id
    channel_id = message.channel.id

    channel_settings = config_loader.get_channel_settings(server_id, channel_id)
    active_watermark = channel_settings.get("active_watermark")

    if not active_watermark:
        return

    active_watermark_path = Path(str(active_watermark))
    if not active_watermark_path.exists():
        logging.warning("Configured watermark does not exist: %s", active_watermark_path)
        return

    opacity = channel_settings.get("transparency", DEFAULT_TRANSPARENCY)
    transparency = int(opacity) / 100

    supported_attachments = [
        attachment
        for attachment in message.attachments
        if is_supported_image(attachment.filename)
    ]

    if not supported_attachments:
        return

    async with lock:
        TEMP_DIR.mkdir(parents=True, exist_ok=True)

        for attachment in supported_attachments:
            ext = Path(attachment.filename).suffix.lower()
            input_path = TEMP_DIR / f"{secrets.token_hex(8)}{ext}"
            output_path: Path | None = None

            try:
                await attachment.save(input_path)

                output_path = process_images(
                    base_image_path=input_path,
                    overlay_image_path=active_watermark_path,
                    output_folder=TEMP_DIR,
                    transparency=transparency,
                )

                # 合成後のファイルがサーバーのアップロード上限を超えると
                # Discord 側で 413 (error code 40005) になるため送信前に確認する。
                size_limit = message.guild.filesize_limit
                output_size = output_path.stat().st_size
                if output_size > size_limit:
                    await send_error_file_log(
                        f"Output too large: attachment={attachment.filename}, "
                        f"size={output_size}, limit={size_limit}"
                    )
                    await message.channel.send(
                        f"加工後の画像がこのサーバーのアップロード上限を超えたため送信できません: "
                        f"`{attachment.filename}` "
                        f"({output_size / 1024 / 1024:.1f}MB > 上限 {size_limit / 1024 / 1024:.1f}MB)"
                    )
                    continue

                send_filename = f"{Path(attachment.filename).stem}_wm{ext}"
                await message.channel.send(
                    file=discord.File(str(output_path), filename=send_filename)
                )

            except Exception as e:
                logging.exception("Failed to process attachment: %s", attachment.filename)
                await send_error_file_log(
                    f"Unexpected error: attachment={attachment.filename}, error={e}"
                )
                await message.channel.send(
                    f"画像処理中にエラーが発生しました: `{attachment.filename}`"
                )

            finally:
                # 失敗時も一時ファイルを残さない。
                input_path.unlink(missing_ok=True)
                if output_path is not None:
                    output_path.unlink(missing_ok=True)


# ------------------------------------------------------------
# Run
# ------------------------------------------------------------

if __name__ == "__main__":
    if not TOKEN:
        raise RuntimeError("DISCORD_TOKEN is not set.")

    bot.run(TOKEN)
