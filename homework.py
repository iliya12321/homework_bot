import logging
import logging.handlers
import os
import sys
import time

import requests
from dotenv import load_dotenv
from telegram import Bot

from exceptions import NotTokenException, StatusException

load_dotenv()

PRACTICUM_TOKEN = os.getenv('TOKEN')
TELEGRAM_TOKEN = os.getenv('TOKENBOT')
TELEGRAM_CHAT_ID = os.getenv('CHAT_ID')

RETRY_TIME = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}

TEXT_IF_NOT_TOKEN = 'Отсутствуют одна или несколько переменных окружения'
HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}

SECRET_DATA = [
    'PRACTICUM_TOKEN',
    'TELEGRAM_TOKEN',
    'TELEGRAM_CHAT_ID'
]


def send_message(bot, message):
    """Отправляет сообщение в телеграм бот."""
    try:
        logging.info('Отправка сообщения в телеграм')
        bot.send_message(TELEGRAM_CHAT_ID, message)
    except Exception as error:
        logging.error(
            f'Что-то не так при отправке сообщения. '
            f'Id чата в который отправляется сообщение {TELEGRAM_CHAT_ID}, '
            f'сообщение которое отправляется: {message}. '
            f'Возникла ошибка - {error}'
        )
    else:
        logging.info('Сообщение отправлено!')


def get_api_answer(current_timestamp):
    """Делает запрос к единственному эндпоинту API-сервиса."""
    params = {'from_date': current_timestamp}
    requests_params = {
        'url': ENDPOINT,
        'headers': HEADERS,
        'params': params
    }

    try:
        response = requests.get(**requests_params)
    except Exception as error:
        raise ConnectionError(
            f'При запросе к API по адресу: "{requests_params["url"]}", '
            f'с параметрами: "{requests_params["params"]}", '
            f'с заголовками: "{requests_params["headers"]}", '
            f'возникла ошибка: {error}'
        )

    if response.status_code != 200:
        raise StatusException(
            f'Cтатус ответа API: {response.status_code}, '
            f'Ответ сервера: {response.text}'
        )

    return response.json()


def check_response(response):
    """Проверяет ответ API на корректность."""
    if not isinstance(response, dict):
        raise TypeError(f'response не dict, a {type(response)}')

    if 'homeworks' not in response:
        raise KeyError('В ответе API отсутствует ключ homeworks')

    if 'current_date' not in response:
        raise KeyError('В ответе API отсутсвует ключ current_date')

    homeworks = response['homeworks']

    if not isinstance(homeworks, list):
        raise TypeError(f'response не dict, a {type(homeworks)}')

    return homeworks


def parse_status(homework):
    """Извлекает из информации о домашней работе статус этой работы."""
    if not isinstance(homework, dict):
        raise TypeError(f'homework не dict, а {type(homework)} ')

    if 'homework_name' not in homework:
        raise KeyError('Отсутсвует значение ключа homework_name')

    if 'status' not in homework:
        raise KeyError('Отсутствует ключ "status"')

    homework_status = homework['status']
    homework_name = homework['homework_name']

    if homework_status not in HOMEWORK_VERDICTS:
        raise KeyError(
            f'{homework_status} нет в словаре HOMEWORK_VERDICTS'
        )

    verdict = HOMEWORK_VERDICTS[homework_status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def check_tokens():
    """Проверяет доступность переменных окружения."""
    available_token = True
    for token in SECRET_DATA:
        if not globals().get(token):
            available_token = False
            logging.info(f'Отсутвует токен: {token}, {TELEGRAM_CHAT_ID}')
    return available_token


def errors_catcher(error):
    """Выводит в ошибку более детальный ответ."""
    traceback = error.__traceback__.next
    error_func_name = traceback.nb_frame.f_code.co_name
    error_line = traceback.tb_lineno
    error_info = (
        f'{error_func_name}, {error_line}, '
        f'[{type(error).__name__}] {error}'
    )
    return error_info


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        logging.critical(
            TEXT_IF_NOT_TOKEN
        )
        raise NotTokenException(
            TEXT_IF_NOT_TOKEN
        )
    bot = Bot(token=TELEGRAM_TOKEN)
    current_timestamp = 0
    status = ''
    message = ''

    while True:
        try:
            response = get_api_answer(current_timestamp)
            homework = check_response(response)
            if not homework:
                logging.debug('отсутствие в ответе новых статусов')
                continue
            message = parse_status(homework[0])
            if message != status:
                send_message(bot, message)
                status = message
            current_timestamp = response.get('current_date', current_timestamp)

        except Exception as error:
            logging.error(errors_catcher(error))
            if message != str(error):
                message = str(error)
                send_message(bot, message)

        finally:
            time.sleep(RETRY_TIME)


if __name__ == '__main__':

    logging.basicConfig(
        level=logging.INFO,
        handlers=[
            logging.handlers.RotatingFileHandler(
                filename=__file__[:-2] + 'log',
                maxBytes=500000,
                backupCount=3,
                encoding='utf-8'
            ),
            logging.StreamHandler(sys.stdout)
        ],
        format=(
            '%(asctime)s, '
            '[%(levelname)s], '
            '%(message)s, '
            '%(filename)s'
        )
    )
    main()
