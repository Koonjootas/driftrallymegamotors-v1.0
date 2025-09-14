import feedparser

def read_rss_sources(path="rss_sources.txt"):
    with open(path, "r") as f:
        return [line.strip() for line in f if line.strip()]

def fetch_news(url, limit=5):
    feed = feedparser.parse(url)
    items = []

    for entry in feed.entries[:limit]:
        image = None
        if "media_content" in entry:
            image = entry.media_content[0]["url"]
        elif "media_thumbnail" in entry:
            image = entry.media_thumbnail[0]["url"]
        elif "image" in entry:
            image = entry.image

        items.append({
            "title": entry.title,
            "link": entry.link,
            "summary": entry.get("summary", ""),
            "image": image
        })

    return items
