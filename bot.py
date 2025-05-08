import os
import json
import logging
from dotenv import load_dotenv
from aiohttp import web

from aiogram import Bot, Dispatcher, Router, types
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command, CommandStart
from aiogram.client.default import DefaultBotProperties

# === Chargement .env ===
load_dotenv("token.env")
BOT_TOKEN = os.getenv("BOT_TOKEN")
CANAL_ID = os.getenv("CANAL_ID")
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "secret")
RENDER_EXTERNAL_URL = os.getenv("RENDER_EXTERNAL_URL")

# === Initialisation ===
router = Router()
storage = MemoryStorage()
dp = Dispatcher(storage=storage)
dp.include_router(router)

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))

# === Fichier de parrainage ===
REFERRALS_FILE = "referrals.json"
if os.path.exists(REFERRALS_FILE):
    with open(REFERRALS_FILE, "r") as f:
        try:
            referrals = json.load(f)
        except:
            referrals = {}
else:
    referrals = {}

# === Commande /start ===
@router.message(CommandStart())
async def start_handler(message: Message):
    user_id = message.from_user.id
    args = message.text.split(" ")
    referrer_id = None

    if len(args) > 1:
        try:
            referrer_id = int(args[1])
            if referrer_id != user_id:
                if str(referrer_id) not in referrals:
                    referrals[str(referrer_id)] = []
                if user_id not in referrals[str(referrer_id)]:
                    referrals[str(referrer_id)].append(user_id)
                    with open(REFERRALS_FILE, "w") as f:
                        json.dump(referrals, f, indent=2)
        except:
            pass

    bot_username = (await bot.get_me()).username
    referral_link = f"https://t.me/{bot_username}?start={user_id}"
    canal_url = "https://t.me/VelocityInvestments"
    first_name = message.from_user.first_name

    webapp_url = "https://velocity-parrainage.onrender.com"
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🚀 Ouvrir l'application", web_app={"url": webapp_url})]
    ])

    await message.answer(
        f"👋 Bienvenue <b>{first_name}</b> !\n\n"
        f"👉 Rejoins le canal Telegram pour valider ton parrainage :\n"
        f"📲 <a href='{canal_url}'>{canal_url}</a>\n\n"
        f"Voici ton lien de parrainage 👇\n"
        f"<code>{referral_link}</code>\n\n"
        f"/stats – Voir tes parrainages\n"
        f"/top – Classement des parrains",
        reply_markup=keyboard
    )

# === Commande /stats ===
@router.message(Command("stats"))
async def stats_handler(message: Message):
    user_id = str(message.from_user.id)
    filleuls = referrals.get(user_id, [])

    if not filleuls:
        await message.answer("Tu n’as encore parrainé personne.")
        return

    actifs = 0
    for fid in filleuls:
        try:
            status = await bot.get_chat_member(CANAL_ID, fid)
            if status.status in ["member", "administrator", "creator"]:
                actifs += 1
        except:
            pass

    classement = []
    for parrain_id, filleuls_list in referrals.items():
        actifs_par_parrain = 0
        for fid in filleuls_list:
            try:
                status = await bot.get_chat_member(CANAL_ID, fid)
                if status.status in ["member", "administrator", "creator"]:
                    actifs_par_parrain += 1
            except:
                pass
        classement.append((parrain_id, actifs_par_parrain))

    classement.sort(key=lambda x: x[1], reverse=True)
    position = next((i + 1 for i, (pid, _) in enumerate(classement) if pid == user_id), None)

    await message.answer(
        f"📊 <b>Statistiques de parrainage</b> :\n\n"
        f"👥 Parrainés : <b>{len(filleuls)}</b>\n"
        f"✅ Toujours abonnés : <b>{actifs}</b>\n"
        f"🏆 Position : <b>#{position}</b>"
    )

# === Commande /top ===
@router.message(Command("top"))
async def top_handler(message: Message):
    classement = []
    for parrain_id, filleuls in referrals.items():
        actifs = 0
        for fid in filleuls:
            try:
                status = await bot.get_chat_member(CANAL_ID, fid)
                if status.status in ["member", "administrator", "creator"]:
                    actifs += 1
            except:
                pass
        classement.append((parrain_id, actifs))

    classement.sort(key=lambda x: x[1], reverse=True)
    if not classement or all(actifs == 0 for _, actifs in classement):
        await message.answer("Aucun parrain actif pour le moment.")
        return

    message_text = "🏆 <b>Top 5 Parrains</b>\n\n"
    for i, (parrain_id, actifs) in enumerate(classement[:5]):
        try:
            user = await bot.get_chat_member(chat_id=message.chat.id, user_id=int(parrain_id))
            name = user.user.first_name
        except:
            name = f"ID {parrain_id}"
        message_text += f"{i+1}. {name} – <b>{actifs}</b> actifs\n"

    await message.answer(message_text)

# === Serveur aiohttp pour Render ===
async def handle(request):
    raw_body = await request.read()
    update = types.Update.model_validate_json(raw_body.decode())
    await dp.feed_update(bot, update)
    return web.Response()

async def main():
    app = web.Application()
    app.router.add_post(f"/webhook/{WEBHOOK_SECRET}", handle)

    # Supprime le polling
    await bot.delete_webhook()
    
    # Ajoute le webhook
    webhook_url = f"{RENDER_EXTERNAL_URL}/webhook/{WEBHOOK_SECRET}"
    await bot.set_webhook(webhook_url)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, port=10000)
    await site.start()

    print(f"🚀 Webhook lancé sur {webhook_url}")

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())

