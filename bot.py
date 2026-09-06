import os
import json
import hmac
import hashlib
import sqlite3
import threading
from urllib.parse import parse_qsl
from flask import Flask, request, jsonify, Response
from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from telegram.ext import ApplicationBuilder, MessageHandler, CommandHandler, CallbackQueryHandler, ContextTypes, filters

BOT_TOKEN = "8676656976:AAHSxTVOlapIL0l1Sz--HidQT-SOZaNI-_U"
ADMIN_ID = 5967757528
AUTO_REPLY_TEXT = "سلام الان آنلاین نیستم آنلاین شدم جواب میدم ممنون از اینکه صبر می‌کنی ❤️"
WEBAPP_URL = "https://support-bot-production-c8c9.up.railway.app/webapp"

conn = sqlite3.connect("messages.db", check_same_thread=False)
cur = conn.cursor()
cur.execute("""
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    business_account_name TEXT,
    business_connection_id TEXT,
    sender_name TEXT,
    sender_chat_id INTEGER,
    direction TEXT,
    text TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
)
""")
conn.commit()

# ---------------- Telegram Bot ----------------

PANEL_KEYBOARD = ReplyKeyboardMarkup([["پنل مدیریت"]], resize_keyboard=True)

async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id == ADMIN_ID:
        await update.message.reply_text("خوش اومدی 👋", reply_markup=PANEL_KEYBOARD)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.business_message:
        bm = update.business_message
        sender = bm.from_user
        sender_name = f"{sender.first_name or ''} {sender.last_name or ''}".strip()
        conn_info = await context.bot.get_business_connection(bm.business_connection_id)
        account_name = f"{conn_info.user.first_name or ''} {conn_info.user.last_name or ''}".strip()

        cur.execute(
            "INSERT INTO messages (business_account_name, business_connection_id, sender_name, sender_chat_id, direction, text) VALUES (?,?,?,?,?,?)",
            (account_name, bm.business_connection_id, sender_name, bm.chat.id, "in", bm.text or "")
        )
        conn.commit()

        await context.bot.send_message(
            chat_id=bm.chat.id,
            text=AUTO_REPLY_TEXT,
            business_connection_id=bm.business_connection_id
        )

        cur.execute(
            "INSERT INTO messages (business_account_name, business_connection_id, sender_name, sender_chat_id, direction, text) VALUES (?,?,?,?,?,?)",
            (account_name, bm.business_connection_id, sender_name, bm.chat.id, "out", AUTO_REPLY_TEXT)
        )
        conn.commit()
        return

    if update.message and update.effective_user.id == ADMIN_ID:
        text = update.message.text
        if text == "پنل مدیریت":
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("🖥 باز کردن مینی اپ", web_app=WebAppInfo(url=WEBAPP_URL))],
                [InlineKeyboardButton("✏️ تغییر متن پاسخ خودکار", callback_data="edit_reply")]
            ])
            await update.message.reply_text("منو:", reply_markup=keyboard)
            return

    if update.message:
        await update.message.reply_text(AUTO_REPLY_TEXT)

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query.from_user.id != ADMIN_ID:
        return
    await query.answer()
    if query.data == "edit_reply":
        await query.message.reply_text("برای تغییر متن پاسخ خودکار دستور زیر رو بفرست:\n/setreply متن جدید")

async def setreply_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global AUTO_REPLY_TEXT
    if update.effective_user.id != ADMIN_ID:
        return
    new_text = update.message.text.replace("/setreply", "", 1).strip()
    if not new_text:
        await update.message.reply_text("بعد از دستور، متن جدید رو بنویس.")
        return
    AUTO_REPLY_TEXT = new_text
    await update.message.reply_text("متن پاسخ خودکار عوض شد ✅")

telegram_app = ApplicationBuilder().token(BOT_TOKEN).build()

# ---------------- Flask Web App ----------------

flask_app = Flask(__name__)

def validate_init_data(init_data):
    try:
        parsed = dict(parse_qsl(init_data))
        received_hash = parsed.pop("hash", None)
        data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(parsed.items()))
        secret_key = hmac.new(b"WebAppData", BOT_TOKEN.encode(), hashlib.sha256).digest()
        computed_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
        if computed_hash != received_hash:
            return None
        user = json.loads(parsed.get("user", "{}"))
        return user
    except Exception:
        return None

def require_admin(data):
    user = validate_init_data(data.get("initData", ""))
    return user and user.get("id") == ADMIN_ID

HTML_PAGE = """
<!DOCTYPE html>
<html lang="fa" dir="rtl">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<script src="https://telegram.org/js/telegram-web-app.js"></script>
<style>
body { font-family: sans-serif; margin: 0; background: #17212b; color: #fff; }
#users { padding: 10px; }
.user-item { padding: 12px; margin-bottom: 8px; background: #232e3c; border-radius: 10px; cursor: pointer; }
.user-item b { display: block; }
.user-item span { font-size: 12px; color: #aaa; }
#chat { display: none; flex-direction: column; height: 100vh; }
#chatHeader { padding: 12px; background: #232e3c; display:flex; align-items:center; gap:10px; }
#chatHeader button { background: none; border: none; color: #fff; font-size: 18px; }
#messages { flex: 1; overflow-y: auto; padding: 10px; display: flex; flex-direction: column; gap: 6px; }
.bubble { max-width: 75%; padding: 8px 12px; border-radius: 12px; font-size: 14px; }
.bubble.in { align-self: flex-start; background: #232e3c; }
.bubble.out { align-self: flex-end; background: #3a6ea5; }
.bubble small { display:block; font-size:10px; color:#ccc; margin-top:4px; }
#sendRow { display: flex; padding: 10px; gap: 6px; background: #17212b; }
#sendRow input { flex: 1; padding: 10px; border-radius: 8px; border: none; }
#sendRow button { padding: 10px 16px; border-radius: 8px; border: none; background: #3a6ea5; color: #fff; }
</style>
</head>
<body>

<div id="users"></div>

<div id="chat">
  <div id="chatHeader">
    <button onclick="showUsers()">→ برگشت</button>
    <div id="chatTitle"></div>
  </div>
  <div id="messages"></div>
  <div id="sendRow">
    <input id="msgInput" placeholder="پیام..." />
    <button onclick="sendMsg()">ارسال</button>
  </div>
</div>

<script>
const tg = window.Telegram.WebApp;
tg.ready();
tg.expand();
const initData = tg.initData;
let currentChatId = null;

async function loadUsers() {
  const res = await fetch('/api/users', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({initData})
  });
  const data = await res.json();
  const container = document.getElementById('users');
  container.innerHTML = '';
  data.users.forEach(u => {
    const div = document.createElement('div');
    div.className = 'user-item';
    div.innerHTML = `<b>${u.sender_name} (ID: ${u.sender_chat_id})</b><span>${u.business_account_name} • ${u.count} پیام</span>`;
    div.onclick = () => openChat(u.sender_chat_id, u.sender_name);
    container.appendChild(div);
  });
}

async function openChat(chatId, name) {
  currentChatId = chatId;
  document.getElementById('users').style.display = 'none';
  document.getElementById('chat').style.display = 'flex';
  document.getElementById('chatTitle').innerText = name + ' (ID: ' + chatId + ')';
  await loadMessages();
}

function showUsers() {
  document.getElementById('chat').style.display = 'none';
  document.getElementById('users').style.display = 'block';
  loadUsers();
}

async function loadMessages() {
  const res = await fetch('/api/messages', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({initData, chat_id: currentChatId})
  });
  const data = await res.json();
  const box = document.getElementById('messages');
  box.innerHTML = '';
  data.messages.forEach(m => {
    const div = document.createElement('div');
    div.className = 'bubble ' + m.direction;
    div.innerHTML = m.text + '<small>' + m.created_at + '</small>';
    box.appendChild(div);
  });
  box.scrollTop = box.scrollHeight;
}

async function sendMsg() {
  const input = document.getElementById('msgInput');
  const text = input.value.trim();
  if (!text) return;
  await fetch('/api/send', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({initData, chat_id: currentChatId, text})
  });
  input.value = '';
  await loadMessages();
}

loadUsers();
</script>
</body>
</html>
"""

@flask_app.route("/webapp")
def webapp():
    return Response(HTML_PAGE, mimetype="text/html")

@flask_app.route("/api/users", methods=["POST"])
def api_users():
    data = request.get_json()
    if not require_admin(data):
        return jsonify({"error": "unauthorized"}), 403
    cur.execute("""
        SELECT sender_chat_id, sender_name, business_account_name, COUNT(*)
        FROM messages GROUP BY sender_chat_id ORDER BY MAX(id) DESC
    """)
    rows = cur.fetchall()
    users = [{"sender_chat_id": r[0], "sender_name": r[1], "business_account_name": r[2], "count": r[3]} for r in rows]
    return jsonify({"users": users})

@flask_app.route("/api/messages", methods=["POST"])
def api_messages():
    data = request.get_json()
    if not require_admin(data):
        return jsonify({"error": "unauthorized"}), 403
    chat_id = data.get("chat_id")
    cur.execute("""
        SELECT direction, text, created_at FROM messages
        WHERE sender_chat_id = ? ORDER BY id ASC
    """, (chat_id,))
    rows = cur.fetchall()
    messages = [{"direction": r[0], "text": r[1], "created_at": r[2]} for r in rows]
    return jsonify({"messages": messages})

@flask_app.route("/api/send", methods=["POST"])
def api_send():
    data = request.get_json()
    if not require_admin(data):
        return jsonify({"error": "unauthorized"}), 403
    chat_id = data.get("chat_id")
    text = data.get("text")

    cur.execute("""
        SELECT business_account_name, business_connection_id FROM messages
        WHERE sender_chat_id = ? AND direction = 'in' ORDER BY id DESC LIMIT 1
    """, (chat_id,))
    row = cur.fetchone()
    if not row:
        return jsonify({"error": "not found"}), 404
    account_name, business_connection_id = row

    import asyncio
    async def send():
        await telegram_app.bot.send_message(
            chat_id=chat_id, text=text, business_connection_id=business_connection_id
        )
    asyncio.run(send())

    cur.execute(
        "INSERT INTO messages (business_account_name, business_connection_id, sender_name, sender_chat_id, direction, text) VALUES (?,?,?,?,?,?)",
        (account_name, business_connection_id, "", chat_id, "out", text)
    )
    conn.commit()
    return jsonify({"ok": True})

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    flask_app.run(host="0.0.0.0", port=port)

if __name__ == "__main__":
    threading.Thread(target=run_flask, daemon=True).start()
    telegram_app.add_handler(CommandHandler("start", start_cmd))
    telegram_app.add_handler(CommandHandler("setreply", setreply_cmd))
    telegram_app.add_handler(CallbackQueryHandler(button_handler))
    telegram_app.add_handler(MessageHandler(filters.ALL, handle_message))
    telegram_app.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)
