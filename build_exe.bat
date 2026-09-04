@echo off
echo SQL Sunucu Takip Uygulamasi - EXE Olusturuluyor...
echo.

REM PyInstaller yuklu mu kontrol et
python -c "import PyInstaller" 2>nul
if errorlevel 1 (
    echo HATA: PyInstaller bulunamadi.
    echo Once python -m pip install -r requirements.txt komutunu calistirin.
    exit /b 1
)

echo.
echo EXE dosyasi olusturuluyor...
echo.

python -m PyInstaller build_exe.spec
if errorlevel 1 exit /b 1

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
    echo 3. Hassas olmayan baglanti tercihleri connection_config.json dosyasinda kaydedilir
    echo 4. SQL Server Authentication parolasi kaydedilmez
    echo.
) else (
    echo ========================================
    echo HATA: EXE dosyasi olusturulamadi!
    echo ========================================
)

pause

