import logging
import openai
import os
import sys
import asyncio
import sqlite3
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters

# Константы
CHANNEL_ID = ''  # ID канала, куда бот отправляет ответы
TOKEN = ''  #@Melict_bot 
assistantId=''  # @Melict_bot
OPENAI_API_KEY = '' #@Melict_bot


# Настройка логирования
# Определение числового значения для нового уровня
NOTICE_LEVEL_NUM = 35
# Регистрация нового уровня
logging.addLevelName(NOTICE_LEVEL_NUM, "NOTICE")
def notice(self, message, *args, **kwargs):
    if self.isEnabledFor(NOTICE_LEVEL_NUM):
        self._log(NOTICE_LEVEL_NUM, message, args, **kwargs)
# Добавление метода notice к классу Logger
logging.Logger.notice = notice
logging.basicConfig(level=logging.WARNING, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    filename='bot_log.log', filemode='a')
logger = logging.getLogger(__name__)
logger.setLevel(logging.WARNING)
logger.notice("Запуск скрипта")

os.environ['OPENAI_API_KEY'] = OPENAI_API_KEY  

def init_db():
    """Создает таблицу в базе данных, если она не существует."""
    conn = sqlite3.connect('threads.db')
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS threads (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );
    ''')
    conn.commit()
    conn.close()

def load_threads():
    """Загружает данные из базы данных в словарь."""
    global threads
    conn = sqlite3.connect('threads.db')
    c = conn.cursor()
    c.execute('SELECT key, value FROM threads')
    rows = c.fetchall()
    threads = {key: value for key, value in rows}
    conn.close()

def save_thread_to_db(key, value):
    """Обновляет или вставляет пару ключ-значение в базу данных."""
    conn = sqlite3.connect('threads.db')
    c = conn.cursor()
    c.execute('INSERT OR REPLACE INTO threads (key, value) VALUES (?, ?)', (key, value))
    conn.commit()
    conn.close()

# Словарь для хранения ID тредов
threads = {}
# Инициализация базы данных и загрузка данных в threads 
init_db()
load_threads()



# Семафор для ограничения одновременных запросов
semaphore = asyncio.Semaphore(1)

def error_handler(update, context):
    logger.error(f"Ошибка вызвана исключением: {context.error}")


def read_instructions(file_name):
    try:
        with open(file_name, 'r', encoding='utf-8') as file:
            return file.read().strip()
    except FileNotFoundError:
        logger.error("Файл инструкций не найден.")
        return "Вы модератор"

#instructions = read_instructions("chatgpt_instructions.txt")
client = openai.OpenAI()
#assistant = client.beta.assistants.create(
#    name="Math Tutor",
#    instructions=instructions,
#    tools=[{"type": "code_interpreter"}],
#    model="gpt-4-turbo-preview",
#)

async def start(update: Update, context):
    #await update.message.reply_text('Привет! Я готов помочь вам с математикой.')
    logger.notice("Бот запущен")

async def handle_message(update: Update, context):
    global threads    
    #new_instructions = read_instructions("chatgpt_instructions.txt")
    #if instructions != new_instructions:
    #    logger.notice("Инструкции изменились, перезапуск бота.")
    #    os.execv(sys.executable, ['python'] + sys.argv)

    await semaphore.acquire()  # Запрашиваем ресурс
    try:
        message = update.message if update.message else update.channel_post
        if not message or not message.text:
            logger.error("Получено сообщение без текста.")
            return
        chat = update.effective_chat

        logger.notice(f"\n{message}\n")
        send_message = message.text
        if message and message.from_user:
            user_id = message.from_user.id
            send_message = f"{user_id} | {message.text}"
            logger.notice(f"send message = {send_message}")

        else:
            logger.error("сообщения без user id")
            
        chatId= str(chat.id)
        # Проверяем, есть ли уже тред для этого чата
        if chatId not in threads:
            thread = client.beta.threads.create()
            threads[chatId] = thread.id
            save_thread_to_db(chatId, thread.id)
        threadId = threads[chatId]
        logger.notice(f"chat Id = {chatId} ,  threadId = {threadId}")
        
               

        client.beta.threads.messages.create(thread_id=threadId, role="user", content=send_message)
        run = client.beta.threads.runs.create_and_poll(thread_id=threadId, assistant_id=assistantId)

        if run.status == 'completed':
            messages = client.beta.threads.messages.list(thread_id=threadId).data
            assistant_messages = [msg for msg in messages if msg.role == 'assistant']
            if assistant_messages:
                # Получаем первое сообщение ассистента
                response_content = ' '.join(content.text.value for content in assistant_messages[0].content)
                logger.notice(assistant_messages[0])
            else:
                response_content = "Извините, не могу обработать запрос. Нет сообщений от ассистента."

        else:
            response_content = f"Статус выполнения: {run.status}"

        # Отправка ответа и ссылки на сообщение в канал

        # Генерация ссылки на сообщение
        
        message_id = message.message_id
        if chat.username:
            link = f"https://t.me/{chat.username}/{message_id}"
        else:
            link = f"https://t.me/c/{abs(chat.id)}/{message_id}"

        #message_link = f"https://t.me/{message.chat.username}/{message.message_id}"
        #await context.bot.send_message(chat_id=CHANNEL_ID, text=response_content)
        #удаляем пробелы
        response_content = response_content.rstrip()
        if response_content.lower() != 'ok':
            # Здесь указывается код, который выполнится, если response_content не равно 'Ok'
            await context.bot.send_message(chat_id=CHANNEL_ID, text=f"{message.text}\n{link}\n—\n{response_content}")
    finally:
        semaphore.release()  # Освобождаем ресурс после завершения обработки

def main():
    application = Application.builder().token(TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_error_handler(error_handler)
    application.run_polling()

if __name__ == '__main__':
    main()
