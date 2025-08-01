import time
import datetime as dt
from typing import Optional, Tuple

import streamlit as st
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

PAGSTAR_URL = "https://finance.pagstar.com/"
context_store = {}

def fmt_br(d: dt.date) -> str:
    return d.strftime("%d/%m/%Y")

def only_digits(s: str) -> str:
    return "".join(ch for ch in s if ch.isdigit())

def clear_and_type(el, text: str):
    el.click()
    el.fill("")
    el.type(text, delay=30)

def iniciar_automacao(usuario, senha, data_inicio, data_fim, sanitize_id):
    di = fmt_br(data_inicio)
    df = fmt_br(data_fim)
    user_to_fill = only_digits(usuario) if sanitize_id else usuario
    user_agent = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )
    p = sync_playwright().start()
    browser = p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-dev-shm-usage"])
    context = browser.new_context(
        accept_downloads=True,
        viewport={"width": 1366, "height": 900},
        locale="pt-BR",
        timezone_id="America/Sao_Paulo",
        user_agent=user_agent,
    )
    context.add_init_script(
        "Object.defineProperty(navigator, 'webdriver', { get: () => undefined });"
    )
    page = context.new_page()
    page.goto(PAGSTAR_URL, wait_until="domcontentloaded")

    page.locator('input[type="text"]').first.fill(user_to_fill)
    page.locator('input[type="password"]').first.fill(senha)
    page.locator('button:has-text("Entrar")').first.click()

    try:
        page.wait_for_selector("text=Extrato", timeout=15000)
    except:
        if page.locator("text=Alerta de segurança").is_visible():
            context_store["playwright"] = p
            context_store["browser"] = browser
            context_store["context"] = context
            context_store["page"] = page
            return "codigo"
        else:
            raise RuntimeError("Falha no login. Verifique as credenciais.")

    return continuar_automacao(page, context, browser, di, df)

def continuar_automacao(page, context, browser, di, df):
    page.get_by_text("Extrato").click()
    page.get_by_text("Detalhado").click()

    try:
        page.get_by_label("Data inicial").fill(di)
        page.get_by_label("Data final").fill(df)
    except:
        page.locator('input[name="dataInicio"]').fill(di)
        page.locator('input[name="dataFim"]').fill(df)

    for botao in ["Aplicar", "Filtrar", "Buscar"]:
        try:
            page.get_by_role("button", name=botao).click()
            break
        except:
            continue

    page.get_by_text("Exportar").click()
    try:
        page.get_by_text("Excel").click()
    except:
        pass

    with page.expect_download(timeout=60000) as dl_info:
        page.get_by_text("Baixar Relatório").click()
    download = dl_info.value
    data = download.create_read_stream().read()
    fname = download.suggested_filename or f"Extrato_Pagstar_{di.replace('/','')}_{df.replace('/','')}.xlsx"
    context.close()
    browser.close()
    context_store.clear()
    return data, fname

def preencher_codigo(codigo: str) -> Tuple[bytes, str]:
    page = context_store.get("page")
    context = context_store.get("context")
    browser = context_store.get("browser")
    p = context_store.get("playwright")
    for i, char in enumerate(codigo.strip()):
        page.locator(f'input[type="tel"]').nth(i).fill(char)
    page.keyboard.press("Enter")
    page.wait_for_selector("text=Extrato", timeout=15000)
    return continuar_automacao(page, context, browser, context_store["di"], context_store["df"])

# -------- Streamlit UI --------
st.set_page_config(page_title="Extrato Pagstar", layout="centered")
st.title("📄 Extrato Pagstar")

with st.form("login"):
    usuario = st.text_input("Usuário (CPF/CNPJ)", "")
    senha = st.text_input("Senha", type="password")
    col1, col2 = st.columns(2)
    with col1:
        data_inicio = st.date_input("Data inicial", value=dt.date.today())
    with col2:
        data_fim = st.date_input("Data final", value=dt.date.today())
    sanitize = st.checkbox("Remover pontos/traços do CPF/CNPJ", value=True)
    submitted = st.form_submit_button("Entrar e gerar extrato")

if submitted:
    try:
        context_store["di"] = fmt_br(data_inicio)
        context_store["df"] = fmt_br(data_fim)
        resultado = iniciar_automacao(usuario, senha, data_inicio, data_fim, sanitize)
        if resultado == "codigo":
            st.session_state["aguardando_codigo"] = True
            st.warning("Código de segurança requerido. Digite abaixo o código que recebeu por e-mail.")
        else:
            data, fname = resultado
            st.success("Extrato gerado com sucesso!")
            st.download_button("⬇️ Baixar extrato", data, file_name=fname)
    except Exception as e:
        st.error(f"Erro: {e}")

if st.session_state.get("aguardando_codigo"):
    with st.form("codigo_seg"):
        codigo = st.text_input("Código de segurança (6 dígitos)")
        confirmar = st.form_submit_button("Confirmar código")
    if confirmar:
        try:
            data, fname = preencher_codigo(codigo)
            st.success("Extrato gerado com sucesso após verificação!")
            st.download_button("⬇️ Baixar extrato", data, file_name=fname)
            st.session_state["aguardando_codigo"] = False
        except Exception as e:
            st.error(f"Erro ao validar código: {e}")