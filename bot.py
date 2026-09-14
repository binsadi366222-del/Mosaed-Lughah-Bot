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

# 2. خادم فحص الصحة لإبقاء البوت مستيقظاً على Render و UptimeRobot
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
        return

def start_health_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(('0.0.0.0', port), HealthCheckHandler)
    server.serve_forever()

# 3. إدارة وتدوير مفاتيح API المتعددة
raw_keys = os.environ.get("GEMINI_API_KEY", "")
API_KEYS = [k.strip() for k in raw_keys.split(",") if k.strip()]
current_key_index = 0

def get_current_client():
    global current_key_index
    if not API_KEYS:
        return None
    return genai.Client(api_key=API_KEYS[current_key_index])

def switch_to_next_key():
    global current_key_index
    if len(API_KEYS) > 1:
        current_key_index = (current_key_index + 1) % len(API_KEYS)
        logger.info(f"تم الانتقال تلقائياً إلى المفتاح رقم: {current_key_index + 1}")
        return True
    return False

MODEL_ID = 'gemini-3.6-flash'
SYSTEM_INSTRUCTION = """أنت المعلم مساعد سعدي الذبياني، خبير متقدم ومتقن للغة العربية، النحو، الصرف، والإعراب.
إجاباتك دقيقة، مبسطة، وتعتمد على القواعد النحوية المعتمدة، مع الشرح والتوضيح بأسلوب تعليمي راقٍ."""

def generate_with_fallback(contents):
    """إرسال الطلب وتبديل المفتاح فوراً عند ظهور خطأ 429 (نفاذ الحصة)"""
    attempts = len(API_KEYS) if API_KEYS else 1
    for _ in range(attempts):
        client = get_current_client()
        if not client:
            return None, "مفاتيح GEMINI_API_KEY غير مهيأة في متغيرات البيئة."
        try:
            response = client.models.generate_content(
                model=MODEL_ID,
                contents=contents,
                config=types.GenerateContentConfig(system_instruction=SYSTEM_INSTRUCTION)
            )
            return response.text, None
        except Exception as e:
            err_str = str(e)
            logger.error(f"خطأ أثناء الاستدعاء: {err_str}")
            if "429" in err_str or "RESOURCE_EXHAUSTED" in err_str:
                if switch_to_next_key():
                    continue
            return None, err_str
    return None, "عذراً، تم استنفاد الحصة اليومية لجميع المفاتيح المسجلة حالياً."

# 4. معالجات رسائل تليجرام
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome_text = (
        "أهلاً بك! أنا **المعلم مساعد سعدي الذبياني** 🌿\n\n"
        "مستعد لمساعدتك في النحو، الإعراب، البلاغة، وتحليل النصوص والمسائل اللغوية.\n"
        "اكتب مسألتك النحوية مباشرة، أو أرسل صورة تحتوي على التدريب المطلوب!"
    )
    await update.message.reply_text(welcome_text, parse_mode='Markdown')

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text
    logger.info(f"استلام نص: {user_text}")

    reply, err = generate_with_fallback(user_text)
    if reply:
        await update.message.reply_text(reply)
    else:
        await update.message.reply_text("⏳ الخدمة تواجه ضغطاً مؤقتاً في الطلبات، يرجى إعادة المحاولة بعد قليل.")

async def handle_image(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info("استلام صورة")
    try:
        photo_file = await update.message.photo[-1].get_file()
        image_bytes = await photo_file.download_as_bytearray()
        caption = update.message.caption or "اقرأ ما في هذه الصورة وأعربه أو اشرحه لغوياً بدقة."

        part = types.Part.from_bytes(data=bytes(image_bytes), mime_type='image/jpeg')
        reply, err = generate_with_fallback([part, caption])

        if reply:
            await update.message.reply_text(reply)
        else:
            await update.message.reply_text("⏳ الخدمة تواجه ضغطاً مؤقتاً في الطلبات، يرجى إعادة المحاولة بعد قليل.")
    except Exception as e:
        logger.error(f"خطأ أثناء قراءة الصورة: {e}")
        await update.message.reply_text("❌ حدث خطأ أثناء معالجة الصورة.")

# 5. تشغيل التطبيق
def main():
    threading.Thread(target=start_health_server, daemon=True).start()
    logger.info("تم تشغيل سيرفر الصحة الداخلي بنجاح.")

    token = os.environ.get("TELEGRAM_TOKEN")
    if not token:
        logger.error("لم يتم العثور على TELEGRAM_TOKEN في متغيرات البيئة!")
        return

    app = Application.builder().token(token).build()
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(MessageHandler(filters.PHOTO, handle_image))

    logger.info("🤖 البوت يعمل بنظام تدوير المفاتيح ومستعد لاستقبال الرسائل...")
    app.run_polling()

if __name__ == '__main__':
    main()
