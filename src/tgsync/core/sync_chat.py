from sqlalchemy.sql.elements import BindParameter

from telethon.utils import get_peer_id
from telethon.tl.types import Message

from tgsync.config import config
from tgsync.logger import logger
from tgsync.db.entities import *
from tgsync.db.session import session_generator
from sqlalchemy.dialects.postgresql import insert

def get_id(entity):
    if entity is None:
        return None
    return get_peer_id(entity)


def msg_to_dicts(msg, msg_dicts, photo_dicts, document_dicts):
    msg_dict = {
        'id'        : msg.id,
        'chat_id'   : msg.chat_id,
        'sender_id' : msg.sender_id,
        'date'      : msg.date,
        'edit_date' : msg.edit_date,
        'message'   : msg.message,
        'reply_to_msg_id'    : None,
        'reply_to_chat_id'   : None,
        'reply_to_sender_id' : None,
        'fwd_from_msg_id'    : None,
        'fwd_from_chat_id'   : None,
        'fwd_from_sender_id' : None,
        'fwd_from_date'      : None,
        'photo_id'    : None,
        'document_id' : None,
        'linked'      : False,
    }

    if msg.is_reply:
        msg_dict['reply_to_msg_id']    = msg.reply_to_msg_id
        msg_dict['reply_to_chat_id']   = get_id(msg.reply_to_chat)
        msg_dict['reply_to_sender_id'] = get_id(msg.reply_to_sender)

    if msg.forward:
        msg_dict['fwd_from_msg_id']    = msg.forward.channel_post
        msg_dict['fwd_from_chat_id']   = msg.forward.chat_id
        msg_dict['fwd_from_sender_id'] = msg.forward.sender_id
        msg_dict['fwd_from_date']      = msg.forward.date

    if msg.photo:
        msg_dict['photo_id'] = msg.photo.id
        photo_dict = {
            'id'    : msg.photo.id,
            'saved' : False,
        }
        photo_dicts.append(photo_dict)

    if msg.document:
        msg_dict['document_id'] = msg.document.id
        doc_dict = {
            'id'    : msg.document.id,
            'type'  : msg.document.mime_type,
            'size'  : msg.document.size,
            'name'  : msg.file.name,
            'saved' : False,
        }
        document_dicts.append(doc_dict)

    msg_dicts.append(msg_dict)


async def sync_msgs(client, chat_id, min_id, max_id=0):
    '''
    NOTE: min_id and max_id are inclusive

    return the last message id synced
    '''
    logger.info(f'Fetching next {config["tg"]["message_limit"]} messages from {chat_id}/{min_id}')
    min_id = min_id-1
    max_id = 0 if max_id == 0 else max_id+1

    msg_dicts = []
    photo_dicts = []
    document_dicts = []

    msg_iter = client.iter_messages(
        chat_id,
        reverse=True,
        min_id=min_id,
        max_id=max_id,
        limit=config['tg']['message_limit'],
    )
    async for msg in msg_iter:
        if type(msg) is Message:
            msg_to_dicts(msg, msg_dicts, photo_dicts, document_dicts)
    if len(msg_dicts) == 0:
        return -1

    with session_generator() as session:
        if len(photo_dicts) > 0:
            session.execute(
                insert(PhotoEntity)
                .values(photo_dicts)
                .on_conflict_do_nothing(index_elements=['id'])
            )
        if len(document_dicts) > 0:
            session.execute(
                insert(DocumentEntity)
                .values(document_dicts)
                .on_conflict_do_nothing(index_elements=['id'])
            )
        session.execute(
            insert(MessageEntity)
            .values(msg_dicts)
            .on_conflict_do_nothing(index_elements=['id', 'chat_id'])
        )

    return msg_dicts[-1]['id']


async def sync_chat(client, chat_id, min_id=0, max_id=0, resume=True):
    logger.info(f'Synchronizing {chat_id} from {min_id} to {max_id}')

    last_id = 0
    if resume:
        with session_generator() as session:
            last_processed = (
                session.query(MessageEntity)
                .filter(MessageEntity.chat_id == chat_id)
                .order_by(MessageEntity.id.desc())
                .limit(1)
                .one_or_none()
            )
        if last_processed:
            last_id = last_processed.id
            logger.info(f'Resuming from: {last_id}')

    last_id = max(last_id, min_id-1)

    while max_id == 0 or last_id < max_id:
        synced = await sync_msgs(client, chat_id, last_id+1, max_id)

        if synced == -1:
            logger.info(f'Finished synchronizing {chat_id} from {min_id} to {max_id}')
            return last_id

        last_id = synced


async def main():
    from tgsync.core.get_client import get_client
    from sys import argv
    client = await get_client()

    await sync_chat(client, *map(int, argv[1:]))


if __name__ == '__main__':
    import asyncio
    asyncio.run(main())
