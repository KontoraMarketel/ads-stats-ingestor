from utils import chunked

# Пример:
data = list(range(1, 353))
dates_chunked = list(chunked(data, 10))


body = [{"ids": cid, "dates": ["okeoke"]} for cid in dates_chunked]
print(body)
