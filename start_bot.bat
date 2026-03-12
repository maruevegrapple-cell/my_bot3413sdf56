@echo off
chcp 65001 >nul
title 🔞 PORNO BOT
color 0C
cls

echo.
echo    ╔══════════════════════════════════════╗
echo    ║                                      ║
echo    ║    ██████╗  ██████╗ ██████╗ ███╗   ██╗║
echo    ║    ██╔══██╗██╔══██╗██╔══██╗████╗  ██║║
echo    ║    ██████╔╝██║  ██║██████╔╝██╔██╗ ██║║
echo    ║    ██╔═══╝ ██║  ██║██╔══██╗██║╚██╗██║║
echo    ║    ██║     ╚█████╔╝██║  ██║██║ ╚████║║
echo    ║    ╚═╝      ╚════╝ ╚═╝  ╚═╝╚═╝  ╚═══╝║
echo    ║                                      ║
echo    ║          ██████╗  ██████╗           ║
echo    ║          ██╔══██╗██╔══██╗           ║
echo    ║          ██████╔╝██████╔╝           ║
echo    ║          ██╔══██╗██╔══██╗           ║
echo    ║          ██████╔╝██████╔╝           ║
echo    ║          ╚═════╝ ╚═════╝            ║
echo    ║                                      ║
echo    ╠══════════════════════════════════════╣
echo    ║                                      ║
echo    ║   👑 Админ: 8386200808               ║
echo    ║   🤖 Бот: @AnonChaat34_bot           ║
echo    ║   📁 Путь: D:\A PORNO BOT            ║
echo    ║                                      ║
echo    ╚══════════════════════════════════════╝
echo.
echo    Нажми любую клавишу для запуска...
pause >nul

:: Переход на диск D
D:
if %errorlevel% neq 0 (
    echo Ошибка перехода на диск D!
    pause
    exit /b
)

:: Переход в папку
cd "D:\A PORNO BOT"
if %errorlevel% neq 0 (
    echo Папка не найдена!
    pause
    exit /b
)

:: Запуск бота
echo.
echo Запуск бота...
python bot.py

pause