import csv
import ipaddress
import sys


def load_plan(path):
    with open(path, encoding="utf-8-sig", newline="") as file:
        return {
            row["department"]: ipaddress.IPv4Network(row["subnet"])
            for row in csv.DictReader(file)
        }


def load_devices(path):
    with open(path, encoding="utf-8-sig", newline="") as file:
        return list(csv.DictReader(file))


def audit(plan, devices):
    problems = []
    seen_ips = {}

    for device in devices:
        host = device["hostname"]
        department = device["department"]

        try:
            ip = ipaddress.IPv4Address(device["ip"].strip())
        except ValueError:
            problems.append((host, "E1", f"Неверный IP: {device['ip']}"))
            continue

        if ip in seen_ips:
            problems.append((host, "E5", f"IP {ip} уже занят устройством {seen_ips[ip]}"))
        else:
            seen_ips[ip] = host

        network = plan.get(department)
        if network is None:
            problems.append((host, "E2", f"Неизвестный отдел: {department}"))
        else:
            if ip not in network:
                problems.append((host, "E3", f"IP {ip} вне подсети отдела {network}"))
            elif ip in (network.network_address, network.broadcast_address):
                problems.append((host, "E4", f"IP {ip} совпадает с адресом сети или broadcast"))

        try:
            gateway = ipaddress.IPv4Address(device["gateway"].strip())
        except ValueError:
            problems.append((host, "E1", f"Неверный шлюз: {device['gateway']}"))
            continue

        if network is None:
            continue

        if gateway not in network:
            problems.append((host, "E6", f"Шлюз {gateway} вне подсети {network}"))
        elif gateway == ip:
            problems.append((host, "E7", f"Шлюз {gateway} совпадает с IP устройства"))
        elif gateway != network.network_address + 1:
            problems.append((host, "W1", f"Шлюз {gateway} отличается от первого адреса подсети"))

    return problems


def save_report(problems, path):
    with open(path, "w", encoding="utf-8-sig", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(["hostname", "code", "description"])
        writer.writerows(problems)


def print_results(devices, problems):
    for host, code, description in problems:
        print(f"[{code}] {host}: {description}")

    errors = sum(code.startswith("E") for _, code, _ in problems)
    warnings = sum(code.startswith("W") for _, code, _ in problems)
    flagged = {host for host, _, _ in problems}
    clean = sum(device["hostname"] not in flagged for device in devices)

    print(f"\nПроверено устройств: {len(devices)}")
    print(f"Ошибок: {errors}, предупреждений: {warnings}, без замечаний: {clean}")


if __name__ == "__main__":
    plan_path = sys.argv[1] if len(sys.argv) > 1 else "plan_v5.csv"
    devices_path = sys.argv[2] if len(sys.argv) > 2 else "devices.csv"

    devices = load_devices(devices_path)
    problems = audit(load_plan(plan_path), devices)
    print_results(devices, problems)
    save_report(problems, "audit_report.csv")
    print("Результаты сохранены в audit_report.csv")