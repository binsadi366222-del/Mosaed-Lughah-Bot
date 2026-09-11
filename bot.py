import os
import threading
import logging
from http.server import HTTPServer, BaseHTTPRequestHandler
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
from google import genai
from google.genai import types

# 1. تفعيل تسجيل الأخطاء لرؤيتها بوضوح في سجلات Render
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# 2. خادم فحص الصحة لمنصة Render
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"OK")

def start_port():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(("0.0.0.0", port), HealthCheckHandler)
    server.serve_forever()

threading.Thread(target=start_port, daemon=True).start()

# 3. إعداد مفاتيح الاتصال
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

client = genai.Client(api_key=GEMINI_API_KEY)

SYSTEM_INSTRUCTION = """
أنت "المعلم مساعد سعدي الذبياني"، معلم وخبير متخصص في علوم اللغة العربية والمناهج الدراسية.
وظيفتك:
1. الإجابة عن أسئلة الطلاب في النحو، الصرف، الإعراب، البلاغة، والإملاء بأسلوب مبسط ومشجع.
2. عند تقديم الإعراب: اشرح الموقع الإعرابي والعلامات بالتفصيل وخطوة بخطوة.
3. عند إرسال صورة واجب أو صفحة كتاب: اقرأ النص والأسئلة الموجودة فيها بوضوح، وقدم الشرح والإعراب المطلوب بشكل منظم.
"""

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info(f"استلام أمر start من المستخدم: {update.effective_user.id}")
    await update.message.reply_text(
        "أهلاً بك! أنا **المعلم مساعد سعدي الذبياني** 📚🤖\n\n"
        "مستعد لمساعدتك في الإعراب، القواعد النحوية، البلاغة، وتصحيح الواجبات.\n"
        "أرسل سؤالك نصياً أو التقط صورة للواجب/الكتاب وسأشرحه لك!"
    )

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text
    logger.info(f"استلام نص من المستخدم: {user_text}")
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action='typing')
    
    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=user_text,
            config=types.GenerateContentConfig(system_instruction=SYSTEM_INSTRUCTION)
        )
        await update.message.reply_text(response.text)
    except Exception as e:
        logger.error(f"خطأ في Gemini النصي: {e}")
        await update.message.reply_text("❌ حدث خطأ أثناء معالجة النص، يرجى المحاولة لاحقاً.")

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info("استلام صورة من المستخدم")
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action='typing')
    
    try:
        photo_file = await update.message.photo[-1].get_file()
        image_bytes = await photo_file.download_as_bytearray()
        caption = update.message.caption or "اقرأ الأسئلة أو النصوص الموجودة في هذه الصورة واشرحها أو قم بإعرابها بوضوح."
        
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=[
                types.Part.from_bytes(data=bytes(image_bytes), mime_type="image/jpeg"),
                caption
            ],
            config=types.GenerateContentConfig(system_instruction=SYSTEM_INSTRUCTION)
        )
        await update.message.reply_text(response.text)
    except Exception as e:
        logger.error(f"خطأ في تحليل الصورة: {e}")
        await update.message.reply_text("❌ تعذر تحليل الصورة، يرجى التأكد من وضوح الخط وإعادة المحاولة.")

if __name__ == "__main__":
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    
    logger.info("🤖 البوت يعمل بنجاح ومستعد لاستقبال الرسائل...")
    app.run_polling(drop_pending_updates=True)
