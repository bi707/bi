"""
Autenticação única com o Gmail (roda apenas uma vez no seu computador).
Gera o arquivo gmail_token.json com as credenciais de acesso.

Uso:
    pip install google-auth-oauthlib
    python gmail_auth.py
"""

import json
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]

print("Abrindo navegador para autorizar acesso ao Gmail...")
flow = InstalledAppFlow.from_client_secrets_file("gmail_credentials.json", SCOPES)
creds = flow.run_local_server(port=0)

token_data = {
    "token":         creds.token,
    "refresh_token": creds.refresh_token,
    "token_uri":     creds.token_uri,
    "client_id":     creds.client_id,
    "client_secret": creds.client_secret,
    "scopes":        list(creds.scopes),
}

with open("gmail_token.json", "w") as f:
    json.dump(token_data, f, indent=2)

print("\nAutenticação concluída! Arquivo gmail_token.json gerado.")
print("Agora rode: python deploy_cloud.py")
