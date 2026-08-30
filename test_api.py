import os
import requests
from dotenv import load_dotenv
from pathlib import Path

load_dotenv(Path(__file__).resolve().parent / ".env")
api_key = os.environ.get("API_FOOTBALL_KEY")

print(f"1. Okunan API Key: {api_key}")

url = "https://v3.football.api-sports.io/fixtures"
headers = {"x-apisports-key": api_key}
params = {"league": 253, "season": 2025, "status": "FT"} # MLS 2025 Sezonu

print("2. API'ye istek atılıyor...")
r = requests.get(url, headers=headers, params=params)

print(f"3. Durum Kodu: {r.status_code}")
json_data = r.json()

if "errors" in json_data and json_data["errors"]:
    print(f"API ERROR: {json_data['errors']}")
else:
    matches = json_data.get("response", [])
    print(f"Başarılı! Toplam {len(matches)} maç çekildi.")