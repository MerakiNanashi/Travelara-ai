# debug/snapshot.py
import json
from pathlib import Path
from typing import Any
from pydantic import BaseModel

class Debugger:
    def __init__(self, run_id: str, dir: str, enabled: bool = True,):
        self.run_id = run_id
        self.enabled = enabled
        self.dir: Path = dir

        if enabled:
            self.dir.mkdir(parents=True, exist_ok=True)

    def save_stage(
        self,
        stage_name: str,
        seq: int,
        data: BaseModel | list[BaseModel] | Any,
    ):
        if not self.enabled:
            return

        path = self.dir / f"{seq:02d}_{stage_name}.json"

        if isinstance(data, BaseModel):
            payload = data.model_dump(mode="json")

        elif isinstance(data, list):
            payload = [
                item.model_dump(mode="json") if isinstance(item, BaseModel) else item
                for item in data
            ]

        else:
            payload = data

        path.write_text(
            json.dumps(payload, indent=2, default=str),
            encoding="utf-8",
        )

    def report(self, name: str, data: dict):
        if not self.enabled:
            return

        print(f"\n=== {name.upper()} ===")
        for k, v in data.items():
            print(f"{k}: {v}")

        (self.dir / f"{name}.json").write_text(
            json.dumps(data, indent=2, default=str),
            encoding="utf-8",
        )

# def instrumented(stage_name: str):
#     def deco(fn):
#         @functools.wraps(fn)
#         def wrapper(ctx: PipelineContext, *a, **kw):
#             t0 = time.perf_counter()
#             result = fn(ctx, *a, **kw)
#             report = StageReport(
#                 stage=stage_name,
#                 input_count=len(ctx.pois),
#                 output_count=len(result.pois),
#                 duration_ms=(time.perf_counter() - t0) * 1000,
#             )
#             ctx.debugger.report(stage_name, report)
#             ctx.debugger.save_stage(stage_name, ctx.metadata.step, result.pois)
#             return result
#         return wrapper
#     return deco