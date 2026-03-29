import os
from dotenv import load_dotenv
from facebook_business.api import FacebookAdsApi

load_dotenv()


def init_api() -> FacebookAdsApi:
    """Inicializa a API do Meta Ads com as credenciais do .env."""
    app_id = os.environ["META_APP_ID"]
    app_secret = os.environ["META_APP_SECRET"]
    access_token = os.environ["META_ACCESS_TOKEN"]

    api = FacebookAdsApi.init(app_id, app_secret, access_token)
    return api
