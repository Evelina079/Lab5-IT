import argparse

import audit
import netcalc
import netdiag
import services


def cmd_calc(args):
    address = netcalc.parse_cidr(args.address)
    for label, value in netcalc.subnet_info(address).items():
        print(f"{label}: {value}")
    return 0


def cmd_vlsm(args):
    departments = {}
    for item in args.departments:
        name, separator, count = item.partition("=")
        name = name.strip()
        if not separator or not name or name in departments:
            raise ValueError("Укажите уникальные отделы в формате Название=число")
        departments[name] = int(count)

    return netcalc.show_plan(args.base, departments, args.growth, args.csv)


def cmd_audit(args):
    devices = audit.load_devices(args.devices)
    problems = audit.audit(audit.load_plan(args.plan), devices)
    audit.print_results(devices, problems)
    audit.save_report(problems, args.report)
    print(f"Результаты сохранены в {args.report}")
    return int(any(code.startswith("E") for _, code, _ in problems))


def cmd_diag(args):
    return netdiag.main(gateway=args.gateway)


def cmd_services(args):
    if args.workers < 1 or args.timeout <= 0:
        raise ValueError("Число потоков и таймаут должны быть больше нуля")

    if args.parallel:
        results = services.check_all_parallel(
            services.SERVICES, workers=args.workers, timeout=args.timeout
        )
    else:
        results = services.check_all_sequential(
            services.SERVICES, timeout=args.timeout
        )

    services.print_table(results)
    return int(any(row["status"] != "OPEN" for row in results))


def main():
    parser = argparse.ArgumentParser(description="Сетевые утилиты ЛР5")
    commands = parser.add_subparsers(dest="command", required=True)

    calc = commands.add_parser("calc", help="расчёт подсети")
    calc.add_argument("address", help="IPv4 с префиксом или маской")
    calc.set_defaults(func=cmd_calc)

    vlsm = commands.add_parser("vlsm", help="планирование подсетей")
    vlsm.add_argument("base", help="базовая сеть")
    vlsm.add_argument("departments", nargs="+", help="отделы в формате Название=число")
    vlsm.add_argument("--growth", type=int, default=0, help="запас роста в процентах")
    vlsm.add_argument("--csv", default="plan_v5.csv", help="файл для сохранения плана")
    vlsm.set_defaults(func=cmd_vlsm)

    audit_parser = commands.add_parser("audit", help="аудит IP-адресов")
    audit_parser.add_argument("plan")
    audit_parser.add_argument("devices")
    audit_parser.add_argument("--report", default="audit_report.csv")
    audit_parser.set_defaults(func=cmd_audit)

    diag = commands.add_parser("diag", help="диагностика сети")
    diag.add_argument("--gateway", help="IP шлюза для проверки")
    diag.set_defaults(func=cmd_diag)

    service_parser = commands.add_parser("services", help="проверка сервисов")
    service_parser.add_argument("--parallel", action="store_true")
    service_parser.add_argument("--workers", type=int, default=10)
    service_parser.add_argument("--timeout", type=float, default=3)
    service_parser.set_defaults(func=cmd_services)

    args = parser.parse_args()
    try:
        return args.func(args)
    except (ValueError, OSError, KeyError) as error:
        print(f"Ошибка: {error}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())