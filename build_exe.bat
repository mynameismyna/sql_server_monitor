@echo off
echo SQL Sunucu Takip Uygulamasi - EXE Olusturuluyor...
echo.

REM PyInstaller yuklu mu kontrol et
python -c "import PyInstaller" 2>nul
if errorlevel 1 (
    echo PyInstaller yuklu degil. Yukleniyor...
    pip install pyinstaller
)

echo.
echo EXE dosyasi olusturuluyor...
echo.

REM PyInstaller ile exe olustur
pyinstaller --name="SQL_Sunucu_Takip" ^
    --onefile ^
    --windowed ^
    --icon=NONE ^
    --add-data="QUERY_COMPATIBILITY.md;." ^
    --hidden-import="PyQt5" ^
    --hidden-import="pandas" ^
    --hidden-import="openpyxl" ^
    --hidden-import="pyodbc" ^
    --collect-all="PyQt5" ^
    main.py

echo.
echo.
if exist "dist\SQL_Sunucu_Takip.exe" (
    echo ========================================
    echo EXE dosyasi basariyla olusturuldu!
    echo Konum: dist\SQL_Sunucu_Takip.exe
    echo ========================================
    echo.
    echo EXE dosyasini kullanmak icin:
    echo 1. dist klasorundeki SQL_Sunucu_Takip.exe dosyasini calistirin
    echo 2. SQL Server ODBC Driver 17 yuklu olmali
    echo 3. Baglanti ayarlari connection_config.json dosyasinda kaydedilir
    echo.
) else (
    echo ========================================
    echo HATA: EXE dosyasi olusturulamadi!
    echo ========================================
)

pause

