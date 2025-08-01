
import time
import datetime as dt
from typing import Optional, Tuple
import streamlit as st
from playwright.sync_api import sync_playwright

PAGSTAR_URL = "https://finance.pagstar.com/"
context_store = {}

def fmt_br(d: dt.date) -> str:
    return d.strftime("%d/%m/%Y")

def only_digits(s: str) -> str:
    return "".join(ch for ch in s if ch.isdigit())

def iniciar_automacao(usuario, senha, data_inicio, data_fim, sanitize_id):
    di = fmt_br(data_inicio)
    df = fmt_br(data_fim)
    user_to_fill = only_digits(usuario) if sanitize_id else usuario
    user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    p = sync_playwright().start()
    browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
    context = browser.new_context(accept_downloads=True, user_agent=user_agent, locale="pt-BR")
    page = context.new_page()
    page.goto(PAGSTAR_URL, wait_until="domcontentloaded")

    page.locator('input[type="text"]').first.fill(user_to_fill)
    page.locator('input[type="password"]').first.fill(senha)
    page.locator('button:has-text("Entrar")').first.click()

    try:
        page.wait_for_selector("text=Extrato", timeout=10000)
    except:
        if page.locator("text=Alerta de segurança").is_visible():
            context_store["playwright"] = p
            context_store["browser"] = browser
            context_store["context"] = context
            context_store["page"] = page
            return "codigo"
        else:
            raise RuntimeError("Falha no login")

    return continuar_automacao(page, context, browser, di, df)

def continuar_automacao(page, context, browser, di, df):
    page.get_by_text("Extrato").click()
    page.get_by_text("Detalhado").click()
    page.get_by_label("Data inicial").fill(di)
    page.get_by_label("Data final").fill(df)
    page.get_by_role("button", name="Buscar").click()
    page.get_by_text("Exportar").click()
    page.get_by_text("Excel").click()
    with page.expect_download(timeout=60000) as dl_info:
        page.get_by_text("Baixar Relatório").click()
    download = dl_info.value
    data = download.create_read_stream().read()
    nome = download.suggested_filename or f"Extrato_{di}_{df}.xlsx"
    context.close()
    browser.close()
    return data, nome

def preencher_codigo(codigo: str):
    page = context_store["page"]
    context = context_store["context"]
    browser = context_store["browser"]
    for i, digito in enumerate(codigo.strip()):
        page.locator('input[type="tel"]').nth(i).fill(digito)
    page.keyboard.press("Enter")
    page.wait_for_selector("text=Extrato", timeout=15000)
    return continuar_automacao(page, context, browser, context_store["di"], context_store["df"])

st.set_page_config(page_title="Pagstar", layout="centered")
st.title("📄 Extrato Pagstar")

with st.form("login"):
    usuario = st.text_input("Usuário (CPF/CNPJ)", "")
    senha = st.text_input("Senha", type="password")
    col1, col2 = st.columns(2)
    data_inicio = col1.date_input("Data inicial", value=dt.date.today())
    data_fim = col2.date_input("Data final", value=dt.date.today())
    sanitize = st.checkbox("Remover pontos/traços do CPF/CNPJ ao logar", value=True)
    submitted = st.form_submit_button("Baixar extrato")

if submitted:
    try:
        context_store["di"] = fmt_br(data_inicio)
        context_store["df"] = fmt_br(data_fim)
        resultado = iniciar_automacao(usuario, senha, data_inicio, data_fim, sanitize)
        if resultado == "codigo":
            st.session_state["aguardando_codigo"] = True
            st.warning("🔐 Código de segurança necessário. Digite abaixo o código recebido por e-mail.")
        else:
            data, nome = resultado
            st.success("✅ Extrato gerado com sucesso!")
            st.download_button("⬇️ Baixar extrato", data, file_name=nome)
    except Exception as e:
        st.error(f"Erro ao gerar extrato: {e}")

if st.session_state.get("aguardando_codigo"):
    with st.form("codigo"):
        codigo = st.text_input("Código de segurança")
        confirmar = st.form_submit_button("Confirmar código")
    if confirmar:
        try:
            data, nome = preencher_codigo(codigo)
            st.success("✅ Extrato gerado com sucesso!")
            st.download_button("⬇️ Baixar extrato", data, file_name=nome)
            st.session_state["aguardando_codigo"] = False
        except Exception as e:
            st.error(f"Erro ao validar código: {e}")
