import argparse
import csv
import re
import socket
import subprocess
import time
from datetime import datetime
from pathlib import Path


LOG_FILE = Path(__file__).with_name("diag_log.csv")


def run(command):
    try:
        result = subprocess.run(
            command, capture_output=True, text=True,
            encoding="cp866", errors="replace", timeout=15
        )
        return result.stdout
    except (OSError, subprocess.TimeoutExpired):
        return ""


def ping(host):
    if not host:
        return False, None

    output = run(["ping", "-n", "3", "-w", "1000", host])
    matches = re.findall(
        r"(?:time|время)\s*([=<])\s*(\d+(?:[.,]\d+)?)\s*(?:ms|мс)",
        output,
        flags=re.IGNORECASE,
    )
    if not matches:
        return False, None

    times = [
        0.0 if sign == "<" else float(value.replace(",", "."))
        for sign, value in matches
    ]
    return True, round(sum(times) / len(times), 2)


def get_default_route():
    routes = []
    for line in run(["route", "print", "-4", "0.0.0.0"]).splitlines():
        fields = line.split()
        if len(fields) == 5 and fields[:2] == ["0.0.0.0", "0.0.0.0"]:
            gateway, local_ip, metric = fields[2:]
            if metric.isdecimal():
                routes.append((int(metric), gateway, local_ip))

    if routes:
        _, gateway, local_ip = min(routes)
        return gateway, local_ip
    return None, None


def resolve(domain):
    try:
        socket.gethostbyname(domain)
        return True, None
    except OSError:
        return False, None


def tcp_check(host, port):
    start = time.perf_counter()
    try:
        with socket.create_connection((host, port), timeout=3):
            return True, round((time.perf_counter() - start) * 1000, 2)
    except OSError:
        return False, None


def log_result(local_ip, step, status, ms):
    write_header = not LOG_FILE.exists() or LOG_FILE.stat().st_size == 0
    with LOG_FILE.open("a", encoding="utf-8", newline="") as file:
        writer = csv.writer(file)
        if write_header:
            writer.writerow(["datetime", "hostname", "local_ip", "step", "status", "ms"])
        writer.writerow([
            datetime.now().isoformat(timespec="seconds"),
            socket.gethostname(), local_ip, step, status, ms,
        ])


def main(gateway=None, domain="google.com"):
    detected_gateway, local_ip = get_default_route()
    gateway = gateway or detected_gateway
    print(f"Локальный IP: {local_ip or 'нет'} | Шлюз: {gateway or 'нет'}")

    steps = [
        ("Стек TCP/IP", lambda: ping("127.0.0.1"), ()),
        ("Собственный интерфейс", lambda: ping(local_ip), (
            "Проверь адрес интерфейса командой ipconfig /all",
            "Проверь подключение Wi-Fi командой netsh wlan show interfaces",
        )),
        ("Шлюз по умолчанию", lambda: ping(gateway), (
            "Сверь шлюз по команде route print -4 0.0.0.0",
            f"Проверь ответ шлюза командой ping -n 3 {gateway or '<IP шлюза>'}",
        )),
        ("Внешняя сеть (8.8.8.8)", lambda: ping("8.8.8.8"), (
            "Проверь маршрут командой tracert -d 8.8.8.8",
            "Проверь исходящий TCP командой Test-NetConnection 8.8.8.8 -Port 53",
        )),
        (f"DNS ({domain})", lambda: resolve(domain), (
            f"Проверь разрешение имени командой nslookup {domain}",
            "Посмотри настроенные DNS-серверы командой ipconfig /all",
        )),
        ("Веб-сервис (google.com:443)", lambda: tcp_check("google.com", 443), (
            "Проверь порт командой Test-NetConnection google.com -Port 443",
            "Посмотри настройки системного прокси командой netsh winhttp show proxy",
        )),
    ]

    for name, check, advice in steps:
        ok, ms = check()
        status = "OK" if ok else "FAIL"
        log_result(local_ip, name, status, ms)
        timing = f" — {ms} мс" if ms is not None else ""
        print(f"[{status}] {name}{timing}")

        if not ok:
            print(f"Диагностика остановлена на шаге «{name}».")
            for tip in advice:
                print(f"  - {tip}")
            return 1

    print("Все проверки пройдены.")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Диагностика подключения")
    parser.add_argument("--gateway", help="Шлюз для проверки вручную")
    parser.add_argument("--domain", default="google.com", help="Домен для проверки DNS")
    args = parser.parse_args()
    raise SystemExit(main(args.gateway, args.domain))