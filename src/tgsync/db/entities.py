from sqlalchemy.orm import declarative_base
from sqlalchemy import Column, Boolean, BigInteger, DateTime, String, ForeignKey

Base = declarative_base()


class PhotoEntity(Base):
    __tablename__ = 'photo'

    id      = Column(BigInteger, primary_key=True)
    saved   = Column(Boolean, default=False)


class DocumentEntity(Base):
    __tablename__ = 'document'

    id      = Column(BigInteger, primary_key=True)
    type    = Column(String(255))
    size    = Column(BigInteger)
    name    = Column(String(255))
    saved   = Column(Boolean, default=False)


class MessageEntity(Base):
    __tablename__ = 'message'

    id        = Column(BigInteger, primary_key=True)
    chat_id   = Column(BigInteger, primary_key=True)
    sender_id = Column(BigInteger)
    date      = Column(DateTime)
    edit_date = Column(DateTime)
    message   = Column(String(4096))

    reply_to_msg_id    = Column(BigInteger)
    reply_to_chat_id   = Column(BigInteger)
    reply_to_sender_id = Column(BigInteger)

    fwd_from_msg_id    = Column(BigInteger)
    fwd_from_chat_id   = Column(BigInteger)
    fwd_from_sender_id = Column(BigInteger)
    fwd_from_date      = Column(DateTime)

    photo_id    = Column(BigInteger, ForeignKey('photo.id'))
    document_id = Column(BigInteger, ForeignKey('document.id'))
    linked      = Column(Boolean, default=False)
