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
    """Проверяет доступность переменных окружения, необходимых для работы."""
    variables = all((PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID))
    return variables


def send_message(bot, message: str) -> None:
    """Отправляет сообщение в Telegram чат."""
    MESSAGE_IS_NOT_SEND = 'Сообщение не отправилось'

    logger.debug('Подготовка отправки сообщения в телеграм')

    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
    except Exception as error:
        logger.error(MESSAGE_IS_NOT_SEND, {error})
    else:
        logger.debug(f'Бот отправил сообщение {message}')


def get_api_answer(timestamp: int) -> dict:
    """
    Делает запрос к единственному эндпоинту API-сервиса Я.Практикума.
    В качестве параметра в функцию передается временная метка в формате
    времени Unix time. В случае успешного запроса должна вернуть ответ API,
    приведя его из формата JSON к типам данных Python.
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
        message = (
            f'Не доступен эндопоинт {ENDPOINT} со следующими параметрами'
            f'GET-запроса: {HEADERS} и временной меткой {timestamp}.'
            f'Текст ошибки: {error}'
        )
        # logger.error(message)
        raise exceptions.EndPointUnavailable(message)
    try:
        response.json()
    except Exception as error:
        message_2 = f'Ответ сервера не в формате json: {error}'
        raise exceptions.ResponseFormatIsNotJson(message_2)
    else:
        return response.json()


def check_response(response: dict) -> list:
    """
    Проверяет ответ API на соответствие документации.
    В качестве параметра функция получает ответ API, приведенный
    к типам данных Python. Функция возвращает список
    домашних работ по ключу 'homeworks'.
    """
    if not isinstance(response, dict):
        raise TypeError('В ответе API не обнаружен dict')

    if 'homeworks' in response:
        homework = response['homeworks']
        message = 'Получены сведения о последней домашней работе'
        logger.debug(message)
    else:
        message = 'В ответе не обнаружен ключ homeworks'
        # logger.error(message)
        raise exceptions.KeyNotFound(message)

    if not isinstance(homework, list):
        raise TypeError('Тип ключа homeworks не list')
    return homework


def parse_status(homework: dict) -> str:
    """
    Извлекает из информации о конкретной домашней работе статус этой работы.
    В случае успеха, функция возвращает подготовленную для отправки в Telegram
    строку, содержащую один из вердиктов словаря HOMEWORK_VERDICTS.
    """
    if 'homework_name' in homework:
        homework_name = homework.get('homework_name')
        homework_status = homework.get('status')
    else:
        message = 'Ключ homework_name не найден в информации о домашней работе'
        # logger.error(message)
        raise KeyError(message)

    try:
        verdict = HOMEWORK_VERDICTS[homework_status]
        logger.debug('Статус работы известен')
    except KeyError as error:
        message = f'Неизвестный статус домашней работы: {error}'
        # logger.error(message)
        raise exceptions.StatusUnknown(message)

    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    logger.debug('Запуск бота')

    if not check_tokens():
        message = 'Отсутствует обязательная переменная окружения'
        logger.critical(message)
        sys.exit()

    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())
    last_error_homework = {
        'last_error': None,
        'last_homework': None,
    }

    while True:
        try:
            response = get_api_answer(timestamp)
            homework = check_response(response)
            if homework and homework != last_error_homework['last_homework']:
                message = parse_status(homework[0])
                send_message(bot, message)
                logger.debug(message)
                last_error_homework['last_homework'] = homework
            else:
                logger.debug('Статус домашней работы не изменился')
            timestamp = response.get('timestamp')

        except Exception as error:
            if str(error) != last_error_homework['last_error']:
                message = f'Сбой в работе программы: {error}'
                send_message(bot, message)
                logger.error(message)
                last_error_homework['last_error'] = str(error)

        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
