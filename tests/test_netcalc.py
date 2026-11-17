import ipaddress
import unittest

import audit
import netcalc


class TestSubnetInfo(unittest.TestCase):
    def test_slash24(self):
        info = netcalc.subnet_info("192.168.10.35/24")
        self.assertEqual(info["Адрес сети"], "192.168.10.0")
        self.assertEqual(info["Broadcast"], "192.168.10.255")
        self.assertEqual(info["Количество узлов"], 254)

    def test_slash30(self):
        info = netcalc.subnet_info("10.0.0.5/30")
        self.assertEqual(info["Количество узлов"], 2)
        self.assertEqual(info["Первый узел"], "10.0.0.5")
        self.assertEqual(info["Последний узел"], "10.0.0.6")

    def test_slash32(self):
        info = netcalc.subnet_info("8.8.8.8/32")
        self.assertEqual(info["Количество узлов"], 0)
        self.assertEqual(info["Первый узел"], "-")

    def test_address_types(self):
        self.assertEqual(netcalc.subnet_info("169.254.1.5/16")["Тип адреса"], "link-local")
        self.assertEqual(netcalc.subnet_info("8.8.8.8/32")["Тип адреса"], "публичный")

    def test_both_input_formats(self):
        self.assertEqual(
            netcalc.parse_cidr("10.0.0.5/26"),
            netcalc.parse_cidr("10.0.0.5 255.255.255.192"),
        )

    def test_invalid_address(self):
        with self.assertRaises(ValueError):
            netcalc.parse_cidr("192.168.1.300/24")


class TestVlsm(unittest.TestCase):
    def test_growth(self):
        self.assertEqual(netcalc.with_growth(60, 10), 66)

    def test_variant_5_plan(self):
        base = "172.20.0.0/23"
        departments = {"IT": 20, "Колл-центр": 200, "Менеджеры": 70}
        plan = netcalc.vlsm(base, departments, growth=25)
        subnets = [row["subnet"] for row in plan]

        self.assertEqual([subnet.prefixlen for subnet in subnets], [24, 25, 27])
        self.assertEqual(str(subnets[0].network_address), "172.20.0.0")
        self.assertEqual(netcalc.check_plan(base, plan), [])

    def test_not_enough_addresses(self):
        with self.assertRaises(ValueError):
            netcalc.vlsm("10.0.0.0/26", {"A": 50, "B": 30})

    def test_min_base_prefix(self):
        result = netcalc.min_base_prefix("10.0.0.0/26", {"A": 50, "B": 30})
        self.assertEqual(str(result), "10.0.0.0/25")


class TestAudit(unittest.TestCase):
    def test_duplicate_and_broadcast(self):
        plan = {"IT": ipaddress.IPv4Network("10.0.0.0/24")}
        devices = [
            {"hostname": "pc-01", "department": "IT", "ip": "10.0.0.10", "gateway": "10.0.0.1"},
            {"hostname": "pc-02", "department": "IT", "ip": "10.0.0.10", "gateway": "10.0.0.1"},
            {"hostname": "pc-03", "department": "IT", "ip": "10.0.0.255", "gateway": "10.0.0.1"},
        ]

        found = {(host, code) for host, code, _ in audit.audit(plan, devices)}
        self.assertEqual(found, {("pc-02", "E5"), ("pc-03", "E4")})