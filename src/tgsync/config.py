import json
from pathlib import Path

with open(Path('/appdata') / 'config.json', 'r', encoding='utf-8') as f:
    config = json.load(f)
