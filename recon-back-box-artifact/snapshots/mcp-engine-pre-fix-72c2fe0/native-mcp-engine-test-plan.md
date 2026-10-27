# Native MCP Engine — Validation Plan

Run from the repository root with Python 3.12+:

```powershell
python -m unittest discover -s tests -p "test_native_mcp_engine.py" -v
python -m unittest discover -s tests -v
```

## Required test cases

- inspect valid UTF-8 text and record SHA-256;
- diff changed text files and represent binary files without garbled decoding;
- reject absolute paths and traversal outside a configured root;
- reject files above the configured size limit;
- prove copy preview creates no file;
- copy into a new destination and compare source/destination SHA-256;
- refuse to overwrite an existing destination and preserve its bytes.

## Gate labels

- **PASS:** command/test completed and exact output is retained.
- **FAIL:** command/test ran and found a failure.
- **SKIPPED:** a required dependency or environment was intentionally unavailable.
- **UNKNOWN:** no run evidence exists or evidence cannot be tied to the tested commit.

A green unit test suite does not prove MCP wire-protocol interoperability or remote security.
