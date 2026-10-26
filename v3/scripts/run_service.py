from __future__ import annotations

import json
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from research_os_v3 import DataLayout, UnifiedMasterOrchestrator, V3LocalService
from research_os_v3.models import SCALE_PROFILES


def main() -> int:
    host = os.environ.get("RESEARCH_OS_V3_HOST", "127.0.0.1")
    port = int(os.environ.get("RESEARCH_OS_V3_PORT", "8788"))
    layout = DataLayout.from_environment().ensure()
    audit_path = layout.logs / "http-audit.jsonl"
    maximum = SCALE_PROFILES[-1]
    service = V3LocalService(host=host, port=port, audit_path=audit_path)
    server = service.build_server()
    port = service.port
    service_name = os.environ.get("RESEARCH_OS_V3_SERVICE_NAME", "ResearchOSV3Service")
    registry_path = Path(os.environ.get("RESEARCH_OS_V3_DATA_DIR", str(layout.root))) / "service.json"
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    registry = {
        "schema_version": 1,
        "service_name": service_name,
        "host": "127.0.0.1",
        "port": port,
        "health_path": "/health",
        "process_id": os.getpid(),
        "parent_process_id": os.getppid(),
        "process_started_at_utc": datetime.now(timezone.utc).isoformat(),
    }
    fd, temp_path = tempfile.mkstemp(prefix=".service-", suffix=".json.tmp", dir=registry_path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\\n") as stream:
            json.dump(registry, stream, sort_keys=True)
            stream.write("\\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp_path, registry_path)
    except Exception:
        try:
            os.unlink(temp_path)
        except OSError:
            pass
        service.shutdown()
        raise
    print(
        json.dumps(
            {
                "service": "research-os-v3-full-10x10",
                "service_name": service_name,
                "host": host,
                "port": port,
                "contract": UnifiedMasterOrchestrator.contract,
                "maximum_scale": maximum.tier.value,
                "maximum_logical_capacity": maximum.capacity,
                "capacity_policy": "lazy-bounded-execution",
                "data_root": str(layout.root),
                "http_audit": str(audit_path),
            },
            sort_keys=True,
        ),
        flush=True,
    )
    try:
        service.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        service.shutdown()
        try:
            current = json.loads(registry_path.read_text(encoding="utf-8"))
            if current.get("process_id") == os.getpid() and current.get("service_name") == service_name:
                registry_path.unlink(missing_ok=True)
        except (OSError, ValueError, TypeError):
            pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
