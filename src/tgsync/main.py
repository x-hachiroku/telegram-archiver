import os
import asyncio

from pathlib import Path

from tgsync.config import config
from tgsync.logger import logger
from tgsync.core.get_client import get_client
from tgsync.core.list_chats import list_chats

from tgsync.db.session import engine
from tgsync.db.entities import Base

async def main():
    Base.metadata.create_all(engine)

    setup = not os.path.exists(Path('/appdata') / config['tg']['session'])
    if setup:
        logger.warning('No session file found. Please run the container in interactive mode to login.')

    client = await get_client()

    if setup:
        await list_chats(client)
        logger.info('You can now restart the container in detached mode.')
        return

    await asyncio.Future()


if __name__ == '__main__':
    asyncio.run(main())
