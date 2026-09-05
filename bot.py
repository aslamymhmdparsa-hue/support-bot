import sqlite3
from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ApplicationBuilder, MessageHandler, CommandHandler, CallbackQueryHandler, ContextTypes, filters

BOT_TOKEN = "8676656976:AAEVRS_30kIEGnP_D3bGgzieYIbUq_R3DOU"
ADMIN_ID = 5967757528
AUTO_REPLY_TEXT = "سلام الان آنلاین نیستم آنلاین شدم جواب میدم ممنون از اینکه صبر می‌کنی ❤️"

conn = sqlite3.connect("messages.db", check_same_thread=False)
cur = conn.cursor()
cur.execute("""
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    business_account_name TEXT,
    sender_name TEXT,
    sender_chat_id INTEGER,
    text TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
)
""")
conn.commit()

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
            "INSERT INTO messages (business_account_name, sender_name, sender_chat_id, text) VALUES (?, ?, ?, ?)",
            (account_name, sender_name, bm.chat.id, bm.text or "")
        )
        conn.commit()

        await context.bot.send_message(
            chat_id=bm.chat.id,
            text=AUTO_REPLY_TEXT,
            business_connection_id=bm.business_connection_id
        )
        return

    if update.message and update.effective_user.id == ADMIN_ID:
        text = update.message.text
        if text == "پنل مدیریت":
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("📥 پیام‌ها بر اساس کاربر", callback_data="list_users")],
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

    if query.data == "list_users":
        cur.execute("""
            SELECT sender_chat_id, sender_name, business_account_name, COUNT(*)
            FROM messages
            GROUP BY sender_chat_id
            ORDER BY MAX(id) DESC
        """)
        rows = cur.fetchall()
        if not rows:
            await query.message.reply_text("هنوز پیامی ثبت نشده.")
            return
        buttons = []
        for chat_id, sender_name, account_name, count in rows:
            label = f"{sender_name} → {account_name} ({count})"
            buttons.append([InlineKeyboardButton(label, callback_data=f"user_{chat_id}")])
        await query.message.reply_text("کاربرا:", reply_markup=InlineKeyboardMarkup(buttons))

    elif query.data.startswith("user_"):
        chat_id = int(query.data.replace("user_", ""))
        cur.execute("""
            SELECT sender_name, text, created_at
            FROM messages
            WHERE sender_chat_id = ?
            ORDER BY id ASC
        """, (chat_id,))
        rows = cur.fetchall()
        if not rows:
            await query.message.reply_text("پیامی پیدا نشد.")
            return
        reply = f"💬 مکالمه با {rows[0][0]}:\n\n"
        for sender, text, ts in rows:
            reply += f"🕒 {ts}\n{text}\n\n"
        await query.message.reply_text(reply)

    elif query.data == "edit_reply":
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

if __name__ == "__main__":
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(CommandHandler("setreply", setreply_cmd))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.ALL, handle_message))
    app.run_polling(allowed_updates=Update.ALL_TYPES)
