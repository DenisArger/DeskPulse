# DeskPulse

## English
## Problem
Linux desktop users often need small focused automations for window management, audio recovery, and panel-volume shortcuts.
## Solution
DeskPulse is a set of Python utilities for X11 workflows: window toggle, audio guard, Bluetooth headphones connect helper, and taskbar wheel volume control.
## Tech Stack
- Python
- Linux/X11 utilities
- PipeWire/PulseAudio/ALSA integration scripts
- BlueZ (`bluetoothctl`) for Bluetooth pairing/connection
## Architecture
```text
minimize_all.py
hide_all.py
headphones_guard.py
bt_headphones_connect.py
layout_switcher.py
toggle_layout_switcher.py
taskbar_volume_hover.py
toggle_taskbar_wheel_volume.py
```
```mermaid
flowchart TD
  A[User hotkey/command] --> B[Utility script]
  B --> C[X11 window control]
  B --> D[Audio stack guard]
  B --> E[Bluetooth connect helper]
  B --> F[Panel wheel volume handler]
  B --> G[Layout fixer helper]
```
## Features
- Minimize/restore window behavior
- Audio sink watchdog and recovery
- Reliable Bluetooth headphones connect with retries
- Volume control by mouse wheel on taskbar area
- Punto-like EN/RU last-word fix by hotkey
- Toggle script for quick on/off workflow
## How to Run
```bash
python3 minimize_all.py
python3 headphones_guard.py --watch --interval 5
./bt_headphones_connect.py
./toggle_layout_switcher.py
```

Layout switcher options:
```bash
./layout_switcher.py --hotkey Pause --layout-a us --layout-b ru --max-word-len 64 --cooldown-ms 220
```
Dependencies: `python-xlib`, `xdotool`, `setxkbmap`, optional `xkb-switch`.
Limitations: X11 only, no auto-fix on separators, and password fields cannot be reliably detected on X11.

## Russian
## Проблема
Пользователям Linux часто нужны небольшие утилиты для управления окнами, стабилизации звука и быстрого управления громкостью.
## Решение
DeskPulse — это набор Python-скриптов для X11: переключение окон, audio watchdog, подключение BT-наушников и управление громкостью колесиком в зоне панели.
## Стек
- Python
- Linux/X11 утилиты
- Скрипты для PipeWire/PulseAudio/ALSA
- BlueZ (`bluetoothctl`) для сопряжения/подключения Bluetooth
## Архитектура
```text
minimize_all.py
hide_all.py
headphones_guard.py
bt_headphones_connect.py
layout_switcher.py
toggle_layout_switcher.py
taskbar_volume_hover.py
toggle_taskbar_wheel_volume.py
```
```mermaid
flowchart TD
  A[Горячая клавиша/команда] --> B[Утилита]
  B --> C[Управление окнами X11]
  B --> D[Стабилизация аудио]
  B --> E[Подключение Bluetooth]
  B --> F[Управление громкостью панели]
  B --> G[Исправление раскладки]
```
## Возможности
- Сворачивание/восстановление окон
- Watchdog аудио-выхода
- Надежное подключение Bluetooth-наушников с повторами
- Громкость колесиком мыши в зоне панели
- Punto-подобное исправление последнего слова EN/RU по горячей клавише
- Быстрое переключение режима on/off
## Как запустить
```bash
python3 minimize_all.py
python3 headphones_guard.py --watch --interval 5
./bt_headphones_connect.py
./toggle_layout_switcher.py
```

Параметры переключателя раскладки:
```bash
./layout_switcher.py --hotkey Pause --layout-a us --layout-b ru --max-word-len 64 --cooldown-ms 220
```
Зависимости: `python-xlib`, `xdotool`, `setxkbmap`, опционально `xkb-switch`.
Ограничения: только X11, без автоисправления на разделителях, поля пароля на X11 надежно не детектируются.

## Важно
- В среде без X RECORD fallback-режим (`--allow-grab`) может перехватывать wheel-события у приложений.
- Если wheel в браузере перестал работать, отключите режим колесика через `toggle_taskbar_wheel_volume.py`.
- Для автозапуска стабилизации звука используется user service `headphones-guard.service`.
