# futbot — Futbol Maç Olasılık & Kupon Botu

Geçmiş maç verisinden bir **Dixon-Coles/Poisson modeli** kurar, maçlar için
1X2, 2.5 Alt/Üst, Karşılıklı Gol ve en olası skorları hesaplar; canlı
maçlarda kalan süreye göre olasılıkları günceller ve birden fazla maçtan
"en değerli" seçimleri bir araya getirerek kupon önerir.

Modelin çalışma şekli en aşağıda anlatıldı.
Sistemin oluşturulmasında yapay zeka yardımı alındı.

## Kurulum

```bash
git clone https://github.com/icizay/futbot.git
cd futbot
python -m venv .venv && source .venv/bin/activate
pip install -e .          # ya da: pip install -r requirements.txt
```

`pip install -e .` ile kurarsan `python -m futbot.cli ...` yerine kısaca
`futbot ...` komutunu da kullanabilirsin.

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
(8 takım, 200 maç) 

## Gerçek veriyle çalıştırma

1. https://www.api-football.com/ üzerinden (RapidAPI ya da doğrudan
   api-sports.io) ücretsiz bir API anahtarı al.
2. `.env.example` dosyasını `.env` olarak kopyala ve anahtarını yaz
   (`.env` git'e eklenmez):
   ```bash
   cp .env.example .env
   # .env içinde: API_FOOTBALL_KEY=your_key
   ```
   Anahtarın çalıştığını kontrol etmek için: `python scripts/check_api.py`
3. `--demo` bayrağını kaldırıp `--league-id` ve `--season` belirt:
   ```bash
   python -m futbot.cli predict --home Galatasaray --away Fenerbahce \
       --league-id 203 --season 2025
   ```
   (Liglerin `league-id` değerini API-Football dokümantasyonundan
   bulabilirsin: https://www.api-football.com/documentation-v3)

`coupon` komutu şu an sadece `--demo` modunda fikstür üretiyor; gerçek
kullanımda `cli.py` içindeki `cmd_coupon` fonksiyonuna `DataFetcher.get_live_fixtures()` ile takip edilmek istenen güncel fikstür listesini eklemek gerekiyor.

## Backtest (modeli piyasaya karşı ölçmek)

Her sezonun ilk yarısıyla model eğitilir, ikinci yarısı tahmin edilir ve 1X2
tahminleri **log-loss** ve **Brier** skoruyla puanlanır. Karşılaştırma
noktası, Pinnacle kapanış oranlarının ima ettiği olasılıklardır (marj power
yöntemiyle temizlenir). Veri: [football-data.co.uk](https://www.football-data.co.uk/),
API anahtarı gerekmez.

```bash
python -m futbot backtest --league T1 --season 2122 2223 2324 2425
```

| Lig (2021/22–2024/25, 2. yarılar) | Maç | futbot log-loss | Pinnacle log-loss | Baz çizgi | Mesafe kapatma |
|---|---|---|---|---|---|
| Süper Lig (`T1`) | 708 | 0.9914 | 0.9388 | 1.0547 | %55 |
| Premier League (`E0`) | 760 | 0.9713 | 0.9268 | 1.0622 | %67 |

*Mesafe kapatma:* takımlardan habersiz baz çizgiden (sadece ev/beraberlik/deplasman
frekansı) piyasaya olan log-loss farkının ne kadarını modelin kapattığı.

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
futbot/                  # repo kökü
├── futbot/              # Python paketi
│   ├── poisson_model.py   # Dixon-Coles/Poisson model: fit(), market_probabilities()
│   ├── data_fetcher.py    # API-Football entegrasyonu + demo veri üreteci
│   ├── live_tracker.py    # Canlı maç için kalan-süre ölçekli olasılık güncelleme
│   ├── coupon_builder.py  # Value/olasılık bazlı kupon oluşturma mantığı
│   ├── backtest.py        # Piyasaya karşı geriye dönük test (log-loss / Brier)
│   └── cli.py             # Komut satırı arayüzü (predict / live / coupon / backtest)
├── scripts/
│   └── check_api.py     # API anahtarını test eden küçük script
├── .env.example         # Ortam değişkeni şablonu
├── pyproject.toml
└── requirements.txt
```

## Yeni fikirler
- **Başka bir spor eklemek**
- **Daha güçlü model:** xG (expected goals) verisi eklemek (ör. Understat)
  gol sayısından daha efektif.
- **Canlı polling**

## Sorumlu kullanım

Geçmiş veriye dayalı istatistiksel tahminlerdir; sakatlık,
hakem kararları, motivasyon gibi faktörleri (veri olarak sağlanmadıkça)
hesaba katmaz. Bahis oynamayın.

# Model nasıl çalışıyor

Geçmiş maçlar okunur, her maç için ev sahibi takım, deplasman takımı ve golleri eğitim seti olur. Takım için attack/defense hesaplanır. Beklenen goller hesaplanır;

ev sahibi için:
```
  λ_home = exp(attack_home - defense_away + home_advantage)
```
deplasman takımı için:
```
  λ_away = exp(attack_away - defense_home)
```

Poisson dağılımı "X gol atma olasılığı" için kullanılır. Klasik poisson modellerinde bazı skor olasılıkları abartılmış olacağı için modelin gerçekçiliği amacıyla Dixon-Coles düzeltmesi eklenmiştir.

Basit şekilde model takım A'nın hücum gücü, ev sahibi avantajı ve B takımının savunma zayıflığı üzerinden gol tahmini yapar, beklenen golleri de skor olasılıklarına çevirir. Çıktılar da böylece, 

```
  ev sahibi oranı
  beraberlik oranı
  under/over
  karşılıklı gol
  en olası skorlar
```