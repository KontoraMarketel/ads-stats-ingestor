import asyncio
import json
import logging
import os

from aiokafka import AIOKafkaConsumer, AIOKafkaProducer

from fetch_data import fetch_data
from minio_pool import MinioClientPool
from storage import upload_to_minio, download_from_minio

logging.basicConfig(level=logging.INFO)

BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS")
CONSUMER_TOPIC = os.getenv("KAFKA_INGEST_COMMISSIONS_TASKS_TOPIC")
CONSUMER_GROUP = os.getenv("KAFKA_CONSUMER_GROUP")
PRODUCER_TOPIC = os.getenv("KAFKA_PRODUCER_STG_ADS_STATS_TASKS")
MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT")
MINIO_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY")
MINIO_SECRET_KEY = os.getenv("MINIO_SECRET_KEY")
MINIO_BUCKET = os.getenv("MINIO_BUCKET")

CONCURRENT_TASKS = 100  # максимальное количество одновременных задач
semaphore = asyncio.Semaphore(CONCURRENT_TASKS)


async def handle_message(msg, minio_pool: MinioClientPool):
    task_id = msg["task_id"]
    api_token = msg["wb_token"]
    ts = msg["ts"]
    minio_key = msg["minio_key"]

    logging.info(f"Start processing task {task_id}")

    campaigns = await download_from_minio(
        pool=minio_pool,
        bucket=MINIO_BUCKET,
        key=minio_key,
    )

    logging.info(f"Campaigns IDs: {campaigns}")

    data = await fetch_data(api_token, campaigns, ts)
    load_data = {
        "data": data,
        "task_id": task_id,
        "ts": ts,
    }
    filename = "ads_stats.json"
    prefix = f"{ts}/{task_id}/"
    minio_key = prefix + filename

    await upload_to_minio(
        pool=minio_pool,
        bucket=MINIO_BUCKET,
        data=load_data,
        key=minio_key,
    )

    logging.info(f"Task {task_id} completed successfully.")

    return {
        "task_id": task_id,
        "ts": ts,
        "minio_key": minio_key
    }


async def process_and_produce(msg_value, producer, minio_pool: MinioClientPool):
    async with semaphore:
        try:
            next_msg = await handle_message(msg_value, minio_pool)
            encoded_task_id = str(next_msg["task_id"]).encode("utf-8")
            await producer.send(
                PRODUCER_TOPIC,
                value=next_msg,
                key=encoded_task_id,
            )
        except Exception as e:
            logging.error(f"Error processing message: {e}")
            # TODO: write task to out of the box table


async def main():
    consumer = AIOKafkaConsumer(
        CONSUMER_TOPIC,
        bootstrap_servers=BOOTSTRAP_SERVERS,
        group_id=CONSUMER_GROUP,
        auto_offset_reset="earliest",
        enable_auto_commit=True,
        value_deserializer=lambda m: json.loads(m.decode("utf-8")),
    )

    producer = AIOKafkaProducer(
        bootstrap_servers=BOOTSTRAP_SERVERS,
        value_serializer=lambda v: json.dumps(v).encode("utf-8"),
    )

    minio_pool = MinioClientPool(
        endpoint_url=MINIO_ENDPOINT,
        access_key=MINIO_ACCESS_KEY,
        secret_key=MINIO_SECRET_KEY,
        size=5,
    )

    await minio_pool.start()
    await producer.start()
    await consumer.start()
    tasks = set()
    try:
        async for msg in consumer:
            task = asyncio.create_task(process_and_produce(msg.value, producer, minio_pool))
            tasks.add(task)
            task.add_done_callback(tasks.discard)
    finally:
        logging.info("Stopping consumer. Waiting for tasks to finish...")
        await consumer.stop()
        await producer.stop()
        await minio_pool.stop()
        await asyncio.gather(*tasks, return_exceptions=True)


if __name__ == "__main__":
    asyncio.run(main())
