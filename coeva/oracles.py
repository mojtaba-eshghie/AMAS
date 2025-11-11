from __future__ import annotations
from typing import Tuple, Any
import random
from .logging_utils import get_logger
from . import config

log_oracle = get_logger("coeva.oracle", config.LOG_LEVEL)

def _clip01(x: float) -> float:
    return max(0.0, min(1.0, x))

def evaluate_injector(diff_patch: Any) -> Tuple[float, str]:
    reward = 0.6 if 'require(' in getattr(diff_patch, 'diff_text', '') else 0.3
    reward += random.uniform(-0.1, 0.1)
    r = _clip01(reward)
    log_oracle.debug(f"injector reward={r:.3f}")
    return (r, 'toy-eval')

def evaluate_exploiter(tx_plan: Any) -> Tuple[float, str]:
    n = len(getattr(tx_plan, 'sequence', []))
    base = 0.7 if n <= 2 else 0.5
    r = _clip01(base + random.uniform(-0.1, 0.1))
    log_oracle.debug(f"exploiter n={n} reward={r:.3f}")
    return (r, 'toy-eval')

def evaluate_detector(finding: Any) -> Tuple[float, str]:
    conf = getattr(finding, 'confidence', 0.5)
    r = _clip01(0.4 + 0.6*conf + random.uniform(-0.1,0.1))
    log_oracle.debug(f"detector conf={conf:.2f} reward={r:.3f}")
    return (r, 'toy-eval')

def evaluate_patcher(diff_patch: Any) -> Tuple[float, str]:
    reward = 0.6 if 'require(' in getattr(diff_patch, 'diff_text','') else 0.3
    reward += random.uniform(-0.1,0.1)
    r = _clip01(reward)
    log_oracle.debug(f"patcher reward={r:.3f}")
    return (r, 'toy-eval')
