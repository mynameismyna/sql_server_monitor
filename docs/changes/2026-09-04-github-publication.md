# GitHub Yayını

## İşlem özeti

- **İşlem:** Güvenliği güçlendirilmiş SQL Server Monitor kaynaklarının GitHub `main` dalında yayımlanması
- **Amaç:** Eski kaynak içeriğini test edilmiş ve dokümante edilmiş yayın adayıyla değiştirmek
- **Depo:** `https://github.com/mynameismyna/sql_server_monitor`
- **Tarih:** 2026-09-04

## Teknik değişiklikler

- Kod ve güvenlik değişiklikleri `22a0ec4c47c241803b30e99f8496104d313b65be` commit'iyle yayımlandı.
- Kod ve testleri taşıyan ilk yayın ağacı 22 izlenen dosyadan oluşuyordu; bu yayın kaydının eklenmesiyle nihai `main` ağacı 23 dosyadır.
- Uzak `main`, `d604ff79ad5cacd61113cf3fd5ed9b553f92879c` commit'inden normal ve geri alınabilir push ile ilerletildi.
- Force-push veya Git geçmişini yeniden yazma işlemi yapılmadı.
- Derlenmiş EXE, bağlantı yapılandırması, kullanıcı sorguları ve hassas anahtar dosyaları depoya eklenmedi.

## Kurulum ve devreye alma

Yayın komutu:

```powershell
git push origin main
```

Kaynak kurulum ve EXE üretim adımları `README.md` ile `BUILD_INSTRUCTIONS.md` dosyalarında yer almaktadır. Veritabanı, IIS, DNS, firewall veya servis değişikliği yapılmadı.

## Test ve doğrulama

- 18 unit test yerelde başarılı oldu.
- Dokuz Python dosyası AST kontrolünden geçti.
- 71 çalıştırılabilir hazır sorgunun tamamı read-only politika kontrolünden geçti.
- Geçici EXE derlemesi ve Windows ana pencere açılışı başarılı oldu.
- GitHub Actions `Tests` çalışmaları Python 3.9, 3.11 ve 3.12 matrisinde başarılı oldu.
- Kod yayını CI kaydı: `https://github.com/mynameismyna/sql_server_monitor/actions/runs/33850096232`
- Yayın dokümantasyonu CI kaydı: `https://github.com/mynameismyna/sql_server_monitor/actions/runs/33850364891`
- Push sonrasında uzak ve yerel commit değerlerinin aynı olduğu doğrulandı.

## Güvenlik ve yetkilendirme

- Yayın ağacında açık kimlik bilgisi veya hassas dağıtım artefaktı bulunmadı.
- Commit içeriğinde araç atfı veya ortak-yazar metadata kaydı bulunmadı.
- Commit kimliği için GitHub'ın gizlilik korumalı `users.noreply.github.com` adresi kullanıldı.
- SQL Server hesabı read-only ve en düşük yetkili olmalıdır; uygulama katmanındaki sorgu kontrolü tek başına yetkilendirme sınırı değildir.

## Riskler ve dikkat edilmesi gerekenler

- Gerçek SQL Server bağlantısı ve hedef ortamdaki sorgu akışı henüz doğrulanmadı.
- Önceki commitler Git geçmişinde korunmaktadır. İncelemede geçmişte yayımlanmış gerçek secret bulunmadığı için geçmiş yeniden yazılmadı.
- TLS sertifikası istemci tarafından güvenilir değilse bağlantı kurulmayacaktır.

## Geri alma yöntemi

Kod yayınını geri almak için yeni bir tersine çevirme commit'i oluşturulabilir:

```powershell
git revert 22a0ec4c47c241803b30e99f8496104d313b65be
git push origin main
```

Bu işlem Git geçmişini korur. Eski parola saklama ve yazma sorgusu davranışlarının geri gelmesi güvenlik riski oluşturacağı için geri alma yalnızca zorunlu durumda uygulanmalıdır.

## Sonraki adımlar

- Güvenilir test SQL Server üzerinde bağlantı ve sorgu entegrasyon testini tamamlayın.
- İlk gerçek kullanımda TLS, yetki hataları ve uygulama loglarını izleyin.
- Yeni sürüm hazırlanırken aynı test, güvenlik taraması ve GitHub Actions kapılarını koruyun.
