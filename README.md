# Лабораторная работа №5. Сетевые утилиты на Python

Белашова Эвелина Валерьевна, вариант 5.

## Файлы проекта

- `netcalc.py` — расчёт подсетей, интерактивное меню и планирование VLSM.
- `audit.py` — проверка IP-адресов и шлюзов устройств по плану.
- `netdiag.py` — диагностика подключения в Windows и запись в CSV.
- `services.py` — последовательная и параллельная проверка TCP-сервисов.
- `netkit.py` — общий интерфейс командной строки.
- `tests/` — 11 модульных тестов.

## Примеры запуска

```powershell
python netkit.py calc 172.20.0.10/24
python netkit.py vlsm 172.20.0.0/23 "Колл-центр=200" "Менеджеры=70" "IT=20" --growth 25 --csv plan_v5.csv
python netkit.py audit plan_v5.csv devices.csv --report audit_report.csv
python netkit.py diag
python netkit.py services --parallel --workers 5 --timeout 3
```

## Пример результата

Для сети `172.20.0.0/23` с запасом роста 25% выделено 416 адресов из 512. Свободно 96 адресов. План сохранён в `plan_v5.csv`.

## Запуск тестов

```powershell
python -m unittest -v
```