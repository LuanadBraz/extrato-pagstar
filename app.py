import streamlit as st
from datetime import datetime
import os
import io
from playwright.sync_api import sync_playwright

def baixar_extrato(data_inicio, data_fim):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()

        page.goto("https://finance.pagstar.com/")
        st.info("Aguardando login manual...")

        page.wait_for_timeout(20000)  # 20 segundos para login manual

        try:
            page.get_by_role("button", name="Extrato", exact=True).click()
        except:
            browser.close()
            raise Exception("❌ Botão 'Extrato' não encontrado.")

        page.wait_for_timeout(2000)
        page.get_by_role("button", name="Detalhado", exact=True).click()
        page.wait_for_timeout(2000)
        page.get_by_role("button", name="Exportar", exact=True).click()
        page.wait_for_timeout(2000)

        # Preenche datas
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

        # Salva em memória
        buffer = io.BytesIO()
        download.save_as(buffer)
        buffer.seek(0)

        nome_arquivo = f"Extrato_Pagstar_{data_inicio_fmt}_a_{data_fim_fmt}.csv"

        browser.close()
        return buffer, nome_arquivo

# Interface Streamlit
st.set_page_config(page_title="Download Extrato Pagstar", layout="centered")
st.title("📄 Download de Extrato - Pagstar")

with st.form("form_extrato"):
    col1, col2 = st.columns(2)
    with col1:
        data_inicio = st.date_input("Data de Início")
    with col2:
        data_fim = st.date_input("Data de Fim")

    submitted = st.form_submit_button("🔽 Baixar Extrato")

if submitted:
    try:
        st.info("Aguardando geração do extrato... Realize o login manual na janela que será aberta.")
        buffer, nome_arquivo = baixar_extrato(str(data_inicio), str(data_fim))
        st.success("✅ Extrato gerado com sucesso!")
        st.download_button("📥 Clique para baixar", buffer, file_name=nome_arquivo)
    except Exception as e:
        st.error(f"❌ Erro ao gerar extrato:\n\n{e}")
