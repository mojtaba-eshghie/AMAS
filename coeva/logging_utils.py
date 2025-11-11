from __future__ import annotations
import json, logging, os, sys, time, uuid
from typing import Any, Dict

def get_logger(name: str, level: str = "INFO") -> logging.Logger:
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))
    h = logging.StreamHandler(sys.stdout)
    fmt = logging.Formatter(fmt="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
                            datefmt="%H:%M:%S")
    h.setFormatter(fmt)
    logger.addHandler(h)
    logger.propagate = False
    return logger

def jsonl_write(path: str, obj: Dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False) + "\n")

def preview(s: str, n: int) -> str:
    if s is None:
        return ""
    return s if len(s) <= n else (s[:n] + "…")

def new_run_id() -> str:
    return uuid.uuid4().hex[:12]

def now_ts() -> float:
    return time.time()

def write_text(path: str, text: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text if text is not None else "")