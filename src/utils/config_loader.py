import json, os
from pathlib import Path
from dotenv import load_dotenv # type: ignore

class ConfigLoader:
    def __init__(self, base_dir="data"):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(exist_ok=True)

    def get_server_dir(self, server_id):
        server_dir = self.base_dir / str(server_id)
        server_dir.mkdir(parents=True, exist_ok=True)
        return server_dir

    def get_settings_file(self, server_id):
        server_dir = self.get_server_dir(server_id)
        return server_dir / "settings.json"

    def load_server_settings(self, server_id):
        settings_file = self.get_settings_file(server_id)
        if not settings_file.exists():
            return {"channels": {}}
        with open(settings_file, "r") as f:
            return json.load(f)

    def save_server_settings(self, server_id, settings):
        settings_file = self.get_settings_file(server_id)
        with open(settings_file, "w") as f:
            json.dump(settings, f, indent=4)

    def get_channel_settings(self, server_id, channel_id):
        server_settings = self.load_server_settings(server_id)
        return server_settings["channels"].get(str(channel_id), {})

    def set_channel_settings(self, server_id, channel_id, settings):
        """
        チャンネル設定を保存。既存の設定がある場合は上書きせず追記。
        """
        server_settings = self.load_server_settings(server_id)
        channel_settings = server_settings["channels"].get(str(channel_id), {})

        # 既存の設定に新しい設定を更新
        channel_settings.update(settings)

        # サーバー全体の設定を更新
        server_settings["channels"][str(channel_id)] = channel_settings

        # 保存
        self.save_server_settings(server_id, server_settings)

    def delete_channel_settings(self, server_id, channel_id):
        server_settings = self.load_server_settings(server_id)
        if str(channel_id) in server_settings["channels"]:
            del server_settings["channels"][str(channel_id)]
            self.save_server_settings(server_id, server_settings)

    # 透過度のみを変更するメソッド
    async def set_transparency(self, server_id, channel_id, transparency):
        """
        チャンネル設定に透過度を保存
        """
        if not isinstance(transparency, int) or not (1 <= transparency <= 100):
            raise ValueError("Transparency must be an integer between 1 and 100.")
        
        try:
            self.set_channel_settings(server_id, channel_id, {"transparency": transparency})
        except Exception as e:
            raise RuntimeError(f"Failed to set transparency: {e}")

    
def load_env():
    """
    Load environment variables from a .env file and return them as a dictionary.
    """
    load_dotenv()
    return {
        "DISCORD_TOKEN": os.getenv("DISCORD_TOKEN"),
        "COMMAND_PREFIX": os.getenv("COMMAND_PREFIX", "/"),
        "BASE_DIR": os.getenv("BASE_DIR", "data/src"),
    }

def ensure_base_dir(base_dir):
    """
    Ensure the base directory exists. Create it if it doesn't exist.
    """
    path = Path(base_dir)
    path.mkdir(parents=True, exist_ok=True)
    return path
