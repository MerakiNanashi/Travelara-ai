from pydantic import BaseModel, Field
from typing import Any

class StageReport(BaseModel):
    stage: str
    input_count: int
    output_count: int
    duration_ms: float
    extra: dict[str, Any] = Field(default_factory=dict)

    def pretty(self) -> str:
        drop_pct = 100 * (1 - self.output_count / max(self.input_count, 1))
        lines = [
            f"── {self.stage} ──",
            f"  in={self.input_count}  out={self.output_count}  ({drop_pct:.0f}% dropped)  {self.duration_ms:.0f}ms",
        ]
        lines += [f"  {k}={v}" for k, v in self.extra.items()]
        return "\n".join(lines)