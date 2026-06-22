import json
import os

def save_artifact(run_id: str,
                  artifact: str,
                  data):

    path = f"runs/{run_id}"
    os.makedirs(path, exist_ok=True)

    with open(
        f"{path}/{artifact}.json",
        "w",
        encoding="utf-8"
    ) as f:
        json.dump(
            data,
            f,
            indent=2,
            default=str,
            ensure_ascii=False,
        )