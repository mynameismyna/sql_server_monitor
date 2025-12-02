# SQL Sunucu Takip Uygulaması

SQL Server üzerinde analizler yapmak, hataları takip etmek ve özel sorgular çalıştırmak için geliştirilmiş basit masaüstü uygulaması.

## Özellikler

- **SQL Server Bağlantı Yönetimi**: Windows Authentication ve SQL Server Authentication desteği
- **Özel SQL Sorguları**: Kendi yazdığınız SQL sorgularını çalıştırma
- **Hazır Analiz Sorguları**: 
  - Aktif bağlantılar
  - Yavaş çalışan sorgular
  - SQL Server hataları (son 24 saat)
  - Veritabanı boyutları
  - Bekleyen işlemler (blocking)
  - En çok CPU kullanan sorgular
  - Aktif işlemler
  - Veritabanı dosya bilgileri
  - Tablo satır sayıları
- **Sorgu Sonuçları**: Sonuçları tablo formatında görüntüleme
- **Hata Yönetimi**: Detaylı hata mesajlarını görüntüleme

## Kurulum

### Gereksinimler
- Python 3.8 veya üzeri
- SQL Server ODBC Driver 17 (veya üzeri)

### Adımlar

1. Gerekli Python paketlerini yükleyin:
```bash
pip install -r requirements.txt
```

2. SQL Server ODBC Driver'ı yükleyin (eğer yüklü değilse):
   - [Microsoft SQL Server ODBC Driver](https://docs.microsoft.com/en-us/sql/connect/odbc/download-odbc-driver-for-sql-server) indirin ve yükleyin

## Kullanım

Uygulamayı çalıştırmak için:
```bash
python main.py
```

## SQL Server Bağlantısı

Uygulama açıldığında:

1. **Sunucu**: SQL Server adresini girin (örn: `localhost`, `192.168.1.100` veya `SERVERNAME\INSTANCENAME`)
2. **Veritabanı**: Bağlanmak istediğiniz veritabanı adını girin (varsayılan: `master`)
3. **Kimlik Doğrulama**: 
   - **Windows**: Windows kimlik bilgilerinizle otomatik giriş
   - **SQL Server**: SQL Server kullanıcı adı ve şifresi gerektirir
4. **Bağlan** butonuna tıklayın

## Kullanım İpuçları

- **F5 Tuşu**: Sorguyu hızlıca çalıştırmak için F5 tuşunu kullanabilirsiniz
- **Hazır Sorgular**: Dropdown menüden hazır analiz sorgularını seçebilirsiniz
- **Sonuçlar**: Sorgu sonuçları otomatik olarak tablo formatında gösterilir
- **Hatalar**: Herhangi bir hata durumunda detaylı mesajlar "Hata Mesajları" bölümünde görüntülenir

## Teknik Detaylar

- **Framework**: PyQt5 (Python GUI framework)
- **Veritabanı Bağlantısı**: pyodbc (ODBC driver kullanarak)
- **Veri İşleme**: pandas (sonuçları işlemek için)

## Notlar

- Windows Authentication için SQL Server'ın Windows kimlik doğrulamasını desteklemesi gerekir
- SQL Server Authentication için geçerli bir kullanıcı adı ve şifre gereklidir
- Uygulama, SQL Server'ın varsayılan portu olan 1433'ü kullanır (farklı port için sunucu adına `:port` ekleyin, örn: `localhost:1434`)
- Uzun süren sorgular UI'ı dondurmaz (thread kullanımı sayesinde)

## Sorgu Uyumluluğu

**ÖNEMLİ**: Tüm sorgular her SQL Server'da çalışmayabilir. Bazı sorgular:

- **Belirli SQL Server versiyonları** gerektirebilir (örn: Always On için 2012+ Enterprise)
- **Özel izinler** gerektirebilir (VIEW SERVER STATE, sysadmin)
- **Belirli özelliklerin yüklü olmasını** gerektirebilir (Replication, SQL Agent)
- **System database'lere erişim** gerektirebilir (msdb, distribution)

Detaylı uyumluluk bilgileri için `QUERY_COMPATIBILITY.md` dosyasına bakın.

### Genel Öneriler

1. **Temel sorgularla başlayın**: Aktif Bağlantılar, Veritabanı Boyutları gibi
2. **İzinleri kontrol edin**: VIEW SERVER STATE izni olup olmadığını kontrol edin
3. **Hata alırsanız**: Hata mesajını okuyun ve gerekli izin/özellik eksikliğini kontrol edin
4. **Alternatif sorgular**: Bazı sorgular çalışmazsa, benzer bilgileri almak için alternatif sorgular kullanın

