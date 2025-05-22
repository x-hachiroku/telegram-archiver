import json
from os import environ
from pathlib import Path

appdata = Path(environ.get('APPDATA', '/appdata'))

with open(appdata / 'config.json', 'r', encoding='utf-8') as f:
    config = json.load(f)
    config['download']['media'] = Path(config['download']['media'])
    config['download']['incomplete'] = Path(config['download']['incomplete'])
