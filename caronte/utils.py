from database.db import SessionLocal
from enum import Enum


def get_db():
    with SessionLocal() as ses:
        yield ses


class ChatModes(Enum):
    NONE = 0
    AUTH_BEGIN = 1
    AUTH_WAIT = 2
    AUTH_TOKEN = 3
    VISIBILITY = 4
