from openai import OpenAI
import os

client = OpenAI(
    api_key=os.getenv("OPENROUTER_API_KEY"),
    base_url="https://openrouter.ai/api/v1"
)

def rewrite_news(title, summary):
    prompt = f"""Переработай следующую статью автожурнала в виде короткого, информативного поста для Telegram канала посвященного ралли и дрифту, пиши как экспертный копирайтер своим языком.

Вот заголовок оригинальной статьи:
{title}

Вот краткое описание:
{summary}

Сформируй:
1. Новый короткий и выразительный заголовок (без ссылки)
2. Затем — 3–4 абзаца пояснительного текста до 600 символов, с подходом как копирайтер

Тон: динамичный автожурнал, без «воды», без эмодзи.
Формат ответа:
Звголовок (сформируй на основе заголовка статьи)

Текст
"""

    response = client.chat.completions.create(
        model="deepseek/deepseek-r1-0528-qwen3-8b:free",
        messages=[{
            "role": "user",
            "content": [{"type": "text", "text": prompt}]
        }],
        extra_headers={
            "HTTP-Referer": "https://t.me/FuturePulse",
            "X-Title": "FuturePulse Rewrite"
        },
        extra_body={}
    )

    result = response.choices[0].message.content.strip()
    if "\n\n" in result:
        headline, body = result.split("\n\n", 1)
    else:
        headline, body = result, ""

    return headline.strip(), body.strip()