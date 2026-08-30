# futbot — Futbol Maç Olasılık & Kupon Botu

Geçmiş maç verisinden bir **Dixon-Coles/Poisson modeli** kurar, maçlar için
1X2, 2.5 Alt/Üst, Karşılıklı Gol ve en olası skorları hesaplar; canlı
maçlarda kalan süreye göre olasılıkları günceller ve birden fazla maçtan
"en değerli" seçimleri bir araya getirerek kupon önerir.

> **Not:** Bu araç istatistiksel olasılık tahmini üretir, kesin sonuç
> garantisi vermez. Bahis kararlarını kendi sorumluluğunuzda verin.

## Kurulum

```bash
pip install -r requirements.txt
```

## Hızlı başlangıç (API anahtarı gerekmez)

```bash
# Tek maç tahmini
python -m futbot.cli predict --home Galatasaray --away Kasimpasa --demo

# Devam eden bir maçın güncel olasılığı (60. dakika, skor 1-0)
python -m futbot.cli live --home Galatasaray --away Kasimpasa --minute 60 --score 1-0 --demo

# Birden fazla maçtan kupon önerisi
python -m futbot.cli coupon --demo --top 5
```

`--demo` bayrağı, sabit bir seed ile üretilmiş sentetik lig verisi kullanır
(8 takım, 200 maç) — gerçek veriye bağlanmadan sistemi test etmen için.

## Gerçek veriyle çalıştırma

1. https://www.api-football.com/ üzerinden (RapidAPI ya da doğrudan
   api-sports.io) ücretsiz bir API anahtarı al.
2. Anahtarı gir — iki yoldan biriyle:

   **A) `.env` dosyası (önerilen, tek seferlik kurulum):**
   ```bash
   cp .env.example .env
   ```
   Sonra `.env` dosyasını aç ve satırı kendi anahtarınla değiştir:
   ```
   API_FOOTBALL_KEY=senin_gercek_anahtarin
   ```
   Kod bu dosyayı hangi dizinden çalıştırırsan çalıştır otomatik okur.
   `.env` dosyasını asla paylaşma/git'e ekleme (git kullanıyorsan
   `.gitignore`'a `.env` satırını ekle).

   **B) Ortam değişkeni (sadece o terminal oturumu için geçerli):**
   ```bash
   export API_FOOTBALL_KEY="senin_anahtarin"      # macOS/Linux
   $env:API_FOOTBALL_KEY = "senin_anahtarin"       # Windows PowerShell
   ```

3. `--demo` bayrağını kaldırıp `--league-id` ve `--season` belirt:
   ```bash
   python -m futbot.cli predict --home Galatasaray --away Fenerbahce \
       --league-id 203 --season 2025
   ```
   (Süper Lig'in `league-id` değerini API-Football dokümantasyonundan
   bulabilirsin: https://www.api-football.com/documentation-v3)

`coupon` komutu şu an sadece `--demo` modunda fikstür üretiyor; gerçek
kullanımda `cli.py` içindeki `cmd_coupon` fonksiyonuna
`DataFetcher.get_live_fixtures()` ile çekilen güncel fikstür listesini
eklemen gerekiyor (bilinçli olarak sana bıraktım, çünkü hangi ligi/hangi
maçları takip edeceğin sana kalmış).

## Model önbellekleme (cache)

Model her komut çalıştığında sıfırdan eğitilmiyor — ilk çalıştırmada eğitilip
`futbot/.cache/` klasörüne kaydediliyor, sonraki çalıştırmalarda (varsayılan
**24 saat** boyunca) doğrudan diskten yükleniyor. Bu hem API kotanı korur
hem de komutları anında sonuç verir hale getirir.

```bash
# Cache süresi dolmadan zorla yeniden eğitmek istersen:
python -m futbot.cli predict --home Galatasaray --away Fenerbahce --demo --refresh

# Cache'in kaç saat geçerli sayılacağını değiştirmek istersen (örn. 6 saat):
python -m futbot.cli predict --home Galatasaray --away Fenerbahce --demo --cache-hours 6
```

Cache anahtarı `--demo` modunda tek bir dosya (`model_demo.json`), gerçek
veriyle her `league-id`/`season` kombinasyonu için ayrı bir dosya olarak
tutulur (`model_league39_season2025.json` gibi) — yani farklı ligler
birbirinin cache'ini ezmez.

## Proje yapısı

```
futbot/
  poisson_model.py    # Dixon-Coles/Poisson model: fit(), market_probabilities()
  data_fetcher.py      # API-Football entegrasyonu + demo veri üreteci
  live_tracker.py       # Canlı maç için kalan-süre ölçekli olasılık güncelleme
  coupon_builder.py     # Value/olasılık bazlı kupon oluşturma mantığı
  cli.py                 # Komut satırı arayüzü (predict / live / coupon)
```

## Nasıl geniştirilir

- **Başka bir spor eklemek:** `poisson_model.py`'deki model futbole özgü
  (gol bazlı Poisson). Basketbol için sayı bazlı bir model (ör. Elo + toplam
  sayı regresyonu) ya da farklı bir dağılım gerekir; `data_fetcher.py`'ye
  yeni bir spor için ayrı bir fetcher sınıfı eklemek en temiz yol.
- **Oran (odds) verisiyle value bulma:** `DataFetcher.get_odds()` zaten var;
  `coupon_builder.picks_from_market_probs()`'a `odds` sözlüğü verirsen
  (`{("1x2","home"): 1.85, ...}`), kupon otomatik olarak model olasılığı ile
  oranın ima ettiği olasılığı kıyaslayıp "edge"e göre sıralar.
- **Daha güçlü model:** xG (expected goals) verisi eklemek (ör. Understat)
  gol sayısından daha öngörücü olur; `generate_demo_history` yerine gerçek
  xG bazlı ağırlıklandırma eklenebilir.
- **Telegram/Discord botuna dönüştürmek:** `cli.py`'deki `cmd_*`
  fonksiyonları zaten saf mantığı içeriyor; bir `python-telegram-bot`
  handler'ından bu fonksiyonları çağırman yeterli.
- **Canlı polling:** `live_tracker.poll_live_match()` hazır; `fetch_live_state`
  parametresine `DataFetcher.get_live_fixtures()`'ı saran bir fonksiyon
  verip gerçek zamanlı çalıştırabilirsin.

## Sorumlu kullanım

Model çıktıları geçmiş veriye dayalı istatistiksel tahminlerdir; sakatlık,
hakem kararları, motivasyon gibi faktörleri (veri olarak sağlanmadıkça)
hesaba katmaz. Kupon/bahis kararlarında tek girdi olarak kullanılmamalı.
