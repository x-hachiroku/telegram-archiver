import re
import os
from mimetypes import guess_extension

from tgsync.config import config
from tgsync.logger import logger
from tgsync.db.session import session_generator
from tgsync.db.entities import MessageEntity, PhotoEntity, DocumentEntity


def make_safe_filename(name):
    invalid_chars = r'[\\/:*?"<>|]'
    name = re.sub(invalid_chars, '_', name)

    name = name.strip(' .')

    reserved = {
        'CON', 'PRN', 'AUX', 'NUL',
        *(f'COM{i}' for i in range(1, 10)),
        *(f'LPT{i}' for i in range(1, 10)),
    }
    if name.upper().split('.')[0] in reserved:
        name = f'_{name}'

    encoded = name.encode('utf-8')
    safe_name = encoded[:240] + encoded[-10:]
    safe_name = encoded.decode('utf-8', errors='ignore')

    return safe_name


def link_media():
    with session_generator() as session:
        candidates = (
            session.query(
                MessageEntity,
                PhotoEntity.id.label('photo_id'),
            )
            .join(PhotoEntity, MessageEntity.photo_id == PhotoEntity.id)
            .filter(
                MessageEntity.linked == False,
                PhotoEntity.saved == True
            )
        ).all()

        for msg, photo_id in candidates:
            chat_dir = config['download']['media'] / str(msg.chat_id)
            chat_dir.mkdir(parents=True, exist_ok=True)

            dst = chat_dir / f'{msg.id}_{photo_id}.jpg'

            logger.debug(f'Linking {photo_id} to {dst}')
            if os.path.exists(config['download']['media'] / 'photos-by-id' / f'{photo_id}.jpg'):
                if not os.path.exists(dst):
                    os.link(config['download']['media'] / 'photos-by-id' / f'{photo_id}.jpg', dst)
                else:
                    logger.warning(f'File {dst} already exists, skipping...')
            else:
                logger.warning(f'Previous saved photo {photo_id} is removed, skipping {msg.chat_id}/{msg.id}')

            msg.linked = True

    with session_generator() as session:
        candidates = (
            session.query(
                MessageEntity,
                DocumentEntity.id.label('document_id'),
                DocumentEntity.name.label('document_name'),
                DocumentEntity.type.label('document_type')
            )
            .join(DocumentEntity, MessageEntity.document_id == DocumentEntity.id)
            .filter(
                MessageEntity.linked == False,
                DocumentEntity.saved == True
            )
        ).all()

        for msg, document_id, document_name, document_type in candidates:
            chat_dir = config['download']['media'] / str(msg.chat_id)
            chat_dir.mkdir(parents=True, exist_ok=True)

            ext = guess_extension(document_type)
            if ext is None:
                ext = '.bin'
            src = config['download']['media'] / 'documents-by-id' / f'{document_id}{ext}'

            filename = f'{msg.id}'
            if document_name:
                filename += f' {document_name}'
            else:
                filename += ext
            filename = make_safe_filename(filename)
            dst = chat_dir / filename

            logger.debug(f'Linking {src} to {dst}')
            if os.path.exists(src):
                if not os.path.exists(dst):
                    os.link(src, dst)
                else:
                    logger.warning(f'File {dst} already exists, skipping...')
            else:
                logger.warning(f'Previous saved document {document_id} is removed, skipping {msg.chat_id}/{msg.id}')

            msg.linked = True


if __name__ == '__main__':
    link_media()
