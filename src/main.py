import os, datetime, traceback
from typing import List
from logging_utils import setup_logger, RunReport, save_run_report
from rss_reader import load_sources, parse_feed, mark_new, update_sent_log
from telegram_sender import safe_post, PostResult
# из ваших файлов — не трогаем внутренности:
from rewrite import rewrite_news

BOT_TOKEN = os.getenv("TG_TOKEN", "")
CHAT_ID   = os.getenv("TG_CHAT_ID", "")

logger = setup_logger("main")

def build_message(title: str, text: str, link: str) -> str:
    title = title or "(без заголовка)"
    link = link or ""
    return f"<b>{title}</b>\n\n{text}\n\n<a href='{link}'>Источник</a>"

def should_post(title: str, summary_html: str) -> bool:
    # Пока пропускаем фильтрацию; публикуем все новые записи.
    return True

def process_source(url: str, report_obj) -> None:
    entries, src = parse_feed(url)
    report_obj.sources.append(src)

    # определяем новые записи
    new_entries, n_new = mark_new(entries)
    src.new_found = n_new
    src.skipped = src.fetched - n_new

    logger.info("Источник: %s | всего=%d, новые=%d, пропуск=%d",
                url, src.fetched, src.new_found, src.skipped)

    # обрабатываем только записи, прошедшие фильтр should_post
    successful_to_log = []
    for e in new_entries:
        try:
            if not should_post(e.title, e.summary_html):
                logger.info("Фильтр отклонил: %s", e.title)
                continue
            headline, body = rewrite_news(e.title, e.summary_html)
            msg = build_message(headline, body, e.link)
            res: PostResult = safe_post(BOT_TOKEN, CHAT_ID, msg)
            if res.ok:
                src.sent += 1
                successful_to_log.append(e)
            else:
                src.errors.append(f"TG: {res.error}")
        except Exception as ex:
            logger.exception("Ошибка при обработке записи: %s", e.link)
            src.errors.append(f"PROCESS: {ex}")

    # обновляем sent_log только для успешно отправленных записей
    if successful_to_log:
        update_sent_log(successful_to_log)

def main():
    started = datetime.datetime.now().isoformat(timespec="seconds")
    run = RunReport(started_at=started)

    sources = load_sources()
    run.total_sources = len(sources)
    if not sources:
        logger.warning("Список источников пуст.")
        return

    for url in sources:
        process_source(url, run)

    # агрегированные итоги
    run.total_new_found = sum(s.new_found for s in run.sources)
    run.total_sent = sum(s.sent for s in run.sources)
    run.total_errors = sum(len(s.errors) for s in run.sources)
    run.finished_at = datetime.datetime.now().isoformat(timespec="seconds")

    # логируем сводку и сохраняем JSON-отчёт
    logger.info("=== СВОДКА РАНА ===")
    for s in run.sources:
        if s.errors:
            logger.warning("Источник: %s | новые=%d | отправлено=%d | ошибок=%d",
                        s.source, s.new_found, s.sent, len(s.errors))
            for err in s.errors:
                logger.warning("  • %s", err)
        else:
            logger.info("Источник: %s | новые=%d | отправлено=%d | ошибок=0",
                        s.source, s.new_found, s.sent)

    path = save_run_report(run)
    logger.info("Отчёт сохранён: %s", path)

if __name__ == "__main__":
    main()
