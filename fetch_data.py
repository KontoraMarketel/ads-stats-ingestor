import asyncio
import logging
from datetime import datetime, timedelta
import aiohttp

from utils import chunked, get_yesterday_bounds_msk

GET_ADS_STATS_URL = "https://advert-api.wildberries.ru/adv/v3/fullstats"


# <ts> это дата когда выполняется функция, найди от нее вчерашнюю дату и используй
async def fetch_data(api_token: str, campaigns: dict, ts: str) -> list:
    headers = {"Authorization": api_token}
    date_from, date_to = get_yesterday_bounds_msk(ts)
    result = []
    campaigns_list = campaigns["data"]

    # TODO: пока что норм, но в будущем переделать. Тк сейчас мы обрабатываем только те компании, которые активны на момент получения данных. Но мы в системе обрабатываем данные за прошлые сутки, а компания вчера могла быть активной, а сегодня до получения данных ее остановили, и она не учитывается. Надо как то шарить данные по активным кампаниям за вчера
    campaigns_with_correct_status = []
    for i in campaigns_list:
        if i["status"] == 9:
            campaigns_with_correct_status.extend(
                [i["advertId"] for i in i["advert_list"]]
            )

    async with aiohttp.ClientSession(headers=headers) as session:
        for ids_batch in chunked(campaigns_with_correct_status, 100):
            logging.info(f"Fetching data for IDs: {ids_batch}")
            body = {
                "ids": ",".join(map(str, ids_batch)),  # <-- ключевой момент
                "beginDate": date_from,
                "endDate": date_to,
            }
            data = await fetch_page_with_retry(session, GET_ADS_STATS_URL, body)
            result.extend(data)
    return result


async def fetch_page_with_retry(session: aiohttp.ClientSession, url, payload):
    while True:
        async with session.get(url, params=payload) as response:
            if response.status == 429:
                retry_after = int(response.headers.get("X-Ratelimit-Retry", 10))
                logging.warning(
                    f"Rate limited (429). Retrying after {retry_after} seconds..."
                )
                await asyncio.sleep(retry_after)
                continue

            response.raise_for_status()
            return await response.json()
