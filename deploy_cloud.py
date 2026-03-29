"""
Script de deploy da Cloud Function no Google Cloud.

Pré-requisitos:
  1. gcloud CLI instalado (cloud.google.com/sdk/docs/install)
  2. Rodado uma vez: gcloud auth login
  3. Este script deve ser rodado na pasta C:\\Users\\Vanessa\\bi

Uso:
    python deploy_cloud.py
"""

import base64
import json
import os
import subprocess
import sys
from pathlib import Path

PROJECT_ID = "analytics-contas"
REGION = "us-central1"
FUNCTION_NAME = "meta-ads-sheets"
CREDENTIALS_FILE = "credentials.json"
ENV_FILE = ".env"


def load_env(path: str) -> dict:
    env = {}
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, value = line.partition("=")
                env[key.strip()] = value.strip()
    return env


def encode_credentials(path: str) -> str:
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode()


def run(cmd: list, check=True):
    print(f"\n$ {' '.join(cmd)}")
    result = subprocess.run(cmd, check=check, capture_output=False, shell=True)
    return result


def main():
    # Verifica arquivos necessários
    for f in [CREDENTIALS_FILE, ENV_FILE]:
        if not Path(f).exists():
            print(f"ERRO: arquivo '{f}' não encontrado na pasta atual.")
            sys.exit(1)

    print("=== Deploy Meta Ads → Google Sheets (Cloud Function) ===\n")

    # Carrega variáveis de ambiente
    env = load_env(ENV_FILE)
    creds_b64 = encode_credentials(CREDENTIALS_FILE)

    # Monta as variáveis de ambiente para a Cloud Function
    env_vars = ",".join([
        f"META_APP_ID={env['META_APP_ID']}",
        f"META_APP_SECRET={env['META_APP_SECRET']}",
        f"META_ACCESS_TOKEN={env['META_ACCESS_TOKEN']}",
        f"META_AD_ACCOUNT_ID={env['META_AD_ACCOUNT_ID']}",
        f"GOOGLE_CREDENTIALS_B64={creds_b64}",
    ])

    # Define o projeto
    run(["gcloud", "config", "set", "project", PROJECT_ID])

    # Habilita APIs necessárias
    print("\nHabilitando APIs do Google Cloud...")
    run(["gcloud", "services", "enable",
         "cloudfunctions.googleapis.com",
         "cloudscheduler.googleapis.com",
         "cloudbuild.googleapis.com",
         "run.googleapis.com"])

    # Deploy da Cloud Function
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

    # Pega a URL da função
    result = subprocess.run([
        "gcloud", "functions", "describe", FUNCTION_NAME,
        "--gen2", f"--region={REGION}", "--format=value(serviceConfig.uri)"
    ], capture_output=True, text=True)
    function_url = result.stdout.strip()

    print(f"\nCloud Function disponível em:\n  {function_url}")

    # Cria o agendamento no Cloud Scheduler (2x por dia)
    print("\nConfigurando Cloud Scheduler (8h e 20h, horário de Brasília)...")

    for hora, job_name in [("8", f"{FUNCTION_NAME}-manha"), ("20", f"{FUNCTION_NAME}-tarde")]:
        run([
            "gcloud", "scheduler", "jobs", "create", "http", job_name,
            f"--location={REGION}",
            f"--schedule=0 {hora} * * *",
            "--time-zone=America/Sao_Paulo",
            f"--uri={function_url}",
            "--http-method=GET",
        ], check=False)  # check=False pois o job pode já existir

    print("\n" + "="*55)
    print("Deploy concluído com sucesso!")
    print(f"A planilha será atualizada todos os dias às 8h e 20h.")
    print("="*55)


if __name__ == "__main__":
    main()
