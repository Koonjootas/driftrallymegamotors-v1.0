import json
import os
import requests
import re
from openai import OpenAI
from rss_reader import load_sources, parse_feed
from rewrite import rewrite_news
from telegram_sender import send_telegram_message_with_photo, send_telegram_message_without_photo

TELEGRAM_TOKEN = os.getenv("TG_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TG_CHAT_ID")
UNSPLASH_ACCESS_KEY = "7UmMOEVE5pNZxC6Mu1R6ZXvpbOyuAKL41-yUfrtoMdQ"

print("⚙️ Используем OpenRouter API: deepseek/deepseek-r1-0528-qwen3-8b:free")

SENT_LOG = "sent_log.json"

# Загрузка лога отправленных ссылок
if os.path.exists(SENT_LOG):
    with open(SENT_LOG, "r") as f:
        sent_links = set(json.load(f))
else:
    sent_links = set()

print(f"📅 Загружено {len(sent_links)} ссылок из лога")

def save_log():
    print(f"📏 Сохраняем {len(sent_links)} ссылок в {SENT_LOG}")
    with open(SENT_LOG, "w") as f:
        json.dump(list(sent_links), f)

# Загрузка новостей с RSS-ленты
def fetch_news(url: str):
    entries, _ = parse_feed(url)
    items = []
    for e in entries:
        item = {"title": e.title or "", "summary": e.summary_html or "", "link": e.link or ""}
        # Проверяем наличие изображения в описании записи
        image = None
        if "<img" in e.summary_html:
            m = re.search(r'<img[^>]+src="([^"]+)"', e.summary_html)
            if m:
                image = m.group(1)
        if image:
            item["image"] = image
        items.append(item)
    return items

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

# 🧠 Получение ключевого слова по теме статьи
client = OpenAI(
    api_key=os.getenv("OPENROUTER_API_KEY"),
    base_url="https://openrouter.ai/api/v1"
)

def extract_image_topic(title, summary):
    prompt = f"""
Ты — редактор автожурнала. Верни один английский тег (одно слово),
который лучше всего описывает тему новости для поиска фото на Unsplash.
Подойдут, например: rally, drift, wrc, racing, motorsport, offroad, podium, 
servicepark, pitstop, supercar, burnout.

Правила:
— Только 1 английское слово в нижнем регистре.
— Без точек, кавычек и пояснений.

Заголовок:
{title}

Описание:
{summary}
"""
    try:
        response = client.chat.completions.create(
            model="deepseek/deepseek-r1-0528-qwen3-8b:free",
            messages=[{
                "role": "user",
                "content": [{"type": "text", "text": prompt}]
            }],
            extra_headers={
                "HTTP-Referer": "https://t.me/FuturePulse",
                "X-Title": "FuturePulse Topic"
            },
            extra_body={}
        )
        topic = response.choices[0].message.content.strip().lower()
        if " " in topic or not topic.isascii():
            return None
        return topic
    except Exception as e:
        print(f"❌ Ошибка в extract_image_topic: {e}")
        return None

# 🧬 Основной цикл отправки
def main():
    for url in load_sources():
        for item in fetch_news(url):
            if item["link"] in sent_links:
                print(f"🛑 Пропущено (дубль): {item['link']}")
                continue

            try:
                # Генерируем новый заголовок и текст новости
                headline, body = rewrite_news(item["title"], item["summary"])

                # Подбираем изображение
                image_url = item.get("image")
                if not image_url:
                    topic = extract_image_topic(item["title"], item["summary"])
                    if topic:
                        image_url = get_unsplash_image_url(topic)

                # Отправка в Telegram
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
                print(f"❌ Ошибка при обработке записи {item['link']}: {e}")

    save_log()

if __name__ == "__main__":
    main()
