import logging, os, sys, json, datetime
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional

LOG_DIR = os.path.join(os.path.dirname(__file__), "logs")
os.makedirs(LOG_DIR, exist_ok=True)

def setup_logger(name: str = "drift", level: int = logging.INFO) -> logging.Logger:
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger
    logger.setLevel(level)
    fmt = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    sh = logging.StreamHandler(sys.stdout)
    sh.setFormatter(fmt)
    logger.addHandler(sh)

    # файл дня
    fname = datetime.datetime.now().strftime("%Y-%m-%d") + ".log"
    fh = logging.FileHandler(os.path.join(LOG_DIR, fname), encoding="utf-8")
    fh.setFormatter(fmt)
    logger.addHandler(fh)
    return logger

@dataclass
class SourceReport:
    source: str
    fetched: int = 0           # всего записей в ленте
    new_found: int = 0         # пометили как новые
    sent: int = 0              # успешно отправлено в канал
    skipped: int = 0           # пропущено (дубликаты, фильтр и т.п.)
    errors: List[str] = field(default_factory=list)

@dataclass
class RunReport:
    started_at: str
    finished_at: Optional[str] = None
    total_sources: int = 0
    total_new_found: int = 0
    total_sent: int = 0
    total_errors: int = 0
    sources: List[SourceReport] = field(default_factory=list)
    extra: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "total_sources": self.total_sources,
            "total_new_found": self.total_new_found,
            "total_sent": self.total_sent,
            "total_errors": self.total_errors,
            "sources": [vars(s) for s in self.sources],
            "extra": self.extra,
        }

def save_run_report(report: RunReport) -> str:
    out_dir = os.path.join(os.path.dirname(__file__), "run_reports")
    os.makedirs(out_dir, exist_ok=True)
    ts = datetime.datetime.now().strftime("%Y%m%dT%H%M%S")
    path = os.path.join(out_dir, f"run_{ts}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(report.to_dict(), f, ensure_ascii=False, indent=2)
    return path
