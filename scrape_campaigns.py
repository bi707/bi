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

        # Ajusta período para "Este mês" (1º do mês até hoje)
        print("Ajustando período para o mês atual...")
        try:
            # Abre o seletor de datas clicando em qualquer texto de período visível
            page.evaluate("""
                () => {
                    const els = Array.from(document.querySelectorAll('[role="button"]'));
                    const dateBtn = els.find(el =>
                        el.innerText && (
                            el.innerText.includes('dias') ||
                            el.innerText.includes('mês') ||
                            el.innerText.includes('days') ||
                            el.innerText.includes('month') ||
                            el.innerText.includes('Hoje') ||
                            el.innerText.includes('Today') ||
                            el.innerText.includes('Ontem') ||
                            el.innerText.includes('fev') ||
                            el.innerText.includes('mar') ||
                            el.innerText.includes('jan')
                        )
                    );
                    if (dateBtn) dateBtn.click();
                }
            """)
            page.wait_for_timeout(1500)

            # Clica em "Este mês"
            page.evaluate("""
                () => {
                    const els = Array.from(document.querySelectorAll('[role="option"], [role="menuitem"], li, div'));
                    const opt = els.find(el =>
                        el.innerText && (
                            el.innerText.trim() === 'Este mês' ||
                            el.innerText.trim() === 'This month'
                        )
                    );
                    if (opt) opt.click();
                }
            """)
            page.wait_for_timeout(1500)

            # Confirma clicando em Atualizar/Update
            page.evaluate("""
                () => {
                    const btns = Array.from(document.querySelectorAll('button, [role="button"]'));
                    const btn = btns.find(el =>
                        el.innerText && (
                            el.innerText.trim() === 'Atualizar' ||
                            el.innerText.trim() === 'Update' ||
                            el.innerText.trim() === 'Aplicar' ||
                            el.innerText.trim() === 'Apply'
                        )
                    );
                    if (btn) btn.click();
                }
            """)
            page.wait_for_timeout(3000)
            print("  Período ajustado: 1º do mês até hoje.")
        except Exception as e:
            print(f"Aviso ao ajustar data: {e}")

        # Clica no botão Exportar (seta para baixo no canto direito da barra de ferramentas)
        print("Clicando em Exportar...")
        page.wait_for_timeout(3000)

        export_clicked = False

        # Usa JavaScript para encontrar o botão que abre o menu de exportação
        # O menu contém "Exportar como .csv", então procuramos o botão que abre esse menu
        export_clicked = page.evaluate("""
            () => {
                // Tenta encontrar por aria-label
                const labels = ['Exportar', 'Export', 'Exportar tabela', 'Export table'];
                for (const label of labels) {
                    const el = document.querySelector(`[aria-label="${label}"]`);
                    if (el) { el.click(); return true; }
                }

                // Procura todos os botões/divs clicáveis com role=button na barra de ferramentas
                const buttons = Array.from(document.querySelectorAll('[role="button"]'));

                // Filtra os botões visíveis que têm seta para baixo (chevron)
                // e estão no lado direito da página (x > 800px)
                const rightButtons = buttons.filter(b => {
                    const rect = b.getBoundingClientRect();
                    return rect.x > 800 && rect.y > 280 && rect.y < 380 && rect.width < 60;
                });

                // Clica no segundo botão de seta para baixo (conforme instrução do usuário)
                if (rightButtons.length >= 2) {
                    rightButtons[1].click();
                    return true;
                } else if (rightButtons.length === 1) {
                    rightButtons[0].click();
                    return true;
                }
                return false;
            }
        """)

        if export_clicked:
            print("  Botão de exportar clicado via JavaScript.")


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
