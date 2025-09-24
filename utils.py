from datetime import datetime, timedelta
from zoneinfo import ZoneInfo


def chunked(data, size):
    for i in range(0, len(data), size):
        yield data[i : i + size]


def get_yesterday_bounds_msk(ts: str):
    """
    Принимает строку с UTC-временем (ISO8601),
    возвращает (date_from, date_to) — календарные даты вчерашнего дня по МСК.
    Оба значения одинаковые → закрытый интервал [вчера, вчера].
    """
    # парсим входное UTC-время
    dt_utc = datetime.fromisoformat(ts)

    # часовой пояс МСК
    msk_zone = ZoneInfo("Europe/Moscow")

    # конвертируем в МСК
    dt_msk = dt_utc.astimezone(msk_zone)

    # вчерашняя дата по МСК
    yesterday = dt_msk.date() - timedelta(days=1)

    return yesterday, yesterday