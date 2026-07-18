from __future__ import annotations

import re
from pathlib import Path

from src.shared.schemas import PlanningState


class RunResumer:
    def __init__(self, runs_dir: Path):
        self.runs_dir = runs_dir

    def latest_snapshot(
        self,
        seed_id: str,
    ) -> tuple[int, PlanningState] | None:

        run_dir = self.runs_dir / seed_id

        if not run_dir.exists():
            return None

        latest_seq = -1
        latest_file: Path | None = None

        for path in run_dir.glob("*.json"):
            match = re.match(r"(\d+)_", path.stem)
            if not match:
                continue

            seq = int(match.group(1))

            if seq > latest_seq:
                latest_seq = seq
                latest_file = path

        if latest_file is None:
            return None

        state = PlanningState.model_validate_json(
            latest_file.read_text(encoding="utf-8")
        )

        return latest_seq, state