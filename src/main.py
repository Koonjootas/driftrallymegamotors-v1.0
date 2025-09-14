import json
import os
import requests
from rss_reader import read_rss_sources, fetch_news
from rewrite import rewrite_news
from topic_selector import extract_image_topic
from telegram_sender import send_telegram_message_with_photo, send_telegram_message_without_photo

TELEGRAM_TOKEN = os.getenv("TG_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TG_CHAT_ID")
UNSPLASH_ACCESS_KEY = "7UmMOEVE5pNZxC6Mu1R6ZXvpbOyuAKL41-yUfrtoMdQ"

SENT_LOG = "sent_log.json"

# Загрузка лога
if os.path.exists(SENT_LOG):
    with open(SENT_LOG, "r") as f:
        sent_links = set(json.load(f))
else:
    sent_links = set()

print(f"📅 Загружено {len(sent_links)} ссылок из лога")

def save_log():
    print(f"📏 Сохраняем {len(sent_links)} ссылок в sent_log.json")
    with open(SENT_LOG, "w") as f:
        json.dump(list(sent_links), f)

# 💡 Получение URL фото с Unsplash

def get_unsplash_image_url(query):
    url = "https://api.unsplash.com/search/photos"
    params = {
        "query": query,
        "orientation": "landscape",
        "per_page": 1,
        "client_id": UNSPLASH_ACCESS_KEY,
    }

    try:
        response = requests.get(url, params=params, timeout=5)
        response.raise_for_status()
        data = response.json()
        if data["results"]:
            return data["results"][0]["urls"]["regular"]
        else:
            print("⚠️ Unsplash: нет результатов")
            return None
    except Exception as e:
        print(f"❌ Unsplash API error: {e}")
        return None

# 🧬 Основной цикл

def main():
    for url in read_rss_sources():
        for item in fetch_news(url):
            if item["link"] in sent_links:
                print(f"🛑 Пропущено (дубль): {item['link']}")
                continue

            try:
                headline, body = rewrite_news(item["title"], item["summary"])

                # Ищем фото
                image_url = item.get("image")
                if not image_url:
                    topic = extract_image_topic(item["title"], item["summary"])
                    if topic:
                        image_url = get_unsplash_image_url(topic)

                # Отправка
                if image_url:
                    send_telegram_message_with_photo(
                        title=headline,
                        link=item["link"],
                        text=body,
                        image_url=image_url,
                        token=TELEGRAM_TOKEN,
                        chat_id=TELEGRAM_CHAT_ID
                    )
                else:
                    send_telegram_message_without_photo(
                        title=headline,
                        link=item["link"],
                        text=body,
                        token=TELEGRAM_TOKEN,
                        chat_id=TELEGRAM_CHAT_ID
                    )

                print(f"✅ Отправлено: {item['link']}")
                sent_links.add(item["link"])

            except Exception as e:
                print(f"❌ Ошибка: {e}")

    save_log()

if __name__ == "__main__":
    main()
