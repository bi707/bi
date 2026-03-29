"""
Ponto de entrada para a integração com o Meta Ads Manager.

Execute:
    pip install -r requirements.txt
    cp .env.example .env   # preencha com suas credenciais
    python main.py
"""

import json
from meta_ads import MetaAdsClient


def main():
    client = MetaAdsClient()

    print("=== Informações da Conta ===")
    info = client.get_account_info()
    print(json.dumps(info, indent=2, ensure_ascii=False))

    print("\n=== Campanhas ===")
    campaigns = client.get_campaigns()
    print(json.dumps(campaigns, indent=2, ensure_ascii=False))

    print("\n=== Insights (últimos 30 dias, nível campanha) ===")
    insights = client.get_insights(level="campaign", date_preset="last_30d")
    print(json.dumps(insights, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
