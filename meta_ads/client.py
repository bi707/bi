import os
from typing import Any

from dotenv import load_dotenv
from facebook_business.adobjects.adaccount import AdAccount
from facebook_business.adobjects.campaign import Campaign
from facebook_business.adobjects.adset import AdSet
from facebook_business.adobjects.ad import Ad
from facebook_business.adobjects.adsinsights import AdsInsights

from .auth import init_api

load_dotenv()


class MetaAdsClient:
    """Cliente para o Meta Ads Manager (Marketing API)."""

    def __init__(self):
        init_api()
        account_id = os.environ["META_AD_ACCOUNT_ID"]
        self.account = AdAccount(account_id)

    # ------------------------------------------------------------------
    # Campanhas
    # ------------------------------------------------------------------

    def get_campaigns(self, fields: list[str] | None = None) -> list[dict[str, Any]]:
        """Retorna todas as campanhas da conta."""
        fields = fields or [
            Campaign.Field.name,
            Campaign.Field.status,
            Campaign.Field.objective,
            Campaign.Field.start_time,
            Campaign.Field.stop_time,
            Campaign.Field.daily_budget,
            Campaign.Field.lifetime_budget,
        ]
        campaigns = self.account.get_campaigns(fields=fields)
        return [c.export_all_data() for c in campaigns]

    # ------------------------------------------------------------------
    # Conjuntos de anúncios (Ad Sets)
    # ------------------------------------------------------------------

    def get_ad_sets(self, fields: list[str] | None = None) -> list[dict[str, Any]]:
        """Retorna todos os conjuntos de anúncios da conta."""
        fields = fields or [
            AdSet.Field.name,
            AdSet.Field.status,
            AdSet.Field.campaign_id,
            AdSet.Field.daily_budget,
            AdSet.Field.lifetime_budget,
            AdSet.Field.start_time,
            AdSet.Field.end_time,
            AdSet.Field.targeting,
        ]
        ad_sets = self.account.get_ad_sets(fields=fields)
        return [a.export_all_data() for a in ad_sets]

    # ------------------------------------------------------------------
    # Anúncios
    # ------------------------------------------------------------------

    def get_ads(self, fields: list[str] | None = None) -> list[dict[str, Any]]:
        """Retorna todos os anúncios da conta."""
        fields = fields or [
            Ad.Field.name,
            Ad.Field.status,
            Ad.Field.campaign_id,
            Ad.Field.adset_id,
            Ad.Field.creative,
        ]
        ads = self.account.get_ads(fields=fields)
        return [a.export_all_data() for a in ads]

    # ------------------------------------------------------------------
    # Insights (métricas de desempenho)
    # ------------------------------------------------------------------

    def get_insights(
        self,
        level: str = "campaign",
        date_preset: str = "last_30d",
        fields: list[str] | None = None,
        extra_params: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """
        Retorna métricas de desempenho (insights).

        Parâmetros
        ----------
        level : str
            Nível de agregação: 'account', 'campaign', 'adset' ou 'ad'.
        date_preset : str
            Período predefinido do Meta Ads, ex: 'today', 'yesterday',
            'last_7d', 'last_30d', 'this_month', 'last_month'.
        fields : list[str] | None
            Lista de campos/métricas a retornar.
        extra_params : dict | None
            Parâmetros adicionais para a chamada da API.
        """
        fields = fields or [
            AdsInsights.Field.campaign_name,
            AdsInsights.Field.adset_name,
            AdsInsights.Field.ad_name,
            AdsInsights.Field.impressions,
            AdsInsights.Field.clicks,
            AdsInsights.Field.spend,
            AdsInsights.Field.reach,
            AdsInsights.Field.cpm,
            AdsInsights.Field.cpc,
            AdsInsights.Field.ctr,
            AdsInsights.Field.actions,
            AdsInsights.Field.date_start,
            AdsInsights.Field.date_stop,
        ]
        params = {"level": level, "date_preset": date_preset}
        if extra_params:
            params.update(extra_params)

        insights = self.account.get_insights(fields=fields, params=params)
        return [i.export_all_data() for i in insights]

    # ------------------------------------------------------------------
    # Informações da conta
    # ------------------------------------------------------------------

    def get_account_info(self, fields: list[str] | None = None) -> dict[str, Any]:
        """Retorna informações básicas da conta de anúncios."""
        fields = fields or [
            AdAccount.Field.name,
            AdAccount.Field.account_status,
            AdAccount.Field.currency,
            AdAccount.Field.timezone_name,
            AdAccount.Field.amount_spent,
            AdAccount.Field.balance,
        ]
        self.account.api_get(fields=fields)
        return self.account.export_all_data()
