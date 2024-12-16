import json, os
from pathlib import Path
from dotenv import load_dotenv

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
        server_settings = self.load_server_settings(server_id)
        server_settings["channels"][str(channel_id)] = settings
        self.save_server_settings(server_id, server_settings)

    def delete_channel_settings(self, server_id, channel_id):
        server_settings = self.load_server_settings(server_id)
        if str(channel_id) in server_settings["channels"]:
            del server_settings["channels"][str(channel_id)]
            self.save_server_settings(server_id, server_settings)


    
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
