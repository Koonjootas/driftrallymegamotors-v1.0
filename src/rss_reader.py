# rss_reader.py
import os
import time
import traceback
from typing import List, Tuple
from dataclasses import dataclass
from urllib.parse import urljoin

import feedparser
import requests
from bs4 import BeautifulSoup

from logging_utils import setup_logger, SourceReport

logger = setup_logger("rss_reader")

# --- Публичный API файла ------------------------------------------------------

def load_sources(path: str = "rss_sources.txt") -> List[str]:
    if not os.path.exists(path):
        logger.warning("rss_sources.txt не найден — вернётся пустой список.")
        return []
    with open(path, "r", encoding="utf-8") as f:
        sources = [
            line.strip()
            for line in f
            if line.strip() and not line.strip().startswith("#")
        ]
    return sources


@dataclass
class ParsedEntry:
    id: str
    title: str
    link: str
    published: str
    summary_html: str


def parse_feed(url: str, timeout: int = 20) -> Tuple[List["ParsedEntry"], SourceReport]:
    """
    Универсальный парсер:
    - если источник начинается с 'HTML:', то парсим HTML-листинг (WordPress)
      и добираем полный текст каждой статьи;
    - иначе пробуем обычный RSS/Atom через feedparser.
    """
    report = SourceReport(source=url)

    try:
        if url.startswith("HTML:"):
            base_url = url.split("HTML:", 1)[1].strip()
            entries = _parse_html_source(base_url, timeout=timeout, report=report)
            report.fetched = len(entries)
            return entries, report

        # --- Обычный RSS/Atom ---
        feed = feedparser.parse(url)
        if feed.bozo:
            report.errors.append(f"bozo={feed.bozo}; exc={getattr(feed, 'bozo_exception', None)}")
            logger.error("Проблема парсинга '%s': %s", url, getattr(feed, 'bozo_exception', None))

        entries: List[ParsedEntry] = []
        for e in feed.entries:
            eid = getattr(e, "id", None) or getattr(e, "guid", None) or getattr(e, "link", "")
            title = (getattr(e, "title", "") or "").strip()
            link = (getattr(e, "link", "") or "").strip()
            published = getattr(e, "published", "") or getattr(e, "updated", "")
            summary = getattr(e, "summary", "") or getattr(e, "description", "")

            entries.append(ParsedEntry(
                id=eid or link,
                title=title,
                link=link,
                published=published,
                summary_html=summary
            ))

        report.fetched = len(entries)
        return entries, report

    except Exception as ex:
        report.errors.append(f"Exception: {ex}")
        logger.exception("Исключение при парсинге '%s': %s", url, ex)
        return [], report


def mark_new(entries: List[ParsedEntry], sent_log_path: str = "sent_log.json") -> Tuple[List[ParsedEntry], int]:
    """
    Фильтрует только новые записи, используя sent_log.json (формат: {entry_id: timestamp})
    ВНИМАНИЕ: используем словарь {id: ts}. Если у вас старый формат-список — он будет прочитан как пустой.
    """
    import json
    sent = {}
    if os.path.exists(sent_log_path):
        try:
            with open(sent_log_path, "r", encoding="utf-8") as f:
                sent = json.load(f)
                # Если вдруг формат — список ссылок (старый), преобразуем во временный словарь
                if isinstance(sent, list):
                    sent = {k: int(time.time()) for k in sent}
        except Exception:
            pass

    new_entries = []
    for e in entries:
        key = e.id or e.link
        if key and key not in sent:
            new_entries.append(e)
    return new_entries, len(new_entries)


def update_sent_log(entries: List[ParsedEntry], sent_log_path: str = "sent_log.json") -> None:
    import json
    sent = {}
    if os.path.exists(sent_log_path):
        try:
            with open(sent_log_path, "r", encoding="utf-8") as f:
                sent = json.load(f)
                if isinstance(sent, list):  # совместимость со старым форматом
                    sent = {k: int(time.time()) for k in sent}
        except Exception:
            pass

    now = int(time.time())
    for e in entries:
        key = e.id or e.link
        if key:
            sent[key] = now

    with open(sent_log_path, "w", encoding="utf-8") as f:
        json.dump(sent, f, ensure_ascii=False, indent=2)

# --- Внутренние функции для HTML-режима ---------------------------------------

_UA = {
    "User-Agent": "Mozilla/5.0 (compatible; DriftRallyBot/1.0; +https://t.me/futurepulse)",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

def _http_get(url: str, timeout: int = 20) -> requests.Response:
    resp = requests.get(url, headers=_UA, timeout=timeout, allow_redirects=True)
    resp.raise_for_status()
    return resp


def _parse_html_source(listing_url: str, timeout: int, report: SourceReport) -> List[ParsedEntry]:
    """
    Разбираем страницу листинга новостей WordPress:
    - вытягиваем ссылки и заголовки (обычно h2.entry-title > a)
    - по каждой ссылке заходим и забираем полный текст (.entry-content)
    """
    try:
        r = _http_get(listing_url, timeout=timeout)
    except Exception as ex:
        msg = f"LISTING GET fail: {ex}"
        logger.error(msg)
        report.errors.append(msg)
        return []

    soup = BeautifulSoup(r.text, "html.parser")

    # На типовых WP: h2.entry-title a (иногда h3)
    link_nodes = soup.select("h2.entry-title a, h3.entry-title a")
    if not link_nodes:
        # fallback: ссылки внутри article
        link_nodes = soup.select("article a")

    collected: List[ParsedEntry] = []

    for a in link_nodes:
        href = (a.get("href") or "").strip()
        title = a.get_text(strip=True)
        if not href or not title:
            continue
        full_url = urljoin(listing_url, href)

        # Забираем полный текст статьи
        text_html, published = _fetch_full_article(full_url, timeout=timeout, report=report)
        entry = ParsedEntry(
            id=full_url,
            title=title,
            link=full_url,
            published=published,
            summary_html=text_html or ""  # важно: сюда кладём «тело», чтобы downstream мог переписать
        )
        collected.append(entry)

    return collected


def _fetch_full_article(url: str, timeout: int, report: SourceReport) -> Tuple[str, str]:
    """
    Переходим в статью и достаём HTML-тело.
    Ищем типичные WP-селекторы .entry-content, .post-content и т.п.
    Возвращаем (html, published_str)
    """
    try:
        r = _http_get(url, timeout=timeout)
    except Exception as ex:
        msg = f"ARTICLE GET fail: {ex} | {url}"
        logger.warning(msg)
        report.errors.append(msg)
        return "", ""

    soup = BeautifulSoup(r.text, "html.parser")

    # Основное содержимое
    body = (
        soup.select_one(".entry-content")
        or soup.select_one("article .entry-content")
        or soup.select_one("article .post-content")
        or soup.select_one("article .content")
        or soup.select_one("main article")
    )

    # Дата, если есть
    date_node = (
        soup.select_one("time.entry-date")
        or soup.select_one("time.published")
        or soup.select_one("meta[property='article:published_time']")
    )
    published = ""
    if date_node:
        if date_node.name == "meta":
            published = date_node.get("content", "") or ""
        else:
            published = date_node.get("datetime", "") or date_node.get_text(strip=True) or ""

    # Чистим лишнее: скрипты/стили/шэры
    if body:
        for bad in body.select("script, style, .sharedaddy, .share, .post-meta, .post-tags"):
            bad.decompose()

        # Превращаем относительные ссылки в абсолютные
        for tag in body.select("img, a"):
            attr = "src" if tag.name == "img" else "href"
            if tag.has_attr(attr):
                tag[attr] = urljoin(url, tag[attr])

        html = str(body).strip()
        return html, published

    # Фолбэк: берём хотя бы текст всей статьи
    article = soup.select_one("article")
    html = article.get_text("\n", strip=True) if article else ""
    return html, published
