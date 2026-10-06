# 🎵 Piyade RP — Profesyonel Discord Müzik Botu

Piyade RP sunucusu için özel olarak geliştirilmiş; YouTube müzik arama, doğrudan bağlantı ve cihazdan dosya yükleme desteği sunan, interaktif butonlu kontrol paneline sahip gelişmiş Discord müzik botu.

---

## ✨ Özellikler

- 🎶 **YouTube Müzik Çalma:** Şarkı adı yazarak otomatik arama yapma veya doğrudan YouTube URL'si (video/shorts) ile anında çalma.
- 📁 **Özel Ses Dosyası Oynatma (`/dosya-oynat`):** Bilgisayarınızdan veya telefonunuzdan MP3, WAV, OGG, FLAC gibi ses dosyalarını yükleyerek dinleme.
- 📥 **Akıllı Kuyruk & Sıra Sistemi:** Müzik çalarken yeni bir şarkı veya dosya eklendiğinde otomatik olarak sıraya eklenir ve sırası geldiğinde çalar.
- 🎛️ **İnteraktif Kontrol Paneli (UI Butonları):**
  - ⏯️ **Duraklat / Devam Et**
  - ⏭️ **Sıradakine Geç (Atla)**
  - 🔁 **Döngü Modu:** Kapalı / Tek Şarkı / Tüm Liste
  - 🔀 **Sırayı Karıştır**
  - 📜 **Kuyruğu Görüntüle**
  - 🔉 / 🔊 **Ses Seviyesi Ayarı (%10 artır / azalt)**
  - ⏹️ **Durdur & Kanaldan Ayrıl**
- 🔒 **Ses Kanalı Kilidi:** Bot bir ses kanalında aktifken, başka bir ses kanalındaki kullanıcılar botu kendi kanalına çekemez veya oradan çaları kontrol edemez.
- 👑 **Rol Yetki Koruması:** Müzik komutlarını ve panel butonlarını yalnızca **`@| Müzik Açma İzni`** (Rol ID: `1547589732937240627`) rolüne sahip üyeler ve sunucu yöneticileri kullanabilir.
- ⚡ **Railway & Docker Hazır:** FFmpeg ve Opus kütüphaneleri otomatik Docker container içerisinde yapılandırılmıştır, 7/24 kesintisiz çalışır.

---

## 📋 Slash Komutları

| Komut | Açıklama |
|---|---|
| `/oynat <şarkı>` | YouTube üzerinden isim aratarak veya YouTube linki ile şarkı çalar / sıraya ekler. |
| `/dosya-oynat <dosya>` | Cihazınızdan yüklediğiniz ses dosyasını (MP3, WAV, OGG vb.) çalar / sıraya ekler. |
| `/kuyruk` | Sırada bekleyen şarkı listesini ve toplam şarkı sayısını gösterir. |
| `/atla` | Şu anda çalan şarkıyı atlayarak sıradaki şarkıya geçer. |
| `/durdur` | Çalmayı durdurur, kuyruğu temizler ve bot ses kanalından ayrılır. |
| `/panel` | Aktif şarkı kontrol panelini komutun yazıldığı kanala tekrar gönderir. |
| `/karistir` | Sıradaki şarkıları rastgele sıraya dizer. |
| `/dongu <mod>` | Döngü modunu ayarlar (Kapalı, Tek Şarkı, Tüm Liste). |
| `/ses <seviye>` | Müzik sesini %0 ile %100 arasında ayarlar. |

---

## 🚀 Kurulum ve Railway'de 7/24 Çalıştırma Rehberi

### 1. Adım: Discord Geliştirici Portalından Botu Hazırlama
1. [Discord Developer Portal](https://discord.com/developers/applications) adresine gidin.
2. **New Application** butonuna tıklayın ve botunuza bir isim verin (Örn: `Piyade Müzik`).
3. Soldaki menüden **Bot** sekmesine gelin:
   - **Reset Token** diyerek botun **Token**'ını kopyalayın ve bir yere not edin (Railway'e ekleyeceğiz).
   - Sayfayı biraz aşağı kaydırın ve **Privileged Gateway Intents** bölümündeki:
     - ✅ **Server Members Intent**
     - ✅ **Message Content Intent**  
     seçeneklerini **AÇIK (Enabled)** konuma getirip kaydedin.
4. Soldaki menüden **OAuth2 ➔ URL Generator** sekmesine gelin:
   - **Scopes** kısmından: `bot` ve `applications.commands` kutucuklarını işaretleyin.
   - **Bot Permissions** kısmından:
     - `Send Messages`, `Embed Links`, `Attach Files`, `Connect`, `Speak`, `Use Application Commands` yetkilerini seçin (veya en kolayı `Administrator`).
   - En altta oluşan davet linkini kopyalayıp tarayıcınızda açarak botu Discord sunucunuza ekleyin.

---

### 2. Adım: Rol Sıralamasını Kontrol Edin
- Discord sunucunuzun **Sunucu Ayarları ➔ Roller** kısmında botun rolünün, yöneteceği üyelerin rollerinin üstünde olduğundan emin olun.
- Yetki rolü ID'niz olan `1547589732937240627` nolu role sahip kişilerin komutları kullanabileceğini unutmayın.

---

### 3. Adım: Kodları GitHub'a Gönderme
Eğer **GitHub Desktop** kullanıyorsanız:
1. GitHub Desktop uygulamasını açın.
2. Değişiklikler sol tarafta listelenecektir.
3. Sol alttaki açıklama kısmına `Piyade RP Muzik Botu ilk surum` yazın ve **Commit to main** butonuna basın.
4. Üst kısımdaki **Push origin** butonuna basarak dosyaları GitHub deponuza gönderin.

---

### 4. Adım: Railway'de Projeyi Başlatma (Deploy)
1. [Railway.app](https://railway.app/) sitesine gidin ve GitHub hesabınızla giriş yapın.
2. Sağ üstten **New Project** ➔ **Deploy from GitHub repo** seçeneğini seçin.
3. `piyade.rp.music.bot` deponuzu seçin.
4. Railway projeyi otomatik olarak algılayacaktır. Açılan proje panelinde bot servisinizin üzerine tıklayın.
5. **Variables** (Ortam Değişkenleri) sekmesine gelin ve şu değişkenleri ekleyin:

| Değişken Adı | Değer | Açıklama |
|---|---|---|
| `MUSIC_TOKEN` | *Botunuzun Tokeni* | Discord Developer Portal'dan aldığınız gizli bot tokeni |
| `MUSIC_ROLE_ID` | `1547589732937240627` | Müzik açma yetkisine sahip rolün ID'si |
| `GUILD_ID` | *Sunucunuzun ID'si* | (Opsiyonel) Slash komutlarının sunucuda anında görünmesini sağlar |

6. Değişkenleri ekledikten sonra Railway, projenin içindeki `Dockerfile`'ı kullanarak otomatik olarak FFmpeg dahil tüm kütüphaneleri yükleyecek ve botunuzu 7/24 çalışır hale getirecektir.
7. **View Logs** sekmesinden botun bağlandığını (`🤖 Bot Aktif: ...`) görebilirsiniz.

Tebrikler! Müzik botunuz kullanıma hazır. 🎧