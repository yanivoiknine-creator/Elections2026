@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo.
echo מרענן את כל הסקרים מהמחשב הזה.
echo (ערוץ 14 וזמן ישראל חוסמים את שרתי GitHub, אבל מהבית הם נגישים)
echo.
python pipeline.py
echo.
echo ============================================================
echo   סיום. כדי שהאתר באינטרנט יתעדכן, העלו ל-GitHub את הקובץ:
echo       data\polls.json
echo   (Add file - Upload files, וגררו אותו לתיקיית data)
echo ============================================================
echo.
pause
