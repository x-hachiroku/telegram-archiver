import re
import asyncio
from abc import ABC, abstractmethod

from sqlalchemy.dialects.postgresql import insert

from tgsync.logger import logger
from tgsync.core.get_client import get_client
from tgsync.core.sync_chat import sync_chat

from tgsync.db.session import session_generator
from tgsync.db.entities import FileCodeEntity


class FileBotHandler(ABC):
    username = None
    patterns = []
    refresh_interval = 5
    max_refreshes = 5

    def __init__(self, client):
        self.client = client
        self.start_id = 0
        self.last_id = 0


    async def wait_for_new_msg(self):
        for i in range(self.max_refreshes):
            await asyncio.sleep(self.refresh_interval)
            reply = (await self.client.get_messages(self.username, limit=1))[0]
            if reply.id != self.last_id:
                return reply
        logger.warning(f'No new message received from {self.username} after {self.max_refreshes} attempts')
        return None


    def search_code(self, string):
        code = []
        for pattern in self.patterns:
            code.extend(re.findall(pattern, string))

        code_dicts = [{'code': c, 'bot_username': self.username} for c in code]
        if len(code_dicts) == 0:
            logger.warning(f'No code found in {string} for @{self.username}')
            return
        with session_generator() as session:
            session.execute(
                insert(FileCodeEntity)
                .values(code_dicts)
                .on_conflict_do_nothing(index_elements=['code'])
            )


    async def sync_retrived(self, code):
        logger.info(f'Starting sync response from {self.username}/{self.start_id}')
        end_id = await sync_chat(self.client, self.username, self.start_id, resume=False)

        file_code_entity = FileCodeEntity(
            code = code,
            bot_username = self.username,
            start_id = self.start_id,
            end_id = end_id
        )

        with session_generator() as session:
            code_entity = session.get(FileCodeEntity, code)
            code_entity.start_id = self.start_id
            code_entity.end_id = end_id


    @abstractmethod
    async def process_code(self, code):
        pass


    async def retrive_files(self):
        with session_generator() as session:
            code = (
                session.query(FileCodeEntity)
                .filter(FileCodeEntity.bot_username == self.username)
                .filter(FileCodeEntity.start_id == None)
            ).all()

        for c in code:
            await self.process_code(c.code)


class ShowFilesBotHandler(FileBotHandler):
    username = 'ShowFilesBot'
    patterns = [
        re.compile(r'\b(?:vi|pk|p|d)_[a-zA-Z0-9-_]+'),
        re.compile(r'\bshowfilesbot_[a-zA-Z0-9-_]+'),
    ]


    def __init__(self, client):
        super().__init__(client)


    async def get_new_page(self, reply):
        flatted_buttons = []
        if reply.buttons:
            for button in reply.buttons:
                if isinstance(button, list):
                    flatted_buttons.extend(button)
                else:
                    flatted_buttons.append(button)

        if len(flatted_buttons) > 0:
            logger.info(f'Buttons found: {",".join([b.text for b in flatted_buttons])}')

        for button in flatted_buttons:
            if re.match(r'\d+', button.text):
                await asyncio.sleep(self.refresh_interval)
                logger.info(f'Clicking button: {button.text}')
                await button.click()
                return True

        logger.info('No more valid buttons found')
        return False


    async def process_code(self, code):
        logger.info(f'Processing code by {self.username}: {code}')

        sent = await self.client.send_message(
            self.username,
            code,
        )
        self.start_id = sent.id
        self.last_id = sent.id

        while True:
            if not (reply := await self.wait_for_new_msg()):
                return
            self.last_id = reply.id
            logger.info(f'New message received: {reply.id}')

            if not await self.get_new_page(reply):
                break

        await self.sync_retrived(code)


async def main():
    from tgsync.config import appdata
    from tgsync.core.get_client import get_client

    client = await get_client()
    bot = ShowFilesBotHandler(client)

    with open(appdata / 'code.txt', 'r') as f:
        line = f.read().splitlines()
    for l in line:
        bot.search_code(l)

    await bot.retrive_files()


if __name__ == '__main__':
    asyncio.run(main())
