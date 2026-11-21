"""API-Football anahtarinin calisip calismadigini hizlica kontrol eder.

Kullanim:  python scripts/check_api.py
"""

import os

import requests
from dotenv import load_dotenv

load_dotenv()
api_key = os.environ.get("API_FOOTBALL_KEY")

if not api_key:
    raise SystemExit("API_FOOTBALL_KEY bulunamadi. .env.example dosyasini .env olarak kopyalayip doldur.")

print(f"1. API key okundu: {api_key[:4]}...{api_key[-4:]}")

url = "https://v3.football.api-sports.io/fixtures"
headers = {"x-apisports-key": api_key}
params = {"league": 253, "season": 2025, "status": "FT"}  # MLS 2025 Sezonu

print("2. API'ye istek atiliyor...")
r = requests.get(url, headers=headers, params=params, timeout=15)

print(f"3. Durum kodu: {r.status_code}")
json_data = r.json()

if json_data.get("errors"):
    print(f"API ERROR: {json_data['errors']}")
else:
    matches = json_data.get("response", [])
    print(f"Basarili! Toplam {len(matches)} mac cekildi.")
