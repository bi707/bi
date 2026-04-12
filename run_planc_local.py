"""
Plano C — Local
Fluxo: Gmail (e-mail do Meta) → download CSV com cookies FB → Google Sheets

Roda no computador via Task Scheduler (substitui scrape_campaigns.py + upload_sheets.py).
Não precisa abrir browser.

Pré-requisitos (todos já na pasta C:\\Users\\Vanessa\\bi):
  - gmail_token.json  (gerado por gmail_auth.py)
  - session.json      (gerado por scrape_campaigns.py ao fazer login)
  - credentials.json  (Service Account do Google)
"""

import base64
import csv
import io
import json
import sys
from pathlib import Path

import gspread
from bs4 import BeautifulSoup
from google.oauth2.credentials import Credentials
from google.oauth2.service_account import Credentials as SACredentials
from googleapiclient.discovery import build

# ─── Constantes ───────────────────────────────────────────────────────────────

SHEET_NAME   = "Meta Ads - Campanhas"
SHEETS_SCOPE = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]
EMAIL_QUERY = (
    'from:advertise-noreply@support.facebook.com '
    '"Kuna Capital Ad Account" '
    '"Campanhas" '
    'newer_than:3d'
)
BASE_DIR = Path(__file__).parent


# ─── Autenticação ─────────────────────────────────────────────────────────────

def get_gmail_service():
    token_path = BASE_DIR / "gmail_token.json"
    if not token_path.exists():
        print("ERRO: gmail_token.json não encontrado. Rode gmail_auth.py primeiro.")
        sys.exit(1)

    with open(token_path) as f:
        data = json.load(f)

    creds = Credentials(
        token         = data.get("token"),
        refresh_token = data["refresh_token"],
        token_uri     = data["token_uri"],
        client_id     = data["client_id"],
        client_secret = data["client_secret"],
        scopes        = data["scopes"],
    )
    return build("gmail", "v1", credentials=creds, cache_discovery=False)


def get_sheets_client():
    creds_path = BASE_DIR / "credentials.json"
    if not creds_path.exists():
        print("ERRO: credentials.json não encontrado.")
        sys.exit(1)

    creds = SACredentials.from_service_account_file(
        str(creds_path), scopes=SHEETS_SCOPE
    )
    return gspread.authorize(creds)


# ─── Gmail ────────────────────────────────────────────────────────────────────

def find_latest_meta_email(service):
    result   = service.users().messages().list(
        userId="me", q=EMAIL_QUERY, maxResults=1
    ).execute()
    messages = result.get("messages", [])

    if not messages:
        print("Nenhum e-mail do Meta encontrado nos últimos 3 dias.")
        print(f"Query: {EMAIL_QUERY}")
        sys.exit(1)

    return service.users().messages().get(
        userId="me", id=messages[0]["id"], format="full"
    ).execute()


def extract_html_body(msg: dict) -> str:
    payload = msg["payload"]

    if payload.get("mimeType") == "text/html":
        data = payload.get("body", {}).get("data")
        if data:
            return base64.urlsafe_b64decode(data).decode("utf-8", errors="replace")

    def find_html(parts):
        for part in parts:
            if part.get("mimeType") == "text/html":
                data = part.get("body", {}).get("data")
                if data:
                    return base64.urlsafe_b64decode(data).decode("utf-8", errors="replace")
            result = find_html(part.get("parts", []))
            if result:
                return result
        return ""

    return find_html(payload.get("parts", []))


def extract_csv_url(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")

    for a in soup.find_all("a", href=True):
        if "csv" in a.get_text(strip=True).lower():
            return a["href"]

    for a in soup.find_all("a", href=True):
        href = a["href"]
        if ".csv" in href.lower() or "type=csv" in href.lower():
            return href

    raise RuntimeError("Link 'Baixar .csv' não encontrado no e-mail.")


# ─── Download ─────────────────────────────────────────────────────────────────

def download_csv(url: str) -> bytes:
    """
    Baixa o CSV usando Playwright (browser real com sessão salva).
    requests.get() é rejeitado pelo Facebook por TLS fingerprinting;
    o Playwright usa um Chromium real que passa pela verificação.
    """
    import tempfile
    import os
    from playwright.sync_api import sync_playwright

    session_path = BASE_DIR / "session.json"
    if not session_path.exists():
        print("ERRO: session.json não encontrado. Rode scrape_campaigns.py para fazer login.")
        sys.exit(1)

    tmp_dir = tempfile.mkdtemp()
    csv_path = None

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(storage_state=str(session_path))
        page    = context.new_page()

        print("  Abrindo link no browser (headless)...")
        with page.expect_download(timeout=60_000) as dl_info:
            try:
                page.goto(url, timeout=20_000)
            except Exception:
                # goto pode levantar timeout/navigation ao iniciar download
                pass

        download = dl_info.value
        filename = download.suggested_filename or "report.csv"
        csv_path = os.path.join(tmp_dir, filename)
        download.save_as(csv_path)
        print(f"  Download concluído: {filename}")

        browser.close()

    with open(csv_path, "rb") as f:
        content = f.read()

    os.unlink(csv_path)
    os.rmdir(tmp_dir)
    return content


def parse_csv(content: bytes) -> list[list]:
    for encoding in ("utf-8-sig", "utf-8", "latin-1"):
        try:
            text   = content.decode(encoding)
            reader = csv.reader(io.StringIO(text))
            rows   = list(reader)
            if rows:
                return rows
        except Exception:
            continue
    raise RuntimeError("Não foi possível decodificar o CSV.")


# ─── Google Sheets ─────────────────────────────────────────────────────────────

def write_to_sheets(rows: list[list], client) -> str:
    spreadsheet = client.open(SHEET_NAME)

    try:
        sheet = spreadsheet.worksheet("Campanhas")
        sheet.clear()
    except gspread.exceptions.WorksheetNotFound:
        sheet = spreadsheet.add_worksheet(title="Campanhas", rows=10000, cols=100)

    sheet.update(rows)
    sheet.format("1:1", {"textFormat": {"bold": True}})
    return f"https://docs.google.com/spreadsheets/d/{spreadsheet.id}"


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    print("=== Plano C Local: Gmail → CSV → Google Sheets ===\n")

    print("Conectando ao Gmail...")
    gmail = get_gmail_service()

    print("Conectando ao Google Sheets...")
    sheets = get_sheets_client()

    print("Buscando e-mail do Meta...")
    msg = find_latest_meta_email(gmail)

    subject = next(
        (h["value"] for h in msg["payload"]["headers"] if h["name"] == "Subject"),
        "(sem assunto)"
    )
    print(f"  E-mail: {subject}")

    html = extract_html_body(msg)
    url  = extract_csv_url(html)
    print(f"  Link: {url[:80]}...")

    print("\nBaixando CSV...")
    content = download_csv(url)

    rows = parse_csv(content)
    print(f"  {len(rows) - 1} linhas de dados.")

    print("\nAtualizando Google Sheets...")
    sheet_url = write_to_sheets(rows, sheets)

    print(f"\nConcluído! Planilha: {sheet_url}")


if __name__ == "__main__":
    main()
