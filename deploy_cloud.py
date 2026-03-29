"""
Script de deploy da Cloud Function no Google Cloud (Plano C).

Pré-requisitos:
  1. gcloud CLI instalado e autenticado (gcloud auth login)
  2. gmail_auth.py já rodado → gmail_token.json gerado
  3. Rodar na pasta C:\\Users\\Vanessa\\bi

Uso:
    python deploy_cloud.py
"""

import base64
import json
import subprocess
import sys
from pathlib import Path

PROJECT_ID     = "analytics-contas"
REGION         = "us-central1"
FUNCTION_NAME  = "meta-ads-sheets"
FUNCTION_URL   = "https://meta-ads-sheets-zjeanpzfeq-uc.a.run.app"

REQUIRED_FILES = ["credentials.json", "gmail_token.json", ".env"]


def load_env(path: str) -> dict:
    env = {}
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, value = line.partition("=")
                env[key.strip()] = value.strip()
    return env


def encode_file(path: str) -> str:
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode()


def run(cmd: list, check=True):
    print(f"\n$ {' '.join(cmd)}")
    return subprocess.run(cmd, check=check, shell=True)


def main():
    # Verifica arquivos necessários
    missing = [f for f in REQUIRED_FILES if not Path(f).exists()]
    if missing:
        for f in missing:
            print(f"ERRO: arquivo '{f}' não encontrado.")
            if f == "gmail_token.json":
                print("  → Rode primeiro: python gmail_auth.py")
        sys.exit(1)

    print("=== Deploy Plano C — Gmail → CSV → Google Sheets ===\n")

    env           = load_env(".env")
    creds_b64     = encode_file("credentials.json")
    gmail_b64     = encode_file("gmail_token.json")

    env_vars = ",".join([
        f"GOOGLE_CREDENTIALS_B64={creds_b64}",
        f"GMAIL_TOKEN_B64={gmail_b64}",
        f"META_APP_ID={env['META_APP_ID']}",
        f"META_APP_SECRET={env['META_APP_SECRET']}",
        f"META_ACCESS_TOKEN={env['META_ACCESS_TOKEN']}",
        f"META_AD_ACCOUNT_ID={env['META_AD_ACCOUNT_ID']}",
    ])

    run(["gcloud", "config", "set", "project", PROJECT_ID])

    print("\nHabilitando APIs necessárias...")
    run(["gcloud", "services", "enable",
         "cloudfunctions.googleapis.com",
         "cloudscheduler.googleapis.com",
         "cloudbuild.googleapis.com",
         "run.googleapis.com",
         "gmail.googleapis.com"])

    print("\nFazendo deploy da Cloud Function...")
    run([
        "gcloud", "functions", "deploy", FUNCTION_NAME,
        "--gen2",
        "--runtime=python311",
        f"--region={REGION}",
        "--source=cloud",
        "--entry-point=run",
        "--trigger-http",
        "--allow-unauthenticated",
        "--timeout=300s",
        "--memory=512MB",
        f"--set-env-vars={env_vars}",
    ])

    print(f"\nCloud Function: {FUNCTION_URL}")

    # Cloud Scheduler — 8h (Brasília)
    print("\nConfigurando agendamento às 8h (Brasília)...")
    run([
        "gcloud", "scheduler", "jobs", "create", "http", f"{FUNCTION_NAME}-8h",
        f"--location={REGION}",
        "--schedule=0 8 * * *",
        "--time-zone=America/Sao_Paulo",
        f"--uri={FUNCTION_URL}",
        "--http-method=GET",
        "--attempt-deadline=320s",
    ], check=False)

    print("\n" + "="*55)
    print("Deploy concluído!")
    print("A planilha será atualizada todo dia às 8h.")
    print(f"Para testar agora:")
    print(f"  gcloud scheduler jobs run {FUNCTION_NAME}-8h --location={REGION}")
    print("="*55)


if __name__ == "__main__":
    main()
