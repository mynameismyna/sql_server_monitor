# Düz Metin Parola Saklamanın Kaldırılması

## İşlem özeti

- **İşlem:** SQL Server Authentication parolasının yerel dosyada saklanmasının kaldırılması
- **Amaç:** Kimlik bilgilerinin kaynak proje, dağıtım klasörü veya paylaşılabilir arşiv üzerinden açığa çıkma riskini azaltmak
- **Kapsam:** Bağlantı ayarları, kullanıcı arayüzündeki kayıtlı ayar yükleme akışı, dağıtım talimatları, testler ve mevcut yerel hassas dosyalar
- **Tarih:** 2026-09-04

## Teknik değişiklikler

- `config_manager.py`, yeni bağlantı ayarlarına parola alanı yazmayacak şekilde değiştirildi.
- Eski `connection_config.json` dosyalarında parola alanı bulunursa yükleme sırasında kaldıran geriye dönük temizleme eklendi.
- Yapılandırma yazma işlemi geçici dosya ve atomik değiştirme yöntemiyle güncellendi.
- `main.py`, kayıtlı parolayı arayüze yüklemeyecek ve parola değerini yapılandırma yöneticisine iletmeyecek şekilde değiştirildi.
- `README.md` ve `BUILD_INSTRUCTIONS.md` güvenli parola davranışına göre güncellendi.
- `build_exe.bat` çıktısı, parolanın kaydedilmediğini açıkça belirtecek şekilde güncellendi.
- `dist.rar`, hassas yapılandırma içeren dağıtım arşivinin yanlışlıkla Git'e eklenmesini engellemek için `.gitignore` kapsamına alındı.
- Antivirüsü kapatma veya geniş kapsamlı istisna oluşturma önerileri kaldırıldı.
- `tests/test_config_manager.py` ile parola alanının yazılmadığı ve eski alanın temizlendiği doğrulandı.
- Yerel ve dağıtım klasörlerindeki `connection_config.json` dosyaları silindi.
- Kullanıcı onayı sonrasında hassas yapılandırma kopyası içeren eski `dist.rar` arşivi ve eski davranışla derlenmiş `dist\SQL_Sunucu_Takip.exe` kalıcı olarak silindi.

## Kurulum ve devreye alma

- Yeni bağımlılık eklenmedi.
- Uygulama normal şekilde `python main.py` veya yeniden oluşturulan EXE üzerinden çalıştırılır.
- SQL Server Authentication kullanılırken parola her uygulama oturumunda yeniden girilir.
- Dağıtım paketi gerekiyorsa temiz kaynak koddan yeniden derlenmeli ve `connection_config.json` pakete eklenmemelidir.

## Test ve doğrulama

- Python kaynak dosyaları AST söz dizimi kontrolünden geçirilir.
- `python -m unittest discover -s tests -v` komutuyla yapılandırma güvenlik testleri çalıştırılır.
- Git geçmişinde `connection_config.json` ve `user_queries.json` dosyalarının izlenmediği kontrol edilir.
- Proje ve dağıtım klasörlerinde `connection_config.json` kalmadığı doğrulanır.
- Eski `dist.rar` arşivinin hassas yapılandırma içerdiği doğrulandı; kullanıcı onayıyla arşiv ve eski EXE silindi, ardından yoklukları kontrol edildi.

## Güvenlik ve yetkilendirme

- Parola artık kalıcı depolamaya yazılmaz.
- Parola yalnızca bağlantı kurulurken uygulama belleğinde ve ODBC bağlantı çağrısında kullanılır.
- SQL Server hesapları için minimum yetki ilkesi geçerlidir; bazı tanılama sorguları ek sunucu izinleri gerektirebilir.
- Gerçek kimlik bilgileri yedeklenmedi, loglanmadı veya dokümana yazılmadı.

## Riskler ve dikkat edilmesi gerekenler

- SQL Server Authentication kullanıcıları parolayı her oturumda yeniden girmelidir.
- Daha önce başka konumlara kopyalanmış arşiv veya yapılandırma dosyaları bu işlemle otomatik temizlenmez.
- Eski arşivin veya yapılandırma dosyasının başka konumlara kopyalanmış örnekleri varsa bunlar ayrıca bulunup güvenli şekilde kaldırılmalıdır.
- Parolanın daha önce paylaşılmış olma ihtimali varsa ilgili SQL Server hesabının parolası ayrıca değiştirilmelidir.
- Uygulamanın özel sorgu çalıştırma yeteneği devam eder; hesap yetkileri en düşük gerekli seviyede tutulmalıdır.

## Geri alma yöntemi

- Kod değişiklikleri Git üzerinden geri alınabilir; ancak düz metin parola saklama davranışının geri getirilmesi güvenlik nedeniyle önerilmez.
- Silinen hassas yapılandırma dosyası, eski dağıtım arşivi ve eski EXE için yedek oluşturulmadı; EXE temiz kaynak koddan yeniden üretilebilir.
- Dağıtım paketi temiz kaynak kod ve `BUILD_INSTRUCTIONS.md` kullanılarak yeniden üretilebilir.

## Sonraki adımlar

- SQL Server hesabının mevcut parolasını döndürün; eski parolanın dosya veya arşiv kopyalarında bulunmuş olabileceğini varsayın.
- Yeni bir EXE oluşturup parola alanı içermeyen temiz bir dağıtım paketi hazırlayın.
- İstenirse Windows Credential Manager veya DPAPI tabanlı isteğe bağlı güvenli kimlik bilgisi saklama ayrı bir değişiklik olarak tasarlanabilir.
