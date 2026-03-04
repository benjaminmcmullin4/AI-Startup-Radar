from dataclasses import dataclass, field
from typing import Optional
import json


@dataclass
class Score:
    id: Optional[int] = None
    company_id: int = 0
    thesis_id: Optional[int] = None
    team_score: float = 0.0
    financial_score: float = 0.0
    market_score: float = 0.0
    product_score: float = 0.0
    momentum_score: float = 0.0
    composite_score: float = 0.0
    tier: str = "pass"
    score_breakdown_json: Optional[str] = None

    @property
    def breakdown(self) -> dict:
        if self.score_breakdown_json:
            try:
                return json.loads(self.score_breakdown_json)
            except (json.JSONDecodeError, TypeError):
                pass
        return {}

    @classmethod
    def from_row(cls, row: dict) -> "Score":
        data = dict(row)
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class ThesisCriteria:
    min_arr: float = 0.0
    max_arr: float = 1000.0
    min_growth_pct: float = 0.0
    sectors: list = field(default_factory=list)
    geographies: list = field(default_factory=list)
    round_types: list = field(default_factory=list)
    min_gross_margin_pct: float = 0.0
    min_net_retention_pct: float = 0.0

    def to_json(self) -> str:
        return json.dumps(self.__dict__)

    @classmethod
    def from_json(cls, s: str) -> "ThesisCriteria":
        try:
            data = json.loads(s) if isinstance(s, str) else s
            return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})
        except (json.JSONDecodeError, TypeError):
            return cls()
