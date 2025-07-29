import streamlit as st
from datetime import datetime
import io
from playwright.sync_api import sync_playwright

def baixar_extrato(data_inicio, data_fim):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)  # Render não suporta janelas
        context = browser.new_context()
        page = context.new_page()

        page.goto("https://finance.pagstar.com/")
        page.wait_for_timeout(20000)  # 20s para login manual

        page.get_by_role("button", name="Extrato", exact=True).click()
        page.wait_for_timeout(2000)
        page.get_by_role("button", name="Detalhado", exact=True).click()
        page.wait_for_timeout(2000)
        page.get_by_role("button", name="Exportar", exact=True).click()
        page.wait_for_timeout(2000)

        data_inicio_fmt = datetime.strptime(data_inicio, "%Y-%m-%d").strftime("%Y-%m-%d")
        data_fim_fmt = datetime.strptime(data_fim, "%Y-%m-%d").strftime("%Y-%m-%d")

        page.fill('#initialDate', f"{data_inicio_fmt}T00:00")
        page.fill('#finalDate', f"{data_fim_fmt}T23:59")
        page.wait_for_timeout(1000)

        page.get_by_role("button", name="Excel", exact=True).click()
        page.wait_for_timeout(1000)

        with page.expect_download() as download_info:
            page.get_by_role("button", name="Baixar Relatório", exact=True).click()

        download = download_info.value
        buffer = io.BytesIO(download.content())

        browser.close()
        return buffer, f"Extrato_Pagstar_{data_inicio_fmt}_a_{data_fim_fmt}.csv"

# STREAMLIT
st.title("📄 Download de Extrato - Pagstar")

with st.form("form_extrato"):
    col1, col2 = st.columns(2)
    data_inicio = col1.date_input("Data de Início")
    data_fim = col2.date_input("Data de Fim")
    submit = st.form_submit_button("🔽 Baixar Extrato")

if submit:
    st.info("⏳ Gerando extrato... faça login na janela aberta")
    try:
        buffer, nome_arquivo = baixar_extrato(str(data_inicio), str(data_fim))
        st.success("✅ Extrato gerado!")
        st.download_button("📥 Clique para baixar", buffer, file_name=nome_arquivo)
    except Exception as e:
        st.error(f"❌ Erro ao gerar extrato: {e}")

