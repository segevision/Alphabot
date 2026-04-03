import logging
from collections import defaultdict
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, LabeledPrice
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    PreCheckoutQueryHandler,
    ContextTypes,
    filters,
)
import anthropic

# ─────────────────────────────────────────────
TOKEN = "8768250568:AAFVkG1iDLI5I47kfxAjyer9B7C5sLMHaZU"
ANTHROPIC_API_KEY = "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"
# ─────────────────────────────────────────────

logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

claude_client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

def is_premium(user_id: int) -> bool:
    return True  # כל המשתמשים פרימיום

# ─── State per user ───────────────────────────
def default_state():
    return {
        "mode": "flirt",
        "action": None,
        "history": [],
        "last_her_message": None,
    }

user_state: dict = defaultdict(default_state)

# ─── Mode config ──────────────────────────────
MODE_DATA = {
    "flirt": {"label": "😏 פלרטטני", "desc": "שובב, מושך, קצת עוקצני",   "premium": False},
    "funny": {"label": "😂 מצחיק",   "desc": "הומוריסטי, קליל, wit ישראלי", "premium": False},
    "deep":  {"label": "🧠 עמוק",    "desc": "רגשי, חכם, יוצר חיבור אמיתי", "premium": False},
}

# ─── System Prompts ───────────────────────────
BASE = """
כללים:
- תמיד בעברית, סלנג ישראלי טבעי.
- מקסימום 1-2 משפטים קצרים. כמו הודעת וואטסאפ/טינדר אמיתית.
- לא להזכיר AI. לענות כמוהו בלבד.
- לא סימני קריאה מיותרים. לא להתחיל בשמה.
"""

SYSTEM_PROMPTS = {
    "flirt": f"""אתה כותב הודעות לאישה עבור גבר ישראלי — בטוח, שובב, מושך.
- יוצר מתח ומשיכה. לא ישיר מדי אבל ברור שמתעניין.
- משתמש בדחיפה-משיכה: "את צרות" / "עוד לא החלטתי אם אני אוהב אותך"
- לא מתחנן. אם היא קרה — הוא נשאר רגוע ובטוח.
{BASE}""",

    "funny": f"""אתה כותב הודעות לאישה עבור גבר ישראלי — מצחיק, קליל, עוקצני.
- הומור ישראלי אמיתי — לא בדיחות, אלא wit.
- גורם לה לצחוק בלי לנסות יותר מדי.
{BASE}""",

    "deep": f"""אתה כותב הודעות לאישה עבור גבר ישראלי — עמוק, חכם, מחובר.
- שואל שאלות שגורמות לה לחשוב.
- יוצר חיבור אמיתי. קצר אבל כל מילה בחרה בכוונה.
- רגשי אבל לא נחלש.
{BASE}""",
}

ANALYZE_SYSTEM = """אתה מנתח הודעות מנשים עבור גבר ישראלי. היה ישיר וחד.
החזר תמיד בדיוק בפורמט הזה:

🎯 רמת עניין: [גבוהה / בינונית / נמוכה]
💭 מה היא משדרת: [משפט אחד קצר]
⚡ מה לענות: [טיפ קצר]
💬 דוגמה: [תשובה קצרה לדוגמה]"""

INITIATIVE_SYSTEM = """אתה מייצר הודעה יוזמת לאישה עבור גבר ישראלי — הודעה שמקדמת את השיחה קדימה.
- קצרה, טבעית, לא desperate.
- תן 3 אופציות שונות ממוספרות.
- בעברית, סלנג ישראלי."""

OPENERS_SYSTEM = """אתה מייצר פתיחות לשיחה עם אישה עבור גבר ישראלי.
תן 4 פתיחות לפי הסיטואציות הבאות:
1. 🔥 טינדר/אפליקציה – פתיחה שמבדילה אותו מכולם
2. 📱 אחרי חילוף מספרים – פתיחה טבעית
3. 😴 היא לא ענתה יומיים – re-engage קצר
4. 🎯 אחרי דייט ראשון – המשך טבעי

כל פתיחה: שורה אחת, עברית, טבעית ובטוחה בעצמה."""


# ─── Keyboards ────────────────────────────────
def main_menu_keyboard(mode: str, user_id: int) -> InlineKeyboardMarkup:
    mode_label = MODE_DATA[mode]["label"]
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("💬 צור תשובה", callback_data="action_reply"),
            InlineKeyboardButton("📊 ניתוח הודעה", callback_data="action_analyze"),
        ],
        [
            InlineKeyboardButton("🔥 מה לשלוח עכשיו", callback_data="action_initiative"),
            InlineKeyboardButton("📚 פתיחות מוכנות", callback_data="action_openers"),
        ],
        [
            InlineKeyboardButton(f"מצב: {mode_label}", callback_data="action_mode"),
        ],
    ])


def mode_select_keyboard(user_id: int) -> InlineKeyboardMarkup:
    buttons = []
    for key, data in MODE_DATA.items():
        buttons.append([InlineKeyboardButton(f"{data['label']}", callback_data=f"set_mode_{key}")])
    buttons.append([InlineKeyboardButton("🔙 חזרה לתפריט", callback_data="main_menu")])
    return InlineKeyboardMarkup(buttons)


def back_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔙 תפריט ראשי", callback_data="main_menu")]
    ])


def after_reply_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🔄 תשובה אחרת", callback_data="action_retry"),
            InlineKeyboardButton("🔙 תפריט ראשי", callback_data="main_menu"),
        ]
    ])


def buy_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(f"⭐ רכוש פרימיום — {STARS_PRICE} כוכבים", callback_data="confirm_buy")],
        [InlineKeyboardButton("🔙 חזרה", callback_data="main_menu")],
    ])


# ─── Helper: send main menu ───────────────────
async def send_main_menu(update: Update, mode: str, user_id: int, edit: bool = False):
    text = (
        f"🐺 *Alpha AI Wingman*\n\n"
        f"מצב: {MODE_DATA[mode]['label']} — _{MODE_DATA[mode]['desc']}_\n\n"
        "בחר פעולה:"
    )
    keyboard = main_menu_keyboard(mode, user_id)

    if edit and update.callback_query:
        await update.callback_query.edit_message_text(
            text, reply_markup=keyboard, parse_mode="Markdown"
        )
    else:
        msg = update.message or update.callback_query.message
        await msg.reply_text(text, reply_markup=keyboard, parse_mode="Markdown")


# ─── /start ──────────────────────────────────
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_state[user_id] = default_state()
    await send_main_menu(update, "flirt", user_id, edit=False)




# ─── Callback buttons ────────────────────────
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    state = user_state[user_id]
    data = query.data

    # ── Main menu ──
    if data == "main_menu":
        state["action"] = None
        await send_main_menu(update, state["mode"], user_id, edit=True)
        return


    # ── Mode selection screen ──
    if data == "action_mode":
        await query.edit_message_text(
            "😈 *בחר מצב:*\nהמצב משפיע על סגנון כל התשובות.",
            reply_markup=mode_select_keyboard(user_id),
            parse_mode="Markdown",
        )
        return

    # ── Set mode ──
    if data.startswith("set_mode_"):
        mode = data.replace("set_mode_", "")
        if MODE_DATA[mode]["premium"] and not is_premium(user_id):
            await query.answer("🔒 המצב הזה דורש פרימיום. שלח /buy", show_alert=True)
            return
        state["mode"] = mode
        state["action"] = None
        state["history"] = []
        await send_main_menu(update, mode, user_id, edit=True)
        return

    # ── Create reply (free) ──
    if data == "action_reply":
        state["action"] = "waiting_reply"
        await query.edit_message_text(
            "💬 *צור תשובה*\n\nהדבק את ההודעה שהיא שלחה לך 👇",
            reply_markup=back_keyboard(),
            parse_mode="Markdown",
        )
        return

    # ── Analyze (free) ──
    if data == "action_analyze":
        state["action"] = "waiting_analyze"
        await query.edit_message_text(
            "📊 *ניתוח הודעה*\n\nשלח לי את ההודעה שלה ואני אנתח אותה 🔍",
            reply_markup=back_keyboard(),
            parse_mode="Markdown",
        )
        return

    # ── Initiative (premium) ──
    if data == "action_initiative":
        if not is_premium(user_id):
            await query.answer("🔒 מה לשלוח עכשיו זמין לפרימיום בלבד. שלח /buy", show_alert=True)
            return
        state["action"] = "waiting_initiative"
        await query.edit_message_text(
            "🔥 *מה לשלוח עכשיו*\n\nתאר בקצרה איפה אתם בשיחה (או שלח ״כלום״ לאפשרויות כלליות):",
            reply_markup=back_keyboard(),
            parse_mode="Markdown",
        )
        return

    # ── Openers (premium) ──
    if data == "action_openers":
        if not is_premium(user_id):
            await query.answer("🔒 פתיחות מוכנות זמין לפרימיום בלבד. שלח /buy", show_alert=True)
            return
        await query.edit_message_text("📚 מייצר פתיחות...", reply_markup=None)
        await context.bot.send_chat_action(chat_id=query.message.chat_id, action="typing")
        result = await call_claude(OPENERS_SYSTEM, [{"role": "user", "content": "תן לי 4 פתיחות"}], max_tokens=350)
        await query.edit_message_text(
            f"📚 *פתיחות מוכנות:*\n\n{result}",
            reply_markup=back_keyboard(),
            parse_mode="Markdown",
        )
        return

    # ── Retry ──
    if data == "action_retry":
        history = state["history"]
        mode = state["mode"]
        if not history:
            await query.edit_message_text("אין הודעה לנסות שוב.", reply_markup=main_menu_keyboard(mode, user_id))
            return
        if history[-1]["role"] == "assistant":
            history.pop()
        await query.edit_message_text("🔄 מייצר תשובה אחרת...", reply_markup=None)
        await context.bot.send_chat_action(chat_id=query.message.chat_id, action="typing")
        reply = await call_claude(SYSTEM_PROMPTS[mode], history, max_tokens=150)
        history.append({"role": "assistant", "content": reply})
        await query.edit_message_text(
            f"🔄 *תשובה חלופית:*\n\n{reply}",
            reply_markup=after_reply_keyboard(),
            parse_mode="Markdown",
        )
        return


# ─── Message handler ─────────────────────────
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    state = user_state[user_id]
    action = state.get("action")
    text = update.message.text

    if not action:
        await send_main_menu(update, state["mode"], user_id, edit=False)
        return

    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")

    # ── Create reply ──
    if action == "waiting_reply":
        mode = state["mode"]
        history = state["history"]
        history.append({"role": "user", "content": text})
        if len(history) > 20:
            state["history"] = history[-20:]
            history = state["history"]
        reply = await call_claude(SYSTEM_PROMPTS[mode], history, max_tokens=150)
        history.append({"role": "assistant", "content": reply})
        state["last_her_message"] = text
        await update.message.reply_text(
            f"💬 *התשובה שלך:*\n\n{reply}",
            reply_markup=after_reply_keyboard(),
            parse_mode="Markdown",
        )
        return

    # ── Analyze ──
    if action == "waiting_analyze":
        result = await call_claude(
            ANALYZE_SYSTEM,
            [{"role": "user", "content": f'ההודעה שלה: "{text}"'}],
            max_tokens=300,
        )
        state["action"] = None
        await update.message.reply_text(
            f"📊 *ניתוח ההודעה:*\n\n{result}",
            reply_markup=back_keyboard(),
            parse_mode="Markdown",
        )
        return

    # ── Initiative ──
    if action == "waiting_initiative":
        context_text = text if text.strip() != "כלום" else "שיחה כללית, אין הקשר מיוחד"
        result = await call_claude(
            INITIATIVE_SYSTEM,
            [{"role": "user", "content": f"הקשר השיחה: {context_text}"}],
            max_tokens=250,
        )
        state["action"] = None
        await update.message.reply_text(
            f"🔥 *אפשרויות לשלוח עכשיו:*\n\n{result}",
            reply_markup=back_keyboard(),
            parse_mode="Markdown",
        )
        return


# ─── Claude API call ─────────────────────────
async def call_claude(system: str, messages: list, max_tokens: int = 150) -> str:
    try:
        response = claude_client.messages.create(
            model="claude-opus-4-6",
            max_tokens=max_tokens,
            system=system,
            messages=messages,
        )
        return response.content[0].text.strip()
    except anthropic.AuthenticationError:
        return "❌ בעיה עם מפתח ה-API."
    except Exception as e:
        logging.error(f"Claude error: {e}")
        return "משהו השתבש, נסה שוב."


# ─── Main ─────────────────────────────────────
if __name__ == "__main__":
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("✅ Alpha AI Wingman פועל 🐺")
    app.run_polling()
