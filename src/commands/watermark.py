from pathlib import Path
import json

def get_channel_dir(base_dir, channel_id):
    channel_dir = Path(base_dir) / str(channel_id)
    channel_dir.mkdir(parents=True, exist_ok=True)
    return channel_dir

def save_channel_config(base_dir, channel_id, config):
    config_path = get_channel_dir(base_dir, channel_id) / "config.json"
    with open(config_path, "w") as file:
        json.dump(config, file, indent=4)

def get_channel_config(base_dir, channel_id):
    config_path = get_channel_dir(base_dir, channel_id) / "config.json"
    if config_path.exists():
        with open(config_path, "r") as file:
            return json.load(file)
    return {}

def get_active_watermark(base_dir, channel_id):
    config = get_channel_config(base_dir, channel_id)
    return config.get("active_watermark")
