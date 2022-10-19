import logging
import os

import time
import requests

from telegram import Bot

from dotenv import load_dotenv

from exceptions import (
    ApiEmptyDataException,
    StatusException,
    ApiDataException,
    ApiTokenException,
    HomeworkStatusError,
    NotTokenException
)

load_dotenv()


PRACTICUM_TOKEN = os.getenv('TOKEN')
TELEGRAM_TOKEN = os.getenv('TOKENBOT')
TELEGRAM_CHAT_ID = os.getenv('CHAT_ID')

logging.basicConfig(
    format='%(asctime)s - %(levelname)s - %(message)s',
    level=logging.INFO)


RETRY_TIME = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_STATUSES = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


def send_message(bot, message):
    """Отправляет сообщение в телеграм бот."""
    try:
        logging.info(
            f'Отправка сообщения в телеграм:{TELEGRAM_CHAT_ID}:\n{message}'
        )
        bot.send_message(TELEGRAM_CHAT_ID, message)
    except Exception:
        logging.error('Сбой при отправке сообщения в телеграм бот')
    else:
        logging.info(f'Успешно отправлен:{TELEGRAM_CHAT_ID}:\n{message}')


def get_api_answer(current_timestamp):
    """Делает запрос к единственному эндпоинту API-сервиса."""
    timestamp = current_timestamp or int(time.time())
    params = {'from_date': timestamp}
    requests_params = {
        'url': ENDPOINT,
        'headers': HEADERS,
        'params': params
    }
    response = requests.get(**requests_params)

    if response.status_code != 200:
        raise StatusException(
            'Что-то не так со статусом ответа API'
        )

    response = response.json()
    return response


def check_response(response):
    """Проверяет ответ API на корректность."""
    if not isinstance(response, dict):
        raise TypeError
    if not response:
        raise ApiEmptyDataException('API вернул пустой словарь')
    if response.get('code') == 'UnknownError':
        raise ApiDataException('Неверный формта даты в запросе к API')
    if response.get('code') == 'not_authenticated':
        raise ApiTokenException(
            'неверный или недействительный токен'
            'в запросе к API'
        )

    homework = response.get('homeworks')

    if not isinstance(homework, list):
        raise TypeError

    return response.get('homeworks')


def parse_status(homework):
    """Извлекает из информации о домашней работе статус этой работы."""
    try:
        if not isinstance(homework, dict):
            raise TypeError
        homework_name = homework.get('homework_name')
        homework_status = homework.get('status')
        if homework_status not in HOMEWORK_STATUSES:
            raise HomeworkStatusError(
                f'Статуса {homework_status} нет в словаре HOMEWORK_STATUSES'
            )
    except HomeworkStatusError:
        print('Вот тут')
    verdict = HOMEWORK_STATUSES[homework_status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def check_tokens():
    """Проверяет доступность переменных окружения."""
    TOKENS_NAME = {
        'PRACTICUM_TOKEN': PRACTICUM_TOKEN,
        'TELEGRAM_TOKEN': TELEGRAM_TOKEN,
        'TELEGRAM_CHAT_ID': TELEGRAM_CHAT_ID
    }
    for tokens in TOKENS_NAME.values():
        token = False
        if tokens is not None:
            token = True
    return token


def main():
    """Основная логика работы бота."""
    bot = Bot(token=TELEGRAM_TOKEN)
    current_timestamp = int(time.time())
    status = ''

    if not check_tokens():
        logging.critical(
            'Отсутствуют одна или несколько переменных окружения'
        )
        raise NotTokenException(
            'Отсутствуют одна или несколько переменных окружения'
        )
    while True:
        try:
            response = get_api_answer(current_timestamp)
            current_timestamp = response.get('current_date')
            homework = check_response(response)
            message = parse_status(homework[0])
            if message != status:
                send_message(bot, message)
                status = message
            time.sleep(RETRY_TIME)

        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            time.sleep(RETRY_TIME)


if __name__ == '__main__':
    main()
