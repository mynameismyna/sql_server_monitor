# SQL Sunucu Takip Uygulaması - EXE Derleme Talimatları

## Gereksinimler

1. Python 3.9 veya üzeri
2. Tüm bağımlılıkların yüklü olması
3. PyInstaller paketi

## Adım Adım Derleme

### Yöntem 1: Otomatik (Önerilen)

Windows için batch dosyasını çalıştırın:

```bash
build_exe.bat
```

Bu script:
- Gerekli bağımlılıkların yüklü olduğunu kontrol eder
- EXE dosyasını oluşturur
- Sonuç dosyasını `dist` klasörüne koyar

### Yöntem 2: Manuel

1. PyInstaller'ı yükleyin:
```bash
python -m pip install -r requirements.txt
```

2. EXE oluşturun:
```bash
python -m PyInstaller build_exe.spec
```

VEYA

```bash
python -m PyInstaller --name="SQL_Sunucu_Takip" --onefile --windowed --add-data="QUERY_COMPATIBILITY.md;." main.py
```

## Çıktı Dosyaları

### dist klasörü
- `SQL_Sunucu_Takip.exe` - Çalıştırılabilir dosya (tek dosya)

### build klasörü
- Geçici derleme dosyaları (silinebilir)

### .spec dosyası
- PyInstaller yapılandırma dosyası (özelleştirme için)

## EXE Dosyasını Kullanma

### Gereksinimler
- Windows 10/11
- SQL Server ODBC Driver 17 (veya üzeri)

### Çalıştırma
1. `dist\SQL_Sunucu_Takip.exe` dosyasını çalıştırın
2. İlk çalıştırmada bağlantı ayarlarını girin
3. Hassas olmayan bağlantı tercihleri `connection_config.json` dosyasına kaydedilir
4. SQL Server Authentication parolası kaydedilmez ve her oturumda yeniden girilir

### Dağıtım
EXE dosyasını başka bilgisayarlara kopyalayabilirsiniz. Gereksinimler:
- Windows işletim sistemi
- SQL Server ODBC Driver 17

## Sorun Giderme

### "ODBC Driver not found" hatası
- SQL Server ODBC Driver 17'yi yükleyin:
  https://docs.microsoft.com/en-us/sql/connect/odbc/download-odbc-driver-for-sql-server

### "Failed to execute script" hatası
- Antivirüs korumasını devre dışı bırakmayın ve geniş kapsamlı istisna oluşturmayın
- EXE'yi güvenilir kaynak koddan yerel olarak yeniden derleyin ve dosya bütünlüğünü doğrulayın
- Kurumsal güvenlik ekibinizle uyarı ayrıntılarını ve dosya hash'ini paylaşarak false-positive incelemesi isteyin

### Dosya boyutu büyük
- Normal: 150-250 MB (tüm bağımlılıklar dahil)
- UPX ile sıkıştırılmış hali daha küçük olabilir

## Özelleştirme

### Icon eklemek
`build_exe.bat` dosyasında:
```
--icon=icon.ico
```

### Tek dosya yerine klasör
`--onefile` yerine `--onedir` kullanın

### Console penceresini göstermek
`--windowed` yerine `--console` kullanın

## Notlar

- EXE dosyası ilk çalıştırmada biraz yavaş açılabilir (normal)
- Ayar dosyaları (`connection_config.json`, `user_queries.json`) EXE ile aynı klasörde oluşturulur; parola kaydedilmez
- Antivirüs uyarısı oluşursa dosya hash'i ve kaynak kod incelenmeden istisna oluşturulmamalıdır

