import os

from caronte.database.db import SessionLocal
from enum import Enum
import random
import string
import requests


def get_db():
    with SessionLocal() as ses:
        yield ses


class ChatModes(Enum):
    NONE = 0
    AUTH_BEGIN = 1
    AUTH_WAIT = 2
    AUTH_TOKEN = 3
    VISIBILITY = 4


def create_token(size):
    return "".join(random.choice(string.ascii_uppercase) for i in range(size))


async def send_email_sb(email, token):
    r = requests.post(url="https://api.sendinblue.com/v3/smtp/email", headers={
        'accept': 'application/json',
        'api-key': os.getenv("SB_API"),
        'content-type': 'application/json'
    }, json={
        'sender': {'name': 'Caronte', 'email': 'noreply@fermitech.info'},
        'to': [{'email': email}],
        'subject': "Caronte - Token usa e getta",
        'htmlContent': "Ciao, questo è il token usa e getta per autenticare il tuo account: {}.".format(token)
    })
