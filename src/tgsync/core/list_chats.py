import json
from pathlib import Path

from tgsync.config import config
from tgsync.logger import logger


async def list_chats(client):
    chats = {}
    async for dialog in client.iter_dialogs():
        chats[dialog.name] = str(dialog.id)

    with open(Path('/appdata') / 'chats.json', 'w') as f:
        json.dump(chats, f, ensure_ascii=False, indent=2)

    logger.info(f'Chats saved to {Path("/appdata") / "chats.json"}.')

    return chats


async def main():
    from tgsync.core.get_client import get_client
    client = await get_client()
    await list_chats(client)


if __name__ == '__main__':
    import asyncio
    asyncio.run(main())
