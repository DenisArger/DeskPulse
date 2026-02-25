# DeskPulse

## English
## Problem
Linux desktop users often need small focused automations for window management, audio recovery, and panel-volume shortcuts.
## Solution
DeskPulse is a set of Python utilities for X11 workflows: window toggle, audio guard, and taskbar wheel volume control.
## Tech Stack
- Python
- Linux/X11 utilities
- PipeWire/PulseAudio/ALSA integration scripts
## Architecture
```text
minimize_all.py
hide_all.py
headphones_guard.py
taskbar_volume_hover.py
toggle_taskbar_wheel_volume.py
```
```mermaid
flowchart TD
  A[User hotkey/command] --> B[Utility script]
  B --> C[X11 window control]
  B --> D[Audio stack guard]
  B --> E[Panel wheel volume handler]
```
## Features
- Minimize/restore window behavior
- Audio sink watchdog and recovery
- Volume control by mouse wheel on taskbar area
- Toggle script for quick on/off workflow
## How to Run
```bash
python3 minimize_all.py
python3 headphones_guard.py --watch --interval 5
```

## Русский
## Проблема
Пользователям Linux часто нужны небольшие утилиты для управления окнами, стабилизации звука и быстрого управления громкостью.
## Решение
DeskPulse — это набор Python-скриптов для X11: переключение окон, audio watchdog и управление громкостью колесиком в зоне панели.
## Стек
- Python
- Linux/X11 утилиты
- Скрипты для PipeWire/PulseAudio/ALSA
## Архитектура
```text
minimize_all.py
hide_all.py
headphones_guard.py
taskbar_volume_hover.py
toggle_taskbar_wheel_volume.py
```
```mermaid
flowchart TD
  A[Горячая клавиша/команда] --> B[Утилита]
  B --> C[Управление окнами X11]
  B --> D[Стабилизация аудио]
  B --> E[Управление громкостью панели]
```
## Возможности
- Сворачивание/восстановление окон
- Watchdog аудио-выхода
- Громкость колесиком мыши в зоне панели
- Быстрое переключение режима on/off
## Как запустить
```bash
python3 minimize_all.py
python3 headphones_guard.py --watch --interval 5
```
