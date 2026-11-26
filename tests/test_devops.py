"""Unit tests for Milestone 10 Cloud, Networking & AWS DevOps toolkit."""

import unittest
from unittest.mock import MagicMock, patch

from knobu.modules.powertools.devops import (
    calculate_cidr,
    get_docker_containers,
    get_kube_contexts,
    http_timing_probe,
    inspect_ssl_cert,
    query_dns,
    tcp_ping,
)


class TestDevopsToolkit(unittest.TestCase):
    def test_calculate_cidr_ipv4(self):
        ok, res, msg = calculate_cidr("192.168.1.0/24")
        self.assertTrue(ok)
        self.assertIsNotNone(res)
        self.assertEqual(res.network_address, "192.168.1.0")
        self.assertEqual(res.broadcast_address, "192.168.1.255")
        self.assertEqual(res.netmask, "255.255.255.0")
        self.assertEqual(res.total_ips, 256)
        self.assertEqual(res.usable_hosts, 254)
        self.assertEqual(res.first_host, "192.168.1.1")
        self.assertEqual(res.last_host, "192.168.1.254")

    def test_calculate_cidr_invalid(self):
        ok, res, msg = calculate_cidr("not-a-cidr")
        self.assertFalse(ok)
        self.assertIsNone(res)

    def test_query_dns_mocked(self):
        mock_output = "google.com. 300 IN A 142.250.193.14\ngoogle.com. 300 IN A 142.250.193.46\n"
        with patch("shutil.which", return_value="/usr/bin/dig"), \
             patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout=mock_output)
            ok, records, msg = query_dns("google.com", "A")
            self.assertTrue(ok)
            self.assertEqual(len(records), 2)
            self.assertEqual(records[0].record_type, "A")
            self.assertEqual(records[0].value, "142.250.193.14")
            self.assertEqual(records[0].ttl, 300)

    def test_tcp_ping_success_and_failure(self):
        with patch("socket.create_connection", return_value=MagicMock()):
            ok, ms, msg = tcp_ping("127.0.0.1", 80)
            self.assertTrue(ok)
            self.assertGreaterEqual(ms, 0)

        with patch("socket.create_connection", side_effect=ConnectionRefusedError("Connection refused")):
            ok, ms, msg = tcp_ping("127.0.0.1", 9999)
            self.assertFalse(ok)
            self.assertIn("refused", msg)

    def test_get_docker_containers_mock(self):
        mock_out = "a24db0f0cadd|beszel-agent|henrygd/beszel-agent|Up 9 hours|\n"
        with patch("shutil.which", return_value="/usr/bin/docker"), \
             patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout=mock_out)
            conts = get_docker_containers()
            self.assertEqual(len(conts), 1)
            self.assertEqual(conts[0].id, "a24db0f0cadd")
            self.assertEqual(conts[0].name, "beszel-agent")
            self.assertEqual(conts[0].image, "henrygd/beszel-agent")

    def test_get_kube_contexts_mock(self):
        with patch("shutil.which", return_value="/snap/bin/kubectl"), \
             patch("subprocess.run") as mock_run:
            mock_run.side_effect = [
                MagicMock(returncode=0, stdout="ctx-dev\nctx-prod\n"),
                MagicMock(returncode=0, stdout="ctx-dev\n"),
            ]
            cur, all_c = get_kube_contexts()
            self.assertEqual(cur, "ctx-dev")
            self.assertEqual(all_c, ["ctx-dev", "ctx-prod"])


if __name__ == "__main__":
    unittest.main()
