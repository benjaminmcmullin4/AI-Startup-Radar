from enum import Enum


class PipelineStage(str, Enum):
    NEW = "new"
    SCREENING = "screening"
    DEEP_DIVE = "deep_dive"
    IC_REVIEW = "ic_review"
    PASS = "pass"
    MONITOR = "monitor"

    @property
    def label(self) -> str:
        labels = {
            "new": "New",
            "screening": "Screening",
            "deep_dive": "Deep Dive",
            "ic_review": "IC Review",
            "pass": "Pass",
            "monitor": "Monitor",
        }
        return labels.get(self.value, self.value)
