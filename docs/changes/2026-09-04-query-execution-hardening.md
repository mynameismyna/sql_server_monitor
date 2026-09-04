# Query Execution and Connection Hardening

## İşlem özeti

- **İşlem:** SQL sorgu yürütme ve SQL Server bağlantı güvenliğinin güçlendirilmesi
- **Amaç:** Kalıcı veri değişikliği, tekrarlanan yazma sorgusu, açık transaction, güvensiz bağlantı ve sınırsız sonuç kümesi risklerini azaltmak
- **Kapsam:** Sorgu politikası, bağlantı katmanı, otomatik çalıştırma, hazır VLF sorgusu, testler, build süreci ve kullanıcı dokümantasyonu
- **Tarih:** 2026-09-04

## Teknik değişiklikler

- Yeni `query_safety.py` modülü tek seferde yalnızca bir read-only `SELECT` veya CTE sorgusuna izin verir.
- DML, DDL, `EXEC`, `DBCC`, backup/restore, sunucu yönetimi, harici veri erişimi ve transaction komutları engellenir.
- Sorgu sonuçları metin başlangıcından tahmin edilmek yerine `cursor.description` üzerinden belirlenir.
- Hata ve başarı sonrasında rollback uygulanır; uygulama sorguları kalıcı olarak commit etmez.
- Sonuçlar 10.000 satırla sınırlandırılır.
- Aynı anda ikinci sorgu başlatılması hem arayüz hem bağlantı katmanında engellenir.
- Otomatik çalıştırma yalnızca read-only sorgulara izin verir ve hata aldığında durur.
- ODBC bağlantısı `Encrypt=yes` ve `TrustServerCertificate=no` kullanır.
- Bağlantı parametreleri ODBC değer kaçışıyla oluşturulur ve parola nesne alanında tutulmaz.
- Bağlantı hatasında parola metni dönen hata mesajından maskelenir.
- Veritabanı tanımlayıcısındaki kapanış köşeli parantezi güvenli biçimde kaçışlanır.
- VLF sorgusu `sys.dm_db_log_info` kullanacak şekilde read-only hâle getirildi.
- Build scriptinin kendiliğinden paket yüklemesi kaldırıldı ve izlenen spec dosyasıyla çalışması sağlandı.
- Kaynak ve dokümantasyon dosyaları için platformlar arası satır sonu kuralları eklendi.
- Windows tabanlı üç Python sürümü için test iş akışı eklendi.

## Değiştirilen dosyalar

- `sql_connection.py`
- `main.py`
- `predefined_queries.py`
- `README.md`
- `QUERY_COMPATIBILITY.md`
- `BUILD_INSTRUCTIONS.md`
- `build_exe.bat`
- `.gitignore`
- `.gitattributes`

## Eklenen dosyalar

- `query_safety.py`
- `tests/test_query_safety.py`
- `tests/test_sql_connection.py`
- `tests/test_predefined_queries.py`
- `.github/workflows/tests.yml`
- `SECURITY.md`
- `docs/changes/2026-09-04-query-execution-hardening.md`

## Kurulum ve devreye alma

1. Python 3.9 veya üzerini kurun.
2. `python -m pip install -r requirements.txt` komutunu çalıştırın.
3. SQL Server ODBC Driver 17 veya üzerini kurun.
4. SQL Server'a istemci tarafından güvenilen bir TLS sertifikası tanımlayın.
5. Uygulamayı `python main.py` ile çalıştırın.
6. Dağıtım için `build_exe.bat` veya `python -m PyInstaller build_exe.spec` kullanın.

Yeni ortam değişkeni, veritabanı migration'ı, servis yeniden başlatması veya IIS değişikliği yoktur.

## Test ve doğrulama

- `python -m unittest discover -s tests -v`
- Python AST söz dizimi kontrolü
- Tüm çalıştırılabilir hazır sorguların read-only politika kontrolü
- Git diff ve geçersiz eski referans taraması
- Açık kimlik bilgisi ve yayınlanmaması gereken dosya taraması
- Açık araç atfı ve commit metadata taraması
- Sabitlenmiş bağımlılıkların Python 3.12 üzerinde gerçek import kontrolü
- PyQt5 ana pencere oluşturma ve kapatma kontrolü (`QT_QPA_PLATFORM=offscreen`)
- Pandas ve openpyxl ile geçici XLSX yazma/okuma round-trip kontrolü
- PyInstaller 6.3.0 ile geçici klasörde EXE derlemesi
- OSV üzerinden kurulan doğrudan ve transitif bağımlılık sürümlerinin açık taraması; 19 pakette kayıtlı açık bulunmadı

Toplam 18 unit test ve dokuz Python dosyası için AST kontrolü başarılıdır. Son geçici build çıktısı 76.700.389 bayttır ve SHA-256 değeri `3083B4CB91966FCA25C7D109052AD487F0D45614B445DCD03CD20ADB8E2FAC7A` olarak kaydedilmiştir. Paketlenmiş EXE Windows oturumunda başarıyla açılmış ve ana pencere görüntülenmiştir; gerçek SQL Server bağlantısı bu aşamada doğrulanmamıştır.

## Güvenlik ve yetkilendirme

- Uygulama katmanı bilinen yazma ve yönetim komutlarını reddeder, birden çok ifadeli batch çalıştırmaz ve kalıcı transaction commit etmez.
- Uygulama katmanı kontrolü tek başına bir yetkilendirme sınırı kabul edilmez; SQL Server hesabı read-only ve en düşük yetkili olmalıdır.
- En düşük yetkili SQL Server hesabı kullanılmalıdır.
- `VIEW SERVER STATE` gerektiren tanılamalar için `sysadmin` verilmemelidir.
- Parola diskte, yapılandırma dosyasında veya nesne alanında saklanmaz.
- Sertifika doğrulaması kapatılmaz.
- `connection_config.json` ve `user_queries.json` Git ve dağıtım paketi dışında tutulmalıdır.

## Riskler ve dikkat edilmesi gerekenler

- Kendinden imzalı veya istemci tarafından güvenilmeyen SQL Server sertifikalarıyla bağlantı kurulmaz.
- Yazma sorgusu ihtiyacı olan kullanıcılar SSMS veya yetkili kurumsal yönetim aracını kullanmalıdır.
- Sonuç sınırı nedeniyle 10.000 satırdan büyük sonuç kümeleri arayüzde kırpılır.
- VLF sorgusu SQL Server 2016 SP2 veya üzerini gerektirir.
- Gerçek sunucu üzerinde entegrasyon testi yapılmadan production kullanıma alınmamalıdır.
- PyInstaller analizinde opsiyonel/koşullu modüller ve Windows API-set çözümlemesi için uyarılar oluştu; kaynak modül importu, görünmez GUI oluşturma, build ve paketlenmiş ana pencere açılışı başarılıdır. SQL bağlantısı ile sorgu/Excel akışları hedef ortamda ayrıca test edilmelidir.
- OSV sonucu tarama tarihindeki kayıtlara dayanır ve gelecekte açıklanacak güvenlik açıklarını kapsamaz.

## Geri alma yöntemi

- Kod değişiklikleri Git diff veya ilgili commit üzerinden geri alınabilir.
- Eski commit davranışı parolayı sakladığı ve yazma sorgularını commit ettiği için geri dönüş güvenlik açısından önerilmez.
- Eski VLF sorgusuna dönmek yerine eski SQL Server sürümleri için ayrı ve güvenli bir sorgu geliştirilmelidir.
- Veritabanı değişikliği yapılmadığı için veritabanı rollback işlemi yoktur.

## Sonraki adımlar

- Güvenilir test SQL Server üzerinde bağlantı, hazır sorgular, satır sınırı ve otomatik çalıştırmayı doğrulayın.
- Yayın sonrasında GitHub Actions testlerinin başarılı olduğunu doğrulayın.
