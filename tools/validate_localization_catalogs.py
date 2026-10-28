#!/usr/bin/env python3
"""Validate translation catalogs against a source JSON catalog using stdlib only."""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


PLACEHOLDER = re.compile(r"\{([A-Za-z_][A-Za-z0-9_.-]*)\}")


class DuplicateKeyError(ValueError):
    """Raised when a JSON object repeats a key."""


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise DuplicateKeyError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def load_catalog(path: Path) -> dict[str, str]:
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"), object_pairs_hook=_unique_object)
    except (OSError, UnicodeError, json.JSONDecodeError, DuplicateKeyError) as exc:
        raise ValueError(f"{path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"{path}: expected a JSON object")
    invalid = [key for key, text in value.items() if not isinstance(key, str) or not isinstance(text, str)]
    if invalid:
        raise ValueError(f"{path}: all keys and values must be strings")
    return value


def placeholders(value: str) -> tuple[str, ...]:
    return tuple(sorted(PLACEHOLDER.findall(value)))


def validate(source: dict[str, str], target: dict[str, str]) -> list[str]:
    errors: list[str] = []
    for key, source_text in source.items():
        if key not in target:
            errors.append(f"missing key: {key}")
            continue
        target_text = target[key]
        if not target_text.strip():
            errors.append(f"empty translation: {key}")
        if placeholders(source_text) != placeholders(target_text):
            errors.append(f"placeholder mismatch: {key} (source={placeholders(source_text)}, target={placeholders(target_text)})")
    for key in target:
        if key not in source:
            errors.append(f"unknown key: {key}")
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True, help="Source catalog JSON")
    parser.add_argument("--target", type=Path, required=True, help="Target catalog JSON")
    args = parser.parse_args(argv)
    try:
        source = load_catalog(args.source)
        target = load_catalog(args.target)
    except ValueError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 2
    errors = validate(source, target)
    if errors:
        print(f"FAIL: {len(errors)} localization issue(s)")
        for error in errors:
            print(f"- {error}")
        return 1
    print(f"PASS: {len(source)} key(s); key set and placeholders match")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
