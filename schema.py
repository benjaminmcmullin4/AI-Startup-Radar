"""Pydantic data models for startup pipeline management."""

from __future__ import annotations

import json
from enum import Enum

from pydantic import BaseModel, Field, field_validator


class PipelineStage(str, Enum):
    """Deal pipeline stages."""
    NEW = "new"
    SCREENING = "screening"
    DEEP_DIVE = "deep_dive"
    IC_REVIEW = "ic_review"
    PASS = "pass"
    MONITOR = "monitor"

    @property
    def label(self) -> str:
        labels = {"new": "New", "screening": "Screening", "deep_dive": "Deep Dive",
                  "ic_review": "IC Review", "pass": "Pass", "monitor": "Monitor"}
        return labels.get(self.value, self.value)


class Company(BaseModel):
    """A company in the deal pipeline."""
    id: int | None = Field(default=None, description="Database ID")
    name: str = Field(default="", description="Company name")
    domain: str | None = Field(default=None, description="Website domain")
    description: str | None = Field(default=None, description="Company description")
    sector: str | None = Field(default=None, description="Industry sector")
    sub_sector: str | None = Field(default=None, description="Industry sub-sector")
    hq_location: str | None = Field(default=None, description="Headquarters location")
    founded_year: int | None = Field(default=None, description="Year founded")
    employee_count: int | None = Field(default=None, description="Number of employees")
    employee_growth_pct: float | None = Field(default=None, description="Employee growth %")
    arr_millions: float | None = Field(default=None, description="Annual Recurring Revenue ($M)")
    revenue_growth_pct: float | None = Field(default=None, description="Revenue growth %")
    gross_margin_pct: float | None = Field(default=None, description="Gross margin %")
    net_retention_pct: float | None = Field(default=None, description="Net revenue retention %")
    total_raised_millions: float | None = Field(default=None, description="Total capital raised ($M)")
    last_round_type: str | None = Field(default=None, description="Last funding round type")
    last_round_amount_millions: float | None = Field(default=None, description="Last round size ($M)")
    last_round_date: str | None = Field(default=None, description="Last round date (YYYY-MM-DD)")
    last_valuation_millions: float | None = Field(default=None, description="Last valuation ($M)")
    key_investors: list[str] = Field(default_factory=list, description="Key investors")
    pipeline_stage: str = Field(default="new", description="Current pipeline stage")
    ai_summary: str | None = Field(default=None, description="AI-generated summary")
    ai_memo: str | None = Field(default=None, description="AI-generated memo")
    source: str | None = Field(default=None, description="Data source")

    @field_validator("key_investors", mode="before")
    @classmethod
    def _parse_investors(cls, v):
        if isinstance(v, str):
            try:
                return json.loads(v)
            except (json.JSONDecodeError, TypeError):
                return []
        return v or []

    def to_dict(self) -> dict:
        d = self.model_dump()
        d["key_investors"] = json.dumps(d["key_investors"])
        return d


class Score(BaseModel):
    """Company score against an investment thesis."""
    id: int | None = Field(default=None, description="Database ID")
    company_id: int = Field(default=0, description="Company ID")
    thesis_id: int | None = Field(default=None, description="Thesis ID")
    team_score: float = Field(default=0.0, description="Team dimension score")
    financial_score: float = Field(default=0.0, description="Financial dimension score")
    market_score: float = Field(default=0.0, description="Market dimension score")
    product_score: float = Field(default=0.0, description="Product dimension score")
    momentum_score: float = Field(default=0.0, description="Momentum dimension score")
    composite_score: float = Field(default=0.0, description="Weighted composite score")
    tier: str = Field(default="pass", description="Tier classification")
    score_breakdown_json: str | None = Field(default=None, description="JSON breakdown")

    @property
    def breakdown(self) -> dict:
        if self.score_breakdown_json:
            try:
                return json.loads(self.score_breakdown_json)
            except (json.JSONDecodeError, TypeError):
                pass
        return {}


class ThesisCriteria(BaseModel):
    """Investment thesis screening criteria."""
    min_arr: float = Field(default=0.0, description="Minimum ARR ($M)")
    max_arr: float = Field(default=1000.0, description="Maximum ARR ($M)")
    min_growth_pct: float = Field(default=0.0, description="Minimum revenue growth %")
    sectors: list[str] = Field(default_factory=list, description="Target sectors")
    geographies: list[str] = Field(default_factory=list, description="Target geographies")
    round_types: list[str] = Field(default_factory=list, description="Target round types")
    min_gross_margin_pct: float = Field(default=0.0, description="Minimum gross margin %")
    min_net_retention_pct: float = Field(default=0.0, description="Minimum net retention %")
