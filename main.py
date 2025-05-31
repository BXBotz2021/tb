import asyncio
import logging
import time

import humanreadable as hr
from telethon.sync import TelegramClient, events
from telethon.tl.custom.message import Message

from config import ADMINS, API_HASH, API_ID, BOT_TOKEN
from redis_db import db
from send_media import VideoSender
from terabox import get_data
from tools import extract_code_from_url, get_urls_from_string

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

bot = TelegramClient("main", API_ID, API_HASH)


@bot.on(
    events.NewMessage(
        incoming=True,
        outgoing=False,
        func=lambda message: message.text
        and get_urls_from_string(message.text)
        and message.is_private,
    )
)
async def get_message(m: Message):
    await handle_message(m)  # Direct await for better error handling


async def handle_message(m: Message):
    urls = get_urls_from_string(m.text)
    if not urls:
        return await m.reply("Please enter a valid URL.")
    
    url = urls[0]
    hm = await m.reply("Sending you the media, wait...")

    is_spam = db.get(m.sender_id)
    if is_spam and m.sender_id not in ADMINS:
        ttl = db.ttl(m.sender_id)
        t = hr.Time(str(ttl), default_unit=hr.Time.Unit.SECOND)
        return await hm.edit(
            f"You are spamming.\n**Please wait {t.to_humanreadable()} and try again.**",
            parse_mode="markdown",
        )

    if_token_avl = db.get(f"active_{m.sender_id}")
    if not if_token_avl and m.sender_id not in ADMINS:
        return await hm.edit(
            "Your account is deactivated. Send /gen to activate it again."
        )

    shorturl = extract_code_from_url(url)
    if not shorturl:
        return await hm.edit("Seems like your link is invalid.")

    fileid = db.get_key(shorturl)
    if fileid:
        uid = db.get_key(f"mid_{fileid}")
        if uid:
            try:
                check = await VideoSender.forward_file(
                    file_id=fileid, message=m, client=bot, edit_message=hm, uid=uid
                )
                if check:
                    return
            except Exception as e:
                log.error(f"Error forwarding file: {e}")

    try:
        data = get_data(url)  # Call this as async if it's async
    except Exception as e:
        log.error(f"get_data() failed: {e}")
        return await hm.edit("Sorry! API is dead or maybe your link is broken.")

    if not data:
        return await hm.edit("Sorry! API is dead or maybe your link is broken.")

    db.set(m.sender_id, time.monotonic(), ex=60)

    if int(data["sizebytes"]) > 524_288_000 and m.sender_id not in ADMINS:
        return await hm.edit(
            f"Sorry! File is too big.\n**I can download only 500MB and this file is of {data['size']}.**\n"
            f"Rather you can download this file from the link below:\n{data['url']}",
            parse_mode="markdown",
        )

    sender = VideoSender(
        client=bot,
        data=data,
        message=m,
        edit_message=hm,
        url=url,
    )
    try:
        asyncio.create_task(sender.send_video())
    except Exception as e:
        log.error(f"Error while sending video: {e}")
        await hm.edit("Failed to send video due to an internal error.")


bot.start(bot_token=BOT_TOKEN)
bot.run_until_disconnected()
