from pathlib import Path
import json

def load_json(file_path):
    file_path = Path(file_path)
    if file_path.exists():
        with open(file_path, "r") as file:
            return json.load(file)
    return {}

def save_json(file_path, data):
    file_path = Path(file_path)
    with open(file_path, "w") as file:
        json.dump(data, file, indent=4)
