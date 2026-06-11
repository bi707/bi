"""
Coleta Instagram Insights da CazeTv e envia para Google Sheets.

Cria/atualiza a planilha "Instagram Insights - CazeTv" com 4 abas:
  Perfil   — métricas diárias da conta (seguidores, alcance, impressões...)
  Posts    — métricas por publicação de feed (imagens, vídeos, carrosséis)
  Reels    — métricas por Reel (plays, alcance, tempo médio de visualização...)
  Stories  — métricas por Story (impressões, taps, saídas...)

Uso:
    python cazetv_instagram.py                          # últimos 30 dias
    python cazetv_instagram.py --since 2026-05-01
    python cazetv_instagram.py --since 2026-05-01 --until 2026-05-31

Credenciais necessárias no .env:
    CAZETV_INSTAGRAM_ACCESS_TOKEN  — Page Access Token com permissões de insights
    CAZETV_INSTAGRAM_ACCOUNT_ID    — ID numérico da conta Instagram Business
"""

import argparse
from datetime import date, timedelta

import gspread
from google.oauth2.service_account import Credentials
from dotenv import load_dotenv

from instagram.client import InstagramClient

load_dotenv()

SPREADSHEET_NAME = "Instagram Insights - CazeTv"
CREDENTIALS_FILE = "credentials.json"
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

HEADER_FORMAT = {
    "textFormat": {"bold": True, "foregroundColor": {"red": 1, "green": 1, "blue": 1}},
    "backgroundColor": {"red": 0.18, "green": 0.31, "blue": 0.60},
}


# ------------------------------------------------------------------
# Helpers de Sheets
# ------------------------------------------------------------------

def sheets_client() -> gspread.Client:
    creds = Credentials.from_service_account_file(CREDENTIALS_FILE, scopes=SCOPES)
    return gspread.authorize(creds)


def open_or_create(gc: gspread.Client) -> gspread.Spreadsheet:
    try:
        return gc.open(SPREADSHEET_NAME)
    except gspread.exceptions.SpreadsheetNotFound:
        print(f'  Criando nova planilha "{SPREADSHEET_NAME}"...')
        return gc.create(SPREADSHEET_NAME)


def upsert_sheet(spreadsheet: gspread.Spreadsheet, title: str) -> gspread.Worksheet:
    try:
        ws = spreadsheet.worksheet(title)
        ws.clear()
        return ws
    except gspread.exceptions.WorksheetNotFound:
        return spreadsheet.add_worksheet(title=title, rows=5000, cols=50)


def write_sheet(ws: gspread.Worksheet, rows: list[list]):
    if not rows:
        return
    ws.update(rows)
    ws.format("1:1", HEADER_FORMAT)


# ------------------------------------------------------------------
# Construção das tabelas
# ------------------------------------------------------------------

def build_perfil_rows(account_insights: dict) -> list[list]:
    header = [
        "Data",
        "Novos Seguidores",
        "Alcance",
        "Impressões",
        "Visitas ao Perfil",
        "Contas Engajadas",
        "Cliques no Site",
    ]
    metric_keys = [
        "follower_count",
        "reach",
        "impressions",
        "profile_views",
        "accounts_engaged",
        "website_clicks",
    ]
    # Indexar cada métrica por data
    by_date: dict[str, dict[str, int]] = {}
    for key in metric_keys:
        for entry in account_insights.get(key, []):
            d = entry["date"]
            by_date.setdefault(d, {})[key] = entry["value"]

    rows = [header]
    for d in sorted(by_date):
        row = [d] + [by_date[d].get(k, "") for k in metric_keys]
        rows.append(row)
    return rows


def build_posts_rows(media_with_insights: list[dict]) -> list[list]:
    header = [
        "ID", "Data", "Tipo", "Caption",
        "Curtidas", "Comentários", "Impressões",
        "Alcance", "Compartilhamentos", "Salvamentos",
        "Interações Totais", "Link",
    ]
    rows = [header]
    for m in media_with_insights:
        ins = m.get("_insights", {})
        rows.append([
            m["id"],
            m.get("timestamp", "")[:10],
            m.get("media_type", ""),
            (m.get("caption") or "")[:300],
            m.get("like_count", ins.get("likes", "")),
            m.get("comments_count", ins.get("comments", "")),
            ins.get("impressions", ""),
            ins.get("reach", ""),
            ins.get("shares", ""),
            ins.get("saved", ""),
            ins.get("total_interactions", ""),
            m.get("permalink", ""),
        ])
    return rows


def build_reels_rows(media_with_insights: list[dict]) -> list[list]:
    header = [
        "ID", "Data", "Caption",
        "Plays", "Alcance", "Curtidas", "Comentários",
        "Compartilhamentos", "Salvamentos", "Interações Totais",
        "Tempo Médio de Visualização (s)", "Link",
    ]
    rows = [header]
    for m in media_with_insights:
        ins = m.get("_insights", {})
        rows.append([
            m["id"],
            m.get("timestamp", "")[:10],
            (m.get("caption") or "")[:300],
            ins.get("plays", ""),
            ins.get("reach", ""),
            ins.get("likes", ""),
            ins.get("comments", ""),
            ins.get("shares", ""),
            ins.get("saved", ""),
            ins.get("total_interactions", ""),
            ins.get("ig_reels_avg_watch_time", ""),
            m.get("permalink", ""),
        ])
    return rows


def build_stories_rows(media_with_insights: list[dict]) -> list[list]:
    header = [
        "ID", "Data",
        "Impressões", "Alcance", "Respostas",
        "Taps Avançar", "Taps Voltar", "Saídas",
    ]
    rows = [header]
    for m in media_with_insights:
        ins = m.get("_insights", {})
        rows.append([
            m["id"],
            m.get("timestamp", "")[:10],
            ins.get("impressions", ""),
            ins.get("reach", ""),
            ins.get("replies", ""),
            ins.get("taps_forward", ""),
            ins.get("taps_back", ""),
            ins.get("exits", ""),
        ])
    return rows


# ------------------------------------------------------------------
# Runner principal
# ------------------------------------------------------------------

def run(since: str, until: str):
    print(f"\nInstagram Insights — CazeTv")
    print(f"Período: {since} → {until}")
    print("=" * 50)

    ig = InstagramClient()

    # 1. Perfil
    print("\n[1/4] Perfil...")
    profile = ig.get_profile()
    username = profile.get("username", "?")
    followers = profile.get("followers_count", "?")
    print(f"  @{username} · {followers} seguidores")

    # 2. Account insights
    print("\n[2/4] Insights da conta (diário)...")
    account_insights = ig.get_account_insights(since, until)
    total_days = max((len(v) for v in account_insights.values()), default=0)
    print(f"  {total_days} dias coletados.")

    # 3. Mídias + insights individuais
    print("\n[3/4] Mídias e insights individuais...")
    media_items = ig.get_media(since, until)
    print(f"  {len(media_items)} mídias encontradas.")

    posts, reels, stories = [], [], []
    for idx, m in enumerate(media_items, 1):
        mpt = (m.get("media_product_type") or m.get("media_type") or "FEED").upper()
        ts = m.get("timestamp", "")[:10]
        print(f"  [{idx:>3}/{len(media_items)}] {mpt:<15} {ts}")
        m["_insights"] = ig.get_media_insights(m["id"], mpt)

        if mpt == "REELS":
            reels.append(m)
        elif mpt == "STORY":
            stories.append(m)
        else:
            posts.append(m)

    print(f"\n  Posts: {len(posts)}  |  Reels: {len(reels)}  |  Stories: {len(stories)}")

    # 4. Enviar para Sheets
    print("\n[4/4] Enviando para Google Sheets...")
    gc = sheets_client()
    spreadsheet = open_or_create(gc)

    write_sheet(upsert_sheet(spreadsheet, "Perfil"), build_perfil_rows(account_insights))
    write_sheet(upsert_sheet(spreadsheet, "Posts"), build_posts_rows(posts))
    write_sheet(upsert_sheet(spreadsheet, "Reels"), build_reels_rows(reels))
    write_sheet(upsert_sheet(spreadsheet, "Stories"), build_stories_rows(stories))

    # Remove a aba padrão "Sheet1" se existir
    try:
        spreadsheet.del_worksheet(spreadsheet.worksheet("Sheet1"))
    except Exception:
        pass

    sheet_url = f"https://docs.google.com/spreadsheets/d/{spreadsheet.id}"
    print(f"\n  Planilha atualizada: {sheet_url}")
    print("\nConcluido.")


if __name__ == "__main__":
    today = date.today()
    default_since = (today - timedelta(days=30)).strftime("%Y-%m-%d")
    default_until = today.strftime("%Y-%m-%d")

    parser = argparse.ArgumentParser(
        description="Coleta Instagram Insights da CazeTv e envia para Google Sheets."
    )
    parser.add_argument("--since", default=default_since, help="Data de início YYYY-MM-DD (padrão: -30 dias)")
    parser.add_argument("--until", default=default_until, help="Data de fim YYYY-MM-DD (padrão: hoje)")
    args = parser.parse_args()

    run(args.since, args.until)
