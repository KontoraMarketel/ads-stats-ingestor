import logging
from datetime import datetime, timedelta

import aiohttp

from utils import chunked

GET_ADS_STATS_URL = "https://advert-api.wildberries.ru/adv/v2/fullstats"


# <ts> это дата когда выполняется функция, найди от нее вчерашнюю дату и используй
async def fetch_data(api_token: str, campaign_ids: list, ts: str) -> list:
    headers = {"Authorization": api_token}
    dt_ts = datetime.fromisoformat(ts)
    yesterday = (dt_ts - timedelta(days=1)).strftime("%Y-%m-%d")
    result = []
    body = [{"id": cid, "dates": [yesterday]} for cid in campaign_ids]
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
