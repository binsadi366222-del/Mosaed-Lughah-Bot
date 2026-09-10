import os
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
import logging
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
from google import genai
from google.genai import types

# 1. خادم ويب مصغر لإبقاء منصة Render متصلة بنجاح
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is running successfully!")

def start_health_check_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), HealthCheckHandler)
    server.serve_forever()

# 2. قراءة المفاتيح من البيئة
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
    await update.message.reply_text(
        "أهلاً بك! أنا **المعلم مساعد سعدي الذبياني** 📚🤖\n\n"
        "مستعد لمساعدتك في الإعراب، القواعد النحوية، البلاغة، وتصحيح الواجبات.\n"
        "أرسل سؤالك نصياً أو التقط صورة للواجب/الكتاب وسأشرحه لك!"
    )

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action='typing')
    
    try:
        response = client.models.generate_content(
            model="gemini-3.6-flash",
            contents=user_text,
            config={"system_instruction": SYSTEM_INSTRUCTION}
        )
        await update.message.reply_text(response.text)
    except Exception as e:
        print(f"Error: {e}")
        await update.message.reply_text("❌ حدث خطأ أثناء معالجة النص.")

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action='typing')
    
    try:
        photo_file = await update.message.photo[-1].get_file()
        image_bytes = await photo_file.download_as_bytearray()
        caption = update.message.caption or "اقرأ الأسئلة أو النصوص الموجودة في هذه الصورة واشرحها أو قم بإعرابها بوضوح."
        
        response = client.models.generate_content(
            model="gemini-3.6-flash",
            contents=[
                types.Part.from_bytes(data=bytes(image_bytes), mime_type="image/jpeg"),
                caption
            ],
            config={"system_instruction": SYSTEM_INSTRUCTION}
        )
        await update.message.reply_text(response.text)
    except Exception as e:
        print(f"Error: {e}")
        await update.message.reply_text("❌ تعذر تحليل الصورة، يرجى التأكد من ووضوح الخط وإعادة المحاولة.")

if __name__ == "__main__":
    # تشغيل خادم الويب في الخلفية للرد على فحص Render
    threading.Thread(target=start_health_check_server, daemon=True).start()
    
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    
    print("🤖 البوت يعمل بنجاح على Render...")
    app.run_polling()