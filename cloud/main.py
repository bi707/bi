"""
Cloud Function - Meta Ads → Google Sheets
Acionada pelo Cloud Scheduler 2x por dia.
"""

import base64
import json
import os
from datetime import date

import functions_framework
import gspread
from facebook_business.adobjects.adaccount import AdAccount
from facebook_business.adobjects.adsinsights import AdsInsights
from facebook_business.adobjects.campaign import Campaign
from facebook_business.api import FacebookAdsApi
from google.oauth2.service_account import Credentials

SHEET_NAME = "Meta Ads - Campanhas"
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

# Nomes amigáveis para eventos padrão do Meta
NOMES_PADRAO = {
    "link_click": "Cliques no link",
    "lead": "Lead",
    "purchase": "Compra",
    "offsite_conversion.fb_pixel_lead": "Lead (Pixel)",
    "offsite_conversion.fb_pixel_purchase": "Compra (Pixel)",
    "post_engagement": "Engajamento",
    "page_like": "Curtida na Página",
    "video_view": "Visualização de Vídeo",
    "landing_page_view": "Visualização de Página de Destino",
    "add_to_cart": "Adicionar ao Carrinho",
    "initiate_checkout": "Iniciar Checkout",
    "complete_registration": "Registro Completo",
    "view_content": "Visualização de Conteúdo",
    "subscribe": "Assinatura",
}


# ─── Autenticação ─────────────────────────────────────────────────────────────

def init_meta_api():
    FacebookAdsApi.init(
        os.environ["META_APP_ID"],
        os.environ["META_APP_SECRET"],
        os.environ["META_ACCESS_TOKEN"],
    )
    return AdAccount(os.environ["META_AD_ACCOUNT_ID"])


def init_google():
    """Credenciais do Google a partir de base64 salvo como variável de ambiente."""
    raw = base64.b64decode(os.environ["GOOGLE_CREDENTIALS_B64"])
    info = json.loads(raw)
    return Credentials.from_service_account_info(info, scopes=SCOPES)


# ─── Meta API ────────────────────────────────────────────────────────────────

def get_custom_conversion_names(account) -> dict:
    """Busca nomes amigáveis das conversões personalizadas da conta."""
    try:
        conversions = account.get_custom_conversions(fields=["name", "id"])
        return {
            f"offsite_conversion.custom.{c['id']}": c["name"]
            for c in (c.export_all_data() for c in conversions)
        }
    except Exception as e:
        print(f"Aviso ao buscar conversões customizadas: {e}")
        return {}


def nome_amigavel(action_type: str, custom_names: dict) -> str:
    if action_type in NOMES_PADRAO:
        return NOMES_PADRAO[action_type]
    if action_type in custom_names:
        return custom_names[action_type]
    return action_type


def get_action_value(lst: list | None, action_type: str) -> str:
    for item in (lst or []):
        if item.get("action_type") == action_type:
            return item.get("value", "")
    return ""


def fetch_data(since: str, until: str) -> list[dict]:
    account = init_meta_api()
    custom_names = get_custom_conversion_names(account)

    insight_fields = [
        AdsInsights.Field.campaign_id,
        AdsInsights.Field.campaign_name,
        AdsInsights.Field.impressions,
        AdsInsights.Field.reach,
        AdsInsights.Field.clicks,
        AdsInsights.Field.spend,
        AdsInsights.Field.cpm,
        AdsInsights.Field.cpc,
        AdsInsights.Field.ctr,
        AdsInsights.Field.frequency,
        AdsInsights.Field.actions,
        AdsInsights.Field.cost_per_action_type,
        AdsInsights.Field.date_start,
        AdsInsights.Field.date_stop,
    ]
    params = {
        "level": "campaign",
        "time_range": {"since": since, "until": until},
    }
    insights = account.get_insights(fields=insight_fields, params=params)
    rows = [i.export_all_data() for i in insights]

    # Enriquece com campos da campanha (status, orçamento, objetivo)
    campaigns = account.get_campaigns(fields=[
        Campaign.Field.id,
        Campaign.Field.status,
        Campaign.Field.effective_status,
        Campaign.Field.objective,
        Campaign.Field.daily_budget,
        Campaign.Field.lifetime_budget,
    ])
    camp_meta = {c["id"]: c.export_all_data() for c in campaigns}

    for row in rows:
        m = camp_meta.get(row.get("campaign_id"), {})
        row["status"] = m.get("status", "")
        row["effective_status"] = m.get("effective_status", "")
        row["objective"] = m.get("objective", "")
        daily = m.get("daily_budget", "")
        lifetime = m.get("lifetime_budget", "")
        row["budget"] = daily if daily else lifetime
        row["budget_type"] = "Diário" if daily else "Vitalício"
        row["_custom_names"] = custom_names

    return rows


# ─── Montar planilha ──────────────────────────────────────────────────────────

def build_rows(rows: list[dict]) -> list[list]:
    if not rows:
        return []

    custom_names = rows[0].get("_custom_names", {})

    # Coleta todos os tipos de ação na ordem em que aparecem
    action_types, seen = [], set()
    for row in rows:
        for a in (row.get("actions") or []):
            at = a["action_type"]
            if at not in seen:
                action_types.append(at)
                seen.add(at)

    cabecalho = [
        "Campanha", "ID Campanha", "Veiculação", "Objetivo",
        "Orçamento", "Tipo Orçamento", "Valor Usado",
        "Impressões", "Alcance", "Frequência",
        "Cliques", "CTR (%)", "CPM", "CPC",
        "Data Início", "Data Fim",
    ]
    # Colunas de Resultados com nomes amigáveis (igual ao Meta Ads Manager)
    cabecalho += [f"Resultado: {nome_amigavel(at, custom_names)}" for at in action_types]
    cabecalho += [f"Custo por: {nome_amigavel(at, custom_names)}" for at in action_types]

    data = [cabecalho]
    for row in rows:
        actions = row.get("actions") or []
        cost_per = row.get("cost_per_action_type") or []

        linha = [
            row.get("campaign_name", ""),
            row.get("campaign_id", ""),
            row.get("effective_status", row.get("status", "")),
            row.get("objective", ""),
            row.get("budget", ""),
            row.get("budget_type", ""),
            row.get("spend", ""),
            row.get("impressions", ""),
            row.get("reach", ""),
            row.get("frequency", ""),
            row.get("clicks", ""),
            row.get("ctr", ""),
            row.get("cpm", ""),
            row.get("cpc", ""),
            row.get("date_start", ""),
            row.get("date_stop", ""),
        ]
        for at in action_types:
            linha.append(get_action_value(actions, at))
        for at in action_types:
            linha.append(get_action_value(cost_per, at))

        data.append(linha)

    return data


# ─── Google Sheets ────────────────────────────────────────────────────────────

def write_to_sheets(data: list[list], creds) -> str:
    client = gspread.authorize(creds)
    spreadsheet = client.open(SHEET_NAME)

    try:
        sheet = spreadsheet.worksheet("Campanhas")
        sheet.clear()
    except gspread.exceptions.WorksheetNotFound:
        sheet = spreadsheet.add_worksheet(title="Campanhas", rows=5000, cols=150)

    sheet.update(data)
    sheet.format("1:1", {"textFormat": {"bold": True}})

    return f"https://docs.google.com/spreadsheets/d/{spreadsheet.id}"


# ─── Entry point ──────────────────────────────────────────────────────────────

@functions_framework.http
def run(request):
    today = date.today()
    since = today.replace(day=1).strftime("%Y-%m-%d")
    until = today.strftime("%Y-%m-%d")

    print(f"Período: {since} → {until}")
    rows = fetch_data(since, until)

    if not rows:
        return "Nenhum dado encontrado.", 200

    data = build_rows(rows)
    google_creds = init_google()
    url = write_to_sheets(data, google_creds)

    msg = f"OK — {len(rows)} campanhas enviadas para o Sheets. {url}"
    print(msg)
    return msg, 200
