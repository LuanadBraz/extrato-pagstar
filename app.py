#!/usr/bin/env python
# coding: utf-8

# In[ ]:


import streamlit as st
import asyncio
from datetime import datetime
import os
from playwright.async_api import async_playwright


# In[ ]:


async def baixar_extrato(data_inicio, data_fim):
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context()
        page = await context.new_page()

        await page.goto("https://finance.pagstar.com/")
        await page.wait_for_timeout(20000)  # Tempo para login manual

        await page.get_by_role("button", name="Extrato", exact=True).click()
        await page.wait_for_timeout(2000)

        await page.get_by_role("button", name="Detalhado", exact=True).click()
        await page.wait_for_timeout(2000)

        await page.get_by_role("button", name="Exportar", exact=True).click()
        await page.wait_for_timeout(2000)

        data_inicio_fmt = datetime.strptime(data_inicio, "%Y-%m-%d").strftime("%Y-%m-%d")
        data_fim_fmt = datetime.strptime(data_fim, "%Y-%m-%d").strftime("%Y-%m-%d")

        await page.fill('#initialDate', f"{data_inicio_fmt}T00:00")
        await page.fill('#finalDate', f"{data_fim_fmt}T23:59")
        await page.wait_for_timeout(1000)

        await page.get_by_role("button", name="Excel", exact=True).click()
        await page.wait_for_timeout(1000)

        with page.expect_download() as download_info:
            await page.get_by_role("button", name="Baixar Relatório", exact=True).click()

        download = await download_info.value

        nome_arquivo = f"Extrato_Pagstar_{data_inicio_fmt}_a_{data_fim_fmt}.csv"
        caminho = os.path.join("downloads", nome_arquivo)
        os.makedirs("downloads", exist_ok=True)
        await download.save_as(caminho)

        await browser.close()
        return caminho

# Streamlit interface
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
    st.info("Aguardando geração do extrato...")
    caminho = asyncio.run(baixar_extrato(str(data_inicio), str(data_fim)))
    st.success("✅ Extrato gerado com sucesso!")
    with open(caminho, "rb") as f:
        st.download_button("📥 Clique para baixar", f, file_name=os.path.basename(caminho))

