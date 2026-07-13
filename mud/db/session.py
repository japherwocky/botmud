import os

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///mud.db")

# In-memory SQLite needs a single shared connection across all uses of the
# engine, otherwise each new SQLAlchemy connection gets a fresh empty
# database (the default SingletonThreadPool hands out a new connection per
# thread, so a session opened in one thread can't see schema/data created
# in another). StaticPool pins the engine to one connection and is the
# standard fix for this — see SQLAlchemy docs on "Using a Memory Database
# in Multiple Threads".
_is_memory_sqlite = ":memory:" in DATABASE_URL

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {},
    poolclass=StaticPool if _is_memory_sqlite else None,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
