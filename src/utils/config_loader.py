from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv  # type: ignore


class ConfigLoader:
    def __init__(self, base_dir: str | Path = "data/src"):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def get_server_dir(self, server_id: int | str) -> Path:
        server_dir = self.base_dir / str(server_id)
        server_dir.mkdir(parents=True, exist_ok=True)
        return server_dir

    def get_settings_file(self, server_id: int | str) -> Path:
        return self.get_server_dir(server_id) / "settings.json"

    def load_server_settings(self, server_id: int | str) -> dict[str, Any]:
        settings_file = self.get_settings_file(server_id)

        if not settings_file.exists():
            return {"channels": {}}

        with open(settings_file, "r", encoding="utf-8") as f:
            settings = json.load(f)

        if not isinstance(settings, dict):
            return {"channels": {}}

        if "channels" not in settings or not isinstance(settings["channels"], dict):
            settings["channels"] = {}

        return settings

    def save_server_settings(self, server_id: int | str, settings: dict[str, Any]) -> None:
        settings_file = self.get_settings_file(server_id)

        with open(settings_file, "w", encoding="utf-8") as f:
            json.dump(settings, f, indent=4, ensure_ascii=False)

    def get_channel_settings(self, server_id: int | str, channel_id: int | str) -> dict[str, Any]:
        server_settings = self.load_server_settings(server_id)
        return server_settings["channels"].get(str(channel_id), {})

    def set_channel_settings(
        self,
        server_id: int | str,
        channel_id: int | str,
        settings: dict[str, Any],
    ) -> None:
        server_settings = self.load_server_settings(server_id)
        channel_settings = server_settings["channels"].get(str(channel_id), {})

        channel_settings.update(settings)
        server_settings["channels"][str(channel_id)] = channel_settings

        self.save_server_settings(server_id, server_settings)

    def delete_channel_settings(self, server_id: int | str, channel_id: int | str) -> None:
        server_settings = self.load_server_settings(server_id)

        if str(channel_id) in server_settings["channels"]:
            del server_settings["channels"][str(channel_id)]
            self.save_server_settings(server_id, server_settings)

    def set_transparency(self, server_id: int | str, channel_id: int | str, transparency: int) -> None:
        if not isinstance(transparency, int) or not (1 <= transparency <= 100):
            raise ValueError("Transparency must be an integer between 1 and 100.")

        self.set_channel_settings(
            server_id,
            channel_id,
            {"transparency": transparency},
        )


def load_env() -> dict[str, str | None]:
    load_dotenv()

    return {
        "DISCORD_TOKEN": os.getenv("DISCORD_TOKEN"),
        "BASE_DIR": os.getenv("BASE_DIR", "data/src"),
    }


def ensure_base_dir(base_dir: str | Path) -> Path:
    path = Path(base_dir)
    path.mkdir(parents=True, exist_ok=True)
    return path
