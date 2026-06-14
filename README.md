# Standoff History App

Локальное Python-приложение для интерактивной зоны «История Standoff». Работает на Windows-ноутбуке или mini-PC без интернета, читает цифры года от Arduino по Serial, собирает год как `20YY` и показывает нужный ролик или заглушку на основном экране.

## Установка

Требуется Python 3.11+.

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

## Запуск

```bash
python main.py
```

По умолчанию приложение открывается fullscreen, показывает idle и пытается найти две Arduino автоматически.

Для операторов стенда можно собрать Windows exe. Инструкция: [BUILD_WINDOWS.md](BUILD_WINDOWS.md).

Для теста без Arduino:

```bash
python main.py --simulate
```

В simulate-режиме работают быстрые клавиши:

- `F1` - debug-панель
- `F2` - ручной режим
- `I` - idle
- `B` - before_2016
- `A` - after_2026
- `V` - тестовый запуск 2017

## Контент

Файлы кладутся в `content/`:

```text
standoff_2016.mp4 ... standoff_2026.mp4
standoff_idle.mp4
standoff_before_2016.mp4
standoff_after_2026.mp4
```

Для `idle`, `before_2016`, `after_2026` также допустимы `.png`, `.jpg`, `.jpeg`. Если файла нет или он пустой, приложение не падает: показывает техническую заглушку, пишет ошибку в `logs/events.log` и показывает её в debug.

Проверка контента:

```bash
python tools/content_check.py
```

## Serial и COM-порты

Актуальный режим стенда: две Arduino в двух USB-портах.

```text
Arduino 1 -> десятки года -> D\n
Arduino 2 -> единицы года -> D\n
```

Каждая плата отправляет одну цифру `0-9` и перенос строки.

Пример:

```text
tens Arduino отправляет: 1
ones Arduino отправляет: 7
приложение собирает: 17 -> 2017 -> standoff_2017.mp4
```

В `config.json` можно указать конкретные порты:

```json
"serial": {
  "enabled": true,
  "mode": "dual_digit",
  "baudRate": 9600,
  "dual": {
    "tensPort": "COM3",
    "onesPort": "COM4",
    "ledTarget": "tens"
  }
}
```

Если стоит `"auto"`, приложение выбирает два Arduino-подобных COM-порта с приоритетом по описаниям `Arduino`, `CH340`, `USB Serial`, `Nano`. У двух одинаковых плат порядок может поменяться, поэтому для площадки надёжнее один раз прописать `tensPort` и `onesPort` явно.

Проверка Serial:

```bash
python tools/serial_check.py --mode dual_digit --tens-port auto --ones-port auto --baud 9600
python tools/serial_check.py --mode dual_digit --tens-port COM3 --ones-port COM4 --baud 9600
```

Старый режим одной Arduino сохранён: поставь `"mode": "single_yy"`, тогда Arduino должна отправлять `YY\n`.

## Логика годов

```text
00-15 -> before_2016
16-26 -> 2016.mp4 ... 2026.mp4
27-99 -> after_2026
```

Первое стабильное значение от Arduino при старте не запускает ролик, если `triggerOnStartup=false`. Это защищает от автозапуска, когда барабан уже стоит на каком-то значении.

Вход стабилизируется через `stabilizationDelayMs`. Повтор того же собранного `YY` не перезапускает ролик бесконечно.

## Ручной режим

Открывается по `F2`.

Можно:

- ввести `00-99`
- запустить конкретный ролик `2016-2026`
- запустить `idle`, `before_2016`, `after_2026`
- отправить `LED_RUN`, `LED_OFF`, `LED_IDLE`, `LED_ERROR`

Ручной режим работает даже без Arduino.

## Debug

Открывается по `F1`.

Показывает:

- статус Arduino и COM-порты
- last raw input, candidate, stable, last triggered
- mapped year, текущий сценарий и файл
- LED status и последнюю LED-команду
- последнюю ошибку
- статус проверки контента

## LED

LED-управление абстрактное и настраивается в `config.json`.

```json
"led": {
  "enabled": false,
  "runCommand": "LED_RUN",
  "offCommand": "LED_OFF",
  "idleCommand": "LED_IDLE",
  "errorCommand": "LED_ERROR"
}
```

Если `led.enabled=false`, приложение не отправляет команды и работает без ленты. Если включить LED в режиме двух Arduino, команда отправляется в порт из `serial.dual.ledTarget`: `tens`, `ones` или `both`.

## Настройка экрана

Основные параметры:

```json
"display": {
  "fullscreen": true,
  "screenIndex": 0,
  "hideCursor": true,
  "keepAspectRatio": true
}
```

Для разработки можно временно поставить `"fullscreen": false`.

Перед монтажом на Windows стоит отключить сон, заставку, автоотключение экрана, уведомления и автообновления на время мероприятия.
