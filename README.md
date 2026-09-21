# SQL Sunucu Takip Uygulaması

SQL Server üzerinde analiz yapmak, hataları takip etmek ve read-only sorgular çalıştırmak için geliştirilmiş masaüstü uygulaması. Gelişmiş sürüm **120 hazır diagnostik sorgu** ve **22 kategori** içerir.

## Özellikler

- **SQL Server Bağlantı Yönetimi**: Windows Authentication ve SQL Server Authentication desteği
- **Read-only SQL Sorguları**: Kendi yazdığınız `SELECT` ve CTE sorgularını güvenli varsayılanlarla çalıştırma
- **Gelişmiş Hazır Diagnostik Kataloğu (120 sorgu)**:
  - Sunucu sağlık özeti (PLE, scheduler, memory grant, I/O)
  - Performans derin analiz (plan cache, parameter sniffing, wait/latch)
  - Index / schema sağlığı (yinelenen index, FK index eksikleri, heap, identity kapasitesi)
  - Yedekleme ve RPO riski, suspect pages, autogrowth
  - Güvenlik ve erişim (sysadmin, zayıf login politikası, orphaned users, sertifikalar)
  - SQL Agent operasyon, Always On gecikme, TempDB dengesi, açık transaction
  - Yapılandırma, Query Store, CDC/Change Tracking, Service Broker, In-Memory OLTP
  - Ring buffer exception / connectivity / scheduler monitor
- **Sorgu Arama**: Ada, belirtiye ve rehber metnine göre hızlı filtreleme
- **Sorgu Rehberi**: Her sorgu için ne zaman kullanılacağı, fayda ettiği durumlar, önce/sonra teyit sorguları ve sonuç yorumlama ipuçları
- **Durum Playbook'ları**: Blocking, CPU, I/O, bellek, TempDB, RPO, güvenlik gibi yaşanan duruma göre önerilen sorgu sırası
- **SQL Belirti Seçici**: `LCK_M_*`, `PAGEIOLATCH`, PLE düşük, `LOG_BACKUP`, AG lag gibi sunucu sinyallerine göre script listesi
- **Sorgu Sonuçları**: Sonuçları tablo formatında görüntüleme ve Excel’e aktarma
- **Hata Yönetimi**: Detaylı hata mesajlarını görüntüleme
- **Sonuç Sınırı**: Büyük sonuç kümelerini ilk 10.000 satırla sınırlandırma
- **Eşzamanlı Çalışma Koruması**: Önceki sorgu tamamlanmadan yeni sorgu başlatmama

## Kurulum

### Gereksinimler
- Python 3.9 veya üzeri
- SQL Server ODBC Driver 17 (veya üzeri)

### Adımlar

1. Gerekli Python paketlerini yükleyin:
```bash
python -m pip install -r requirements.txt
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

1. **Sunucu**: SQL Server adresini girin (örn: `localhost` veya `SERVERNAME\INSTANCENAME`)
2. **Kimlik Doğrulama**:
   - **Windows**: Windows kimlik bilgilerinizle otomatik giriş
   - **SQL Server**: SQL Server kullanıcı adı ve şifresi gerektirir
3. **Bağlan** butonuna tıklayın
4. Bağlantı kurulduktan sonra aktif veritabanını listeden seçin

### Güvenlik

- SQL Server Authentication parolası diske kaydedilmez ve her uygulama oturumunda yeniden girilmelidir.
- Bağlantı `Encrypt=yes` ve `TrustServerCertificate=no` ile kurulur; SQL Server sertifikasının istemci tarafından güvenilir olması gerekir.
- Kalıcı veri veya şema değiştiren T-SQL komutları engellenir. Uygulama tek seferde yalnızca bir read-only `SELECT` veya CTE sorgusu çalıştırır.
- Her sorgu sonunda transaction geri alınır ve hata durumunda rollback uygulanır.
- `connection_config.json` yalnızca sunucu, veritabanı, kimlik doğrulama türü ve kullanıcı adı gibi hassas olmayan bağlantı tercihlerini içerir.
- Uygulamaya ve SQL Server hesabına yalnızca gerekli en düşük yetkileri verin; hazır sorguların izin gereksinimlerini `QUERY_COMPATIBILITY.md` üzerinden kontrol edin.
- Uygulama katmanındaki sorgu kontrolü tek başına bir yetkilendirme sınırı değildir; kalıcı koruma SQL Server hesabının read-only ve en düşük yetkili olmasıyla sağlanmalıdır.
- Yapılandırma, sorgu veya dağıtım dosyalarını paylaşmadan önce kurumunuza ait sunucu adlarını, kullanıcı adlarını ve özel sorguları gözden geçirin.

## Kullanım İpuçları

- **F5 Tuşu**: Sorguyu hızlıca çalıştırmak için F5 tuşunu kullanabilirsiniz
- **Kategori + Arama**: Önce kategori seçin veya `blocking`, `backup`, `PLE` gibi anahtar kelimelerle arayın
- **Yaşadığım durum**: Belirtiye göre playbook seçin; önerilen sıradaki sorgulara tıklayarak ilerleyin
- **SQL belirtisi**: Wait tipi / performans sayacı / operasyonel sinyali seçin; ilgili scriptler otomatik listelenir
- **Rehber paneli**: Seçili sorgunun ne zaman kullanılacağını, önce/sonra teyit zincirini, ilişkili belirtileri ve yorum ipuçlarını gösterir
- **Otomatik Çalıştırma**: Yalnızca read-only sorgular otomatik çalıştırılabilir; önceki sorgu bitmeden yenisi başlamaz
- **Sonuçlar**: Sorgu sonuçları otomatik olarak tablo formatında gösterilir
- **Hatalar**: Herhangi bir hata durumunda detaylı mesajlar "Hata Mesajları" bölümünde görüntülenir

## Teknik Detaylar

- **Framework**: PyQt5 (Python GUI framework)
- **Veritabanı Bağlantısı**: pyodbc (ODBC driver kullanarak)
- **Sorgu Kataloğu**: `predefined_queries.py` + `advanced_queries.py`
- **Sorgu Rehberi / Playbook**: `query_guides.py`
- **Güvenlik Katmanı**: `query_safety.py` (yalnızca SELECT/CTE)

- **Veri İşleme**: pandas (sonuçları işlemek için)

## Notlar

- Windows Authentication için SQL Server'ın Windows kimlik doğrulamasını desteklemesi gerekir
- SQL Server Authentication için geçerli bir kullanıcı adı ve şifre gereklidir
- Uygulama, SQL Server'ın varsayılan portu olan 1433'ü kullanır (farklı TCP portu için sunucu adına virgülle port ekleyin, örn: `localhost,1434`)
- Uzun süren sorgular UI'ı dondurmaz (thread kullanımı sayesinde)
- İlk 10.000 sonuç satırı gösterilir; daha büyük sonuçlar sorguda filtrelenmelidir

## Sorgu Uyumluluğu

**ÖNEMLİ**: Tüm sorgular her SQL Server'da çalışmayabilir. Bazı sorgular:

- **Belirli SQL Server versiyonları** gerektirebilir (örn: Always On için 2012+ Enterprise)
- **Özel izinler** gerektirebilir (VIEW SERVER STATE, sysadmin)
- **Belirli özelliklerin yüklü olmasını** gerektirebilir (Replication, SQL Agent)
- **System database'lere erişim** gerektirebilir (msdb, distribution)
- **VLF sorgusu için SQL Server 2016 SP2 veya üzeri** gerektirir

Detaylı uyumluluk bilgileri için `QUERY_COMPATIBILITY.md` dosyasına bakın.

### Genel Öneriler

1. **Temel sorgularla başlayın**: Aktif Bağlantılar, Veritabanı Boyutları gibi
2. **İzinleri kontrol edin**: VIEW SERVER STATE izni olup olmadığını kontrol edin
3. **Hata alırsanız**: Hata mesajını okuyun ve gerekli izin/özellik eksikliğini kontrol edin
4. **Alternatif sorgular**: Bazı sorgular çalışmazsa, benzer bilgileri almak için alternatif sorgular kullanın

