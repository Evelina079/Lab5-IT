import socket
import time
from concurrent.futures import ThreadPoolExecutor
from functools import partial


SERVICES = [
    ("Google HTTPS", "google.com", 443),
    ("GitHub SSH", "github.com", 22),
    ("Google DNS", "8.8.8.8", 53),
    ("Cloudflare DNS", "1.1.1.1", 53),
    ("Локальный веб-сервер", "127.0.0.1", 8050),
    ("Закрытый локальный порт", "127.0.0.1", 8051),
    ("Несуществующий домен", "no-such-host.example", 80),
    ("Фильтруемый адрес", "10.255.255.1", 80),
    ("КБТУ HTTPS", "kbtu.edu.kz", 443),
    ("Gmail IMAP", "imap.gmail.com", 993),
    ("Wikipedia HTTPS", "wikipedia.org", 443),
    ("Python HTTPS", "python.org", 443),
]


def check_service(name, host, port, timeout=3):
    start = time.perf_counter()
    addresses = []

    try:
        records = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
        addresses = sorted({record[4][0] for record in records})

        with socket.create_connection((host, port), timeout=timeout):
            status = "OPEN"
    except socket.gaierror:
        status = "DNS-ERROR"
    except ConnectionRefusedError:
        status = "REFUSED"
    except TimeoutError:
        status = "TIMEOUT"
    except OSError:
        status = "ERROR"

    return {
        "name": name,
        "host": host,
        "port": port,
        "status": status,
        "ms": round((time.perf_counter() - start) * 1000, 1),
        "addresses": addresses,
    }


def check_all_sequential(services, timeout=3):
    return [check_service(*service, timeout=timeout) for service in services]


def check_all_parallel(services, workers=10, timeout=3):
    check = partial(check_service, timeout=timeout)
    with ThreadPoolExecutor(max_workers=workers) as pool:
        return list(pool.map(lambda service: check(*service), services))


def print_table(results):
    print(f"{'Сервис':26} {'Узел':26} {'Порт':>5} {'Статус':10} {'мс':>8}  IP")
    for row in results:
        print(
            f"{row['name']:26} {row['host']:26} {row['port']:>5} "
            f"{row['status']:10} {row['ms']:>8}  {len(row['addresses'])}"
        )


def measure(check, *args):
    start = time.perf_counter()
    results = check(*args)
    return results, time.perf_counter() - start


if __name__ == "__main__":
    results, elapsed = measure(check_all_sequential, SERVICES)
    print_table(results)

    print("\nРежим          Время, с")
    print(f"Последовательно {elapsed:>8.2f}")

    for workers in (1, 2, 5, 10, 20):
        _, elapsed = measure(check_all_parallel, SERVICES, workers)
        print(f"workers = {workers:<2}    {elapsed:>8.2f}")