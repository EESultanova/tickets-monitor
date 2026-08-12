from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class Observation:
    status: str
    raw_status: str
    places: Optional[int]
