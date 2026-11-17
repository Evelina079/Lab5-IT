import csv
import ipaddress


def subnet_info(cidr):
    interface = ipaddress.IPv4Interface(cidr)
    ip = interface.ip
    network = interface.network
    has_hosts = network.num_addresses > 2

    if ip.is_loopback:
        address_type = "loopback"
    elif ip.is_link_local:
        address_type = "link-local"
    elif ip.is_multicast:
        address_type = "multicast"
    elif ip.is_private:
        address_type = "частный"
    else:
        address_type = "публичный"

    return {
        "Адрес узла": str(ip),
        "Адрес сети": str(network.network_address),
        "Маска": str(network.netmask),
        "Префикс": f"/{network.prefixlen}",
        "Broadcast": str(network.broadcast_address),
        "Первый узел": str(network.network_address + 1) if has_hosts else "-",
        "Последний узел": str(network.broadcast_address - 1) if has_hosts else "-",
        "Количество узлов": network.num_addresses - 2 if has_hosts else 0,
        "Wildcard": str(network.hostmask),
        "Маска (двоичная)": ".".join(f"{octet:08b}" for octet in network.netmask.packed),
        "Тип адреса": address_type,
    }


def parse_cidr(text):
    text = text.strip()

    if "/" in text:
        address, mask = (part.strip() for part in text.split("/", 1))
    else:
        parts = text.split()
        if len(parts) == 1:
            ipaddress.IPv4Address(parts[0])
            raise ValueError("не указана маска")
        if len(parts) != 2:
            raise ValueError("введите IPv4-адрес и маску")
        address, mask = parts

    if not mask:
        raise ValueError("не указана маска")

    return ipaddress.IPv4Interface(f"{address}/{mask}")


def same_subnet(a, b):
    network = parse_cidr(a).network
    return ipaddress.IPv4Address(b.strip()) in network

def with_growth(need, growth):
    return (need * (100 + growth) + 99) // 100


def vlsm(base_network, departments, growth=0):
    base = ipaddress.IPv4Network(base_network, strict=False)
    if growth < 0 or not departments or any(need < 1 for need in departments.values()):
        raise ValueError("Укажите отделы с положительным числом устройств и запас от 0%")

    plan = []
    current = int(base.network_address)

    for name, need in sorted(departments.items(), key=lambda item: item[1], reverse=True):
        need_g = with_growth(need, growth)
        block_size = 1 << (need_g + 1).bit_length()

        if current + block_size - 1 > int(base.broadcast_address):
            raise ValueError(f"Не хватает адресов для отдела «{name}»")

        prefix = 32 - (block_size.bit_length() - 1)
        subnet = ipaddress.IPv4Network((current, prefix))
        plan.append({"name": name, "need": need, "need_g": need_g, "subnet": subnet})
        current += block_size

    return plan


def plan_summary(base_network, plan):
    base = ipaddress.IPv4Network(base_network, strict=False)
    allocated = sum(row["subnet"].num_addresses for row in plan)
    devices = sum(row["need"] for row in plan)
    return {
        "Всего адресов": base.num_addresses,
        "Выделено": allocated,
        "Свободно": base.num_addresses - allocated,
        "Использование, %": round(devices * 100 / allocated, 2) if allocated else 0,
    }


def check_plan(base_network, plan):
    base = ipaddress.IPv4Network(base_network, strict=False)
    errors = []

    for index, row in enumerate(plan):
        subnet = row["subnet"]
        if not subnet.subnet_of(base):
            errors.append(f"{row['name']}: {subnet} выходит за пределы {base}")

        for earlier in plan[:index]:
            if subnet.overlaps(earlier["subnet"]):
                errors.append(f"Подсети отделов «{earlier['name']}» и «{row['name']}» пересекаются")

    return errors


def min_base_prefix(base_network, departments, growth=0):
    base = ipaddress.IPv4Network(base_network, strict=False)

    for prefix in range(base.prefixlen, -1, -1):
        candidate = ipaddress.IPv4Network((base.network_address, prefix), strict=False)
        try:
            vlsm(candidate, departments, growth)
        except ValueError:
            continue
        return candidate

    return None


def summarize(plan):
    subnets = [row["subnet"] for row in plan]
    if not subnets:
        return [], None

    exact_routes = list(ipaddress.collapse_addresses(subnets))
    common = subnets[0]
    while not all(subnet.subnet_of(common) for subnet in subnets):
        common = common.supernet()

    return exact_routes, common


def save_plan_csv(plan, path):
    with open(path, "w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(["department", "need", "need_with_growth", "subnet", "gateway", "broadcast"])
        for row in plan:
            subnet = row["subnet"]
            writer.writerow([
                row["name"], row["need"], row["need_g"], subnet,
                subnet.network_address + 1, subnet.broadcast_address,
            ])


def show_plan(base, departments, growth, filename):
    base = ipaddress.IPv4Network(base, strict=False)
    if growth < 0 or not departments or any(need < 1 for need in departments.values()):
        raise ValueError("Укажите отделы с положительным числом устройств и запас от 0%")

    try:
        plan = vlsm(base, departments, growth)
    except ValueError as error:
        print(f"Ошибка: {error}")
        larger = min_base_prefix(base, departments, growth)
        if larger is None:
            print("План не помещается даже в IPv4-сеть /0.")
        else:
            print(f"Предлагаемая сеть: {larger}")
        return 1

    print("\nОтдел | Устройств | С запасом | Подсеть | Шлюз | Диапазон | Broadcast")
    for row in plan:
        subnet = row["subnet"]
        first = subnet.network_address + 1
        last = subnet.broadcast_address - 1
        print(
            f"{row['name']} | {row['need']} | {row['need_g']} | {subnet} | "
            f"{first} | {first}–{last} | {subnet.broadcast_address}"
        )

    for label, value in plan_summary(base, plan).items():
        print(f"{label}: {value}")

    errors = check_plan(base, plan)
    print("Проверка плана:", "; ".join(errors) if errors else "ошибок нет")

    exact, common = summarize(plan)
    print("Точная агрегация:", ", ".join(map(str, exact)))
    print("Общая надсеть:", common)

    save_plan_csv(plan, filename)
    print(f"План сохранён в {filename}")

    return 0


def plan_menu():
    base = input("Базовая сеть: ").strip()
    growth = int(input("Запас роста, %: "))
    text = input("Отделы в формате Название=число через запятую: ")

    departments = {}
    for item in text.split(","):
        name, separator, count = item.partition("=")
        name = name.strip()
        if not separator or not name or name in departments:
            raise ValueError("Введите уникальные отделы в формате Название=число")
        departments[name] = int(count.strip())

    show_plan(base, departments, growth, "plan_v5.csv")

def main():
    try:
        while True:
            print("\n==== Сетевой калькулятор ====")
            print("1 - Информация о подсети")
            print("2 - Находятся ли два узла в одной подсети")
            print("3 - План VLSM для своего варианта")
            print("0 - Выход")

            choice = input("Ваш выбор: ").strip()

            try:
                if choice == "1":
                    address = parse_cidr(input("Введите IP-адрес с маской: "))
                    for label, value in subnet_info(address).items():
                        print(f"{label}: {value}")
                elif choice == "2":
                    first = input("Введите первый IP-адрес с маской: ")
                    second = input("Введите второй IP-адрес без маски: ")
                    if same_subnet(first, second):
                        print("Узлы находятся в одной подсети.")
                    else:
                        print("Узлы находятся в разных подсетях.")
                elif choice == "3":
                    plan_menu()
                elif choice == "0":
                    break
                else:
                    print("Выберите пункт 0, 1, 2 или 3.")
            except ValueError as error:
                print(f"Ошибка: {error}")
    except (KeyboardInterrupt, EOFError):
        print()

    print("Работа завершена")


if __name__ == "__main__":
    main()