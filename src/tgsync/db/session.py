from contextlib import contextmanager
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from tgsync.config import config
from tgsync.logger import logger


engine = create_engine(
    url=config['db']['url'],
    echo=False,
    pool_pre_ping=True,
    pool_size=20,
    max_overflow=-1,
    pool_recycle=3600,
)


Session = sessionmaker(bind=engine, expire_on_commit=False)

@contextmanager
def session_generator():
    session = Session()
    try:
        yield session
        session.commit()
    except:
        session.rollback()
        raise
    finally:
        session.close()
