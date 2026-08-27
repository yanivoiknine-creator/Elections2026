@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo מפעיל את מעקב הסקרים...
echo (בדיקת סקרים חדשים תרוץ אוטומטית ברקע עם פתיחת האפליקציה)
python app.py
pause
