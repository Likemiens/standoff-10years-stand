# Сборка Windows exe

Да, приложение можно собрать в исполняемый файл для операторов стенда.

Рекомендуемый формат сборки:

```text
dist/
  StandoffHistory/
    StandoffHistory.exe
    START_STANDOFF.bat
    config.json
    config.example.json
    content/
    logs/
      events.log
```

Это лучше, чем один `.exe`, потому что ролики и конфиг можно менять без пересборки.

## Подготовка сборочной машины

Сборку нужно делать на Windows с Python 3.11+.

```bat
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements-build.txt
```

## Сборка

Если финальный контент уже есть, сначала положить его в корневую папку проекта:

```text
content\
```

И проверить:

```bat
python tools\content_check.py
```

Из корня проекта:

```bat
powershell -ExecutionPolicy Bypass -File tools\build_windows.ps1
```

После завершения готовая папка будет здесь:

```text
dist\StandoffHistory\
```

## Как запускать на стенде

Оператору достаточно открыть:

```text
dist\StandoffHistory\StandoffHistory.exe
```

Или:

```text
dist\StandoffHistory\START_STANDOFF.bat
```

Приложение прочитает `config.json` из этой же папки, будет искать контент в `content/` рядом с exe и писать лог в `logs/events.log`.

## Что копировать на mini-PC

На целевой компьютер нужно перенести всю папку:

```text
dist\StandoffHistory\
```

Не только `.exe`.

## Настройка после сборки

Сборка копирует корневой `config.json` в `dist\StandoffHistory\config.json` и проверяет, что JSON валиден. Если боевой конфиг в корне проекта актуален, после сборки его не нужно править вручную.

Перед запуском на стенде:

1. Проверить, что видео лежат в `dist\StandoffHistory\content\`.
2. Проверить `dist\StandoffHistory\config.json`, только если на этом компьютере отличаются COM-порты или номер экрана.
3. Если COM-порт известен, указать его явно:

```json
"serial": {
  "enabled": true,
  "port": "COM3",
  "baudRate": 9600
}
```

Если COM-порт неизвестен, оставить:

```json
"port": "auto"
```

4. Если контент заменяли уже после сборки, проверить список файлов вручную по `TEST_PLAN.md`.

## Режимы запуска

Обычный режим:

```text
StandoffHistory.exe
```

Тест без Arduino:

```bat
StandoffHistory.exe --simulate
```

Ручной режим внутри приложения:

```text
F2
```

Debug:

```text
F1
```

## Важное ограничение

Сборка создаёт переносимую папку, а не установщик. Это осознанно: для мероприятия проще заменить папку целиком, заменить ролики или поправить `config.json`, чем переустанавливать приложение.
