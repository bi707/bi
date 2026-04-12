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
import os
import subprocess
import sys
import tempfile
import yaml
from pathlib import Path

PROJECT_ID    = "analytics-contas"
REGION        = "us-central1"
FUNCTION_NAME = "meta-ads-sheets"
FUNCTION_URL  = "https://meta-ads-sheets-zjeanpzfeq-uc.a.run.app"
ENV_YAML_PATH = ".env.yaml"

REQUIRED_FILES = ["credentials.json", "gmail_token.json", "session.json", ".env"]

# Credenciais grandes → Secret Manager (evita limite de 32 KB por env var)
# env_var_name: (arquivo_fonte, nome_do_secret)
LARGE_SECRETS = {
    "GOOGLE_CREDENTIALS_B64": ("credentials.json", "meta-ads-google-credentials"),
    "GMAIL_TOKEN_B64":        ("gmail_token.json",  "meta-ads-gmail-token"),
    "FB_SESSION_B64":         ("session.json",      "meta-ads-fb-session"),
}


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


def get_project_number() -> str:
    result = subprocess.run(
        ["gcloud", "projects", "describe", PROJECT_ID,
         "--format=value(projectNumber)"],
        capture_output=True, text=True, shell=True, check=True,
    )
    return result.stdout.strip()


def upsert_secret(secret_id: str, b64_value: str):
    """Cria ou atualiza um secret no Secret Manager com o valor base64."""
    # Verifica se o secret já existe
    exists = subprocess.run(
        ["gcloud", "secrets", "describe", secret_id,
         f"--project={PROJECT_ID}"],
        capture_output=True, shell=True,
    )
    if exists.returncode != 0:
        run(["gcloud", "secrets", "create", secret_id,
             f"--project={PROJECT_ID}",
             "--replication-policy=automatic"])

    # Grava valor em arquivo temporário e envia como nova versão
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".b64") as tmp:
        tmp.write(b64_value)
        tmp_path = tmp.name
    try:
        run(["gcloud", "secrets", "versions", "add", secret_id,
             f"--project={PROJECT_ID}",
             f"--data-file={tmp_path}"])
    finally:
        os.unlink(tmp_path)


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

    env = load_env(".env")

    run(["gcloud", "config", "set", "project", PROJECT_ID])

    print("\nHabilitando APIs necessárias...")
    run(["gcloud", "services", "enable",
         "cloudfunctions.googleapis.com",
         "cloudscheduler.googleapis.com",
         "cloudbuild.googleapis.com",
         "run.googleapis.com",
         "gmail.googleapis.com",
         "secretmanager.googleapis.com"])

    # Envia as 3 credenciais grandes para o Secret Manager
    print("\nEnviando credenciais para o Secret Manager...")
    for env_var, (src_file, secret_id) in LARGE_SECRETS.items():
        print(f"  {src_file} → secret '{secret_id}'")
        b64 = encode_file(src_file)
        upsert_secret(secret_id, b64)

    # Obtém o número do projeto para construir o email da service account
    print("\nObtendo número do projeto...")
    project_number = get_project_number()
    sa_email = f"{project_number}-compute@developer.gserviceaccount.com"
    print(f"  Service account: {sa_email}")

    # Concede acesso de leitura aos secrets para a service account da função
    print("\nConcedendo acesso de leitura aos secrets...")
    for _, (_, secret_id) in LARGE_SECRETS.items():
        subprocess.run(
            ["gcloud", "secrets", "add-iam-policy-binding", secret_id,
             f"--project={PROJECT_ID}",
             f"--member=serviceAccount:{sa_email}",
             "--role=roles/secretmanager.secretAccessor"],
            shell=True, check=False,  # check=False: pode já estar concedido
        )

    # Variáveis pequenas vão para .env.yaml (sem limite de tamanho)
    small_env = {
        "META_APP_ID":        env["META_APP_ID"],
        "META_APP_SECRET":    env["META_APP_SECRET"],
        "META_ACCESS_TOKEN":  env["META_ACCESS_TOKEN"],
        "META_AD_ACCOUNT_ID": env["META_AD_ACCOUNT_ID"],
    }
    with open(ENV_YAML_PATH, "w") as f:
        yaml.dump(small_env, f, default_flow_style=False, allow_unicode=True)
    print(f"\nVariáveis pequenas salvas em {ENV_YAML_PATH}")

    # --set-secrets mapeia env var → secret:versão (apenas os nomes, sem o valor)
    set_secrets = ",".join(
        f"{env_var}={secret_id}:latest"
        for env_var, (_, secret_id) in LARGE_SECRETS.items()
    )

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
        f"--env-vars-file={ENV_YAML_PATH}",
        f"--set-secrets={set_secrets}",
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

    print("\n" + "=" * 55)
    print("Deploy concluído!")
    print("A planilha será atualizada todo dia às 8h.")
    print("Para testar agora:")
    print(f"  gcloud scheduler jobs run {FUNCTION_NAME}-8h --location={REGION}")
    print("=" * 55)


if __name__ == "__main__":
    main()
