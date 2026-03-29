"""
Envia o CSV mais recente da pasta reports/ para o Google Sheets.

Uso:
    python upload_sheets.py
    python upload_sheets.py --file reports/campanhas_2026-03-01_2026-03-28.csv
"""

import argparse
import csv
from pathlib import Path

import gspread
from google.oauth2.service_account import Credentials

SHEET_NAME = "Meta Ads - Campanhas"
CREDENTIALS_FILE = "credentials.json"
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]


def get_latest_csv() -> Path:
    reports = sorted(Path("reports").glob("campanhas_*.csv"), reverse=True)
    if not reports:
        raise FileNotFoundError("Nenhum CSV encontrado em reports/. Rode scrape_campaigns.py primeiro.")
    return reports[0]


def upload(csv_path: Path):
    print(f"Conectando ao Google Sheets...")
    creds = Credentials.from_service_account_file(CREDENTIALS_FILE, scopes=SCOPES)
    client = gspread.authorize(creds)

    spreadsheet = client.open(SHEET_NAME)

    # Usa a primeira aba ou cria uma chamada "Campanhas"
    try:
        sheet = spreadsheet.worksheet("Campanhas")
        sheet.clear()
    except gspread.exceptions.WorksheetNotFound:
        sheet = spreadsheet.add_worksheet(title="Campanhas", rows=5000, cols=100)

    print(f"Lendo {csv_path.name} ...")
    with open(csv_path, encoding="utf-8-sig", newline="") as f:
        reader = csv.reader(f)
        rows = list(reader)

    if not rows:
        print("CSV está vazio.")
        return

    print(f"Enviando {len(rows)-1} linhas para '{SHEET_NAME}' → aba 'Campanhas'...")
    sheet.update(rows)

    # Formata o cabeçalho em negrito
    sheet.format("1:1", {"textFormat": {"bold": True}})

    url = f"https://docs.google.com/spreadsheets/d/{spreadsheet.id}"
    print(f"\nPlanilha atualizada com sucesso!")
    print(f"Acesse: {url}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--file", help="Caminho do CSV (padrão: mais recente em reports/)")
    args = parser.parse_args()

    csv_path = Path(args.file) if args.file else get_latest_csv()
    upload(csv_path)
