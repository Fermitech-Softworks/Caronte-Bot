import sqlalchemy.orm
import telepot
import asyncio
import os
from telepot.aio.loop import MessageLoop
from telepot.aio.delegate import pave_event_space, per_chat_id, create_open
from caronte.database.models import User, Base
from caronte.utils import ChatModes, create_token, send_email_sb
from caronte.database.db import SessionLocal, engine

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

    async def private_chat_handler(self, msg):
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
            left, right = msg['text'].split("@")
            if right != domain:
                await self.sender.sendMessage(
                    "L'email non appartiene al dominio indicato.\nPer favore, usa la tua mail istituzionale.")
                return
            self.token = create_token(6)
            self.email = msg['text']
            await send_email_sb(email=self.email, token=self.token)
            await self.sender.sendMessage(
                "E' stato mandato un codice di verifica a {}. Mandamelo entro 5 minuti.\n\nPer interrompere la procedura, fai /start.".format(
                    msg['text']))
            self.mode = ChatModes.AUTH_TOKEN
            return
        elif self.mode == ChatModes.AUTH_BEGIN:
            if self.email:
                await self.sender.sendMessage(
                    "Sei già stato autorizzato!")
                self.mode = ChatModes.NONE
                return

            await self.sender.sendMessage(
                "Inserisci la tua email istituzionale (deve terminare per {}). \n\nPer interrompere la procedura, fai /start.".format(
                    domain))
            self.mode = ChatModes.AUTH_WAIT
            return
        elif self.mode == ChatModes.VISIBILITY:
            with SessionLocal() as db:
                db: sqlalchemy.orm.Session
                user = db.query(User).filter_by(chatid=str(msg['chat']['id'])).first()
                if not user:
                    await self.sender.sendMessage("Utente non autenticato.\nImpossibile modificare le impostazioni per un utente ignoto.")
                    self.mode = ChatModes.NONE
                    return
                user.hidden = not user.hidden
                db.commit()
                if user.hidden:
                    await self.sender.sendMessage("Modalità anonima attivata.")
                else:
                    await self.sender.sendMessage("Modalità anonima disattivata.")
        elif self.mode == ChatModes.NONE:
            await self.sender.sendMessage(
                "Ciao,\nSono Caronte, il bot di Telegram per l'autenticazione e l'accesso a chat riservate. \n\nClicca su /auth per autenticarti, se vuoi cambiare le tue impostazioni di visibilità clicca su /visibility.\nPer accedere all'indice dei gruppi, clicca sul seguente link: \n{}".format(
                    os.getenv("INDEX_URL")))

    async def public_chat_handler(self, msg):
        if "entities" in msg.keys() and msg['entities'][0]['type'] == "bot_command":
            text = msg['text'].split(" ")
            if text[0] == "/whois":
                if len(text) == 3:
                    await self.whois_name_surname(text)
                elif len(text) == 2:
                    await self.whois_username(text)
                else:
                    await self.sender.sendMessage("Sintassi con corretta.\n/whois [Nome] [Cognome]\n/whois [@username]")

    async def whois_username(self, text):
        username = text[1][1:]
        with SessionLocal() as db:
            user = db.query(User).filter_by(username=username).first()
            if user.hidden:
                await self.sender.sendMessage("Nessun utente pubblico è stato trovato.")
            else:
                await self.sender.sendMessage("Risultato ricerca:\n{} {}, @{}".format(user.name, user.surname, user.username))

    async def whois_name_surname(self, text):
        name = text[1].lower()
        surname = text[2].lower()
        with SessionLocal() as db:
            users = db.query(User).filter_by(name=name, surname=surname).all()
            s = "Risultato ricerca:"
            for user in users:
                if user.hidden:
                    s += ""
                else:
                    s += "\n{} {}, @{}".format(user.name, user.surname, user.username)
            if s == "Risultato ricerca:":
                await self.sender.sendMessage("Nessun utente pubblico è stato trovato.")
            else: await self.sender.sendMessage(s)

    async def on_chat_message(self, msg):
        if msg['chat']['type'] == "private":
            await self.private_chat_handler(msg)
        else:
            g = telepot.glance(msg)
            if g[0] == 'new_chat_member':
                await self.new_user_handler(msg)
            await self.public_chat_handler(msg)

    async def on_close(self, ex):
        pass

    async def new_user_handler(self, msg):
        user = msg["new_chat_member"]['username']
        with SessionLocal() as db:
            user = db.query(User).filter_by(username=user).first()
            if not user:
                await self.hammer(msg["new_chat_member"])
                return
            if user.hidden:
                await self.sender.sendMessage(
                    "L'utente che si è collegato è autenticato, ma ha deciso di rimanere anonimo.\nBenvenuto!")
            else:
                await self.sender.sendMessage(
                    "L'utente che si è collegato è {} {}.\nBenvenuto!".format(user.name, user.surname))

    async def hammer(self, member):
        user = member['username']
        try:
            await self.sender.sendMessage("L'utente non è autenticato, e verrà rimosso...")
            await bot.kickChatMember(self.chat_id, member['id'])
        except telepot.exception.NotEnoughRightsError:
            await self.sender.sendMessage("Impossibile rimuovere l'utente {} per mancanza di permessi.".format(user))
        except telepot.exception.TelegramError:
            await self.sender.sendMessage(
                "Impossibile rimuovere l'utente {} a causa di un errore generico.".format(user))


bot_token = os.getenv("TOKEN")

bot = telepot.aio.DelegatorBot(bot_token, [pave_event_space()(per_chat_id(), create_open, CharonProgram, timeout=300)])
loop = asyncio.get_event_loop()
loop.create_task(MessageLoop(bot).run_forever())
print("Charon is running...")
loop.run_forever()
