from playwright.sync_api import sync_playwright
import streamlit as st
from datetime import datetime
import os
from io import BytesIO

def baixar_extrato(data_inicio, data_fim):
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,  # no Render precisa headless
            args=["--no-sandbox", "--disable-dev-shm-usage"]
        )
        context = browser.new_context(accept_downloads=True)
        page = context.new_page()

        page.goto("https://finance.pagstar.com/")
        st.info("Aguardando login manual... (no Render não haverá janela visível)")

        page.wait_for_timeout(20000)  # tempo p/ login (se necessário via cookie/session)

        # continue seu fluxo...
        # clique em Extrato / Detalhado / Exportar, preencher datas etc.

        with page.expect_download() as download_info:
            page.get_by_role("button", name="Baixar Relatório", exact=True).click()
        download = download_info.value

        # Se quiser enviar o arquivo direto no Streamlit:
        conteudo = download.path()  # caminho temporário no container
        with open(conteudo, "rb") as f:
            data = f.read()

        browser.close()
        return data  # bytes do arquivo

# UI
st.title("Pagstar")
col1, col2 = st.columns(2)
data_inicio = col1.date_input("Data de início")
data_fim = col2.date_input("Data de fim")

if st.button("Baixar Extrato"):
    try:
        binario = baixar_extrato(str(data_inicio), str(data_fim))
        st.success("✅ Extrato gerado!")
        st.download_button(
            "📥 Clique para baixar",
            data=binario,
            file_name=f"Extrato_Pagstar_{data_inicio}_a_{data_fim}.csv",
            mime="text/csv"
        )
    except Exception as e:
        st.error(f"❌ Erro ao gerar extrato:\n\n{e}")
