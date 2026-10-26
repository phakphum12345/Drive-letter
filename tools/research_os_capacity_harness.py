"""Bounded, opt-in HTTP GET probe for a Research OS endpoint."""
import argparse
import concurrent.futures
import http.client
import json
import os
import platform
import sys
import time
from datetime import datetime, timezone
from urllib.parse import urlsplit, urlunsplit

# Direct script execution places the tools directory, not the repository root,
# on sys.path. This import therefore also works in the CI CLI smoke test.
from research_os_capacity_metrics import summarize_samples


def request_once(target, timeout):
    start = time.perf_counter()
    result = {"status": None, "error": None, "latency_ms": None}
    path = target.path or "/"
    if target.query:
        path += "?" + target.query
    try:
        if target.scheme == "https":
            connection = http.client.HTTPSConnection(target.hostname, target.port, timeout=timeout)
        else:
            connection = http.client.HTTPConnection(target.hostname, target.port, timeout=timeout)
        try:
            connection.request("GET", path)
            response = connection.getresponse()
            response.read(4096)
            result["status"] = response.status
            if not 200 <= response.status < 400:
                result["error"] = "http_status"
        finally:
            connection.close()
    except Exception as exc:
        result["error"] = type(exc).__name__
    result["latency_ms"] = round((time.perf_counter() - start) * 1000, 3)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", required=True, help="Explicit safe GET endpoint")
    parser.add_argument("--requests", type=int, default=100)
    parser.add_argument("--concurrency", type=int, default=5)
    parser.add_argument("--timeout", type=float, default=5)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    if not 1 <= args.requests <= 10000:
        parser.error("--requests must be in 1..10000")
    if not 1 <= args.concurrency <= 100:
        parser.error("--concurrency must be in 1..100")
    if not 0.1 <= args.timeout <= 60:
        parser.error("--timeout must be in 0.1..60 seconds")
    target = urlsplit(args.url)
    if target.scheme not in {"http", "https"} or not target.hostname:
        parser.error("--url must be an absolute http or https URL")
    if target.username or target.password:
        parser.error("credentials in URL are not allowed; use a secured local environment")

    started_at = datetime.now(timezone.utc).isoformat()
    started = time.perf_counter()
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.concurrency) as pool:
        samples = list(pool.map(lambda _: request_once(target, args.timeout), range(args.requests)))
    elapsed = time.perf_counter() - started
    evidence = {
        "schema_version": 1,
        "started_at_utc": started_at,
        "source_sha": os.environ.get("GITHUB_SHA", "not-provided"),
        "target_url": urlunsplit((target.scheme, target.netloc, target.path or "/", target.query, "")),
        "method": "GET",
        "workload": {
            "requests": args.requests,
            "concurrency": args.concurrency,
            "timeout_seconds": args.timeout,
        },
        "host": {"platform": platform.platform(), "python": sys.version.split()[0]},
        "summary": summarize_samples(samples, elapsed),
        "samples": samples,
        "resource_observation": {
            "server_process_cpu_memory": "NOT_COLLECTED",
            "note": "Runner-side measurements are not a substitute for isolated server-process telemetry.",
        },
        "limitations": [
            "Synthetic endpoint probe only; not a production capacity certification.",
            "Resource metrics for the server process are not collected by this runner.",
            "Define SLOs and run ramp, sustained, burst, and recovery profiles before claiming capacity.",
        ],
    }
    with open(args.output, "w", encoding="utf-8") as handle:
        json.dump(evidence, handle, indent=2, sort_keys=True)
        handle.write("\n")
    print(json.dumps({"summary": evidence["summary"], "output": args.output}, indent=2))
    return 0 if evidence["summary"]["requests_failed"] == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
