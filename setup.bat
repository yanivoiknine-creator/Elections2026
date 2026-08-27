@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo מתקין תלויות...
python -m pip install -r requirements.txt
echo.
echo טוען היסטוריית סקרים...
python seed.py
echo.
echo מוכן. הרץ run.bat כדי להפעיל.
pause
