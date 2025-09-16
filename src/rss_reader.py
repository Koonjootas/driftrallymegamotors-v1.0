import os, time, traceback
from typing import List, Dict, Tuple
from dataclasses import dataclass
from logging_utils import setup_logger, SourceReport
import feedparser

logger = setup_logger("rss_reader")

def load_sources(path: str = "rss_sources.txt") -> List[str]:
    if not os.path.exists(path):
        logger.warning("rss_sources.txt не найден — вернётся пустой список.")
        return []
    with open(path, "r", encoding="utf-8") as f:
        sources = [line.strip() for line in f if line.strip() and not line.strip().startswith("#")]
    return sources

@dataclass
class ParsedEntry:
    id: str
    title: str
    link: str
    published: str
    summary_html: str

def parse_feed(url: str, timeout: int = 20) -> Tuple[List[ParsedEntry], SourceReport]:
    report = SourceReport(source=url)
    try:
        # feedparser сам делает запрос
        feed = feedparser.parse(url)
        if feed.bozo:
            report.errors.append(f"bozo={feed.bozo}; exc={getattr(feed, 'bozo_exception', None)}")
            logger.error("Проблема парсинга '%s': %s", url, getattr(feed, 'bozo_exception', None))

        entries: List[ParsedEntry] = []
        for e in feed.entries:
            eid = getattr(e, "id", None) or getattr(e, "guid", None) or getattr(e, "link", "")
            title = getattr(e, "title", "").strip()
            link = getattr(e, "link", "").strip()
            published = getattr(e, "published", "") or getattr(e, "updated", "")
            summary = getattr(e, "summary", "") or getattr(e, "description", "")
            entries.append(ParsedEntry(id=eid, title=title, link=link, published=published, summary_html=summary))
        report.fetched = len(entries)
        return entries, report
    except Exception as ex:
        tb = traceback.format_exc()
        report.errors.append(f"Exception: {ex}")
        logger.exception("Исключение при парсинге '%s': %s", url, ex)
        return [], report

def mark_new(entries: List[ParsedEntry], sent_log_path: str = "sent_log.json") -> Tuple[List[ParsedEntry], int]:
    """
    Фильтрует только новые записи, используя sent_log.json (формат: {entry_id: timestamp})
    """
    import json, time
    sent = {}
    if os.path.exists(sent_log_path):
        try:
            with open(sent_log_path, "r", encoding="utf-8") as f:
                sent = json.load(f)
        except Exception:
            pass

    new_entries = []
    for e in entries:
        key = e.id or e.link
        if key and key not in sent:
            new_entries.append(e)
    return new_entries, len(new_entries)

def update_sent_log(entries: List[ParsedEntry], sent_log_path: str = "sent_log.json") -> None:
    import json, time
    sent = {}
    if os.path.exists(sent_log_path):
        try:
            with open(sent_log_path, "r", encoding="utf-8") as f:
                sent = json.load(f)
        except Exception:
            pass
    now = int(time.time())
    for e in entries:
        key = e.id or e.link
        if key:
            sent[key] = now
    with open(sent_log_path, "w", encoding="utf-8") as f:
        json.dump(sent, f, ensure_ascii=False, indent=2)
