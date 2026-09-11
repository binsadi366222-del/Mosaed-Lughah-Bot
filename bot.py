import os
import logging
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from google import genai
from google.genai import types

# 1. إعداد السجلات (Logging)
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# 2. خادم صحة الخدمة لإرضاء فحوصات Render و UptimeRobot
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/plain; charset=utf-8')
        self.end_headers()
        self.wfile.write(b"OK")
        
    def do_HEAD(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/plain; charset=utf-8')
        self.end_headers()

    def log_message(self, format, *args):
        return  # إخفاء سجلات طلبات الفحص الدورية لعدم ملء الشاشة

def start_health_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(('0.0.0.0', port), HealthCheckHandler)
    server.serve_forever()

# 3. تهيئة عميل Gemini
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    logger.error("لم يتم العثور على GEMINI_API_KEY في متغيرات البيئة!")

ai_client = genai.Client(api_key=GEMINI_API_KEY) if GEMINI_API_KEY else None

# تغيير النموذج إلى 2.0 للحصول على الحصة المجانية الأكبر (1500 طلب يومياً)
MODEL_ID = 'gemini-2.0-flash'

SYSTEM_INSTRUCTION = """أنت المعلم مساعد سعدي الذبياني، خبير متقدم ومتقن للغة العربية، النحو، الصرف، والإعراب.
إجاباتك دقيقة، مبسطة، وتعتمد على القواعد النحوية المعتمدة، مع الشرح والتوضيح بأسلوب تعليمي راقٍ."""

# 4. معالجات تليجرام
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome_text = (
        "أهلاً بك! أنا **المعلم مساعد سعدي الذبياني** 🌿\n\n"
        "مستعد لمساعدتك في النحو، الإعراب، البلاغة، وتحليل النصوص والمسائل اللغوية.\n"
        "يمكنك كتابة سؤالك مباشرة أو إرسال صورة تحتوي على نص إعرابي أو مسألة لغوية!"
    )
    await update.message.reply_text(welcome_text, parse_mode='Markdown')

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text
    logger.info(f"استلام نص من المستخدم: {user_text}")

    if not ai_client:
        await update.message.reply_text("❌ لم يتم ضبط مفتاح GEMINI_API_KEY في السيرفر.")
        return

    try:
        response = ai_client.models.generate_content(
            model=MODEL_ID,
            contents=user_text,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_INSTRUCTION
            )
        )
        await update.message.reply_text(response.text)
    except Exception as e:
        logger.error(f"خطأ في Gemini النصي: {e}")
        await update.message.reply_text("❌ حدث خطأ أثناء معالجة النص، يرجى المحاولة لاحقاً.")

async def handle_image(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info("استلام صورة من المستخدم")

    if not ai_client:
        await update.message.reply_text("❌ لم يتم ضبط مفتاح GEMINI_API_KEY في السيرفر.")
        return

    try:
        photo_file = await update.message.photo[-1].get_file()
        image_bytes = await photo_file.download_as_bytearray()

        caption = update.message.caption or "اقرأ المحتوى الموجود في هذه الصورة وأعربه أو اشرحه بدقة لغوية."

        part = types.Part.from_bytes(
            data=bytes(image_bytes),
            mime_type='image/jpeg'
        )

        response = ai_client.models.generate_content(
            model=MODEL_ID,
            contents=[part, caption],
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_INSTRUCTION
            )
        )
        await update.message.reply_text(response.text)
    except Exception as e:
        logger.error(f"خطأ في Gemini الصوري: {e}")
        await update.message.reply_text("❌ حدث خطأ أثناء معالجة الصورة، يرجى المحاولة لاحقاً.")

# 5. نقطة التشغيل الرئيسية
def main():
    # تشغيل سيرفر الفحص الصحي في خيط مستقل
    health_thread = threading.Thread(target=start_health_server, daemon=True)
    health_thread.start()
    logger.info("تم تشغيل سيرفر الصحة الخاص بـ Render.")

    token = os.environ.get("TELEGRAM_TOKEN")
    if not token:
        logger.error("لم يتم العثور على TELEGRAM_TOKEN في متغيرات البيئة!")
        return

    app = Application.builder().token(token).build()

    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(MessageHandler(filters.PHOTO, handle_image))

    logger.info("🤖 البوت يعمل بنجاح ومستعد لاستقبال الرسائل...")
    app.run_polling()

if __name__ == '__main__':
    main()
