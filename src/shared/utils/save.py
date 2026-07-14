import json
import os
from datetime import datetime, date
from enum import Enum
from uuid import UUID
from dataclasses import is_dataclass, asdict

from pydantic import BaseModel


def _serialize(obj):
    if isinstance(obj, BaseModel):
        return obj.model_dump(mode="json")

    if is_dataclass(obj):
        return asdict(obj)

    if isinstance(obj, Enum):
        return obj.value

    if isinstance(obj, (datetime, date)):
        return obj.isoformat()

    if isinstance(obj, UUID):
        return str(obj)

    if isinstance(obj, (set, tuple)):
        return list(obj)

    if hasattr(obj, "__dict__"):
        return vars(obj)

    raise TypeError(
        f"Object of type {type(obj).__name__} "
        "is not JSON serializable"
    )


def save_artifact(
    run_id: str,
    artifact: str,
    data,
):
    path = f"runs/{run_id}"
    os.makedirs(path, exist_ok=True)

    with open(
        f"{path}/{artifact}.json",
        "w",
        encoding="utf-8",
    ) as f:
        json.dump(
            data,
            f,
            indent=2,
            ensure_ascii=False,
            default=_serialize,
        )