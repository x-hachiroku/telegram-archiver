import shutil
import asyncio
import traceback
from time import time
from mimetypes import guess_extension
from tabulate import tabulate

from sqlalchemy import select

from tgsync.config import config
from tgsync.logger import logger
from tgsync.core.get_client import get_client
from tgsync.db.session import session_generator
from tgsync.db.entities import MessageEntity, PhotoEntity, DocumentEntity


class ProgressSummary:
    def __init__(self):
        self.report_time = time()
        self.tasks = [{
            'seq': i,
            'name': None,
            'total': 0,
            'speed': 0,
            'received': 0,
            'last_report': 0,
        } for i in range(config['download']['concurrent'])]

    def make_progress_callback(self, seq):
        def progress_callback(received, total):
            self.tasks[seq]['total'] = total
            self.tasks[seq]['speed'] = \
                (received - self.tasks[seq]['received']) / (time() - self.tasks[seq]['last_report'])
            self.tasks[seq]['received'] = received
            self.tasks[seq]['last_report'] = time()
            self.log_progress()
        return progress_callback

    def log_progress(self):
        def format_bytes(b):
            for unit in ['B', 'KiB', 'MiB', 'GiB']:
                if b < 1024:
                    return f'{b:.2f}{unit}'
                b /= 1024

        if time() - self.report_time < config['download']['summary_interval']:
            return
        self.report_time = time()

        task_table = []
        total_speed = 0
        for task in self.tasks:
            if task['name'] is None:
                continue

            total_speed += task['speed']

            name = task['name']
            if len(name) > 64:
                name = name[:50] + '...' + name[-10:]

            task_table.append([
                f'#{task["seq"]}',
                name,
                f'{format_bytes(task["received"])}/{format_bytes(task["total"])}',
                f'{100*task["received"] / task["total"]:.1f}%',
                f'{format_bytes(task["speed"])}/s',
            ])

        task_table.append(['', 'Total:', '', '', f'{format_bytes(total_speed)}/s'])

        logger.info('\n'+tabulate(task_table))


async def save_worker(seq, queue, progress_summary, client):
    logger.debug(f'Worker {seq} started')
    progress_callback = progress_summary.make_progress_callback(seq)

    while True:
        try:
            logger.debug(f'Worker {seq} fetching next message, queue size: {queue.qsize()}')
            msg = await queue.get()

            if msg.photo:
                entity_type = PhotoEntity
                entity_id = msg.photo.id
                tempfile = config['download']['incomplete'] / 'photos-by-id' / f'{msg.photo.id}.jpg'
                file = config['download']['media'] / 'photos-by-id' / f'{msg.photo.id}.jpg'
                progress_summary.tasks[seq]['name'] = f"{msg.chat_id}/{msg.id}.jpg"
            elif msg.document:
                entity_type = DocumentEntity
                entity_id = msg.document.id
                ext = guess_extension(msg.document.mime_type)
                if ext is None:
                    ext = '.bin'
                tempfile = config['download']['incomplete'] / 'documents-by-id' / f'{msg.document.id}{ext}'
                file = config['download']['media'] / 'documents-by-id' / f'{msg.document.id}{ext}'
                progress_summary.tasks[seq]['name'] = f'{msg.chat_id}/{msg.document.id}{ext}'
                if msg.file.name:
                    progress_summary.tasks[seq]['name'] = f'{msg.chat_id}/{msg.file.name}'
            else:
                raise ValueError('Message does not contain a photo or document')

            logger.info(f'Worker {seq} start downloading {progress_summary.tasks[seq]["name"]}')
            await client.download_media(message=msg,
                                        file=tempfile,
                                        progress_callback=None if msg.photo else progress_callback)

            shutil.move(tempfile, file)

            with session_generator() as session:
                entity = session.get(entity_type, entity_id)
                entity.saved = True

            logger.info(f'Worker {seq} download finished {progress_summary.tasks[seq]["name"]}')

        except Exception:
            logger.error(f'Exception in worker {seq}: {traceback.format_exc()}')

        finally:
            progress_summary.tasks[seq]['name'] = None
            queue.task_done()


async def save_all(client, chat_id, photo):
    (config['download']['incomplete'] / 'photos-by-id').mkdir(parents=True, exist_ok=True)
    (config['download']['incomplete'] / 'documents-by-id').mkdir(parents=True, exist_ok=True)
    (config['download']['media'] / 'photos-by-id').mkdir(parents=True, exist_ok=True)
    (config['download']['media'] / 'documents-by-id').mkdir(parents=True, exist_ok=True)

    queue = asyncio.Queue(maxsize=config['tg']['message_limit'] // 2)
    progress_summary = ProgressSummary()

    workers = [asyncio.create_task(save_worker(i, queue, progress_summary, client))
               for i in range(config['download']['concurrent'])]

    if photo:
        stmt = (
            select(
                MessageEntity.id.label('message_id'),
                PhotoEntity.id,
            )
            .join(PhotoEntity, MessageEntity.photo_id == PhotoEntity.id)
            .where(
                MessageEntity.chat_id == chat_id,
                PhotoEntity.saved == False
            )
            .distinct(PhotoEntity.id)
            .limit(config['tg']['message_limit'])
        )
    else:
        stmt = (
            select(
                MessageEntity.id.label('message_id'),
                DocumentEntity.id,
            )
            .join(DocumentEntity, MessageEntity.document_id == DocumentEntity.id)
            .where(
                MessageEntity.chat_id == chat_id,
                DocumentEntity.saved == False
            )
            .distinct(DocumentEntity.id)
            .limit(config['tg']['message_limit'])
        )

    try:
        while True:
            with session_generator() as session:
                msg_ids = session.execute(stmt).scalars().all()

            if not msg_ids:
                logger.info(f'All {"Photos" if photo else "Documents"} saved for {chat_id}')
                break

            msgs = await client.get_messages(
                chat_id,
                ids=msg_ids,
                limit=config['tg']['message_limit'],
            )

            for msg in msgs:
                await queue.put(msg)

            await queue.join()

    except Exception:
        logger.error(traceback.format_exc())

    finally:
        for w in workers:
            w.cancel()
        await asyncio.gather(*workers, return_exceptions=True)


async def main():
    from sys import argv
    client = await get_client()

    await save_all(client, int(argv[1]), argv[2]=='photo')


if __name__ == '__main__':
    asyncio.run(main())
