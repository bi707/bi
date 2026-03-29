"""
Exporta o relatório de campanhas do mês atual para CSV.

Uso:
    python export_campaigns.py                         # mês atual
    python export_campaigns.py --since 2026-02-01 --until 2026-02-28
"""

import argparse
import csv
import json
import os
from datetime import date
from pathlib import Path

from meta_ads import MetaAdsClient


COLUNAS = [
    "campaign_id",
    "campaign_name",
    "status",
    "objective",
    "date_start",
    "date_stop",
    "impressions",
    "reach",
    "frequency",
    "clicks",
    "ctr",
    "cpm",
    "cpc",
    "spend",
    # ações mais comuns extraídas do campo 'actions'
    "link_click",
    "post_engagement",
    "page_like",
    "lead",
    "purchase",
    # custo por ação
    "cost_per_link_click",
    "cost_per_lead",
    "cost_per_purchase",
]


def _extract_action(actions: list[dict] | None, action_type: str) -> str:
    if not actions:
        return ""
    for a in actions:
        if a.get("action_type") == action_type:
            return a.get("value", "")
    return ""


def parse_row(row: dict) -> dict:
    actions = row.get("actions") or []
    cost_per = row.get("cost_per_action_type") or []

    return {
        "campaign_id": row.get("campaign_id", ""),
        "campaign_name": row.get("campaign_name", ""),
        "status": row.get("status", ""),
        "objective": row.get("objective", ""),
        "date_start": row.get("date_start", ""),
        "date_stop": row.get("date_stop", ""),
        "impressions": row.get("impressions", ""),
        "reach": row.get("reach", ""),
        "frequency": row.get("frequency", ""),
        "clicks": row.get("clicks", ""),
        "ctr": row.get("ctr", ""),
        "cpm": row.get("cpm", ""),
        "cpc": row.get("cpc", ""),
        "spend": row.get("spend", ""),
        "link_click": _extract_action(actions, "link_click"),
        "post_engagement": _extract_action(actions, "post_engagement"),
        "page_like": _extract_action(actions, "like"),
        "lead": _extract_action(actions, "lead"),
        "purchase": _extract_action(actions, "purchase"),
        "cost_per_link_click": _extract_action(cost_per, "link_click"),
        "cost_per_lead": _extract_action(cost_per, "lead"),
        "cost_per_purchase": _extract_action(cost_per, "purchase"),
    }


def export(since: str | None = None, until: str | None = None):
    today = date.today()
    since = since or today.replace(day=1).strftime("%Y-%m-%d")
    until = until or today.strftime("%Y-%m-%d")

    print(f"Buscando relatório de campanhas: {since} → {until} ...")
    client = MetaAdsClient()
    data = client.get_campaign_report(since=since, until=until)

    if not data:
        print("Nenhum dado encontrado para o período.")
        return

    output_dir = Path("reports")
    output_dir.mkdir(exist_ok=True)
    filename = output_dir / f"campanhas_{since}_{until}.csv"

    with open(filename, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=COLUNAS, extrasaction="ignore")
        writer.writeheader()
        for row in data:
            writer.writerow(parse_row(row))

    print(f"Relatório exportado: {filename}  ({len(data)} campanhas)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Exporta relatório de campanhas Meta Ads")
    parser.add_argument("--since", help="Data início YYYY-MM-DD (padrão: 1º do mês atual)")
    parser.add_argument("--until", help="Data fim YYYY-MM-DD (padrão: hoje)")
    args = parser.parse_args()

    export(since=args.since, until=args.until)
