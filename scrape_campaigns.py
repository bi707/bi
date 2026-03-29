"""
Exporta o relatório de campanhas do Meta Ads Manager
clicando no botão "Exportar como .csv" via automação de navegador.

Uso:
    python scrape_campaigns.py
"""

import os
import shutil
import time
from datetime import date
from pathlib import Path

from dotenv import load_dotenv
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

load_dotenv()

EMAIL = os.environ["META_FB_EMAIL"]
PASSWORD = os.environ["META_FB_PASSWORD"]
AD_ACCOUNT_ID = os.environ["META_AD_ACCOUNT_ID"].replace("act_", "")

ADS_MANAGER_URL = (
    f"https://adsmanager.facebook.com/adsmanager/manage/campaigns?act={AD_ACCOUNT_ID}"
)

OUTPUT_DIR = Path("reports")
OUTPUT_DIR.mkdir(exist_ok=True)


def run():
    today = date.today()
    since = today.replace(day=1).strftime("%d/%m/%Y")
    until = today.strftime("%d/%m/%Y")
    filename = OUTPUT_DIR / f"campanhas_{today.replace(day=1).strftime('%Y-%m-%d')}_{today.strftime('%Y-%m-%d')}.csv"

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, slow_mo=500)
        context = browser.new_context(accept_downloads=True)
        page = context.new_page()

        # 1. Login no Facebook
        print("Abrindo Facebook...")
        page.goto("https://www.facebook.com/login", wait_until="networkidle")

        # Tenta diferentes seletores para o campo de e-mail
        email_selectors = ["#email", "input[name='email']", "input[type='email']"]
        for sel in email_selectors:
            try:
                page.wait_for_selector(sel, timeout=10_000)
                page.fill(sel, EMAIL)
                break
            except PlaywrightTimeout:
                continue

        pass_selectors = ["#pass", "input[name='pass']", "input[type='password']"]
        for sel in pass_selectors:
            try:
                page.fill(sel, PASSWORD)
                break
            except Exception:
                continue

        login_selectors = ["[name='login']", "button[type='submit']", "#loginbutton"]
        for sel in login_selectors:
            try:
                page.click(sel)
                break
            except Exception:
                continue

        # Aguarda possível 2FA ou checkpoint
        print("Aguardando login... (complete qualquer verificação se solicitado)")
        try:
            page.wait_for_url("**/facebook.com/**", timeout=60_000)
        except PlaywrightTimeout:
            pass
        page.wait_for_timeout(3000)

        # 2. Navega para o Ads Manager
        print("Abrindo Ads Manager...")
        page.goto(ADS_MANAGER_URL, wait_until="domcontentloaded")
        page.wait_for_timeout(5000)

        # 3. Fecha popups se existirem
        for selector in ["[aria-label='Fechar']", "[aria-label='Close']"]:
            try:
                btn = page.locator(selector).first
                if btn.is_visible(timeout=2000):
                    btn.click()
            except Exception:
                pass

        # 4. Ajusta o período para o mês atual
        print(f"Ajustando período: {since} → {until} ...")
        try:
            # Clica no seletor de datas
            date_btn = page.locator("text=Últimos 30 dias").first
            if not date_btn.is_visible(timeout=3000):
                date_btn = page.locator("[data-testid='date-selector']").first
            date_btn.click()
            page.wait_for_timeout(1000)

            # Seleciona "Este mês"
            for label in ["Este mês", "This month"]:
                opt = page.locator(f"text={label}").first
                if opt.is_visible(timeout=2000):
                    opt.click()
                    break
            page.wait_for_timeout(2000)

            # Confirma
            for label in ["Atualizar", "Update", "Aplicar", "Apply"]:
                btn = page.locator(f"text={label}").first
                if btn.is_visible(timeout=2000):
                    btn.click()
                    break
            page.wait_for_timeout(3000)
        except Exception as e:
            print(f"Aviso: não foi possível ajustar a data automaticamente ({e}). Continuando...")

        # 5. Clica no botão de exportar
        print("Clicando em Exportar...")
        page.wait_for_timeout(3000)

        export_clicked = False
        for label in ["Exportar", "Export"]:
            try:
                btn = page.locator(f"[aria-label='{label}']").first
                if btn.is_visible(timeout=3000):
                    btn.click()
                    export_clicked = True
                    break
            except Exception:
                pass

        if not export_clicked:
            # Tenta pelo ícone de download na barra de ferramentas
            try:
                page.locator("[data-testid='export-button']").click()
                export_clicked = True
            except Exception:
                pass

        if not export_clicked:
            print("Botão de exportar não encontrado. Tirando screenshot para diagnóstico...")
            page.screenshot(path="reports/debug.png")
            browser.close()
            return

        page.wait_for_timeout(1500)

        # 6. Clica em "Exportar como .csv"
        print("Selecionando 'Exportar como .csv'...")
        for label in ["Exportar como .csv", "Export as .csv", "Exportar como CSV"]:
            try:
                opt = page.locator(f"text={label}").first
                if opt.is_visible(timeout=3000):
                    with page.expect_download(timeout=30_000) as dl:
                        opt.click()
                    download = dl.value
                    download.save_as(filename)
                    print(f"\nRelatório exportado: {filename}")
                    break
            except Exception:
                continue

        browser.close()


if __name__ == "__main__":
    run()
