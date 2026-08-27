@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo מפעיל את מעקב הסקרים — נגיש גם מהטלפון ברשת הביתית...
python app.py --lan
pause
