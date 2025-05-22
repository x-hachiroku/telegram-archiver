from telethon import TelegramClient

from tgsync.config import appdata, config
from tgsync.logger import logger


async def get_client():
    client = TelegramClient(
        appdata / config['tg']['session'],
        config['tg']['api_id'],
        config['tg']['api_hash'],
    )
    await client.start()
    logger.info('Logging successful.')
    return client


if __name__ == '__main__':
    import asyncio
    asyncio.run(get_client())
