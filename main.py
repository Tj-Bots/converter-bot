import os
import asyncio
import time
import math
import subprocess
import psutil
import shutil
import sys
import random
import string
import re
import logging
from datetime import datetime, timedelta
from dotenv import load_dotenv
load_dotenv()
from motor.motor_asyncio import AsyncIOMotorClient
from pyrogram import Client, filters, enums, StopTransmission, idle
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message, CallbackQuery, InputMediaPhoto, InputMediaDocument, PreCheckoutQuery
from pyrogram.errors import FloodWait, MessageNotModified, MessageIdInvalid
from hachoir.metadata import extractMetadata
from hachoir.parser import createParser

logging.basicConfig(level=logging.ERROR)
logger = logging.getLogger(__name__)

import pyrogram.session
_original_handle = pyrogram.session.Session.handle_packet if hasattr(pyrogram.session.Session, "handle_packet") else None

from pyrogram import raw
_original_resolve = None
try:
    import pyrogram.dispatcher as _dispatcher
    _orig_dispatch = _dispatcher.Dispatcher.update
    async def _safe_dispatch(self, client, update, users, chats):
        try:
            await _orig_dispatch(self, client, update, users, chats)
        except TypeError as e:
            if "topics" in str(e):
                pass
            else:
                raise
    _dispatcher.Dispatcher.update = _safe_dispatch
except Exception:
    pass

# ==================== CONFIGURATION ====================
API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))
DUMP_CHANNEL = int(os.getenv("DUMP_CHANNEL"))

SESSION_STRING = os.getenv("SESSION_STRING", "")

VERSION = "16.1.0 JOKER MASTER"
DEVELOPER_NAME = "𝑻𝒉𝒆 𝑱𝒐𝒌𝒆𝒓🃏"
DEVELOPER_USERNAME = "The_Joker121_bot"
DEVELOPER_LINK = f"https://t.me/{DEVELOPER_USERNAME}"
CHANNEL_LINK = "https://t.me/Tj_Bots"

TEST_PRICE = "Free (one-time)"
GOLD_PRICE = "$1"
ULTRA_PRICE = "$2"

FREE_DAILY_LIMIT = 10
TEST_DAILY_LIMIT = 10
GOLD_DAILY_LIMIT = 20
ULTRA_DAILY_LIMIT = 50

MAX_FILE_SIZE_NORMAL = 1950 * 1024 * 1024  # 2GB
MAX_FILE_SIZE_PREMIUM = 4 * 1024 * 1024 * 1024  # 4GB

COOLDOWN_NORMAL = 60

MAX_CONCURRENT_FREE   = 1
MAX_CONCURRENT_TEST   = 2
MAX_CONCURRENT_GOLD   = 2
MAX_CONCURRENT_ULTRA  = 3
MAX_CONCURRENT_ADMIN  = 999

WORKSPACE = "/root/.openclaw/workspace/converter_bot"
DOWNLOAD_LOCATION = f"{WORKSPACE}/downloads"
PREMIUM_LOG = f"{WORKSPACE}/premium_log.txt"

MONGO_URI = os.getenv("MONGO_URI", "")
DB_NAME = os.getenv("DB_NAME", "tj_rename")

for path in [DOWNLOAD_LOCATION, WORKSPACE]:
    if not os.path.isdir(path):
        os.makedirs(path)

# ==================== TASK MANAGEMENT ====================
tasks = {}                # task_id -> TaskInfo
user_tasks = {}           # user_id -> list of task_ids
tasks_lock = asyncio.Lock()
last_refresh = {}         # user_id -> last refresh time

class TaskInfo:
    def __init__(self, task_id, short_id, user_id, original_msg, filename, target, status_msg):
        self.task_id = task_id
        self.short_id = short_id
        self.user_id = user_id
        self.original_msg = original_msg
        self.filename = filename
        self.target = target
        self.status_msg = status_msg
        self.cancel_event = asyncio.Event()
        self.start_time = time.time()
        self.current = 0
        self.total = 0
        self.stage = "downloading"
        self.lock = asyncio.Lock()
        self.cancelled = False
        self.download_task = None
        self.upload_task = None

# ==================== BOT CLIENTS ====================
bot = Client(
    "converter_bot_final_v16",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    workdir=WORKSPACE,
    parse_mode=enums.ParseMode.HTML,
    max_concurrent_transmissions=10,
    workers=20,
)
bot.start_time = time.time()

premium_client = None
if SESSION_STRING and SESSION_STRING != "your_session_string_here":
    try:
        premium_client = Client(
            "premium_session",
            session_string=SESSION_STRING,
            api_id=API_ID,
            api_hash=API_HASH,
            max_concurrent_transmissions=10,
            no_updates=True
        )
        logger.info("Premium client initialized")
    except Exception as e:
        logger.error(f"Failed to initialize premium client: {e}")

# ==================== UTILITY FUNCTIONS ====================
def get_bot_uptime():
    return time.time() - bot.start_time

def time_formatter(seconds):
    if seconds < 0:
        seconds = 0
    days = int(seconds // 86400)
    hours = int((seconds % 86400) // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    parts = []
    if days > 0:
        parts.append(f"{days}d")
    if hours > 0 or days > 0:
        parts.append(f"{hours}h")
    if minutes > 0 or hours > 0 or days > 0:
        parts.append(f"{minutes}m")
    parts.append(f"{secs}s")
    return " ".join(parts)

def get_prog_bar(percent, length=10):
    filled = int(length * percent / 100)
    return "■" * filled + "□" * (length - filled)

def human_size(size):
    if not size:
        return "0 B"
    if size == float('inf'):
        return "Unlimited"
    units = ["B", "KB", "MB", "GB", "TB"]
    i = int(math.floor(math.log(size, 1024))) if size > 0 else 0
    return f"{round(size / math.pow(1024, i), 2)} {units[i]}"

def get_duration(file_path):
    try:
        metadata = extractMetadata(createParser(file_path))
        if metadata and metadata.has("duration"):
            return metadata.get('duration').seconds
    except Exception as e:
        logger.error(f"Error getting duration: {e}")
    return 0

def get_reset_time():
    now = datetime.now()
    reset = now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
    return reset

def format_timedelta(td):
    total_seconds = int(td.total_seconds())
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"

def format_remaining_time(expiry_date):
    now = datetime.now()
    if now > expiry_date:
        return "Expired"
    diff = expiry_date - now
    days = diff.days
    hours = diff.seconds // 3600
    minutes = (diff.seconds % 3600) // 60
    parts = []
    if days > 0:
        parts.append(f"{days} day{'s' if days > 1 else ''}")
    if hours > 0:
        parts.append(f"{hours} hour{'s' if hours > 1 else ''}")
    if minutes > 0:
        parts.append(f"{minutes} minute{'s' if minutes > 1 else ''}")
    return ", ".join(parts) if parts else "Less than a minute"

# ==================== DATABASE (MongoDB) ====================
_mongo_client = AsyncIOMotorClient(MONGO_URI)
_mongo_db = _mongo_client[DB_NAME]

_col_users        = _mongo_db["users"]
_col_banned       = _mongo_db["banned"]
_col_bought_test  = _mongo_db["bought_test"]
_col_redeem_codes = _mongo_db["redeem_codes"]
_col_premium_logs = _mongo_db["premium_logs"]

DEFAULT_USER = lambda uid: {
    "_id": str(uid),
    "thumb": None,
    "mode": "ask",
    "caption": "<b><i>{filename}</i>\n<blockquote>Size: {filesize}</blockquote></b>",
    "rename": "ask",
    "screenshots": 0,
    "premium": {
        "type": "free",
        "expires": None,
        "daily_conversions": 0,
        "daily_failed": 0,
        "last_reset": str(datetime.now().date())
    },
    "redeem_used": False
}

# ── in-memory cache so sync code can still read db["users"][uid] ──────────────
class _DB:
    """Thin dict-like wrapper. Keeps an in-memory mirror of Mongo collections."""
    def __init__(self):
        self.users        = {}   # uid -> user_doc
        self.banned       = []   # list of uid strings
        self.bought_test  = []   # list of uid strings
        self.redeem_codes = {}   # code -> code_doc
        self.premium_logs = []

    async def load(self):
        async for doc in _col_users.find():
            self.users[doc["_id"]] = doc
        async for doc in _col_banned.find():
            self.banned.append(doc["_id"])
        async for doc in _col_bought_test.find():
            self.bought_test.append(doc["_id"])
        async for doc in _col_redeem_codes.find():
            self.redeem_codes[doc["_id"]] = doc

db = _DB()

async def _save_user(uid):
    uid = str(uid)
    doc = db.users[uid]
    doc["_id"] = uid
    await _col_users.replace_one({"_id": uid}, doc, upsert=True)

def save_db(data=None):
    """Compatibility shim — schedules async saves for any dirty users."""
    loop = asyncio.get_event_loop()
    for uid in db.users:
        loop.create_task(_save_user(uid))

user_cooldowns = {}
temp_context = {}

def parse_duration(duration_str):
    try:
        value = int(duration_str[:-1])
        unit = duration_str[-1].lower()
        if unit == 'd':
            return timedelta(days=value)
        elif unit == 'w':
            return timedelta(weeks=value)
        elif unit == 'm':
            return timedelta(days=value * 30)
        elif unit == 'y':
            return timedelta(days=value * 365)
        else:
            return None
    except:
        return None

def get_user_config(user_id):
    user_id = str(user_id)
    if user_id not in db.users:
        db.users[user_id] = DEFAULT_USER(user_id)
        asyncio.get_event_loop().create_task(_save_user(user_id))
    else:
        changed = False
        u = db.users[user_id]
        if "premium" not in u:
            u["premium"] = {"type": "free", "expires": None, "daily_conversions": 0, "daily_failed": 0, "last_reset": str(datetime.now().date())}
            changed = True
        if "rename" not in u:
            u["rename"] = "ask"; changed = True
        if "redeem_used" not in u:
            u["redeem_used"] = False; changed = True
        if changed:
            asyncio.get_event_loop().create_task(_save_user(user_id))
    return db.users[user_id]

def check_premium(user_id):
    if int(user_id) == ADMIN_ID:
        return "admin"
    config = get_user_config(user_id)
    premium = config.get("premium", {"type": "free", "expires": None})
    if premium["type"] == "free":
        return "free"
    if premium["expires"]:
        expires = datetime.fromisoformat(premium["expires"]) if isinstance(premium["expires"], str) else premium["expires"]
        if datetime.now() > expires:
            config["premium"] = {"type": "free", "expires": None, "daily_conversions": 0, "daily_failed": 0, "last_reset": str(datetime.now().date())}
            asyncio.get_event_loop().create_task(_save_user(user_id))
            return "free"
    return premium["type"]

def get_premium_limits(user_id):
    has_premium_client = bool(SESSION_STRING and SESSION_STRING != "your_session_string_here")
    premium_max_size = MAX_FILE_SIZE_PREMIUM if has_premium_client else MAX_FILE_SIZE_NORMAL

    if int(user_id) == ADMIN_ID:
        return {
            "daily_limit": float('inf'),
            "max_file_size": float('inf'),
            "concurrent": MAX_CONCURRENT_ADMIN,
            "cooldown": 0,
            "use_dump": has_premium_client
        }

    premium_type = check_premium(user_id)

    if premium_type == "free":
        return {
            "daily_limit": FREE_DAILY_LIMIT,
            "max_file_size": MAX_FILE_SIZE_NORMAL,
            "concurrent": MAX_CONCURRENT_FREE,
            "cooldown": COOLDOWN_NORMAL,
            "use_dump": False
        }
    elif premium_type == "test":
        return {
            "daily_limit": TEST_DAILY_LIMIT,
            "max_file_size": premium_max_size,
            "concurrent": MAX_CONCURRENT_TEST,
            "cooldown": 0,
            "use_dump": has_premium_client
        }
    elif premium_type == "gold":
        return {
            "daily_limit": GOLD_DAILY_LIMIT,
            "max_file_size": premium_max_size,
            "concurrent": MAX_CONCURRENT_GOLD,
            "cooldown": 0,
            "use_dump": has_premium_client
        }
    else:  # ultra
        return {
            "daily_limit": ULTRA_DAILY_LIMIT,
            "max_file_size": float('inf') if has_premium_client else MAX_FILE_SIZE_NORMAL,
            "concurrent": MAX_CONCURRENT_ULTRA,
            "cooldown": 0,
            "use_dump": has_premium_client
        }


def check_daily_limit(user_id):
    if int(user_id) == ADMIN_ID:
        return True

    config = get_user_config(user_id)
    today = str(datetime.now().date())

    if config["premium"].get("last_reset") != today:
        config["premium"]["daily_conversions"] = 0
        config["premium"]["daily_failed"] = 0
        config["premium"]["last_reset"] = today
        asyncio.get_event_loop().create_task(_save_user(user_id))

    limits = get_premium_limits(user_id)
    return config["premium"]["daily_conversions"] < limits["daily_limit"]


def add_conversion(user_id, success=True):
    if int(user_id) == ADMIN_ID:
        return

    config = get_user_config(user_id)
    today = str(datetime.now().date())

    if config["premium"].get("last_reset") != today:
        config["premium"]["daily_conversions"] = 0
        config["premium"]["daily_failed"] = 0
        config["premium"]["last_reset"] = today

    if success:
        config["premium"]["daily_conversions"] += 1
    else:
        config["premium"]["daily_failed"] += 1

    asyncio.get_event_loop().create_task(_save_user(user_id))


# ==================== REDEEM CODES ====================
def generate_redeem_codes(count, duration_str, plan="gold"):
    duration = parse_duration(duration_str)
    if not duration:
        return None
    days = duration.days
    codes = []
    for _ in range(count):
        code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
        while code in db.redeem_codes:
            code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
        doc = {
            "_id": code,
            "plan": plan,
            "days": days,
            "used_by": None,
            "used_at": None,
            "created_at": datetime.now().isoformat()
        }
        db.redeem_codes[code] = doc
        asyncio.get_event_loop().create_task(
            _col_redeem_codes.replace_one({"_id": code}, doc, upsert=True)
        )
        codes.append(code)
    return codes

def get_redeem_code(code):
    return db.redeem_codes.get(code)

def has_active_redeemed_plan(user_id):
    uid = str(user_id)
    for code_data in db.redeem_codes.values():
        if code_data["used_by"] == uid:
            config = get_user_config(uid)
            premium = config.get("premium", {})
            if premium.get("type", "free") != "free":
                expires = premium.get("expires")
                if expires:
                    try:
                        if datetime.fromisoformat(expires) > datetime.now():
                            return True
                    except Exception:
                        pass
    return False

def use_redeem_code(code, user_id):
    if code in db.redeem_codes and db.redeem_codes[code]["used_by"] is None:
        if has_active_redeemed_plan(user_id):
            return "active"
        code_data = db.redeem_codes[code]
        plan = code_data["plan"]
        days = code_data["days"]
        config = get_user_config(user_id)
        expires = datetime.now() + timedelta(days=days)
        config["premium"] = {
            "type": plan,
            "expires": expires.isoformat(),
            "daily_conversions": 0,
            "daily_failed": 0,
            "last_reset": str(datetime.now().date())
        }
        db.redeem_codes[code]["used_by"] = str(user_id)
        db.redeem_codes[code]["used_at"] = datetime.now().isoformat()
        asyncio.get_event_loop().create_task(_save_user(user_id))
        asyncio.get_event_loop().create_task(
            _col_redeem_codes.replace_one({"_id": code}, db.redeem_codes[code], upsert=True)
        )
        return True
    return False

def get_active_redeem_count():
    return sum(1 for code in db.redeem_codes.values() if code["used_by"] is None)

def can_buy_test(user_id):
    return str(user_id) not in db.bought_test

def mark_test_bought(user_id):
    uid = str(user_id)
    if uid not in db.bought_test:
        db.bought_test.append(uid)
        asyncio.get_event_loop().create_task(
            _col_bought_test.replace_one({"_id": uid}, {"_id": uid}, upsert=True)
        )

def add_premium(user_id, plan, duration_str):
    duration = parse_duration(duration_str)
    if not duration:
        return False
    config = get_user_config(user_id)
    expires = datetime.now() + duration
    current_type = config["premium"]["type"]
    current_expires = config["premium"]["expires"]
    if current_type == "free" or (current_expires and datetime.fromisoformat(current_expires) < expires):
        config["premium"] = {
            "type": plan,
            "expires": expires.isoformat(),
            "daily_conversions": 0,
            "daily_failed": 0,
            "last_reset": str(datetime.now().date())
        }
        asyncio.get_event_loop().create_task(_save_user(user_id))
        return True
    return False

def get_user_stats_text(user_id):
    config = get_user_config(user_id)
    premium_type = check_premium(user_id)
    limits = get_premium_limits(user_id)
    today = str(datetime.now().date())
    if config["premium"].get("last_reset") != today:
        used = 0
        failed = 0
    else:
        used = config["premium"].get("daily_conversions", 0)
        failed = config["premium"].get("daily_failed", 0)
    if int(user_id) == ADMIN_ID:
        remaining = "∞"
        used_display = f"{used} (admin)"
    else:
        remaining = max(0, limits["daily_limit"] - used)
        used_display = str(used)
    reset_time = get_reset_time()
    time_to_reset = reset_time - datetime.now()
    reset_formatted = format_timedelta(time_to_reset)
    plan_names = {
        "free": "🎯 Free",
        "test": "🧪 Test",
        "gold": "🥇 Gold",
        "ultra": "👑 Ultra",
        "admin": "👑 Admin"
    }
    text = (
        f"<blockquote><b>📊 YOUR STATISTICS</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"<b>Plan:</b> {plan_names.get(premium_type, 'Free')}\n"
        f"<b>Daily Limit:</b> {'∞' if int(user_id) == ADMIN_ID else limits['daily_limit']} conversions\n"
        f"<b>Used Today:</b> {used_display} successful"
    )
    if failed > 0 and int(user_id) != ADMIN_ID:
        text += f" ({failed} failed)"
    if int(user_id) != ADMIN_ID:
        text += f"\n<b>Remaining:</b> {remaining}"
    if premium_type != "free" and premium_type != "admin" and config["premium"].get("expires"):
        expires = datetime.fromisoformat(config["premium"]["expires"])
        remaining_time = format_remaining_time(expires)
        text += f"\n<b>Expires in:</b> {remaining_time}"
    text += f"\n━━━━━━━━━━━━━━━━━━</blockquote>\n\n"
    text += f"<blockquote><b>⏰ NEXT RESET:</b> <code>{reset_formatted}</code></blockquote>\n\n"
    text += f"<b>⭐ CHOOSE A PLAN:</b>"
    return text

# ==================== UI HELPERS ====================
async def get_server_status_button_text():
    cpu = psutil.cpu_percent()
    ram = psutil.virtual_memory()
    disk = psutil.disk_usage('/')
    uptime = time_formatter(get_bot_uptime())
    
    async with tasks_lock:
        total_tasks = len(tasks)
        downloads = sum(1 for t in tasks.values() if t.stage == "downloading" and not t.cancelled)
        uploads = sum(1 for t in tasks.values() if t.stage == "uploading" and not t.cancelled)
    
    max_allowed = 10
    tasks_bar = get_prog_bar((total_tasks / max_allowed) * 100, length=10)
    
    text = (
        f"📊 <b>Sᴇʀᴠᴇʀ Pᴇʀғᴏʀᴍᴀɴᴄᴇ Sᴛᴀᴛᴜs</b>\n\n"
        f"<blockquote><b>CPU:</b> <code>{get_prog_bar(cpu)}</code> {cpu:.1f}%</blockquote>\n"
        f"<blockquote><b>RAM:</b> <code>{get_prog_bar(ram.percent)}</code> {ram.percent:.1f}%\n"
        f"↳ {human_size(ram.used)} / {human_size(ram.total)}</blockquote>\n"
        f"<blockquote><b>Dɪsᴋ:</b> <code>{get_prog_bar(disk.percent)}</code> {disk.percent:.1f}%\n"
        f"↳ {human_size(disk.free)} / {human_size(disk.total)}</blockquote>\n"
        f"<blockquote><b>Task:</b> <code>{tasks_bar}</code> {total_tasks}/{max_allowed}\n"
        f"↳ UP: {uploads} / DL: {downloads}</blockquote>\n"
        f"<blockquote><b>UPTIME:</b> {uptime}</blockquote>"
    )
    return text

async def get_server_status_mini_text():
    cpu = psutil.cpu_percent()
    ram = psutil.virtual_memory()
    disk = psutil.disk_usage('/')
    uptime = time_formatter(get_bot_uptime())
    
    async with tasks_lock:
        downloads = sum(1 for t in tasks.values() if t.stage == "downloading" and not t.cancelled)
        uploads = sum(1 for t in tasks.values() if t.stage == "uploading" and not t.cancelled)
    
    text = (
        f"⌬ <b><i>Bot Stats</i></b>\n"
        f"<blockquote>┎ <b>CPU:</b> {cpu:.1f}% | <b>F:</b> {human_size(disk.free)} [{disk.percent}%]\n"
        f"┠ <b>RAM:</b> {ram.percent}% | <b>Tasks:</b> DL: {downloads} / UP: {uploads}\n"
        f"┖ <b>UPTIME:</b> {uptime}</blockquote>"
    )
    return text

async def build_task_text(task):
    if task.cancelled:
        return f"<blockquote><b><i>{task.filename}</i></b>\n┖ ❌ Cancelled</blockquote>"
    
    stage_display = "Download" if task.stage == "downloading" else "Upload"
    processed_label = "Processed" if task.stage == "downloading" else "Uploaded"
    mode_tag = "#download" if task.stage == "downloading" else "#upload"
    
    current = task.current
    total = task.total
    percent = (current / total * 100) if total > 0 else 0
    elapsed = time.time() - task.start_time
    speed = current / elapsed if elapsed > 0 else 0
    eta = (total - current) / speed if speed > 0 and total > current else 0
    
    filename = task.filename
    if len(filename) > 60:
        filename = filename[:57] + "..."
    
    bar = get_prog_bar(percent, length=15)
    
    text = (
        f"<blockquote><b><i>{filename}</i></b>\n"
        f"┃ [{bar}] {percent:.2f}%\n"
        f"┠ <b>{processed_label}:</b> {human_size(current)} of {human_size(total)}\n"
        f"┠ <b>Status:</b> {stage_display} | <b>ETA:</b> {time_formatter(eta)}\n"
        f"┠ <b>Speed:</b> {human_size(speed)}/s | <b>Elapsed:</b> {time_formatter(elapsed)}\n"
        f"┠ <b>Engine:</b> Pyrofork\n"
        f"┠ <b>Mode:</b>  {mode_tag} | #Tg\n"
        f"┠ <b>User:</b> <code>{task.user_id}</code>\n"
        f"┖ <code>/cancel {task.short_id}</code></blockquote>"
    )
    return text

async def build_combined_status(user_id):
    async with tasks_lock:
        user_task_ids = user_tasks.get(user_id, [])
        user_tasks_list = [tasks[tid] for tid in user_task_ids if tid in tasks and not tasks[tid].cancelled]
    
    if not user_tasks_list:
        return None
    
    all_text = ""
    for task in user_tasks_list:
        task_text = await build_task_text(task)
        all_text += task_text + "\n\n"
    
    server_stats = await get_server_status_mini_text()
    all_text += server_stats
    
    return all_text

async def update_user_status(user_id):
    combined = await build_combined_status(user_id)
    if not combined:
        async with tasks_lock:
            for tid in user_tasks.get(user_id, []):
                if tid in tasks and tasks[tid].status_msg:
                    try:
                        await tasks[tid].status_msg.delete()
                    except:
                        pass
        return
    
    status_msg = None
    async with tasks_lock:
        for tid in user_tasks.get(user_id, []):
            if tid in tasks and tasks[tid].status_msg:
                status_msg = tasks[tid].status_msg
                break
        if not status_msg:
            return
    
    markup = InlineKeyboardMarkup([
        [InlineKeyboardButton("♻️", callback_data=f"refresh_{user_id}")]
    ])
    
    try:
        await status_msg.edit_text(combined, reply_markup=markup)
    except (MessageNotModified, FloodWait):
        pass

async def progress_bar(current, total, task_id):
    task = tasks.get(task_id)
    if not task or task.cancelled:
        return
    if task.cancel_event.is_set():
        task.cancelled = True
        raise StopTransmission
    
    async with task.lock:
        task.current = current
        task.total = total
    
    if not task.status_msg:
        return
    
    now = time.time()
    last_update = getattr(task.status_msg, "last_update_time", 0)
    if now - last_update < 10 and current < total:
        return
    task.status_msg.last_update_time = now
    
    await update_user_status(task.user_id)

async def get_video_thumbnail(video_path, output_path, ss_time=1):
    try:
        process = await asyncio.create_subprocess_exec(
            'ffmpeg', '-ss', str(ss_time), '-i', video_path,
            '-vframes', '1', '-q:v', '2',
            output_path, '-y',
            stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL
        )
        await process.wait()
        return output_path if os.path.exists(output_path) else None
    except Exception as e:
        logger.error(f"Thumbnail error: {e}")
        return None

async def upload_to_dump(client, file_path, file_name, task_id, thumb_path=None, duration=0, file_type="document"):
    try:
        upload_client = premium_client if premium_client else client
        if file_type == "video":
            msg = await upload_client.send_video(
                DUMP_CHANNEL,
                video=file_path,
                file_name=file_name,
                thumb=thumb_path,
                duration=duration,
                supports_streaming=True,
                progress=progress_bar,
                progress_args=(task_id,)
            )
        else:
            msg = await upload_client.send_document(
                DUMP_CHANNEL,
                document=file_path,
                file_name=file_name,
                thumb=thumb_path,
                progress=progress_bar,
                progress_args=(task_id,)
            )
        return msg
    except Exception as e:
        logger.error(f"Error uploading to dump: {e}", exc_info=True)
        print(f"[DUMP ERROR] {e}")
        return None

async def copy_from_dump_to_user(client, dump_msg, user_id, caption, reply_to_message_id):
    try:
        return await client.copy_message(
            chat_id=user_id,
            from_chat_id=DUMP_CHANNEL,
            message_id=dump_msg.id,
            caption=caption,
            reply_to_message_id=reply_to_message_id
        )
    except Exception as e:
        logger.error(f"Error copying from dump: {e}")
        return None

# ==================== COMMAND HANDLERS ====================
def get_main_btns():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💬 Group", url="https://t.me/TJ_Bots_Chat"), InlineKeyboardButton("📢 Channel", url="https://t.me/Tj_Bots")],
        [InlineKeyboardButton("⚙️ Settings", callback_data="ui_settings"), InlineKeyboardButton("⭐ Plans", callback_data="ui_plans")],
        [InlineKeyboardButton("📊 Server", callback_data="ui_status"), InlineKeyboardButton("ℹ️ About", callback_data="ui_about")],
        [InlineKeyboardButton("❓ Help", callback_data="ui_help")],
        [InlineKeyboardButton("❌ Close", callback_data="close_all")]
    ])

@bot.on_message(filters.command("start"))
async def start_cmd(client, message):
    get_user_config(message.from_user.id)
    text = (
        f"👋 <b>Hᴇʟʟᴏ {message.from_user.first_name}!</b>\n\n"
        f"<blockquote><b>I ᴀᴍ ᴀ Fᴀsᴛ & Pᴏᴡᴇʀғᴜʟ Rᴇɴᴀᴍᴇ Bᴏᴛ. 🚀</b></blockquote>\n\n"
        "💎 <b><i>Wʜᴀᴛ ᴄᴀɴ I ᴅᴏ?</i></b>\n"
        "• <b>Rᴇɴᴀᴍᴇ Fɪʟᴇs</b>\n"
        "• <b>Cʜᴀɴɢᴇ Tʜᴜᴍʙɴᴀɪʟs</b>\n"
        "• <b>Cᴏɴᴠᴇʀᴛ Vɪᴅᴇᴏ ↔️ Fɪʟᴇ</b>\n"
        "• <b>Cᴜsᴛᴏᴍ Cᴀᴘᴛɪᴏɴs (HTML)</b>\n"
        "• <b>Sᴄʀᴇᴇɴsʜᴏᴛs</b>\n\n"
        f"<blockquote><b>Bᴏᴛ Dᴇsɪɢɴᴇᴅ & Dᴇᴠᴇʟᴏᴘᴇᴅ ʙʏ <a href='{DEVELOPER_LINK}'>{DEVELOPER_NAME}</a></b></blockquote>"
    )
    await message.reply_text(text, reply_markup=get_main_btns(), reply_to_message_id=message.id, disable_web_page_preview=True)

@bot.on_message(filters.command("help"))
async def help_command(client, message):
    await show_help_menu(client, message, message.from_user.id)

@bot.on_message(filters.command("settings"))
async def settings_command(client, message):
    uid = str(message.from_user.id)
    config = get_user_config(uid)
    m_map = {"ask": "❓ Ask", "video": "🎥 Video", "file": "📁 File", "swap": "🔄 Swap"}
    r_map = {"ask": "❓ Ask", "yes": "✓", "no": "✘"}
    text = (
        "⚙️ <b>User Personal Settings</b>\n"
        "▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬\n"
        f"📍 <b>Mode:</b> <code>{m_map[config['mode']]}</code>\n"
        f"✏️ <b>Rename:</b> <code>{r_map[config['rename']]}</code>\n"
        f"📸 <b>Screenshots:</b> <code>{config['screenshots']}</code>\n"
        "▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬"
    )
    btns = [
        [InlineKeyboardButton("🔄 Mode", callback_data="st_mode"), InlineKeyboardButton("✏️ Rename", callback_data="st_rename")],
        [InlineKeyboardButton("📸 SS", callback_data="st_ss")],
        [InlineKeyboardButton("🔙 Back Home", callback_data="ui_home")]
    ]
    await message.reply_text(text, reply_markup=InlineKeyboardMarkup(btns), reply_to_message_id=message.id)

async def show_help_menu(client, message_or_query, user_id):
    btns = [
        [InlineKeyboardButton("📸 Thumbnail", callback_data="help_thumb"),
         InlineKeyboardButton("📝 Caption", callback_data="help_cap")],
        [InlineKeyboardButton("🎫 Redeem", callback_data="help_redeem"),
         InlineKeyboardButton("📋 Commands", callback_data="help_commands")],
        [InlineKeyboardButton("🔙 Back Home", callback_data="ui_home")]
    ]
    text = (
        f"Hey <b>{message_or_query.from_user.first_name}</b>\n\n"
        "<blockquote><b>Choose a category below to get help.</b></blockquote>"
    )
    if isinstance(message_or_query, Message):
        await message_or_query.reply_text(text, reply_markup=InlineKeyboardMarkup(btns), reply_to_message_id=message_or_query.id)
    else:
        await message_or_query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(btns))

# ==================== STATUS COMMAND ====================
@bot.on_message(filters.command("status"))
async def status_command(client, message):
    uid = message.from_user.id
    
    async with tasks_lock:
        user_task_ids = user_tasks.get(uid, [])
        active_tasks = [tasks[tid] for tid in user_task_ids if tid in tasks and not tasks[tid].cancelled]
    
    try:
        await message.delete()
    except:
        pass

    if not active_tasks:
        msg = await client.send_message(message.chat.id, "<blockquote>📭 No active downloads/uploads.</blockquote>")
        await asyncio.sleep(3)
        await msg.delete()
        return
    
    for task in active_tasks:
        if task.status_msg:
            try:
                await task.status_msg.delete()
            except:
                pass
            task.status_msg = None
    
    all_text = ""
    for task in active_tasks:
        task_text = await build_task_text(task)
        all_text += task_text + "\n\n"
    
    server_stats = await get_server_status_mini_text()
    all_text += server_stats
    
    markup = InlineKeyboardMarkup([
        [InlineKeyboardButton("♻️", callback_data=f"refresh_{uid}")]
    ])
    
    new_status = await client.send_message(message.chat.id, all_text, reply_markup=markup)
    
    async with tasks_lock:
        for task in active_tasks:
            task.status_msg = new_status

# ==================== CANCEL COMMANDS ====================
@bot.on_message(filters.command("cancel"))
async def cancel_command(client, message):
    parts = message.text.split()
    if len(parts) != 2:
        msg = await message.reply_text("Usage: <code>/cancel 12345</code>")
        await asyncio.sleep(3)
        await message.delete()
        await msg.delete()
        return
    
    short_id = parts[1].strip()
    
    found_task = None
    async with tasks_lock:
        for tid, task in tasks.items():
            if task.short_id == short_id and not task.cancelled:
                found_task = task
                break
    
    if not found_task:
        msg = await message.reply_text("❌ Task not found")
        await asyncio.sleep(3)
        await message.delete()
        await msg.delete()
        return
    
    if found_task.user_id != message.from_user.id and message.from_user.id != ADMIN_ID:
        msg = await message.reply_text("❌ Not your task")
        await asyncio.sleep(3)
        await message.delete()
        await msg.delete()
        return
    
    found_task.cancel_event.set()
    found_task.cancelled = True
    
    if found_task.download_task and not found_task.download_task.done():
        found_task.download_task.cancel()
    if found_task.upload_task and not found_task.upload_task.done():
        found_task.upload_task.cancel()
    
    task_dir = os.path.join(DOWNLOAD_LOCATION, found_task.task_id)
    if os.path.exists(task_dir):
        try:
            shutil.rmtree(task_dir)
        except:
            pass
    
    filename_short = found_task.filename[:50] + "..." if len(found_task.filename) > 50 else found_task.filename
    
    async with tasks_lock:
        other_tasks = [t for t in user_tasks.get(found_task.user_id, []) if t != found_task.task_id and t in tasks and not tasks[t].cancelled]
    
    if not other_tasks:
        try:
            await found_task.status_msg.delete()
        except:
            pass
    else:
        await update_user_status(found_task.user_id)
    
    confirm_msg = await message.reply_text(f"❌ <b>Cancelled:</b> <i>{filename_short}</i>")
    
    async with tasks_lock:
        if found_task.user_id in user_tasks and found_task.task_id in user_tasks[found_task.user_id]:
            user_tasks[found_task.user_id].remove(found_task.task_id)
        if found_task.task_id in tasks:
            del tasks[found_task.task_id]
    
    await asyncio.sleep(3)
    await message.delete()
    await confirm_msg.delete()

@bot.on_message(filters.command("cancelall") & filters.user(ADMIN_ID))
async def cancel_all_command(client, message):
    async with tasks_lock:
        for task_id, task in list(tasks.items()):
            task.cancel_event.set()
            task.cancelled = True
            
            if task.download_task and not task.download_task.done():
                task.download_task.cancel()
            if task.upload_task and not task.upload_task.done():
                task.upload_task.cancel()
            
            try:
                await task.status_msg.delete()
            except:
                pass
        
        tasks.clear()
        user_tasks.clear()
    
    confirm_msg = await message.reply_text("✅ All tasks cancelled")
    await asyncio.sleep(3)
    await message.delete()
    await confirm_msg.delete()

# ==================== CALLBACK HANDLERS ====================
@bot.on_callback_query()
async def callback_manager(client, query: CallbackQuery):
    data = query.data
    uid = str(query.from_user.id)
    
    try:
        config = get_user_config(uid)
        
        if data == "ui_home":
            text = (
                f"👋 <b>Hᴇʟʟᴏ {query.from_user.first_name}!</b>\n\n"
                f"<blockquote><b>I ᴀᴍ ᴀ Fᴀsᴛ & Pᴏᴡᴇʀғᴜʟ Rᴇɴᴀᴍᴇ Bᴏᴛ. 🚀</b></blockquote>\n\n"
                "💎 <b><i>Wʜᴀᴛ ᴄᴀɴ I ᴅᴏ?</i></b>\n"
                "• <b>Rᴇɴᴀᴍᴇ Fɪʟᴇs</b>\n"
                "• <b>Cʜᴀɴɢᴇ Tʜᴜᴍʙɴᴀɪʟs</b>\n"
                "• <b>Cᴏɴᴠᴇʀᴛ Vɪᴅᴇᴏ ↔️ Fɪʟᴇ</b>\n"
                "• <b>Cᴜsᴛᴏᴍ Cᴀᴘᴛɪᴏɴs</b>\n"
                "• <b>Screenshots</b>\n\n"
                f"<blockquote><b>Bᴏᴛ Dᴇsɪɢɴᴇᴅ & Dᴇᴠᴇʟᴏᴘᴇᴅ ʙʏ <a href='{DEVELOPER_LINK}'>{DEVELOPER_NAME}</a></b></blockquote>"
            )
            await query.message.edit_text(text, reply_markup=get_main_btns(), disable_web_page_preview=True)
        
        elif data == "ui_plans":
            stats_text = get_user_stats_text(uid)
            text = f"{stats_text}"
            btns = [
                [InlineKeyboardButton("🎯 Free", callback_data="show_free"),
                 InlineKeyboardButton("🧪 Test", callback_data="show_test")],
                [InlineKeyboardButton("🥇 Gold", callback_data="show_gold"),
                 InlineKeyboardButton("👑 Ultra", callback_data="show_ultra")],
                [InlineKeyboardButton("🔄 Refresh", callback_data="refresh_stats")],
                [InlineKeyboardButton("🔙 Back", callback_data="ui_home")]
            ]
            await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(btns))
        
        elif data == "refresh_stats":
            stats_text = get_user_stats_text(uid)
            text = f"{stats_text}"
            btns = [
                [InlineKeyboardButton("🎯 Free", callback_data="show_free"),
                 InlineKeyboardButton("🧪 Test", callback_data="show_test")],
                [InlineKeyboardButton("🥇 Gold", callback_data="show_gold"),
                 InlineKeyboardButton("👑 Ultra", callback_data="show_ultra")],
                [InlineKeyboardButton("🔄 Refresh", callback_data="refresh_stats")],
                [InlineKeyboardButton("🔙 Back", callback_data="ui_home")]
            ]
            await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(btns))
            await query.answer("Stats refreshed!")
        
        elif data == "show_free":
            text = (
                "<blockquote><b>🎯 FREE PLAN</b>\n"
                "━━━━━━━━━━━━━━━━━━\n"
                "• <b>Price:</b> Free\n"
                "• <b>Daily limit:</b> 10 conversions\n"
                "• <b>Max file size:</b> 2GB\n"
                "• <b>Concurrent tasks:</b> 1\n"
                "• <b>Cooldown:</b> 60 seconds\n"
                "• <b>Simultaneous downloads:</b> 1\n"
                "━━━━━━━━━━━━━━━━━━</blockquote>"
            )
            btns = [[InlineKeyboardButton("🔙 Back to Plans", callback_data="ui_plans")]]
            await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(btns))
        
        elif data == "show_test":
            if not can_buy_test(uid) and int(uid) != ADMIN_ID:
                text = (
                    "<blockquote><b>🧪 TEST PLAN</b>\n"
                    "━━━━━━━━━━━━━━━━━━\n"
                    f"• <b>Price:</b> {TEST_PRICE}\n"
                    "• <b>Daily limit:</b> 10 conversions\n"
                    "• <b>Max file size:</b> 4GB\n"
                    "• <b>Concurrent tasks:</b> 2\n"
                    "• <b>Cooldown:</b> None\n"
                    "• <b>Simultaneous downloads:</b> 2\n"
                    "━━━━━━━━━━━━━━━━━━</blockquote>\n\n"
                    "❌ You can only get the Test plan once!"
                )
                btns = [[InlineKeyboardButton("🔙 Back to Plans", callback_data="ui_plans")]]
            else:
                text = (
                    "<blockquote><b>🧪 TEST PLAN</b>\n"
                    "━━━━━━━━━━━━━━━━━━\n"
                    f"• <b>Price:</b> {TEST_PRICE}\n"
                    "• <b>Daily limit:</b> 10 conversions\n"
                    "• <b>Max file size:</b> 4GB\n"
                    "• <b>Concurrent tasks:</b> 2\n"
                    "• <b>Cooldown:</b> None\n"
                    "• <b>Simultaneous downloads:</b> 2\n"
                    "━━━━━━━━━━━━━━━━━━</blockquote>\n\n"
                    "✨ One-time free trial!"
                )
                btns = [
                    [InlineKeyboardButton("✅ Get Test (Free)", callback_data="get_test")],
                    [InlineKeyboardButton("🔙 Back to Plans", callback_data="ui_plans")]
                ]
            await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(btns))
        
        elif data == "show_gold":
            text = (
                "<blockquote><b>🥇 GOLD PLAN</b>\n"
                "━━━━━━━━━━━━━━━━━━\n"
                f"• <b>Price:</b> {GOLD_PRICE}\n"
                "• <b>Daily limit:</b> 20 conversions\n"
                "• <b>Max file size:</b> 4GB\n"
                "• <b>Concurrent tasks:</b> 2\n"
                "• <b>Cooldown:</b> None\n"
                "• <b>Simultaneous downloads:</b> 2\n"
                "━━━━━━━━━━━━━━━━━━</blockquote>"
            )
            btns = [
                [InlineKeyboardButton("👤 Contact Admin", url=f"https://t.me/{DEVELOPER_USERNAME}")],
                [InlineKeyboardButton("🔙 Back to Plans", callback_data="ui_plans")]
            ]
            await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(btns))
        
        elif data == "show_ultra":
            text = (
                "<blockquote><b>👑 ULTRA PLAN</b>\n"
                "━━━━━━━━━━━━━━━━━━\n"
                f"• <b>Price:</b> {ULTRA_PRICE}\n"
                "• <b>Daily limit:</b> 50 conversions\n"
                "• <b>Max file size:</b> Unlimited\n"
                "• <b>Concurrent tasks:</b> 3\n"
                "• <b>Cooldown:</b> None\n"
                "• <b>Simultaneous downloads:</b> 3\n"
                "━━━━━━━━━━━━━━━━━━</blockquote>"
            )
            btns = [
                [InlineKeyboardButton("👤 Contact Admin", url=f"https://t.me/{DEVELOPER_USERNAME}")],
                [InlineKeyboardButton("🔙 Back to Plans", callback_data="ui_plans")]
            ]
            await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(btns))
        
        elif data == "get_test":
            if not can_buy_test(uid) and int(uid) != ADMIN_ID:
                await query.answer("You already used your free test plan!", show_alert=True)
                return
            
            add_premium(uid, "test", "7d")
            mark_test_bought(uid)
            
            config = get_user_config(uid)
            expires = datetime.fromisoformat(config["premium"]["expires"])
            
            await query.message.edit_text(
                f"✅ <b>Test Plan Activated!</b>\n\n"
                f"Your test plan is active until: {expires.strftime('%Y-%m-%d')}\n\n"
                f"Enjoy premium features!"
            )
        
        elif data == "ui_status":
            server_stats = await get_server_status_button_text()
            await query.message.edit_text(
                server_stats,
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="ui_home")]])
            )
        
        elif data == "ui_about":
            me = await client.get_me()
            text = (
                f"🤖 <b>Bᴏᴛ Nᴀᴍᴇ :</b> <a href='https://t.me/{me.username}'>{me.first_name}</a>\n"
                f"📝 <b>Lᴀɴɢᴜᴀɢᴇ :</b> <a href='https://www.python.org/'>Pʏᴛʜᴏɴ 3.13</a>\n"
                f"📚 <b>Lɪʙʀᴀʀʏ :</b> <a href='https://github.com/himeko-org/pyrofork'>Pʏʀᴏғᴏʀᴋ</a>\n"
                f"📢 <b>Cʜᴀɴɴᴇʟ :</b> <a href='{CHANNEL_LINK}'>𝗧𝗷 𝗕𝗼𝘁𝘀</a>\n\n"
                f"<blockquote><b>Bᴏᴛ Dᴇsɪɢɴᴇᴅ & Dᴇᴠᴇʟᴏᴘᴇᴅ ʙʏ <a href='{DEVELOPER_LINK}'>{DEVELOPER_NAME}</a></b></blockquote>"
            )
            await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🐙 𝚂𝚘𝚞𝚛𝚌𝚎 𝙲𝚘𝚍𝚎", url="https://github.com/Tj-Bots/TJ-Rename-Bot")], [InlineKeyboardButton("🔙 Bᴀᴄᴋ", callback_data="ui_home")]]), disable_web_page_preview=True)
        
        elif data == "ui_help":
            await show_help_menu(client, query, uid)
        
        elif data == "help_thumb":
            text = (
                "🖼️ <b>HOW TO SET THUMBNAIL</b>\n\n"
                "<blockquote><b>1. Simply send any photo to the bot.</b>\n"
                "<b>2. The bot will save it as your custom thumbnail.</b>\n"
                "<b>3. This thumbnail will be applied to all your future files.</b></blockquote>\n\n"
                "▫️ <code>/viewthumb</code> - <u>View current thumbnail</u>\n"
                "▫️ <code>/delthumb</code> - <u>Delete your thumbnail</u>"
            )
            btns = [[InlineKeyboardButton("🔙 Back", callback_data="ui_help")]]
            await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(btns))
        
        elif data == "help_cap":
            text = (
                "📝 <b>HOW TO SET CAPTION</b>\n\n"
                "<blockquote><b>Use <code>/set_cap</code> followed by your caption text.</b></blockquote>\n\n"
                "<b>📌 AVAILABLE VARIABLES:</b>\n"
                "• <code>{filename}</code> - File name\n"
                "• <code>{filesize}</code> - File size (e.g., 15.5 MB)\n\n"
                "<b>🎨 HTML TAGS YOU CAN USE:</b>\n"
                "• <code>&lt;b&gt;text&lt;/b&gt;</code> - <b>bold</b>\n"
                "• <code>&lt;i&gt;text&lt;/i&gt;</code> - <i>italic</i>\n"
                "• <code>&lt;u&gt;text&lt;/u&gt;</code> - <u>underline</u>\n"
                "• <code>&lt;code&gt;text&lt;/code&gt;</code> - <code>monospace</code>\n\n"
                "<b>📋 EXAMPLES:</b>\n"
                "1. <code>/set_cap &lt;b&gt;{filename}&lt;/b&gt;</code>\n"
                "2. <code>/set_cap &lt;b&gt;{filename}&lt;/b&gt;\\n\\n📦 {filesize}</code>\n\n"
                "▫️ <code>/see_caption</code> - <u>Check current caption</u>\n"
                "▫️ <code>/del_caption</code> - <u>Reset to default</u>"
            )
            btns = [[InlineKeyboardButton("🔙 Back", callback_data="ui_help")]]
            await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(btns))
        
        elif data == "help_redeem":
            text = (
                "🎫 <b>REDEEM CODES</b>\n\n"
                "<blockquote>You can get premium access by redeeming a code.</blockquote>\n\n"
                "<b>How to use:</b>\n"
                "• Get a code from the admin\n"
                "• Use <code>/redeem CODE</code>\n\n"
                "<b>Example:</b>\n"
                "<code>/redeem ABC12345</code>\n\n"
                "<b>Note:</b> Each user can redeem only one code."
            )
            btns = [[InlineKeyboardButton("🔙 Back", callback_data="ui_help")]]
            await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(btns))
        
        elif data == "help_commands":
            text = (
                "<b>📋 AVAILABLE COMMANDS</b>\n"
                "━━━━━━━━━━━━━━━━━━\n\n"
                "<b>Basic Commands:</b>\n"
                "• <code>/start</code> - Start the bot\n"
                "• <code>/help</code> - Show this help menu\n"
                "• <code>/settings</code> - Open settings\n"
                "• <code>/plans</code> - View premium plans\n\n"
                "<b>Thumbnail Commands:</b>\n"
                "• <code>/viewthumb</code> - View your thumbnail\n"
                "• <code>/delthumb</code> - Delete thumbnail\n\n"
                "<b>Caption Commands:</b>\n"
                "• <code>/set_cap</code> - Set custom caption\n"
                "• <code>/see_caption</code> - View current caption\n"
                "• <code>/del_caption</code> - Reset caption\n\n"
                "<b>Premium Commands:</b>\n"
                "• <code>/redeem CODE</code> - Redeem a code\n"
                "━━━━━━━━━━━━━━━━━━"
            )
            btns = [[InlineKeyboardButton("🔙 Back", callback_data="ui_help")]]
            await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(btns))
        
        elif data == "ui_settings":
            m_map = {"ask": "❓ Ask", "video": "🎥 Video", "file": "📁 File", "swap": "🔄 Swap"}
            r_map = {"ask": "❓ Ask", "yes": "✓", "no": "✘"}
            text = (
                "⚙️ <b>User Personal Settings</b>\n"
                "▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬\n"
                f"📍 <b>Mode:</b> <code>{m_map[config['mode']]}</code>\n"
                f"✏️ <b>Rename:</b> <code>{r_map[config['rename']]}</code>\n"
                f"📸 <b>Screenshots:</b> <code>{config['screenshots']}</code>\n"
                "▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬"
            )
            btns = [
                [InlineKeyboardButton("🔄 Mode", callback_data="st_mode"), InlineKeyboardButton("✏️ Rename", callback_data="st_rename")],
                [InlineKeyboardButton("📸 SS", callback_data="st_ss")],
                [InlineKeyboardButton("🔙 Back Home", callback_data="ui_home")]
            ]
            await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(btns))
        
        elif data == "st_mode":
            btns = [
                [InlineKeyboardButton("🎥 Video", callback_data="m_video"),
                 InlineKeyboardButton("📁 File", callback_data="m_file")],
                [InlineKeyboardButton("🔄 Swap", callback_data="m_swap"),
                 InlineKeyboardButton("❓ Ask", callback_data="m_ask")],
                [InlineKeyboardButton("🔙 Back", callback_data="ui_settings")]
            ]
            mode_text = (
                "<b>⚙️ Choose default conversion mode:</b>\n\n"
                "<blockquote>🎥 <b>Video</b> — Always upload as a streamable video</blockquote>\n"
                "<blockquote>📁 <b>File</b> — Always upload as a document/file</blockquote>\n"
                "<blockquote>🔄 <b>Swap</b> — Auto-flip: video→file, file→video</blockquote>\n"
                "<blockquote>❓ <b>Ask</b> — Ask each time how to upload"
                "</blockquote>"
            )
            await query.message.edit_text(mode_text, reply_markup=InlineKeyboardMarkup(btns))
        
        elif data == "st_rename":
            btns = [
                [InlineKeyboardButton("✓", callback_data="r_yes"),
                 InlineKeyboardButton("✘", callback_data="r_no")],
                [InlineKeyboardButton("❓ Ask", callback_data="r_ask")],
                [InlineKeyboardButton("🔙 Back", callback_data="ui_settings")]
            ]
            await query.message.edit_text(
                "<b>Rename settings:</b>\n\n"
                "<blockquote>✓ = Always ask for new name</blockquote>\n"
                "<blockquote>✘ = Always keep original name</blockquote>\n"
                "<blockquote>❓ = Ask each time</blockquote>",
                reply_markup=InlineKeyboardMarkup(btns)
            )
        
        elif data == "st_ss":
            btns = [
                [InlineKeyboardButton(str(i), callback_data=f"ss_{i}") for i in range(5)],
                [InlineKeyboardButton(str(i), callback_data=f"ss_{i}") for i in range(5, 11)],
                [InlineKeyboardButton("🔙 Back", callback_data="ui_settings")]
            ]
            await query.message.edit_text("<b>Select number of screenshots:</b>", reply_markup=InlineKeyboardMarkup(btns))
        
        elif data.startswith("m_"):
            config["mode"] = data.split("_")[1]
            asyncio.get_event_loop().create_task(_save_user(uid))
            query.data = "ui_settings"
            await callback_manager(client, query)
            return
        
        elif data.startswith("r_"):
            config["rename"] = data.split("_")[1]
            asyncio.get_event_loop().create_task(_save_user(uid))
            query.data = "ui_settings"
            await callback_manager(client, query)
            return
        
        elif data.startswith("ss_"):
            config["screenshots"] = int(data.split("_")[1])
            asyncio.get_event_loop().create_task(_save_user(uid))
            query.data = "ui_settings"
            await callback_manager(client, query)
            return
        
        elif data.startswith("go_"):
            parts = data.split("_")
            if len(parts) < 3:
                await query.answer("Invalid callback data", show_alert=True)
                return
            target = parts[1]
            try:
                mid = int(parts[2])
            except ValueError:
                await query.answer("Invalid message ID", show_alert=True)
                return
            try:
                msg = await client.get_messages(query.message.chat.id, mid)
            except Exception:
                msg = None
            if not msg or not (msg.video or msg.document):
                await query.answer("Original message not found", show_alert=True)
                return
            await start_conversion(client, msg, target, query.message)
        
        elif data.startswith("skp_"):
            parts = data.split("_")
            if len(parts) < 3:
                await query.answer("Invalid callback data", show_alert=True)
                return
            try:
                mid = int(parts[1])
            except ValueError:
                await query.answer("Invalid message ID", show_alert=True)
                return
            target = parts[2]
            try:
                msg = await client.get_messages(query.message.chat.id, mid)
            except Exception:
                msg = None
            if not msg or not (msg.video or msg.document):
                await query.answer("Original message not found", show_alert=True)
                return
            temp_context[f"waiting_{query.from_user.id}"] = False
            await query.message.delete()
            await process_now(client, msg, target, (msg.video or msg.document).file_name or "file")
        
        elif data == "queue_stats":
            async with tasks_lock:
                total = len(tasks)
                downloads = sum(1 for t in tasks.values() if t.stage == "downloading" and not t.cancelled)
                uploads = sum(1 for t in tasks.values() if t.stage == "uploading" and not t.cancelled)
            
            text = (
                f"📊 <b>Task Statistics</b>\n\n"
                f"• Total active: {total}/10\n"
                f"• Downloads: {downloads}\n"
                f"• Uploads: {uploads}"
            )
            await query.answer(text, show_alert=True)
        
        elif data.startswith("refresh_"):
            user_id = int(data.split("_")[1])
            if user_id != query.from_user.id and query.from_user.id != ADMIN_ID:
                await query.answer("Not your tasks!", show_alert=True)
                return
            
            now = time.time()
            last = last_refresh.get(user_id, 0)
            if now - last < 3:
                await query.answer(f"⏳ Please wait {3 - int(now - last)}s", show_alert=True)
                return
            last_refresh[user_id] = now
            
            await update_user_status(user_id)
            #await query.answer("Refreshed!")
        
        elif data == "close_all":
            try:
                uid = str(query.from_user.id)
                if f"waiting_{uid}" in temp_context:
                    temp_context[f"waiting_{uid}"] = False
                if f"pending_{uid}" in temp_context:
                    temp_context.pop(f"pending_{uid}", None)
                if f"prompt_{uid}" in temp_context:
                    temp_context.pop(f"prompt_{uid}", None)
                if query.message.reply_to_message:
                    await query.message.reply_to_message.delete()
                await query.message.delete()
            except Exception as e:
                logger.error(f"Error deleting: {e}")
        
        else:
            await query.answer("Unknown action", show_alert=False)
    
    except Exception as e:
        logger.error(f"Error in callback_manager: {e}", exc_info=True)
        await query.answer("An error occurred", show_alert=True)

# ==================== REDEEM COMMANDS ====================
@bot.on_message(filters.command("gencodes") & filters.user(ADMIN_ID))
async def generate_codes_command(client, message):
    parts = message.text.split()
    if len(parts) < 3:
        await message.reply_text(
            "Usage: <code>/gencodes <count> <duration> [plan]</code>\n"
            "Example: <code>/gencodes 5 30d gold</code>\n"
            "Plan: gold (default) or ultra\n"
            "Duration: 1d, 7d, 2w, 1m, 3m, 1y"
        )
        return
    try:
        count = int(parts[1])
    except ValueError:
        await message.reply_text("❌ Count must be a number.")
        return
    duration_str = parts[2]
    plan = parts[3].lower() if len(parts) > 3 else "gold"
    if plan not in ["gold", "ultra"]:
        await message.reply_text("❌ Plan must be 'gold' or 'ultra'")
        return
    match = re.match(r"^(\d+)([dwm])$", duration_str.lower())
    if not match:
        await message.reply_text("❌ Invalid duration format. Use: 1d, 2w, 3m")
        return
    value = int(match.group(1))
    unit = match.group(2)
    if unit == 'd':
        display = f"{value} day{'s' if value > 1 else ''}"
    elif unit == 'w':
        display = f"{value} week{'s' if value > 1 else ''}"
    else:
        display = f"{value} month{'s' if value > 1 else ''}"
    if count < 1 or count > 100:
        await message.reply_text("❌ Count must be between 1 and 100.")
        return
    codes = generate_redeem_codes(count, duration_str, plan)
    if not codes:
        await message.reply_text("❌ Failed to generate codes.")
        return
    response = f"✅ Generated {count} {plan.upper()} redeem codes ({display}):\n\n"
    for i, code in enumerate(codes, 1):
        response += f"{i}. <code>{code}</code>\n"
    await message.reply_text(response)
    logger.info(f"Admin generated {count} {plan} redeem codes for {display}")

@bot.on_message(filters.command("redeem"))
async def redeem_code_command(client, message):
    user_id = message.from_user.id
    parts = message.text.split()
    if len(parts) != 2:
        await message.reply_text("Usage: <code>/redeem <code></code>")
        return
    code = parts[1].strip().upper()
    code_data = get_redeem_code(code)
    if not code_data:
        await message.reply_text("❌ Code not found.")
        return
    if code_data["used_by"] is not None:
        await message.reply_text("❌ Code already used.")
        return
    plan = code_data["plan"]
    days = code_data["days"]
    result = use_redeem_code(code, user_id)
    if result == "active":
        await message.reply_text("❌ <b>You already have an active premium plan from a redeem code.</b>\nYou can redeem a new code once your current plan expires.")
    elif result is True:
        config = get_user_config(user_id)
        expires = datetime.fromisoformat(config["premium"]["expires"])
        remaining = get_active_redeem_count()
        user_mention = message.from_user.mention
        await client.send_message(
            ADMIN_ID,
            f"🔔 <b>New Redeem Code Used</b>\n\n"
            f"👤 User: {user_mention} (<code>{user_id}</code>)\n"
            f"🔑 Code: <code>{code}</code>\n"
            f"📊 Plan: {plan.upper()}\n"
            f"⏳ Duration: {days} days\n"
            f"📊 Remaining codes: <code>{remaining}</code>"
        )
        await message.reply_text(
            f"✅ <b>Redeem Successful!</b>\n\n"
            f"You now have {plan.upper()} premium for {days} days.\n"
            f"Expires: {expires.strftime('%Y-%m-%d')}"
        )
        logger.info(f"User {user_id} redeemed code {code} for {days} days")
    else:
        await message.reply_text("❌ Error redeeming code. Please try again.")

@bot.on_message(filters.command("redeem_stats") & filters.user(ADMIN_ID))
async def redeem_stats_command(client, message):
    total = len(db.redeem_codes)
    used = sum(1 for code in db.redeem_codes.values() if code["used_by"] is not None)
    available = total - used
    text = (
        f"<b>🎫 Redeem Codes Statistics</b>\n\n"
        f"Total: {total}\n"
        f"Used: {used}\n"
        f"Available: {available}\n\n"
    )
    if available > 0:
        text += "Recent codes:\n"
        count = 0
        for code, data in db.redeem_codes.items():
            if data["used_by"] is None and count < 10:
                days = data["days"]
                plan = data["plan"].upper()
                text += f"• <code>{code}</code> ({plan} - {days} days)\n"
                count += 1
    await message.reply_text(text, reply_to_message_id=message.id)

# ==================== ADMIN COMMANDS ====================
@bot.on_message(filters.command("admin") & filters.user(ADMIN_ID))
async def admin_panel(client, message):
    users_count = len(db.users)
    banned_count = len(db.banned)
    redeem_count = get_active_redeem_count()
    test_count = gold_count = ultra_count = 0
    for uid, user_data in db.users.items():
        premium_type = check_premium(uid)
        if premium_type == "test":
            test_count += 1
        elif premium_type == "gold":
            gold_count += 1
        elif premium_type == "ultra":
            ultra_count += 1
    text = (
        "<b>╭── ˹ ADMIN CONTROL ˼ ──</b>\n"
        "<b>│</b>\n"
        f"<b>├── 👤 Admin:</b> <code>{ADMIN_ID}</code>\n"
        f"<b>├── 📊 Users:</b> <b>{users_count}</b>\n"
        f"<b>├── 🔨 Banned:</b> <b>{banned_count}</b>\n"
        f"<b>├── 🧪 Test:</b> <b>{test_count}</b>\n"
        f"<b>├── 🥇 Gold:</b> <b>{gold_count}</b>\n"
        f"<b>├── 👑 Ultra:</b> <b>{ultra_count}</b>\n"
        f"<b>├── 🎫 Redeem:</b> <b>{redeem_count}</b>\n"
        "<b>│</b>\n"
        "<b>├── 📢 Broadcast:</b>\n"
        "<b>│ ├⊳ /broadcast (Copy)</b>\n"
        "<b>│ └⊳ /broadcast -f (Forward)</b>\n"
        "<b>│</b>\n"
        "<b>├── 👤 Users:</b>\n"
        "<b>│ ├⊳ /ban [id] (Ban)</b>\n"
        "<b>│ ├⊳ /unban [id] (Unban)</b>\n"
        "<b>│ ├⊳ /users (List users)</b>\n"
        "<b>│ └⊳ /allban (List banned)</b>\n"
        "<b>│</b>\n"
        "<b>├── ⭐ Plans:</b>\n"
        "<b>│ ├⊳ /add_plan [id] [test/gold/ultra] [duration]</b>\n"
        "<b>│ ├⊳ /remove_plan [id]</b>\n"
        "<b>│ ├⊳ /plan_list</b>\n"
        "<b>│ └⊳ /refund [payload]</b>\n"
        "<b>│</b>\n"
        "<b>├── 🎫 Redeem Codes:</b>\n"
        "<b>│ ├⊳ /gencodes [count] [duration] [gold/ultra]</b>\n"
        "<b>│ └⊳ /redeem_stats</b>\n"
        "<b>│</b>\n"
        "<b>├── ⚙️ System:</b>\n"
        "<b>│ └⊳ /restart</b>\n"
        "<b>│</b>\n"
        "<b>╰────────────────</b>"
    )
    await message.reply_text(text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🗑️", callback_data="close_all")]]), reply_to_message_id=message.id)

@bot.on_message(filters.command("add_plan") & filters.user(ADMIN_ID))
async def add_plan_cmd(client, message):
    args = message.text.split()
    if len(args) < 4:
        return await message.reply_text(
            "Usage: <code>/add_plan [user_id] [test/gold/ultra] [duration]</code>\n"
            "Duration: 1d, 2w, 3m, 1y\n"
            "Example: <code>/add_plan 123456 gold 1m</code>",
            reply_to_message_id=message.id
        )
    user_id = args[1]
    plan = args[2].lower()
    duration = args[3]
    if plan not in ["test", "gold", "ultra"]:
        return await message.reply_text("❌ Plan must be test, gold, or ultra", reply_to_message_id=message.id)
    if not add_premium(user_id, plan, duration):
        return await message.reply_text("❌ Invalid duration format!", reply_to_message_id=message.id)
    if plan == "test":
        mark_test_bought(user_id)
    config = get_user_config(user_id)
    expires = datetime.fromisoformat(config["premium"]["expires"])
    await message.reply_text(
        f"✅ <b>Plan added to user <code>{user_id}</code></b>\n"
        f"Plan: {plan.upper()}\n"
        f"Expires: {expires.strftime('%Y-%m-%d %H:%M')}",
        reply_to_message_id=message.id
    )
    try:
        await client.send_message(
            int(user_id),
            f"✨ <b>Congratulations!</b>\n\n"
            f"You have been granted <b>{plan.upper()} Plan</b> by the admin!\n"
            f"Your plan is active until: {expires.strftime('%Y-%m-%d')}\n\n"
            f"Enjoy the benefits!"
        )
    except:
        pass

@bot.on_message(filters.command("remove_plan") & filters.user(ADMIN_ID))
async def remove_plan_cmd(client, message):
    if len(message.command) < 2:
        return await message.reply_text("Usage: <code>/remove_plan [user_id]</code>", reply_to_message_id=message.id)
    user_id = message.command[1]
    config = get_user_config(user_id)
    if config["premium"]["type"] == "free":
        return await message.reply_text("❌ User has no active plan.", reply_to_message_id=message.id)
    old_plan = config["premium"]["type"]
    config["premium"] = {"type": "free", "expires": None, "daily_conversions": 0, "daily_failed": 0, "last_reset": str(datetime.now().date())}
    asyncio.get_event_loop().create_task(_save_user(user_id))
    await message.reply_text(f"✅ Removed {old_plan.upper()} plan from user {user_id}", reply_to_message_id=message.id)

@bot.on_message(filters.command("plan_list") & filters.user(ADMIN_ID))
async def plan_list_cmd(client, message):
    test_users = []
    gold_users = []
    ultra_users = []
    for uid, user_data in db.users.items():
        premium_type = check_premium(uid)
        if premium_type == "test":
            test_users.append(uid)
        elif premium_type == "gold":
            gold_users.append(uid)
        elif premium_type == "ultra":
            ultra_users.append(uid)
    text = f"<b>⭐ Active Plans</b>\n\n"
    text += f"<b>🧪 Test ({len(test_users)}):</b>\n"
    for uid in test_users[:20]:
        config = get_user_config(uid)
        expires = datetime.fromisoformat(config["premium"]["expires"])
        remaining = format_remaining_time(expires)
        text += f"• <code>{uid}</code> (expires: {remaining})\n"
    text += f"\n<b>🥇 Gold ({len(gold_users)}):</b>\n"
    for uid in gold_users[:20]:
        config = get_user_config(uid)
        expires = datetime.fromisoformat(config["premium"]["expires"])
        remaining = format_remaining_time(expires)
        text += f"• <code>{uid}</code> (expires: {remaining})\n"
    text += f"\n<b>👑 Ultra ({len(ultra_users)}):</b>\n"
    for uid in ultra_users[:20]:
        config = get_user_config(uid)
        expires = datetime.fromisoformat(config["premium"]["expires"])
        remaining = format_remaining_time(expires)
        text += f"• <code>{uid}</code> (expires: {remaining})\n"
    if len(test_users) > 20 or len(gold_users) > 20 or len(ultra_users) > 20:
        text += "\n... and more"
    await message.reply_text(text, reply_to_message_id=message.id)

@bot.on_message(filters.command("broadcast") & filters.user(ADMIN_ID))
async def broadcast_cmd(client, message):
    if not message.reply_to_message:
        return await message.reply_text("Reply to a message to broadcast.", reply_to_message_id=message.id)
    is_forward = "-f" in message.text
    mode_label = "📨 Forward" if is_forward else "📋 Copy"
    total_users = len(db.users)
    success, failed = 0, 0
    last_edit = time.time()

    status = await message.reply_text(
        f"<b>📢 Broadcasting...</b>\n\n"
        f"<blockquote>"
        f"🔀 <b>Mode:</b> {mode_label}\n"
        f"👥 <b>Users:</b> 0 / {total_users}\n"
        f"✅ <b>Success:</b> 0\n"
        f"❌ <b>Failed:</b> 0"
        f"</blockquote>",
        reply_to_message_id=message.id
    )

    for user_id in db.users:
        try:
            if is_forward:
                await message.reply_to_message.forward(int(user_id))
            else:
                await message.reply_to_message.copy(int(user_id))
            success += 1
        except Exception as e:
            logger.error(f"Broadcast failed to {user_id}: {e}")
            failed += 1
        await asyncio.sleep(0.1)

        now = time.time()
        if now - last_edit >= 5:
            last_edit = now
            sent = success + failed
            try:
                await status.edit_text(
                    f"<b>📢 Broadcasting...</b>\n\n"
                    f"<blockquote>"
                    f"🔀 <b>Mode:</b> {mode_label}\n"
                    f"👥 <b>Users:</b> {sent} / {total_users}\n"
                    f"✅ <b>Success:</b> {success}\n"
                    f"❌ <b>Failed:</b> {failed}"
                    f"</blockquote>"
                )
            except (MessageNotModified, FloodWait):
                pass

    await status.edit_text(
        f"<b>📢 Broadcast Finished!</b>\n\n"
        f"<blockquote>"
        f"🔀 <b>Mode:</b> {mode_label}\n"
        f"👥 <b>Total:</b> {total_users}\n"
        f"✅ <b>Success:</b> {success}\n"
        f"❌ <b>Failed:</b> {failed}"
        f"</blockquote>"
    )

@bot.on_message(filters.command("restart") & filters.user(ADMIN_ID))
async def restart_bot(client, message):
    await message.reply_text("🔄 <b>Restarting...</b>", reply_to_message_id=message.id)
    os.execl(sys.executable, sys.executable, *sys.argv)

@bot.on_message(filters.command("ban") & filters.user(ADMIN_ID))
async def ban_user_cmd(client, message):
    if len(message.command) < 2:
        return await message.reply_text("Usage: <code>/ban [id]</code>", reply_to_message_id=message.id)
    target = message.command[1]
    if target not in db.banned:
        db.banned.append(target)
        asyncio.get_event_loop().create_task(_col_banned.replace_one({"_id": target}, {"_id": target}, upsert=True))
        await message.reply_text(f"🚫 User <code>{target}</code> banned.", reply_to_message_id=message.id)
    else:
        await message.reply_text("User already banned.", reply_to_message_id=message.id)

@bot.on_message(filters.command("unban") & filters.user(ADMIN_ID))
async def unban_user_cmd(client, message):
    if len(message.command) < 2:
        return await message.reply_text("Usage: <code>/unban [id]</code>", reply_to_message_id=message.id)
    target = message.command[1]
    if target in db.banned:
        db.banned.remove(target)
        asyncio.get_event_loop().create_task(_col_banned.delete_one({"_id": target}))
        await message.reply_text(f"✅ User <code>{target}</code> unbanned.", reply_to_message_id=message.id)
    else:
        await message.reply_text("User not banned.", reply_to_message_id=message.id)

@bot.on_message(filters.command("users") & filters.user(ADMIN_ID))
async def users_list(client, message):
    users = list(db.users.keys())
    total = len(users)
    if total == 0:
        return await message.reply_text("<b>👥 No users yet.</b>", reply_to_message_id=message.id)
    
    text = f"<b>👥 Total users: {total}</b>\n\n"
    
    list_lines = []
    if total <= 50:
        for uid in users:
            list_lines.append(f"<code>{uid}</code>")
    else:
        for uid in users[:50]:
            list_lines.append(f"<code>{uid}</code>")
        list_lines.append(f"... and {total - 50} more users.")
    
    text += "<blockquote expandable>\n" + "\n".join(list_lines) + "\n</blockquote>"
    
    await message.reply_text(text, reply_to_message_id=message.id)


@bot.on_message(filters.command("allban") & filters.user(ADMIN_ID))
async def allban_list(client, message):
    banned = db.banned
    total = len(banned)
    if total == 0:
        return await message.reply_text("<b>🔨 No banned users.</b>", reply_to_message_id=message.id)
    
    text = f"<b>🔨 Total banned users: {total}</b>\n\n"
    
    list_lines = []
    if total <= 50:
        for uid in banned:
            list_lines.append(f"<code>{uid}</code>")
    else:
        for uid in banned[:50]:
            list_lines.append(f"<code>{uid}</code>")
        list_lines.append(f"... and {total - 50} more banned users.")
    
    text += "<blockquote expandable>\n" + "\n".join(list_lines) + "\n</blockquote>"
    
    await message.reply_text(text, reply_to_message_id=message.id)

# ==================== THUMBNAIL & CAPTION COMMANDS ====================
@bot.on_message(filters.command(["set_caption", "set_cap"]))
async def set_cap_p(client, message):
    if len(message.command) < 2:
        help_text = (
            "📝 <b>HOW TO SET CAPTION</b>\n\n"
            "<b>Usage:</b> <code>/set_cap YOUR_CAPTION_HERE</code>\n\n"
            "<b>Available variables:</b>\n"
            "• <code>{filename}</code> - File name\n"
            "• <code>{filesize}</code> - File size\n\n"
            "<b>Example:</b>\n"
            "<code>/set_cap <b>{filename}</b>\n\n📦 {filesize}</code>\n\n"
            "Use <code>/see_caption</code> to view current caption\n"
            "Use <code>/del_caption</code> to reset to default"
        )
        return await message.reply_text(help_text, reply_to_message_id=message.id)
    uid = str(message.from_user.id)
    get_user_config(uid)["caption"] = message.text.split(None, 1)[1]
    asyncio.get_event_loop().create_task(_save_user(uid))
    await message.reply_text("✅ <b>Caption Updated!</b>", reply_to_message_id=message.id)

@bot.on_message(filters.command(["see_caption", "view_cap", "view_caption"]))
async def view_cap_p(client, message):
    cap = get_user_config(message.from_user.id)['caption']
    text = (
        "📝 <b>Your Current Caption:</b>\n\n"
        f"<code>{cap}</code>\n\n"
        "Use <code>/set_cap</code> to change it"
    )
    await message.reply_text(text, reply_to_message_id=message.id)

@bot.on_message(filters.command(["del_caption", "del_cap"]))
async def del_cap_p(client, message):
    uid = str(message.from_user.id)
    get_user_config(uid)["caption"] = "<b><i>{filename}</i>\n\n<blockquote>Size: {filesize}</blockquote></b>"
    asyncio.get_event_loop().create_task(_save_user(uid))
    await message.reply_text("🗑 <b>Caption Reset to Default!</b>", reply_to_message_id=message.id)

@bot.on_message(filters.photo | (filters.document & filters.create(lambda _, __, m: m.document and m.document.mime_type.startswith("image/"))))
async def save_thumb_p(client, message):
    uid = str(message.from_user.id)
    get_user_config(uid)["thumb"] = (message.photo or message.document).file_id
    asyncio.get_event_loop().create_task(_save_user(uid))
    await message.reply_text("✅ <b>Thumbnail Saved!</b>", reply_to_message_id=message.id)

@bot.on_message(filters.command(["viewthumb", "view_thumb"]))
async def view_thumb_p(client, message):
    thumb = get_user_config(message.from_user.id)["thumb"]
    if thumb:
        await message.reply_photo(thumb, caption="🖼 <b>Custom Thumbnail</b>", reply_to_message_id=message.id)
    else:
        await message.reply_text("❌ <b>No Thumbnail set!</b>", reply_to_message_id=message.id)

@bot.on_message(filters.command(["delthumb", "del_thumb"]))
async def del_thumb_p(client, message):
    uid = str(message.from_user.id)
    get_user_config(uid)["thumb"] = None
    asyncio.get_event_loop().create_task(_save_user(uid))
    await message.reply_text("🗑 <b>Thumbnail Deleted!</b>", reply_to_message_id=message.id)

@bot.on_message(filters.command("plans"))
async def plans_command(client, message):
    uid = str(message.from_user.id)
    stats_text = get_user_stats_text(uid)
    text = f"{stats_text}"
    btns = [
        [InlineKeyboardButton("🎯 Free", callback_data="show_free"),
         InlineKeyboardButton("🧪 Test", callback_data="show_test")],
        [InlineKeyboardButton("🥇 Gold", callback_data="show_gold"),
         InlineKeyboardButton("👑 Ultra", callback_data="show_ultra")],
        [InlineKeyboardButton("🔄 Refresh", callback_data="refresh_stats")],
        [InlineKeyboardButton("🔙 Back Home", callback_data="ui_home")]
    ]
    await message.reply_text(text, reply_markup=InlineKeyboardMarkup(btns), reply_to_message_id=message.id)

# ==================== FILE HANDLING ====================
@bot.on_message(filters.private & (filters.video | filters.document) & ~filters.service)
async def on_file_receive(client, message):
    uid = message.from_user.id
    config = get_user_config(uid)
    
    if str(uid) in db.banned:
        return await message.reply_text("🚫 <b>You are banned from using this bot.</b>", reply_to_message_id=message.id)
    
    file = message.video or message.document
    if not file:
        return

    file_size = file.file_size
    limits = get_premium_limits(uid)

    if file_size > limits["max_file_size"]:
        text = f"❌ <b>File too large!</b>\nMax size: {human_size(limits['max_file_size'])}"
        if limits["concurrent"] == MAX_CONCURRENT_FREE:
            text += "\n\nUpgrade your plan for larger files!"
        else:
            text += "\n\nUltra plan required for unlimited size."
        btn = [[InlineKeyboardButton("View Plans", callback_data="ui_plans")]]
        return await message.reply_text(text, reply_markup=InlineKeyboardMarkup(btn), reply_to_message_id=message.id)

    if int(uid) != ADMIN_ID and not check_daily_limit(uid):
        reset_time = get_reset_time()
        time_to_reset = reset_time - datetime.now()
        reset_formatted = format_timedelta(time_to_reset)
        text = f"❌ <b>Daily limit reached!</b>\nReset in: <code>{reset_formatted}</code>"
        if limits["concurrent"] == MAX_CONCURRENT_FREE:
            text += "\nUpgrade your plan for higher limits!"
        else:
            text += "\nUltra plan required for more conversions."
        btn = [[InlineKeyboardButton("View Plans", callback_data="ui_plans")]]
        return await message.reply_text(text, reply_markup=InlineKeyboardMarkup(btn), reply_to_message_id=message.id)

    async with tasks_lock:
        active_count = len([
            tid for tid in user_tasks.get(uid, [])
            if tid in tasks and not tasks[tid].cancelled
        ])

    if active_count >= limits["concurrent"]:
        if limits["concurrent"] == MAX_CONCURRENT_FREE:
            text = (
                f"⚠️ <b>You already have {active_count} active task!</b>\n"
                "Free users are limited to 1 conversion at a time.\n\n"
                "Upgrade to Gold or Ultra to convert up to 3 files simultaneously!"
            )
            btns = [[InlineKeyboardButton("Upgrade Plan", callback_data="ui_plans")]]
        else:
            text = (
                f"⚠️ <b>You already have {active_count}/{limits['concurrent']} active tasks!</b>\n"
                "Please wait for one to finish or cancel one."
            )
        return await message.reply_text(text, reply_markup=InlineKeyboardMarkup(btns), reply_to_message_id=message.id)
        
        
    if int(uid) != ADMIN_ID and limits["concurrent"] == MAX_CONCURRENT_FREE:
        if uid in user_cooldowns:
            rem = user_cooldowns[uid] - time.time()
            if rem > 0:
                return await message.reply_text(
                    f"⏳ <b>Cooldown active!</b>\n"
                    f"Please wait <code>{int(rem)} seconds</code> before sending another file.",
                    reply_to_message_id=message.id
                )

    if config["mode"] == "ask":
        btns = [
            [InlineKeyboardButton("🎥 Video", callback_data=f"go_video_{message.id}"),
             InlineKeyboardButton("📁 File", callback_data=f"go_file_{message.id}")],
            [InlineKeyboardButton("❌ Cancel", callback_data="close_all")]
        ]
        msg = await message.reply_text("<b><i>How should I process this file?</i></b>", reply_markup=InlineKeyboardMarkup(btns), reply_to_message_id=message.id)
        temp_context[f"prompt_{uid}"] = msg.id
    elif config["mode"] == "swap":
        if message.video:
            await start_conversion(client, message, "file")
        else:
            await start_conversion(client, message, "video")
    elif config["mode"] == "video":
        await start_conversion(client, message, "video")
    elif config["mode"] == "file":
        await start_conversion(client, message, "file")

async def start_conversion(client, message, target, prompt_msg=None):
    uid = str(message.from_user.id)
    config = get_user_config(uid)
    original_name = (message.video or message.document).file_name or "file"
    
    if config["rename"] in ["ask", "yes"]:
        temp_context[f"pending_{uid}"], temp_context[f"waiting_{uid}"] = {"msg": message, "target": target}, True
        btns = [
            [InlineKeyboardButton("🔄 Keep Original", callback_data=f"skp_{message.id}_{target}")],
            [InlineKeyboardButton("❌ Cancel", callback_data="close_all")]
        ]
        text = f"✏️ <b>Send a new name for:</b>\n\n<code>{original_name}</code>"
        if prompt_msg:
            await prompt_msg.edit_text(text, reply_markup=InlineKeyboardMarkup(btns))
            temp_context[f"prompt_{uid}"] = prompt_msg.id
        else:
            m = await message.reply_text(text, reply_markup=InlineKeyboardMarkup(btns), reply_to_message_id=message.id)
            temp_context[f"prompt_{uid}"] = m.id
    else:  # "no"
        if prompt_msg:
            await prompt_msg.delete()
        await process_now(client, message, target, original_name)

@bot.on_message(filters.private & filters.text & filters.create(lambda _, __, m: temp_context.get(f"waiting_{m.from_user.id}")))
async def receive_name(client, message):
    uid = str(message.from_user.id)
    new_name = message.text
    temp_context[f"waiting_{uid}"] = False
    ctx = temp_context.get(f"pending_{uid}")
    if not ctx:
        await message.delete()
        return
    original_name = (ctx["msg"].video or ctx["msg"].document).file_name or "file"
    if "." not in new_name and "." in original_name:
        new_name += os.path.splitext(original_name)[1]
    await message.delete()
    if temp_context.get(f"prompt_{uid}"):
        try:
            await client.delete_messages(message.chat.id, temp_context[f"prompt_{uid}"])
        except:
            pass
    await process_now(client, ctx["msg"], ctx["target"], new_name)

async def process_now(client, message, target, filename):
    uid = message.from_user.id
    config = get_user_config(uid)
    file_size = (message.video or message.document).file_size
    premium_type = check_premium(uid)
    limits = get_premium_limits(uid)
    
    short_id = str(random.randint(10000, 99999))
    task_id = f"task_{short_id}"
    
    async with tasks_lock:
        existing_tasks = user_tasks.get(uid, [])
        if existing_tasks:
            for tid in existing_tasks:
                if tid in tasks and tasks[tid].status_msg:
                    try:
                        await tasks[tid].status_msg.delete()
                    except:
                        pass
                    tasks[tid].status_msg = None  # איפוס
    
    status_msg = await message.reply_text("⏳ <b>Starting...</b>")
    
    task = TaskInfo(task_id, short_id, uid, message, filename, target, status_msg)
    
    async with tasks_lock:
        tasks[task_id] = task
        if uid not in user_tasks:
            user_tasks[uid] = []
        user_tasks[uid].append(task_id)
        
        for tid in user_tasks[uid]:
            if tid in tasks:
                tasks[tid].status_msg = status_msg
    
    task_dir = os.path.join(DOWNLOAD_LOCATION, task_id)
    os.makedirs(task_dir, exist_ok=True)
    path = os.path.join(task_dir, filename)
    thumb = None
    success = False
    
    try:
        task.stage = "downloading"
        task.download_task = asyncio.current_task()
        
        await client.download_media(
            message,
            file_name=path,
            progress=progress_bar,
            progress_args=(task_id,)
        )
        
        if task.cancel_event.is_set():
            raise asyncio.CancelledError
        
        should_send_as_video = (
            target == "video" or
            (target == "swap" and message.document)
        )

        if config["thumb"]:
            thumb = await client.download_media(config["thumb"], file_name=f"{path}_t.jpg")
        elif should_send_as_video:
            thumb = await get_video_thumbnail(path, f"{path}_t.jpg")
        
        duration = get_duration(path) if should_send_as_video else 0
        cap = config["caption"].format(filename=filename, filesize=human_size(file_size))
        
        task.stage = "uploading"
        task.upload_task = asyncio.current_task()

        if file_size > MAX_FILE_SIZE_NORMAL and limits["use_dump"]:
            dump_msg = await upload_to_dump(
                client, path, filename, task_id,
                thumb_path=thumb,
                duration=duration,
                file_type="video" if should_send_as_video else "document"
            )
            if not dump_msg:
                raise Exception("Failed to upload to dump channel")
            await copy_from_dump_to_user(client, dump_msg, message.chat.id, cap, message.id)
        else:
            if should_send_as_video:
                await client.send_video(
                    message.chat.id, video=path, caption=cap, thumb=thumb,
                    duration=duration, file_name=filename, supports_streaming=True,
                    progress=progress_bar, progress_args=(task_id,),
                    reply_to_message_id=message.id
                )
            else:
                await client.send_document(
                    message.chat.id, document=path, caption=cap, thumb=thumb,
                    file_name=filename, progress=progress_bar, progress_args=(task_id,),
                    reply_to_message_id=message.id
                )
        
        if config["screenshots"] > 0 and should_send_as_video:
            media = []
            dur = get_duration(path)
            for i in range(config["screenshots"]):
                st = (dur // (config["screenshots"] + 1)) * (i + 1)
                ss = await get_video_thumbnail(path, f"{task_dir}/ss_{i}.jpg", ss_time=st)
                if ss:
                    media.append(InputMediaPhoto(ss, caption=f"Shot #{i+1}"))
            if media:
                await client.send_media_group(message.chat.id, media=media, reply_to_message_id=message.id)
        
        success = True
        
        if int(uid) != ADMIN_ID and premium_type == "free":
            user_cooldowns[uid] = time.time() + COOLDOWN_NORMAL
    
    except asyncio.CancelledError:
        task.cancelled = True
        filename_short = filename[:50] + "..." if len(filename) > 50 else filename
        
        if os.path.exists(path):
            try:
                os.remove(path)
            except:
                pass
        
        if os.path.exists(task_dir):
            try:
                shutil.rmtree(task_dir)
            except:
                pass
        
        confirm_msg = await message.reply_text(f"❌ <b>Cancelled:</b> <i>{filename_short}</i>")
        
        await asyncio.sleep(3)
        await confirm_msg.delete()
    
    except Exception as e:
        err_str = str(e)
        if "topics" in err_str or "No such file or directory" in err_str:
            logger.error(f"Ignored known error in process_now: {e}")
        else:
            logger.error(f"Error in process_now: {e}")
            await message.reply_text(f"❌ <b>Error:</b> <code>{err_str}</code>")
    
    finally:
        async with tasks_lock:
            if task_id in tasks:
                del tasks[task_id]
            if uid in user_tasks and task_id in user_tasks[uid]:
                user_tasks[uid].remove(task_id)
        
        if int(uid) != ADMIN_ID and success:
            add_conversion(uid, success)
        
        async with tasks_lock:
            remaining = [t for t in user_tasks.get(uid, []) if t in tasks and not tasks[t].cancelled]
        
        if not remaining:
            try:
                await status_msg.delete()
            except:
                pass
        else:
            await update_user_status(uid)
        
        if os.path.isdir(task_dir):
            try:
                shutil.rmtree(task_dir)
            except:
                pass

# ==================== START BOT ====================
async def main():
    await db.load()
    await bot.start()
    bot_me = await bot.get_me()
    print(f"🤖 Bot:       @{bot_me.username} ({bot_me.first_name})")
    print(f"🆔 Bot ID:    {bot_me.id}")
    print(f"👑 Admin ID:  {ADMIN_ID}")

    if premium_client:
        await premium_client.start()
        try:
            prem_me = await premium_client.get_me()
            uname = f"@{prem_me.username}" if prem_me.username else "(no username)"
            print(f"⭐ UserBot:   {uname} ({prem_me.first_name}) | Premium: {prem_me.is_premium}")
        except Exception:
            print("⭐ UserBot:   started (could not fetch info)")
    else:
        print("⚠️  UserBot:   not configured (max file size limited to 2GB)")

    print(f"📦 Version:   {VERSION}")
    print(f"💾 Workspace: {WORKSPACE}")
    print("=" * 50)
    print("✅ Bot is running. Press Ctrl+C to stop.")
    print("=" * 50)

    await idle()
    await bot.stop()
    if premium_client:
        await premium_client.stop()

if __name__ == "__main__":
    print("=" * 50)
    print(f"🚀 Starting {VERSION}...")
    print("=" * 50)
    bot.run(main())
