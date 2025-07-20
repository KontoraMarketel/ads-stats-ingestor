import logging

import aiohttp

from utils import chunked, get_yesterday_moscow_from_utc

GET_ADS_STATS_URL = "https://advert-api.wildberries.ru/adv/v2/fullstats"


# <ts> это дата когда выполняется функция, найди от нее вчерашнюю дату и используй
async def fetch_data(api_token: str, campaigns: list, ts: str) -> list:
    headers = {"Authorization": api_token}
    yesterday = get_yesterday_moscow_from_utc(ts)
    result = []

    # TODO: пока что норм, но в будущем переделать. Тк сейчас мы обрабатываем только те компании, которые активны на момент получения данных. Но мы в системе обрабатываем данные за прошлые сутки, а компания вчера могла быть активной, а сегодня до получения данных ее остановили, и она не учитывается. Надо как то шарить данные по активным кампаниям за вчера
    campaigns_with_correct_status = []
    for i in campaigns:
        if i['status'] == 9:
            campaigns_with_correct_status.extend([i['advertId'] for i in i['advert_list']])

    body = [{"id": cid, "dates": [yesterday]} for cid in campaigns_with_correct_status]
    async with aiohttp.ClientSession(headers=headers) as session:
        for batch in chunked(body, 100):
            async with session.post(GET_ADS_STATS_URL, json=batch) as response:
                data = await response.json()
                if response.status != 200:
                    logging.error(
                        f"Error fetching {batch}, server response code: {response.status}, server response: {data}")
                response.raise_for_status()
                result.extend(data)
    return result
