"""
Exporta o relatório de campanhas do Meta Ads Manager
clicando no botão "Exportar como .csv" via automação de navegador.

Na primeira execução: faça o login manualmente no navegador que abrir.
Nas próximas execuções: a sessão fica salva e o login é automático.

Uso:
    python scrape_campaigns.py
"""

import os
from datetime import date
from pathlib import Path

from dotenv import load_dotenv
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

load_dotenv()

AD_ACCOUNT_ID = os.environ["META_AD_ACCOUNT_ID"].replace("act_", "")
ADS_MANAGER_URL = (
    f"https://adsmanager.facebook.com/adsmanager/manage/campaigns?act={AD_ACCOUNT_ID}"
)

OUTPUT_DIR = Path("reports")
OUTPUT_DIR.mkdir(exist_ok=True)

SESSION_FILE = Path("session.json")


def esta_logado(page) -> bool:
    try:
        page.wait_for_selector("[aria-label='Sua conta']", timeout=5000)
        return True
    except Exception:
        pass
    try:
        page.wait_for_selector("[data-testid='ads-manager-campaigns-table']", timeout=5000)
        return True
    except Exception:
        pass
    return "adsmanager.facebook.com" in page.url or (
        "facebook.com" in page.url and "login" not in page.url
    )


def run():
    today = date.today()
    filename = OUTPUT_DIR / f"campanhas_{today.replace(day=1).strftime('%Y-%m-%d')}_{today.strftime('%Y-%m-%d')}.csv"

    with sync_playwright() as p:
        # Usa sessão salva se existir
        launch_args = dict(headless=False, slow_mo=300)
        browser = p.chromium.launch(**launch_args)

        ctx_args = dict(accept_downloads=True)
        if SESSION_FILE.exists():
            ctx_args["storage_state"] = str(SESSION_FILE)

        context = browser.new_context(**ctx_args)
        page = context.new_page()

        # Tenta ir direto para o Ads Manager
        print("Abrindo Meta Ads Manager...")
        page.goto(ADS_MANAGER_URL, wait_until="domcontentloaded", timeout=30_000)
        page.wait_for_timeout(4000)

        # Se caiu na tela de login, aguarda o usuário logar manualmente
        if "login" in page.url or "facebook.com/login" in page.url:
            print("\n" + "="*55)
            print("AÇÃO NECESSÁRIA: faça o login no navegador que abriu.")
            print("Após entrar, aguarde — o script continua sozinho.")
            print("="*55 + "\n")

            # Aguarda até estar no Ads Manager (até 3 minutos)
            try:
                page.wait_for_url(f"**{AD_ACCOUNT_ID}**", timeout=180_000)
            except PlaywrightTimeout:
                try:
                    page.wait_for_url("**/adsmanager/**", timeout=60_000)
                except PlaywrightTimeout:
                    pass
            page.wait_for_timeout(5000)

        # Salva sessão para próximas execuções
        context.storage_state(path=str(SESSION_FILE))
        print("Sessão salva.")

        # Fecha popups
        for selector in ["[aria-label='Fechar']", "[aria-label='Close']", "[data-testid='dialog-close-button']"]:
            try:
                btn = page.locator(selector).first
                if btn.is_visible(timeout=1500):
                    btn.click()
                    page.wait_for_timeout(500)
            except Exception:
                pass

        # Ajusta período para "Este mês"
        print("Ajustando período para o mês atual...")
        try:
            for label in ["Últimos 30 dias", "Last 30 days", "Ontem", "Yesterday", "Hoje", "Today"]:
                try:
                    btn = page.locator(f"text='{label}'").first
                    if btn.is_visible(timeout=2000):
                        btn.click()
                        break
                except Exception:
                    pass

            for label in ["Este mês", "This month"]:
                try:
                    opt = page.locator(f"text='{label}'").first
                    if opt.is_visible(timeout=2000):
                        opt.click()
                        break
                except Exception:
                    pass

            for label in ["Atualizar", "Update", "Aplicar", "Apply"]:
                try:
                    btn = page.locator(f"text='{label}'").first
                    if btn.is_visible(timeout=2000):
                        btn.click()
                        break
                except Exception:
                    pass

            page.wait_for_timeout(3000)
        except Exception as e:
            print(f"Aviso ao ajustar data: {e}")

        # Clica no botão Exportar
        print("Clicando em Exportar...")
        page.wait_for_timeout(2000)

        export_clicked = False
        for label in ["Exportar", "Export"]:
            try:
                btn = page.locator(f"[aria-label='{label}']").first
                if btn.is_visible(timeout=4000):
                    btn.click()
                    export_clicked = True
                    break
            except Exception:
                pass

        if not export_clicked:
            print("Botão exportar não encontrado. Salvando screenshot em reports/debug.png ...")
            page.screenshot(path="reports/debug.png", full_page=True)
            browser.close()
            print("Abra reports/debug.png e me envie para diagnóstico.")
            return

        page.wait_for_timeout(1500)

        # Clica em "Exportar como .csv"
        print("Selecionando 'Exportar como .csv'...")
        for label in ["Exportar como .csv", "Export as .csv", "Exportar como CSV", "Export as CSV"]:
            try:
                opt = page.locator(f"text='{label}'").first
                if opt.is_visible(timeout=3000):
                    with page.expect_download(timeout=60_000) as dl:
                        opt.click()
                    download = dl.value
                    download.save_as(str(filename))
                    print(f"\nRelatório exportado com sucesso: {filename}")
                    break
            except Exception:
                continue
        else:
            print("Opção 'Exportar como .csv' não encontrada. Salvando screenshot...")
            page.screenshot(path="reports/debug.png", full_page=True)
            print("Abra reports/debug.png e me envie para diagnóstico.")

        browser.close()


if __name__ == "__main__":
    run()
