@echo off
chcp 65001 > nul
echo [INFO] Идет сканирование корня проекта и генерация MAP.md...

:: %~dp0 указывает на папку, из которой запущен .bat файл (т.е. папка agent/util/)
powershell.exe -ExecutionPolicy Bypass -NoProfile -File "%~dp0generate_map.ps1"

echo [SUCCESS] Файл MAP.md успешно обновлен в папке agent/project!
pause