"""
Plano C — Cloud Function
Fluxo: Gmail (e-mail do Meta) → download CSV → Google Sheets

Acionada pelo Cloud Scheduler todo dia às 8h (horário de Brasília).
"""

import base64
import csv
import io
import json
import os
import re

import functions_framework
import gspread
import requests
from bs4 import BeautifulSoup
from google.oauth2.credentials import Credentials
from google.oauth2.service_account import Credentials as SACredentials
from googleapiclient.discovery import build

# ─── Constantes ───────────────────────────────────────────────────────────────

SHEET_NAME   = "Meta Ads - Campanhas"
GMAIL_USER   = "me"
SHEETS_SCOPE = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

# Critérios de busca do e-mail (AND implícito entre os termos)
EMAIL_QUERY = (
    'from:advertise-noreply@support.facebook.com '
    '"Kuna Capital Ad Account" '
    '"Campanhas" '
    'newer_than:3d'
)


# ─── Autenticação ─────────────────────────────────────────────────────────────

def get_gmail_service():
    """Cria o serviço Gmail API usando o token OAuth armazenado."""
    raw   = base64.b64decode(os.environ["GMAIL_TOKEN_B64"])
    data  = json.loads(raw)
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
    """Cria o cliente do Google Sheets usando a Service Account."""
    raw   = base64.b64decode(os.environ["GOOGLE_CREDENTIALS_B64"])
    info  = json.loads(raw)
    creds = SACredentials.from_service_account_info(info, scopes=SHEETS_SCOPE)
    return gspread.authorize(creds)


# ─── Gmail ────────────────────────────────────────────────────────────────────

def find_latest_meta_email(service):
    """Busca o e-mail mais recente do Meta com o relatório de campanhas."""
    result   = service.users().messages().list(
        userId=GMAIL_USER, q=EMAIL_QUERY, maxResults=1
    ).execute()
    messages = result.get("messages", [])

    if not messages:
        raise RuntimeError(
            "Nenhum e-mail do Meta encontrado nos últimos 3 dias.\n"
            f"Query usada: {EMAIL_QUERY}"
        )

    msg = service.users().messages().get(
        userId=GMAIL_USER, id=messages[0]["id"], format="full"
    ).execute()
    return msg


def _decode_part(part: dict) -> str | None:
    data = part.get("body", {}).get("data")
    if data:
        return base64.urlsafe_b64decode(data).decode("utf-8", errors="replace")
    return None


def extract_html_body(msg: dict) -> str:
    """Extrai o corpo HTML do e-mail."""
    payload = msg["payload"]

    # Mensagem simples
    if payload.get("mimeType") == "text/html":
        return _decode_part(payload) or ""

    # Mensagem multipart — procura recursivamente
    def find_html(parts):
        for part in parts:
            if part.get("mimeType") == "text/html":
                content = _decode_part(part)
                if content:
                    return content
            sub = part.get("parts", [])
            if sub:
                result = find_html(sub)
                if result:
                    return result
        return ""

    return find_html(payload.get("parts", []))


def extract_csv_url(html: str) -> str:
    """Extrai a URL do botão 'Baixar .csv' do corpo HTML."""
    soup = BeautifulSoup(html, "html.parser")

    # Procura link cujo texto contenha "csv"
    for a in soup.find_all("a", href=True):
        text = a.get_text(strip=True).lower()
        if "csv" in text:
            return a["href"]

    # Fallback: qualquer href com ".csv" ou "type=csv"
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if ".csv" in href.lower() or "type=csv" in href.lower():
            return href

    raise RuntimeError("Link 'Baixar .csv' não encontrado no e-mail.")


# ─── Download ────────────────────────────────────────────────────────────────

def get_fb_cookies() -> dict:
    """Extrai cookies do Facebook a partir da sessão salva pelo Playwright."""
    raw     = base64.b64decode(os.environ["FB_SESSION_B64"])
    session = json.loads(raw)
    return {
        c["name"]: c["value"]
        for c in session.get("cookies", [])
        if "facebook.com" in c.get("domain", "")
    }


def download_csv(url: str) -> bytes:
    """Baixa o CSV usando os cookies de sessão do Facebook."""
    cookies = get_fb_cookies()
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Referer": "https://www.facebook.com/",
    }
    resp = requests.get(url, headers=headers, cookies=cookies,
                        timeout=60, allow_redirects=True)
    resp.raise_for_status()

    content_type = resp.headers.get("content-type", "")
    if "text/html" in content_type:
        raise RuntimeError(
            "Sessão do Facebook expirou. "
            "Rode scrape_campaigns.py no seu computador para renovar o session.json, "
            "depois rode deploy_cloud.py novamente."
        )

    return resp.content


def parse_csv(content: bytes) -> list[list[str]]:
    """Converte o conteúdo CSV em lista de listas para o Sheets."""
    # Tenta detectar encoding (Meta usa UTF-8 com BOM ou latin-1)
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


# ─── Google Sheets ────────────────────────────────────────────────────────────

def write_to_sheets(rows: list[list[str]], client) -> str:
    """Escreve os dados na planilha, sobrescrevendo o conteúdo anterior."""
    spreadsheet = client.open(SHEET_NAME)

    try:
        sheet = spreadsheet.worksheet("Campanhas")
        sheet.clear()
    except gspread.exceptions.WorksheetNotFound:
        sheet = spreadsheet.add_worksheet(title="Campanhas", rows=10000, cols=100)

    sheet.update(rows)
    sheet.format("1:1", {"textFormat": {"bold": True}})

    return f"https://docs.google.com/spreadsheets/d/{spreadsheet.id}"


# ─── Entry point ──────────────────────────────────────────────────────────────

@functions_framework.http
def run(request):
    try:
        print("Iniciando Plano C: Gmail → CSV → Google Sheets")

        gmail   = get_gmail_service()
        sheets  = get_sheets_client()

        print("Buscando e-mail do Meta...")
        msg     = find_latest_meta_email(gmail)

        subject = next(
            (h["value"] for h in msg["payload"]["headers"] if h["name"] == "Subject"),
            "(sem assunto)"
        )
        print(f"E-mail encontrado: {subject}")

        html    = extract_html_body(msg)
        url     = extract_csv_url(html)
        print(f"Link CSV extraído: {url[:80]}...")

        content = download_csv(url)
        rows    = parse_csv(content)
        print(f"CSV baixado: {len(rows)-1} linhas de dados.")

        sheet_url = write_to_sheets(rows, sheets)
        msg_ok    = f"OK — {len(rows)-1} linhas enviadas para o Sheets. {sheet_url}"
        print(msg_ok)
        return msg_ok, 200

    except Exception as e:
        print(f"ERRO: {e}")
        return f"Erro: {e}", 500
