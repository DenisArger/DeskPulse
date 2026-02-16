# DeskPulse

Набор утилит для Linux/X11:

- управление окнами (свернуть/восстановить),
- стабилизация аудиовыхода (PipeWire/PulseAudio + ALSA),
- управление громкостью колесиком мыши в зоне панели.

## Файлы

- `minimize_all.py` — переключает состояние окон: если есть видимые, сворачивает; если все скрыты, восстанавливает.
- `hide_all.py` — принудительно показывает (map) верхнеуровневые окна.
- `headphones_guard.py` — watchdog аудио: восстанавливает рабочий sink/порт при сбоях (`auto_null`, смена порта, и т.п.).
- `taskbar_volume_hover.py` — изменение громкости колесиком в зоне панели задач (top/bottom).
- `toggle_taskbar_wheel_volume.py` — toggle для включения/выключения режима колесика (удобно вешать на горячую клавишу).

## Быстрый старт

```bash
cd /home/user/ADV/my_scripts
./minimize_all.py
./headphones_guard.py --watch --interval 5
```

Для колесика (верхняя панель):

```bash
./taskbar_volume_hover.py --panel-position top --panel-height 48 --step 2 --cooldown-ms 220 --allow-grab
```

## Важно

- В среде без X RECORD fallback-режим (`--allow-grab`) может перехватывать wheel-события у приложений.
- Если wheel в браузере перестал работать, отключите режим колесика через `toggle_taskbar_wheel_volume.py`.
- Для автозапуска стабилизации звука используется user service `headphones-guard.service`.
