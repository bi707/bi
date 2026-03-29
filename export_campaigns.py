"""
Exporta o relatório de campanhas no mesmo formato do botão
"Exportar como CSV" do Meta Ads Manager.

Uso:
    python export_campaigns.py                         # mês atual
    python export_campaigns.py --since 2026-02-01 --until 2026-02-28
    python export_campaigns.py --preset last_30d       # últimos 30 dias
"""

import argparse
import csv
from datetime import date
from pathlib import Path

from meta_ads import MetaAdsClient

# Colunas fixas que aparecem antes das ações dinâmicas
COLUNAS_FIXAS = [
    "campaign_name",
    "campaign_id",
    "veiculacao",
    "objetivo",
    "orcamento",
    "tipo_orcamento",
    "valor_usado",
    "impressoes",
    "alcance",
    "frequencia",
    "cliques",
    "ctr",
    "cpm",
    "cpc",
    "date_start",
    "date_stop",
]


def _get_action_value(lst: list[dict] | None, action_type: str) -> str:
    if not lst:
        return ""
    for item in lst:
        if item.get("action_type") == action_type:
            return item.get("value", "")
    return ""


def _collect_action_types(rows: list[dict]) -> list[str]:
    """Coleta todos os tipos de ação únicos em ordem de aparição."""
    seen: dict[str, None] = {}
    for row in rows:
        for action in row.get("actions") or []:
            seen[action["action_type"]] = None
    return list(seen.keys())


def parse_row(row: dict, action_types: list[str]) -> dict:
    actions = row.get("actions") or []
    cost_per = row.get("cost_per_action_type") or []

    out = {
        "campaign_name": row.get("campaign_name", ""),
        "campaign_id": row.get("campaign_id", ""),
        "veiculacao": row.get("effective_status", row.get("status", "")),
        "objetivo": row.get("objective", ""),
        "orcamento": row.get("budget", ""),
        "tipo_orcamento": row.get("budget_type", ""),
        "valor_usado": row.get("spend", ""),
        "impressoes": row.get("impressions", ""),
        "alcance": row.get("reach", ""),
        "frequencia": row.get("frequency", ""),
        "cliques": row.get("clicks", ""),
        "ctr": row.get("ctr", ""),
        "cpm": row.get("cpm", ""),
        "cpc": row.get("cpc", ""),
        "date_start": row.get("date_start", ""),
        "date_stop": row.get("date_stop", ""),
    }

    # Ações dinâmicas (Resultados)
    for at in action_types:
        out[f"resultado_{at}"] = _get_action_value(actions, at)

    # Custo por ação dinâmico (Custo por resultado)
    for at in action_types:
        out[f"custo_por_{at}"] = _get_action_value(cost_per, at)

    return out


def export(since: str | None = None, until: str | None = None, preset: str | None = None):
    today = date.today()
    since = since or today.replace(day=1).strftime("%Y-%m-%d")
    until = until or today.strftime("%Y-%m-%d")

    label = preset if preset else f"{since}_{until}"
    print(f"Buscando relatório de campanhas: {since} → {until} ...")

    client = MetaAdsClient()
    data = client.get_campaign_report(since=since, until=until)

    if not data:
        print("Nenhum dado encontrado para o período.")
        return

    action_types = _collect_action_types(data)
    colunas = (
        COLUNAS_FIXAS
        + [f"resultado_{at}" for at in action_types]
        + [f"custo_por_{at}" for at in action_types]
    )

    output_dir = Path("reports")
    output_dir.mkdir(exist_ok=True)
    filename = output_dir / f"campanhas_{label}.csv"

    with open(filename, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=colunas, extrasaction="ignore")
        writer.writeheader()
        for row in data:
            writer.writerow(parse_row(row, action_types))

    print(f"Relatório exportado: {filename}  ({len(data)} campanhas)")
    print(f"Ações encontradas: {', '.join(action_types) or 'nenhuma'}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Exporta relatório de campanhas Meta Ads")
    parser.add_argument("--since", help="Data início YYYY-MM-DD (padrão: 1º do mês atual)")
    parser.add_argument("--until", help="Data fim YYYY-MM-DD (padrão: hoje)")
    parser.add_argument("--preset", help="Período: last_30d, last_7d, this_month, last_month")
    args = parser.parse_args()

    export(since=args.since, until=args.until, preset=args.preset)
