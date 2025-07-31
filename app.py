import time
from io import BytesIO

import streamlit as st
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout


PAGSTAR_URL = "https://finance.pagstar.com/"


def baixar_extrato(usuario: str, senha: str) -> tuple[bytes, str]:
    """
    Faz login, navega: Extrato -> Detalhado -> Exportar -> Baixar Relatório
    e retorna (bytes_do_arquivo, nome_sugerido).
    Ajuste os seletores conforme a sua tela.
    """
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-dev-shm-usage",
            ],
        )
        context = browser.new_context(accept_downloads=True)
        page = context.new_page()

        page.goto(PAGSTAR_URL, wait_until="domcontentloaded")

        # ===== Login =====
        # Tente por rótulo acessível; caia para seletores de atributo estáveis.
        try:
            page.get_by_label("Usuário").fill(usuario)
        except Exception:
            page.locator('input[name="username"], input#username').first.fill(usuario)

        try:
            page.get_by_label("Senha").fill(senha)
        except Exception:
            page.locator('input[name="password"], input#password, input[type="password"]').first.fill(senha)

        # Clicar "Entrar"
        try:
            page.get_by_role("button", name="Entrar").click()
        except Exception:
            page.locator('button:has-text("Entrar"), text=Entrar').first.click()

        # Aguarda algo que só exista após login (ex.: menu Extrato)
        page.wait_for_selector("text=Extrato", timeout=15000)

        # ===== Fluxo do Extrato =====
        # Extrato
        try:
            page.get_by_role("link", name="Extrato").click()
        except Exception:
            page.locator("text=Extrato").first.click()

        page.wait_for_load_state("networkidle")

        # Detalhado
        try:
            page.get_by_role("button", name="Detalhado").click()
        except Exception:
            page.locator('button:has-text("Detalhado"), text=Detalhado').first.click()

        # (Se precisar selecionar período, ajuste aqui.)

        # Exportar
        try:
            page.get_by_role("button", name="Exportar").click()
        except Exception:
            page.locator('button:has-text("Exportar"), text=Exportar').first.click()

        # (Opcional) Escolher "Excel" se o menu exigir
        # try:
        #     page.get_by_role("menuitem", name="Excel").click()
        # except Exception:
        #     page.locator("text=Excel").first.click()

        # Baixar Relatório (captura do download)
        with page.expect_download(timeout=30000) as dl_info:
            try:
                page.get_by_role("button", name="Baixar Relatório").click()
            except Exception:
                page.locator('button:has-text("Baixar Relatório"), text=Baixar Relatório').first.click()

        download = dl_info.value

        # Lê os bytes SEM salvar em disco
        stream = download.create_read_stream()
        data = stream.read() if stream else b""

        suggested = download.suggested_filename or f"Extrato_Pagstar_{time.strftime('%Y%m%d_%H%M%S')}.xlsx"

        context.close()
        browser.close()

        if not data:
            raise RuntimeError("Não foi possível ler o conteúdo do arquivo baixado.")
        return data, suggested


# ================== Streamlit UI ==================
st.set_page_config(page_title="Extrato Pagstar", page_icon="📄", layout="centered")
st.title("📄 Extrato Pagstar (contorno sem variáveis de ambiente)")

with st.form("login_form"):
    st.write("Informe suas credenciais **apenas para esta sessão**. Elas não serão salvas.")
    usuario = st.text_input("Usuário", "")
    senha = st.text_input("Senha", "", type="password")
    submitted = st.form_submit_button("Baixar extrato")

if submitted:
    if not usuario or not senha:
        st.error("Preencha usuário e senha.")
    else:
        try:
            with st.spinner("Gerando relatório..."):
                data, fname = baixar_extrato(usuario, senha)
            st.success("Pronto! Seu relatório está disponível para download.")
            st.download_button("⬇️ Baixar arquivo", data=data, file_name=fname, type="primary")
        except PlaywrightTimeout:
            st.error("Tempo de espera excedido. Verifique a conexão ou se os seletores precisam de ajuste.")
        except Exception as e:
            st.error(f"Ocorreu um erro: {e}")

st.caption(
    "Dica: quando possível, migre para variáveis de ambiente ou Secret File no Render. "
    "Por ora, este contorno evita salvar credenciais e arquivos no servidor."
)