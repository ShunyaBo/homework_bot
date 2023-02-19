class MissingVariable(Exception):
    """Вызывается, когда переменные окружения отсутсвуют."""

    pass


class EndPointUnavailable(Exception):
    """Вызывается, когда эндопоинт недоступен."""

    pass


class KeyNotFound(Exception):
    """Вызывается, когда ключ не найден."""

    pass


class StatusUnknown(Exception):
    """Вызывается, когда статус неизвестен."""

    pass


class StatusIsNotEqualTo200(Exception):
    """Вызывается, когда API домашки возвращает код, отличный от 200."""

    pass


class ResponseFormatIsNotJson(Exception):
    """Вызывается, если ответ сервера не в формате json."""

    pass
