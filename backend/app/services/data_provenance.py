import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from app.schema.provenance_schema import DataProvenanceResponse


RESOURCE_ROOT = Path(__file__).resolve().parent.parent / "resources"
MANIFEST_PATH = RESOURCE_ROOT / "provenance" / "source_manifest.json"


def _record_count(path: Path) -> int | None:
    if path.suffix.lower() != ".json":
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, list):
        return len(data)
    if isinstance(data, dict):
        if isinstance(data.get("participants"), list):
            return len(data["participants"])
        return len(data)
    return None


def get_data_provenance() -> DataProvenanceResponse:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    sources = []
    for configured in manifest["sources"]:
        source = dict(configured)
        local_path = source.get("local_path")
        if local_path:
            snapshot = RESOURCE_ROOT / local_path
            content = snapshot.read_bytes()
            source.update({
                "snapshot_sha256": hashlib.sha256(content).hexdigest(),
                "snapshot_bytes": len(content),
                "record_count": _record_count(snapshot),
                "snapshot_modified_at": datetime.fromtimestamp(
                    snapshot.stat().st_mtime, tz=timezone.utc
                ).isoformat(),
            })
        sources.append(source)
    verified = sum(item["verification_status"] == "VERIFIED_LOCAL" for item in sources)
    return DataProvenanceResponse(
        manifest_version=manifest["version"],
        generated_at=datetime.now(timezone.utc).isoformat(),
        transparency_notice=(
            "当前参赛阵容是非官方情景快照。只有带 SHA-256 的本地快照可视为已采集证据；"
            "标记为待联网刷新的来源仅表示公开核验入口，不宣称已经抓取。"
        ),
        verified_local_sources=verified,
        pending_network_sources=len(sources) - verified,
        sources=sources,
    )
