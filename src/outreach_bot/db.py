from pathlib import Path

from sqlmodel import Session, SQLModel, create_engine

from outreach_bot.config import Settings, get_settings

_engine = None


def get_engine(settings: Settings | None = None):
    global _engine
    settings = settings or get_settings()
    if _engine is None:
        if settings.database_url.startswith("sqlite:///"):
            db_path = Path(settings.database_url.removeprefix("sqlite:///"))
            db_path.parent.mkdir(parents=True, exist_ok=True)
        _engine = create_engine(
            settings.database_url,
            connect_args={"check_same_thread": False}
            if settings.database_url.startswith("sqlite")
            else {},
        )
    return _engine


def init_db(settings: Settings | None = None) -> None:
    SQLModel.metadata.create_all(get_engine(settings))


def get_session():
    with Session(get_engine()) as session:
        yield session
