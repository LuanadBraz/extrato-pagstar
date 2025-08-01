import time
import datetime as dt
from typing import Tuple, Optional

import streamlit as st
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

PAGSTAR_URL = "https://finance.pagstar.com/"

# ---------------- Utils ----------------
def fmt_br(d: dt.date) -> str:
    return d.strftime("%d/%m/%Y")

def only_digits(s: str) -> str:
    return "".join(ch for ch in s if ch.isdigit())

def clear_and_type(el, text: str):
    # limpa campo de forma robusta e digita com pequena latência (ajuda em máscaras)
    el.click()
    try:
        el.press("Control+A")
    except Exception:
        pass
    el.press("Backspace")
    el.type(text, delay=30)

# --------------- Core ------------------
def baixar_extrato(
    usuario: str,
    senha: str,
    data_inicio: dt.date,
    data_fim: dt.date,
    sanitize_id: bool = False,
    debug: bool = False,
) -> Tuple[bytes, str]:
    """
    Fluxo:
      1) Login (com pequenas técnicas anti-detecção)
      2) Extrato -> Detalhado
      3) Seleciona período (data_inicio..data_fim)
      4) Exportar -> (Excel opcional) -> Baixar Relatório
    Retorna (bytes, nome_sugerido) ou, em debug, screenshot/diagnóstico.
    """
    TIMEOUT_LOGIN = 45_000
    TIMEOUT_PAGE = 35_000
    TIMEOUT_DOWNLOAD = 60_000

    di = fmt_br(data_inicio)
    df = fmt_br(data_fim)

    # Ajuste de credencial (alguns sites exigem só dígitos para CPF/CNPJ)
    user_to_fill = only_digits(usuario) if sanitize_id else usuario

    user_agent = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-blink-features=AutomationControlled",
            ],
        )

        context = browser.new_context(
            accept_downloads=True,
            viewport={"width": 1366, "height": 900},
            locale="pt-BR",
            timezone_id="America/Sao_Paulo",
            user_agent=user_agent,
        )

        # Pequena “des-automação” client-side
        context.add_init_script(
            """
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            Object.defineProperty(navigator, 'languages', { get: () => ['pt-BR', 'pt'] });
            Object.defineProperty(navigator, 'platform', { get: () => 'Win32' });
            """
        )

        page = context.new_page()

        try:
            page.goto(PAGSTAR_URL, wait_until="domcontentloaded")

            # ====== LOGIN ======
            # Usuário
            preenchido_user = False
            for sel in [
                lambda: page.get_by_label("Usuário"),
                lambda: page.get_by_placeholder("Usuário"),
                lambda: page.locator('input[name="username"]'),
                lambda: page.locator("#username"),
                lambda: page.locator('input[autocomplete="username"]'),
                lambda: page.locator('input[type="text"]'),
            ]:
                try:
                    el = sel().first
                    clear_and_type(el, user_to_fill)
                    preenchido_user = True
                    break
                except Exception:
                    pass
            if not preenchido_user:
                raise RuntimeError("Não encontrei o campo de Usuário. Ajuste os seletores.")

            # Senha
            preenchido_senha = False
            for sel in [
                lambda: page.get_by_label("Senha"),
                lambda: page.get_by_placeholder("Senha"),
                lambda: page.locator('input[name="password"]'),
                lambda: page.locator("#password"),
                lambda: page.locator('input[type="password"]'),
            ]:
                try:
                    el = sel().first
                    clear_and_type(el, senha)
                    preenchido_senha = True
                    break
                except Exception:
                    pass
            if not preenchido_senha:
                raise RuntimeError("Não encontrei o campo de Senha. Ajuste os seletores.")

            # Clicar Entrar
            clicou_entrar = False
            for sel in [
                lambda: page.get_by_role("button", name="Entrar"),
                lambda: page.locator('button:has-text("Entrar")'),
                lambda: page.locator('[type="submit"]'),
                lambda: page.locator('[aria-label="Entrar"], [data-testid="login"]'),
            ]:
                try:
                    btn = sel().first
                    btn.click()
                    clicou_entrar = True
                    break
                except Exception:
                    pass
            if not clicou_entrar:
                raise RuntimeError('Não encontrei o botão "Entrar". Ajuste os seletores.')

            # Aguarda pós-login OU identifica modal de erro
            # 1) Espera algo do pós-login
            pos_login_ok = False
            try:
                page.wait_for_selector("text=Extrato", timeout=TIMEOUT_LOGIN)
                pos_login_ok = True
            except Exception:
                # 2) Se aparecer modal com mensagem de erro, tenta capturar
                modal_error = page.locator("text=Conta bloqueada,").first
                if modal_error and modal_error.is_visible():
                    # tenta fechar (x) ou botão "OK"
                    try:
                        page.locator("button:has-text('OK'), button:has-text('Fechar'), .modal [aria-label='Close'], .modal .btn-close").first.click()
                    except Exception:
                        pass
                    raise RuntimeError("O site retornou 'Conta bloqueada' para este ambiente. Tente sem formatação no usuário, ou execute localmente/residencial.")

                # 3) Último check: se o menu “Extrato” existir, seguimos
                if page.locator("text=Extrato").first.count() > 0:
                    pos_login_ok = True

            if not pos_login_ok:
                raise RuntimeError("Login não confirmou a tempo. Pode haver bloqueio do ambiente ou seletores diferentes.")

            # ====== EXTRATO -> DETALHADO ======
            try:
                page.get_by_role("link", name="Extrato").click()
            except Exception:
                page.locator("text=Extrato").first.click()
            page.wait_for_load_state("networkidle", timeout=TIMEOUT_PAGE)

            try:
                page.get_by_role("button", name="Detalhado").click()
            except Exception:
                page.locator('button:has-text("Detalhado"), text=Detalhado').first.click()
            page.wait_for_load_state("networkidle", timeout=TIMEOUT_PAGE)

            # ====== PERÍODO (ENTRE DATAS) ======
            # Tenta abrir seletor de período/personalizado
            for open_period in [
                lambda: page.get_by_role("button", name="Período"),
                lambda: page.get_by_text("Período"),
                lambda: page.get_by_role("button", name="Personalizado"),
                lambda: page.get_by_text("Personalizado"),
            ]:
                try:
                    el = open_period()
                    if el and el.first.is_visible():
                        el.first.click()
                        break
                except Exception:
                    pass

            # Data inicial
            preencheu_ini = False
            for sel in [
                lambda: page.get_by_label("Data inicial"),
                lambda: page.get_by_label("Data início"),
                lambda: page.get_by_label("Início"),
                lambda: page.get_by_label("De"),
                lambda: page.locator('input[name="dataInicio"]'),
                lambda: page.locator("#dataInicio"),
                lambda: page.locator('input[name="startDate"], input[name="inicio"], input[name="data_inicial"]'),
                lambda: page.locator('input[placeholder="dd/mm/aaaa"]').first,
            ]:
                try:
                    el = sel()
                    el = el if hasattr(el, "fill") else el.first
                    clear_and_type(el, di)
                    preencheu_ini = True
                    break
                except Exception:
                    pass

            # Data final
            preencheu_fim = False
            for sel in [
                lambda: page.get_by_label("Data final"),
                lambda: page.get_by_label("Fim"),
                lambda: page.get_by_label("Até"),
                lambda: page.locator('input[name="dataFim"]'),
                lambda: page.locator("#dataFim"),
                lambda: page.locator('input[name="endDate"], input[name="fim"], input[name="data_final"]'),
                lambda: page.locator('input[placeholder="dd/mm/aaaa"]').nth(1),
            ]:
                try:
                    el = sel()
                    el = el if hasattr(el, "fill") else el
                    # quando vier nth(1) já é um locator
                    clear_and_type(el, df)
                    preencheu_fim = True
                    break
                except Exception:
                    pass

            # Aplicar/Filtrar se existir
            for apply_btn in [
                lambda: page.get_by_role("button", name="Aplicar"),
                lambda: page.get_by_role("button", name="Filtrar"),
                lambda: page.get_by_role("button", name="Buscar"),
                lambda: page.get_by_role("button", name="Atualizar"),
                lambda: page.locator('button:has-text("Aplicar"), button:has-text("Filtrar"), button:has-text("Buscar"), button:has-text("Atualizar")'),
            ]:
                try:
                    btn = apply_btn()
                    if btn and btn.first.is_visible():
                        btn.first.click()
                        break
                except Exception:
                    pass

            page.wait_for_load_state("networkidle", timeout=TIMEOUT_PAGE)

            # ====== EXPORTAR & DOWNLOAD ======
            try:
                page.get_by_role("button", name="Exportar").click()
            except Exception:
                page.locator('button:has-text("Exportar"), text=Exportar').first.click()

            # Escolher Excel se houver menu
            for click_excel in [
                lambda: page.get_by_role("menuitem", name="Excel"),
                lambda: page.get_by_text("Excel"),
                lambda: page.locator('button:has-text("Excel"), a:has-text("Excel")'),
            ]:
                try:
                    el = click_excel()
                    if el and el.first.is_visible():
                        el.first.click()
                        break
                except Exception:
                    pass

            with page.expect_download(timeout=TIMEOUT_DOWNLOAD) as dl_info:
                for sel in [
                    lambda: page.get_by_role("button", name="Baixar Relatório"),
                    lambda: page.get_by_role("link", name="Baixar Relatório"),
                    lambda: page.get_by_text("Baixar Relatório"),
                    lambda: page.locator('button:has-text("Baixar Relatório"), a:has-text("Baixar Relatório")'),
                    lambda: page.locator('[download]'),
                ]:
                    try:
                        btn = sel()
                        btn.first.click()
                        break
                    except Exception:
                        pass
            download = dl_info.value

            stream = download.create_read_stream()
            data = stream.read() if stream else b""
            suggested = (
                download.suggested_filename
                or f"Extrato_Pagstar_{data_inicio.strftime('%Y%m%d')}_{data_fim.strftime('%Y%m%d')}.xlsx"
            )

            if not data:
                raise RuntimeError("Download retornou vazio. Talvez o arquivo não tenha sido gerado.")
            return data, suggested

        except Exception as e:
            if debug:
                try:
                    snap = page.screenshot(full_page=True)
                except Exception:
                    snap = None
                name = f"DIAGNOSTICO_{int(time.time())}"
                if snap:
                    return snap, f"{name}.png"
                else:
                    info = f"URL: {getattr(page, 'url', None)}\nERRO: {e}\n"
                    return info.encode("utf-8"), f"{name}.txt"
            raise
        finally:
            context.close()
            browser.close()


# ---------------- Streamlit UI ----------------
st.set_page_config(page_title="Extrato Pagstar", page_icon="📄", layout="centered")
st.title("📄 Extrato Pagstar")

with st.form("login_form"):
    st.write("Informe suas credenciais **apenas para esta sessão**. Elas não serão salvas.")
    col1, col2 = st.columns(2)
    with col1:
        usuario = st.text_input("Usuário (CPF/CNPJ)", "")
    with col2:
        senha = st.text_input("Senha", "", type="password")

    col3, col4 = st.columns(2)
    with col3:
        data_inicio = st.date_input("Data inicial", value=dt.date.today())
    with col4:
        data_fim = st.date_input("Data final", value=dt.date.today())

    sanitize = st.checkbox("Remover pontos/traços do CPF/CNPJ ao logar (recomendado)", value=True)
    debug = st.checkbox("Modo diagnóstico (gera screenshot se falhar)", value=True)

    submitted = st.form_submit_button("Baixar extrato")

if submitted:
    if not usuario or not senha:
        st.error("Preencha usuário e senha.")
    elif data_fim < data_inicio:
        st.error("A data final não pode ser menor que a data inicial.")
    else:
        try:
            with st.spinner(f"Gerando relatório de {fmt_br(data_inicio)} a {fmt_br(data_fim)}..."):
                data, fname = baixar_extrato(
                    usuario, senha, data_inicio, data_fim, sanitize_id=sanitize, debug=debug
                )
            if fname.endswith(".png"):
                st.error("Falha durante a execução. Veja o screenshot abaixo para ajustar seletores/ambiente.")
                st.image(data)
            elif fname.endswith(".txt"):
                st.error("Falha durante a execução. Baixe o diagnóstico e me envie para ajuste fino.")
                st.download_button("Baixar diagnóstico (.txt)", data=data, file_name=fname)
            else:
                st.success("Pronto! Seu relatório está disponível para download.")
                st.download_button("⬇️ Baixar arquivo", data=data, file_name=fname, type="primary")
        except PlaywrightTimeout:
            st.error("Tempo de espera excedido. Verifique a conexão e ajuste os seletores.")
        except Exception as e:
            st.error(f"Ocorreu um erro: {e}")

st.caption(
    "Se continuar aparecendo 'Conta bloqueada' apenas no Render, é provavelmente bloqueio do IP de datacenter. "
    "Teste localmente; se local funcionar, considere usar proxy residencial ou rodar a automação em uma máquina sua."
)
