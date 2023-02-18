import logging
import os
import sys
import time
from http import HTTPStatus

import requests
import telegram
from dotenv import load_dotenv

import exceptions

load_dotenv()


PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler(stream=sys.stdout)
logger.addHandler(handler)

formatter = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
handler.setFormatter(formatter)


def check_tokens() -> bool:
    """
    Проверяет доступность переменных окружения,
    необходимых для работы бота.
    """
    VARIABLE_IS_MISSING = 'Отсутствует обязательная переменная окружения'
    if not PRACTICUM_TOKEN:
        logging.critical(f'{VARIABLE_IS_MISSING} - PRACTICUM_TOKEN')
        raise exceptions.MissingVariable(VARIABLE_IS_MISSING)

    if not TELEGRAM_TOKEN:
        logging.critical(f'{VARIABLE_IS_MISSING} - TELEGRAM_TOKEN')
        raise exceptions.MissingVariable(VARIABLE_IS_MISSING)

    if not TELEGRAM_CHAT_ID:
        logging.critical(f'{VARIABLE_IS_MISSING} - TELEGRAM_CHAT_ID')
        raise exceptions.MissingVariable(VARIABLE_IS_MISSING)


def send_message(bot, message: str) -> str:
    """Отправляет сообщение в Telegram чат."""
    MESSAGE_IS_NOT_SEND = 'Сообщение не отправилось'
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logger.debug(f'Бот отправил сообщение {message}')
    except Exception as error:
        logger.error(MESSAGE_IS_NOT_SEND, {error})


def get_api_answer(timestamp: int) -> dict:
    """
    Делает запрос к единственному эндпоинту API-сервиса Я.Практикума.
    В качестве параметра в функцию передается временная метка.
    В случае успешного запроса должна вернуть ответ API, приведя его
    из формата JSON к типам данных Python.
    """
    payload = {'from_date': timestamp}
    try:
        response = requests.get(
            url=ENDPOINT, headers=HEADERS, params=payload)
        logger.debug(f'Отправлен GET-запрос к API Я.Практикума. '
                     f'Код ответа API: {response.status_code}')
        if response.status_code != HTTPStatus.OK:
            raise exceptions.StatusIsNotEqualTo200
    except Exception as error:
        message = f'Не доступен эндопоинт: {error}'
        logger.error(message)
        raise exceptions.EndPointUnavailable(message)
    return response.json()


def check_response(response: dict) -> list:
    """
    Проверяет ответ API на соответствие документации.
    В качестве параметра функция получает ответ API, приведенный
    к типам данных Python. Функция возвращает список
    домашних работ по ключу 'homeworks'.
    """
    if isinstance(response, dict):
        try:
            homework = response['homeworks']
        except KeyError as error:
            message = f'В ответе не обнаружен ключ {error}'
            logger.error(message)
            raise exceptions.KeyNotFound(message)
        if not isinstance(homework, list):
            raise TypeError('Тип ключа homeworks не list')
        message = 'Получены сведения о последней домашней работе'
        logger.debug(message)
        return homework
    else:
        raise TypeError('В ответе API не обнаружен list')


def parse_status(homework: dict) -> str:
    """
    Извлекает из информации о конкретной домашней работе статус этой работы.
    В случае успеха, функция возвращает подготовленную для отправки в Telegram
    строку, содержащую один из вердиктов словаря HOMEWORK_VERDICTS.
    """
    try:
        homework_name = homework['homework_name']
        homework_status = homework['status']
    except KeyError as error:
        message = f'Ключ {error} не найден в информации о домашней работе'
        logger.error(message)
        raise KeyError(message)

    try:
        verdict = HOMEWORK_VERDICTS[homework_status]
        logger.debug('Статус работы известен')
    except KeyError as error:
        message = f'Неизвестный статус домашней работы: {error}'
        logger.error(message)
        raise exceptions.StatusUnknown(message)

    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    logger.debug('Запуск бота')
    check_tokens()
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())
    last_error = None
    last_homework = None

    while True:
        try:
            response = get_api_answer(timestamp)
            homework = check_response(response)
            if homework and homework != last_homework:
                message = parse_status(homework[0])
                send_message(bot, message)
                last_homework = homework
            else:
                logger.debug('Статус домашней работы не изменился')
            timestamp = response.get('timestamp')
            time.sleep(RETRY_PERIOD)

        except Exception as error:
            if str(error) != last_error:
                message = f'Сбой в работе программы: {error}'
                send_message(bot, message)
                last_error = str(error)
                time.sleep(RETRY_PERIOD)
            else:
                time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
