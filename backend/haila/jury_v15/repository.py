from __future__ import annotations

import json
from pathlib import Path
from threading import Lock
from typing import Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


class JsonObjectRepository(Generic[T]):
    def __init__(self, path: Path, model: type[T]) -> None:
        self.path = path
        self.model = model
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = Lock()

    def _read_all(self) -> list[T]:
        if not self.path.exists():
            return []
        data = json.loads(self.path.read_text(encoding="utf-8"))
        return [self.model.model_validate(item) for item in data]

    def _write_all(self, items: list[T]) -> None:
        self.path.write_text(
            json.dumps(
                [item.model_dump(mode="json") for item in items],
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

    def list(self) -> list[T]:
        with self._lock:
            return self._read_all()

    def get(self, object_id: str) -> T:
        with self._lock:
            for item in self._read_all():
                if getattr(item, "id") == object_id:
                    return item
        raise KeyError(object_id)

    def upsert(self, item: T) -> T:
        with self._lock:
            items = self._read_all()
            replaced = False
            for index, current in enumerate(items):
                if getattr(current, "id") == getattr(item, "id"):
                    items[index] = item
                    replaced = True
                    break
            if not replaced:
                items.append(item)
            self._write_all(items)
        return item
