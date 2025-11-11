from __future__ import annotations
from dataclasses import dataclass
from typing import List, Dict, Any

@dataclass
class DiffPatch:
    strategy: str
    diff_text: str
    meta: Dict[str, Any]

@dataclass
class TxCall:
    to: str
    function: str
    args: List[Any]
    value: str = '0'

@dataclass
class TxPlan:
    strategy: str
    sequence: List[TxCall]
    rationale: str

@dataclass
class Finding:
    strategy: str
    type: str
    location: str
    invariant: str
    confidence: float
