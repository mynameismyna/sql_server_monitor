# SQL Server Sorgu Uyumluluk Rehberi

## Genel Uyumluluk

Çoğu sorgu **SQL Server 2008 ve üzeri** versiyonlarda çalışır. VLF sorgusu ve bazı özellik sorguları daha yeni sürüm veya ek bileşen gerektirir.

## Gerekli İzinler

Çoğu sunucu tanılama sorgusu için **VIEW SERVER STATE** izni gerekir. Yalnızca sorgu çalıştırmak amacıyla `sysadmin` rolü verilmemelidir. Bazı sorgular için ek izinler:

- **msdb** veritabanı sorguları: `msdb` veritabanına erişim
- **distribution** veritabanı sorguları: Replication yapılandırması gerektirir
- **Güvenlik sorguları**: Server ve database seviyesinde izin görüntüleme yetkisi

## Özellik Bazlı Sorgular

### Always On / Availability Groups
- **Gereksinim**: SQL Server 2012+ Enterprise Edition
- **Sorgular**: 
  - Availability Groups Durumu
  - Availability Replicas
- **Not**: Bu özellik yoksa sorgu hata verecektir

### Replication
- **Gereksinim**: Replication özelliği yüklü ve yapılandırılmış olmalı
- **Sorgular**:
  - Replication Yayıncıları
  - Replication Aboneleri
- **Not**: `distribution` veritabanı yoksa sorgu hata verecektir

### SQL Agent
- **Gereksinim**: SQL Server Agent servisi çalışıyor olmalı
- **Sorgular**:
  - SQL Agent Job Durumları
  - Başarısız Job'lar
  - Çalışan Job'lar
- **Not**: Agent servisi kapalıysa veya `msdb` erişimi yoksa sorgu hata verecektir

### VLF (Virtual Log File)
- **Gereksinim**: SQL Server 2016 SP2 veya üzeri
- **Sorgu**: VLF (Virtual Log File) Sayısı
- **Not**: `sys.dm_db_log_info` fonksiyonu ve ilgili performans durumu izni gereklidir

## Versiyon Uyumluluğu

### SQL Server 2008 / 2008 R2
- Çoğu temel sorgu çalışır
- Always On sorguları çalışmaz
- VLF sorgusu çalışmaz
- Bazı DMV'ler farklı kolonlar içerebilir

### SQL Server 2012 / 2014
- Tüm temel sorgular çalışır
- Always On sorguları Enterprise Edition'da çalışır
- VLF sorgusu çalışmaz

### SQL Server 2016+
- Temel sorgular çalışır; VLF sorgusu için SQL Server 2016 SP2 veya üzeri gerekir
- Özellik sorguları yalnızca ilgili bileşen yapılandırılmışsa çalışır

## Read-only Çalışma

- Uygulama tek seferde yalnızca bir `SELECT` veya CTE sorgusu çalıştırır.
- `INSERT`, `UPDATE`, `DELETE`, `MERGE`, DDL, `EXEC`, `DBCC`, backup/restore ve sunucu yönetim komutları engellenir.
- Otomatik çalıştırma aynı read-only kurallara tabidir.
- Sorgu sonuçları ilk 10.000 satırla sınırlandırılır.
- Uygulama katmanındaki kontrol, SQL Server yetkilerinin yerine geçmez; bağlantı hesabı read-only ve en düşük yetkili olmalıdır.

## Hata Durumları

Sorgu çalıştırıldığında hata alırsanız:

1. **"Invalid object name"**: Özellik yüklü değil veya versiyon uyumsuz
2. **"Permission denied"**: Yeterli izin yok
3. **"Invalid column name"**: SQL Server versiyonu farklı kolonlar içeriyor
4. **"Database does not exist"**: System database'e erişim yok

## Öneriler

1. **Temel sorgularla başlayın**: Aktif Bağlantılar, Veritabanı Boyutları gibi
2. **İzinleri kontrol edin**: VIEW SERVER STATE izni olup olmadığını kontrol edin
3. **Versiyonu öğrenin**: `SELECT @@VERSION` ile SQL Server versiyonunu öğrenin
4. **Özellikleri kontrol edin**: Always On, Replication gibi özelliklerin yüklü olup olmadığını kontrol edin

## Alternatif Çözümler

Bazı sorgular çalışmazsa, benzer bilgileri almak için alternatif sorgular kullanabilirsiniz. Örneğin:

- Always On yoksa: Normal backup/restore durumunu kontrol edin
- Replication yoksa: Log shipping durumunu kontrol edin
- Agent yoksa: Manuel backup durumunu kontrol edin

