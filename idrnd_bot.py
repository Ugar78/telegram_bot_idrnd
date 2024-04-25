import logging
import os
import sqlite3
import sys

import face_recognition
from dotenv import load_dotenv
from pydub import AudioSegment
from telegram import Update
from telegram.ext import (CallbackContext, CommandHandler, Filters,
                          MessageHandler, Updater)

load_dotenv()

TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')

logging.basicConfig(
        format='%(asctime)s - %(levelname)s - %(message)s',
        level=logging.INFO,
        handlers=[
            logging.FileHandler('idrnd_bot.log'),
            logging.StreamHandler(sys.stdout)
        ]
    )


def check_tokens():
    '''Проверка доступности переменных окружения.'''
    tokens = {
        'telegram_token': TELEGRAM_TOKEN,
    }
    for key, value in tokens.items():
        if value is None:
            logging.critical(f'Отсутствует токен: {key}')
            raise SystemExit(f'Отсутствует токен: {key}')


def start(update, context):
    '''Обработка команды /start.'''
    start_message = (
            'Привет! Я бот, который сохраняет аудиосообщения и фотографии. '
            'Отправьте мне голосовое или фото. '
            'Фото будет сохранено, только если на нем обнаружены лица. '
            'Аудиосообщения будут сохранятся всегда. '
            'Чтобы получить сохраненные фото или аудио, '
            'используйте команды /get_audio или /get_photo.'
        ),
    context.bot.send_message(
        chat_id=update.effective_chat.id, text=start_message
    )


def save_audio(update, context):
    '''Сохранение аудиосообщения.'''
    user_name = update.message.from_user.first_name
    audio_file = update.message.voice.get_file()
    os.makedirs('audio_wav', exist_ok=True)
    os.makedirs('audio_ogg', exist_ok=True)
    audio_path = f'audio_ogg/audio_{user_name}_{audio_file.file_id}.ogg'
    audio_file.download(audio_path)

    conn = sqlite3.connect('audio_messages.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS audio_messages
             (user_id INTEGER, audio_path TEXT)''')
    c.execute(
        'INSERT INTO audio_messages VALUES (?, ?)',
        (user_name, audio_path)
    )
    conn.commit()
    conn.close()
    update.message.reply_text('Аудиозапись успешно сохранена в базе данных!')

    audio = AudioSegment.from_file(audio_path, format='ogg')
    audio = audio.set_frame_rate(16000)
    audio.export(
        f'audio_wav/audio_{user_name}_{audio_file.file_id}.wav', format='wav'
    )


def save_faces(update: Update, context: CallbackContext):
    '''Сохранение фото с лицами.'''
    user_name = update.message.from_user.first_name
    photo_file = context.bot.get_file(update.message.photo[-1].file_id)
    os.makedirs('photo', exist_ok=True)
    photo_path = f'photo/photo_{user_name}_{photo_file.file_id}.jpg'
    photo_file.download(photo_path)

    image = face_recognition.load_image_file(photo_path)
    face_locations = face_recognition.face_locations(image)

    if face_locations:
        os.rename(
            photo_path, f'photo/face_{user_name}_{photo_file.file_id}.jpg'
        )
        update.message.reply_text('Фото с лицами успешно сохранено!')
    else:
        os.remove(photo_path)
        update.message.reply_text(
            'На фото лица не обнаружены. Фото не было сохранено.'
        )


def get_audio(update: Update, context: CallbackContext):
    '''Получение сохраненных аудиофайлов.'''
    conn = sqlite3.connect('audio_messages.db')
    c = conn.cursor()
    c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='audio_messages'")
    table_exists = c.fetchone()

    if table_exists:
        try:
            c.execute('SELECT audio_path FROM audio_messages')
            audio_paths = c.fetchall()

            for audio_path in audio_paths:
                audio_file = open(audio_path[0], 'rb')
                context.bot.send_audio(
                    chat_id=update.effective_chat.id, audio=audio_file
                )
                audio_file.close()

        except FileNotFoundError:
            update.message.reply_text('Нет сохраненных аудиозаписей.')
    else:
        update.message.reply_text('Нет сохраненных аудиозаписей.')


def get_photo(update: Update, context: CallbackContext):
    '''Получение сохраненных фотографий.'''
    try:
        photo_files = [file for file in os.listdir('photo')]
        if photo_files:
            for photo_file in photo_files:
                context.bot.send_photo(
                    chat_id=update.message.chat_id, photo=open(
                        f'photo/{photo_file}', 'rb'
                    )
                )
        else:
            update.message.reply_text('Нет сохраненных фотографий.')
    except FileNotFoundError:
        update.message.reply_text('Нет сохраненных фотографий.')


def main():
    '''Основная функция для запуска бота.'''
    check_tokens()
    updater = Updater(token=TELEGRAM_TOKEN, use_context=True)
    dp = updater.dispatcher

    dp.add_handler(CommandHandler('start', start))
    dp.add_handler(CommandHandler('get_audio', get_audio))
    dp.add_handler(CommandHandler('get_photo', get_photo))

    dp.add_handler(MessageHandler(Filters.voice, save_audio))
    dp.add_handler(MessageHandler(Filters.photo, save_faces))

    updater.start_polling()
    updater.idle()


if __name__ == '__main__':
    main()
