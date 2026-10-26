# Research OS Capacity Harness

Status: candidate specification.

## Purpose

Define a reproducible, bounded capacity test protocol for a Research OS endpoint. The harness must record the exact source SHA, endpoint, workload, concurrency, timeout, UTC start time, request outcomes, throughput, p50/p95/p99 latency, and raw evidence. Optional resource telemetry must identify whether it measures the server process or the test runner; these are not interchangeable.

## Safety boundaries

- Target only an explicitly supplied endpoint; default to no target and no execution.
- Use bounded request counts, concurrency, and timeouts.
- Do not perform destructive requests or mutate service state.
- Do not include credentials in output evidence.
- Do not claim production capacity from a health endpoint or synthetic load alone.

## Test profile

1. Baseline: low concurrency to establish reference latency and error rate.
2. Ramp: increase concurrency in defined steps.
3. Sustained: hold a declared load for a declared duration.
4. Burst: apply a short peak workload.
5. Recovery: reduce load and verify latency/error rate return to the agreed SLO.
6. Repeatability: repeat the same profile and compare outcomes.

## Required report

Include workload parameters, exact source SHA, machine/runtime details, successful and failed requests, HTTP status counts, timeout counts, throughput, p50/p95/p99 latency, CPU and memory measurement provenance, SLO pass/fail, and the path/hash of raw evidence.

## Acceptance

Capacity is reported only for the highest workload actually tested that satisfies the SLO, alongside the first tested workload that fails. Windows install/upgrade/uninstall and actual service-process resource measurement remain separate release gates. A CI-only synthetic test is not a substitute for Windows end-to-end evidence.
