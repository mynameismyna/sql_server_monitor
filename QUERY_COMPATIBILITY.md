# SQL Server Sorgu Uyumluluk Rehberi

## Genel Uyumluluk

Çoğu sorgu **SQL Server 2008 ve üzeri** versiyonlarda çalışır. VLF, Query Store, Always On derin izleme, database scoped configuration, temporal/In-Memory ve bazı ring buffer sorguları daha yeni sürüm veya ek bileşen gerektirir.

Gelişmiş katalogda **120 hazır diagnostik sorgu** ve **22 kategori** vardır. Özellik yüklü değilse ilgili sorgu hata verebilir; bu beklenen bir durumdur.

## Gerekli İzinler

Çoğu sunucu tanılama sorgusu için **VIEW SERVER STATE** izni gerekir. Yalnızca sorgu çalıştırmak amacıyla `sysadmin` rolü verilmemelidir. Bazı sorgular için ek izinler:

- **msdb** veritabanı sorguları: `msdb` veritabanına erişim (backup, Agent, suspect_pages, Database Mail)
- **distribution** veritabanı sorguları: Replication yapılandırması gerektirir
- **Güvenlik sorguları**: Server ve database seviyesinde izin görüntüleme yetkisi
- **Default Trace / Autogrowth**: Default trace açık olmalı; `fn_trace_gettable` erişimi gerekir
- **Index fiziksel istatistikleri**: İlgili veritabanında `VIEW DATABASE STATE` yararlıdır

## Özellik Bazlı Sorgular

### Always On / Availability Groups
- **Gereksinim**: SQL Server 2012+ Enterprise Edition
- **Sorgular**: 
  - Availability Groups Durumu
  - Availability Replicas
  - AG Senkronizasyon Gecikmesi
  - AG Listener ve Endpoint Durumu
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
  - Job Başarı Oranı (Son 7 Gün)
  - Uzun Süredir Çalışmayan Job'lar
- **Not**: Agent servisi kapalıysa veya `msdb` erişimi yoksa sorgu hata verecektir

### VLF (Virtual Log File)
- **Gereksinim**: SQL Server 2016 SP2 veya üzeri
- **Sorgu**: VLF (Virtual Log File) Sayısı
- **Not**: `sys.dm_db_log_info` fonksiyonu ve ilgili performans durumu izni gereklidir

### Query Store / Temporal / In-Memory
- **Query Store Durum Özeti**: SQL Server 2016+ ve Query Store açık olmalı
- **Temporal Tablo Envanteri**: Temporal table içeren veritabanları
- **In-Memory OLTP Kullanımı**: Memory-optimized table içeren instance

### Ring Buffer Hata Sorguları
- **SQL Server Hataları (Son 24 Saat)** ve ring buffer sorguları `xp_readerrorlog` kullanmaz
- Exception / connectivity / scheduler monitor ring buffer kayıtlarına dayanır
- Ring buffer içeriği instance yeniden başladıktan sonra sıfırlanabilir

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
- Query Store ve birçok gelişmiş diagnostik kullanılabilir
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

1. **Sağlık özeti ile başlayın**: `Sunucu Anlık Durum Kartı`, `Page Life Expectancy ve Buffer Hit`
2. **İzinleri kontrol edin**: VIEW SERVER STATE izni olup olmadığını kontrol edin
3. **Versiyonu öğrenin**: `SELECT @@VERSION` ile SQL Server versiyonunu öğrenin
4. **Arama kutusunu kullanın**: `blocking`, `backup`, `index`, `ag` gibi anahtar kelimelerle filtreleyin
5. **Özellikleri kontrol edin**: Always On, Replication gibi özelliklerin yüklü olup olmadığını kontrol edin

## Alternatif Çözümler

Bazı sorgular çalışmazsa, benzer bilgileri almak için alternatif sorgular kullanabilirsiniz. Örneğin:

- Always On yoksa: Normal backup/restore durumunu kontrol edin
- Replication yoksa: Log shipping durumunu kontrol edin
- Agent yoksa: Manuel backup durumunu kontrol edin
- Error log prosedürü yoksa: Ring buffer exception sorgularını kullanın
