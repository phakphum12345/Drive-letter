from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tools.research_os_api.runtime_endpoint_registry import (
    endpoint_path,
    publish_endpoint,
    read_endpoint,
    remove_endpoint,
)


class RuntimeEndpointRegistryTests(unittest.TestCase):
    def test_services_publish_independent_atomic_records(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            api = publish_endpoint("api", "127.0.0.1", 43121, directory=temporary, pid=101)
            friend = publish_endpoint("friend", "127.0.0.1", 43122, directory=temporary, pid=102)

            self.assertEqual(api["url"], "http://127.0.0.1:43121")
            self.assertEqual(friend["url"], "http://127.0.0.1:43122")
            self.assertEqual(read_endpoint("api", directory=temporary)["pid"], 101)
            self.assertEqual(read_endpoint("friend", directory=temporary)["pid"], 102)
            self.assertTrue(endpoint_path("api", temporary).is_file())
            self.assertTrue(endpoint_path("friend", temporary).is_file())

    def test_rejects_non_loopback_and_invalid_ports(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            for host, port in (("0.0.0.0", 43121), ("192.0.2.10", 43121), ("127.0.0.1", 0), ("127.0.0.1", 65536)):
                with self.subTest(host=host, port=port):
                    with self.assertRaises(ValueError):
                        publish_endpoint("api", host, port, directory=temporary)

    def test_invalid_or_mismatched_registry_record_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = endpoint_path("api", temporary)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps({
                "schema_version": 1,
                "service": "api",
                "host": "0.0.0.0",
                "port": 43121,
                "url": "http://0.0.0.0:43121",
                "pid": 101,
            }), encoding="utf-8")
            self.assertIsNone(read_endpoint("api", directory=temporary))


    def test_developer_endpoint_is_atomic_and_pid_owned(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            record = publish_endpoint(
                "developer", "127.0.0.1", 43127, directory=temporary, pid=4242
            )
            self.assertEqual("developer", record["service"])
            self.assertEqual("http://127.0.0.1:43127", record["url"])
            self.assertEqual(4242, read_endpoint("developer", directory=temporary)["pid"])
            self.assertFalse(
                remove_endpoint("developer", directory=temporary, expected_pid=99)
            )
            self.assertTrue(
                remove_endpoint("developer", directory=temporary, expected_pid=4242)
            )
            self.assertIsNone(read_endpoint("developer", directory=temporary))

    def test_ipv6_loopback_url_is_bracketed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            record = publish_endpoint(
                "api", "::1", 43128, directory=temporary, pid=4243
            )
            self.assertEqual("http://[::1]:43128", record["url"])
            self.assertEqual(record, read_endpoint("api", directory=temporary))

    def test_cleanup_is_pid_scoped_and_does_not_remove_new_owner_record(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            publish_endpoint("friend", "127.0.0.1", 43122, directory=temporary, pid=202)
            self.assertFalse(remove_endpoint("friend", directory=temporary, expected_pid=201))
            self.assertIsNotNone(read_endpoint("friend", directory=temporary))
            self.assertTrue(remove_endpoint("friend", directory=temporary, expected_pid=202))
            self.assertIsNone(read_endpoint("friend", directory=temporary))


if __name__ == "__main__":
    unittest.main()
