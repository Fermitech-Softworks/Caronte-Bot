import sqlalchemy.orm
import telepot
import asyncio
import os
from telepot.aio.loop import MessageLoop
from telepot.aio.delegate import pave_event_space, per_chat_id, create_open
from database.models import User, Base
from utils import ChatModes
from database.db import SessionLocal, engine

Base.metadata.create_all(bind=engine)

domain = os.getenv("DOMAIN")


class CharonProgram(telepot.aio.helper.ChatHandler):
    def __init__(self, *args, **kwargs):
        super(CharonProgram, self).__init__(*args, **kwargs)
        self.mode = ChatModes.NONE
        self.uname = None
        self.email = None
        self.token = None

    async def charon_router(self, msg):
        if msg['text'] == "/start":
            self.mode = ChatModes.NONE
        elif msg['text'] == "/auth":
            self.mode = ChatModes.AUTH_BEGIN
        elif msg['text'] == "/visibility":
            self.mode = ChatModes.VISIBILITY
        else:
            await self.sender.sendMessage("Comando sconosciuto.")

    async def on_chat_message(self, msg):
        if not self.uname and msg['chat']['type'] == "private":
            with SessionLocal() as db:
                db: sqlalchemy.orm.Session
                user = db.query(User).filter_by(chatid=str(msg['chat']['id'])).first()
                if user:
                    if user.username != msg['chat']['username']:
                        user.username = msg['chat']['username']
                        db.commit()
                    self.email = user.email
            self.uname = msg['chat']['username']
        if "entities" in msg.keys() and msg['entities'][0]['type'] == "bot_command":
            await self.charon_router(msg)
        if self.mode == ChatModes.AUTH_TOKEN:
            if self.token != msg['text']:
                await self.sender.sendMessage("Token errato.")
                return
            with SessionLocal() as db:
                db: sqlalchemy.orm.Session
                left, right = self.email.split("@")
                name, surname = left.split(".")
                surname = ''.join([l for l in surname if not l.isdigit()])
                db.add(User(name=name, surname=surname, email=self.email, username=self.uname,
                            chatid=str(msg['chat']['id']), verified=True))
                db.commit()
                await self.sender.sendMessage(
                    "Congratulazioni! Il tuo profilo è stato validato.\nDi default, le tue informazioni come nome e cognome non saranno visibili ad altri utenti, ma puoi renderle visibili con il comando /visibility.")
                self.mode = ChatModes.NONE
                return
        elif self.mode == ChatModes.AUTH_WAIT:
            if "entities" not in msg.keys() or msg["entities"][0]['type'] != "email":
                await self.sender.sendMessage("Email non valida. Riprova.")
                return
            # Check for email compliancy
            # Create and send the token to email
            self.token = "1234"
            self.email = msg['text']
            await self.sender.sendMessage("E' stato mandato un codice di verifica a {}. Mandamelo entro 5 minuti.\n\nPer interrompere la procedura, fai /start.".format(msg['text']))
            self.mode = ChatModes.AUTH_TOKEN
            return
        elif self.mode == ChatModes.AUTH_BEGIN:
            if self.email:
                await self.sender.sendMessage(
                    "Sei già stato autorizzato!")
                self.mode = ChatModes.NONE
                return

            await self.sender.sendMessage(
                "Inserisci la tua email istituzionale (deve terminare per {}).\n\nPer interrompere la procedura, fai /start.".format(
                    domain))
            self.mode = ChatModes.AUTH_WAIT
            return
        elif self.mode == ChatModes.NONE:
            await self.sender.sendMessage(
                "Ciao,\nSono Caronte, il bot di Telegram per l'autenticazione e l'accesso a chat riservate.\n\nClicca su /auth per autenticarti, se vuoi cambiare le tue impostazioni di visibilità clicca su /visibility.")


bot_token = os.getenv("TOKEN")

bot = telepot.aio.DelegatorBot(bot_token, [pave_event_space()(per_chat_id(), create_open, CharonProgram, timeout=300)])
loop = asyncio.get_event_loop()
loop.create_task(MessageLoop(bot).run_forever())
print("Charon is running...")
loop.run_forever()
