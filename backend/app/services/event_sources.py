"""Adapters that normalize maintainable event data sources."""

from __future__ import annotations

import csv
import io
import json
from typing import Protocol


class EventSource(Protocol):
    def parse(self, filename: str, content: bytes) -> list[dict]: ...


class FileEventSource:
    """Parse UTF-8 CSV or JSON event files into dictionaries."""

    def parse(self, filename: str, content: bytes) -> list[dict]:
        text = content.decode("utf-8-sig")
        lower_name = filename.lower()
        if lower_name.endswith(".csv"):
            return [dict(row) for row in csv.DictReader(io.StringIO(text))]
        if lower_name.endswith(".json"):
            data = json.loads(text)
            if not isinstance(data, list):
                raise ValueError("JSON 文件顶层必须是事件数组")
            if not all(isinstance(item, dict) for item in data):
                raise ValueError("JSON 数组中的每一项必须是对象")
            return data
        raise ValueError("仅支持 CSV 或 JSON 文件")
