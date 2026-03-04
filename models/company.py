from dataclasses import dataclass, field
from typing import Optional
import json


@dataclass
class Company:
    id: Optional[int] = None
    name: str = ""
    domain: Optional[str] = None
    description: Optional[str] = None
    sector: Optional[str] = None
    sub_sector: Optional[str] = None
    hq_location: Optional[str] = None
    founded_year: Optional[int] = None
    employee_count: Optional[int] = None
    employee_growth_pct: Optional[float] = None
    arr_millions: Optional[float] = None
    revenue_growth_pct: Optional[float] = None
    gross_margin_pct: Optional[float] = None
    net_retention_pct: Optional[float] = None
    total_raised_millions: Optional[float] = None
    last_round_type: Optional[str] = None
    last_round_amount_millions: Optional[float] = None
    last_round_date: Optional[str] = None
    last_valuation_millions: Optional[float] = None
    key_investors: list = field(default_factory=list)
    pipeline_stage: str = "new"
    ai_summary: Optional[str] = None
    ai_memo: Optional[str] = None
    source: Optional[str] = None

    def to_dict(self) -> dict:
        d = {}
        for k, v in self.__dict__.items():
            if k == "key_investors":
                d[k] = json.dumps(v) if isinstance(v, list) else v
            else:
                d[k] = v
        return d

    @classmethod
    def from_row(cls, row: dict) -> "Company":
        data = dict(row)
        if "key_investors" in data and isinstance(data["key_investors"], str):
            try:
                data["key_investors"] = json.loads(data["key_investors"])
            except (json.JSONDecodeError, TypeError):
                data["key_investors"] = []
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})
