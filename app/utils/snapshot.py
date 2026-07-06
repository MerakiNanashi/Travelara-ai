# debug/snapshot.py
import json
from pydantic import BaseModel
from pathlib import Path

class Debugger:
    def __init__(self, run_id: str, enabled: bool = True):
        self.run_id = run_id
        self.enabled = enabled
        self.dir = Path("runs") / run_id
        if enabled:
            self.dir.mkdir(parents=True, exist_ok=True)

    def save_stage(self, stage_name: str, seq: int, data: BaseModel | list[BaseModel]):
        if not self.enabled:
            return
        path = self.dir / f"{seq:02d}_{stage_name}.json"
        payload = [d.model_dump(mode="json") for d in data] if isinstance(data, list) else data.model_dump(mode="json")
        path.write_text(json.dumps(payload, indent=2, default=str))

    def report(self, name: str, data: dict):
        if not self.enabled:
            return

        print(f"\n=== {name.upper()} ===")
        for k, v in data.items():
            print(f"{k}: {v}")

        (self.dir / f"{name}.json").write_text(
            json.dumps(data, indent=2, default=str)
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

debugger = Debugger(
    run_id="default",
    enabled=True,
)