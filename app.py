import time
import datetime as dt
from typing import Tuple

import streamlit as st
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

PAGSTAR_URL = "https://finance.pagstar.com/"

# --------- Util ---------
def fmt_br(d: dt.date) -> str:
    """Formata data como DD/MM/AAAA."""
    return d.strftime("%d/%m/%Y")


# --------- Core ---------
def baixar_extrato(
    usuario: str,
    senha: str,
    data_inicio: dt.date,
    data_fim: dt.date,
    debug: bool = False,
) -> Tuple[bytes, str]:
    """
    Fluxo:
      1) Login
      2) Extrato -> Detalhado
      3) Selecionar período (data_inicio..data_fim)
      4) Exportar -> Baixar Relatório
    Retorna (bytes_arquivo, nome_sugerido) ou, em debug, screenshot/diagnóstico.
    """
    TIMEOUT_LOGIN = 45_000
    TIMEOUT_PAGE = 30_000
    TIMEOUT_DOWNLOAD = 60_000

    di = fmt_br(data_inicio)
    df = fmt_br(data_fim)

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage"],
        )
        context = browser.new_context(accept_downloads=True, viewport={"width": 1366, "height": 900})
        page = context.new_page()

        try:
            page.goto(PAGSTAR_URL, wait_until="domcontentloaded")

            # ===== 1) LOGIN =====
            # Usuario
            preenchido_user = False
            for sel in [
                lambda: page.get_by_label("Usuário"),
                lambda: page.get_by_placeholder("Usuário"),
                lambda: page.locator('input[name="username"]'),
                lambda: page.locator("input#username"),
                lambda: page.locator('input[autocomplete="username"]'),
                lambda: page.locator('input[type="text"]'),
            ]:
                try:
                    el = sel()
                    el.first.fill(usuario)
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
                lambda: page.locator("input#password"),
                lambda: page.locator('input[type="password"]'),
            ]:
                try:
                    el = sel()
                    el.first.fill(senha)
                    preenchido_senha = True
                    break
                except Exception:
                    pass
            if not preenchido_senha:
                raise RuntimeError("Não encontrei o campo de Senha. Ajuste os seletores.")

            # Entrar
            clicou_entrar = False
            for sel in [
                lambda: page.get_by_role("button", name="Entrar"),
                lambda: page.get_by_text("Entrar").locator("..").locator("button"),
                lambda: page.locator('button:has-text("Entrar")'),
                lambda: page.locator('[type="submit"]'),
                lambda: page.locator('[data-testid="login"], [aria-label="Entrar"]'),
            ]:
                try:
                    btn = sel()
                    btn.first.click()
                    clicou_entrar = True
                    break
                except Exception:
                    pass
            if not clicou_entrar:
                raise RuntimeError('Não encontrei o botão "Entrar". Ajuste os seletores.')

            # pós-login
            ok_pos_login = False
            try:
                page.wait_for_selector("text=Extrato", timeout=TIMEOUT_LOGIN)
                ok_pos_login = True
            except Exception:
                try:
                    page.wait_for_load_state("networkidle", timeout=10_000)
                except Exception:
                    pass
                if page.locator("text=Extrato").first.count() > 0:
                    ok_pos_login = True
            if not ok_pos_login:
                raise RuntimeError("Login não confirmou a tempo. Pode haver 2FA/recaptcha ou seletor diferente.")

            # ===== 2) EXTRATO -> DETALHADO =====
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

            # ===== 3) PERÍODO (data_inicio..data_fim) =====
            # Muitos sistemas têm 2 inputs ou um seletor de período + "Personalizado".
            # Tentamos: abrir período (se existir), preencher início e fim, clicar Aplicar/Filtrar.
            # a) Abrir "Período"/"Personalizado" se for necessário:
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

            # b) Preencher data inicial
            preencheu_ini = False
            for sel in [
                lambda: page.get_by_label("Data inicial"),
                lambda: page.get_by_label("Data início"),
                lambda: page.get_by_label("Início"),
                lambda: page.get_by_label("De"),
                lambda: page.get_by_placeholder("dd/mm/aaaa"),
                lambda: page.locator('input[name="dataInicio"]'),
                lambda: page.locator('input[id="dataInicio"]'),
                lambda: page.locator('input[name="startDate"], input[name="inicio"], input[name="data_inicial"]'),
            ]:
                try:
                    el = sel()
                    el.first.fill(di)
                    preencheu_ini = True
                    break
                except Exception:
                    pass

            # c) Preencher data final
            preencheu_fim = False
            for sel in [
                lambda: page.get_by_label("Data final"),
                lambda: page.get_by_label("Fim"),
                lambda: page.get_by_label("Até"),
                lambda: page.get_by_placeholder("dd/mm/aaaa").nth(1),  # segundo placeholder igual
                lambda: page.locator('input[name="dataFim"]'),
                lambda: page.locator('input[id="dataFim"]'),
                lambda: page.locator('input[name="endDate"], input[name="fim"], input[name="data_final"]'),
            ]:
                try:
                    el = sel()
                    # alguns seletores retornam locator direto; se for nth(1), já é um locator
                    if hasattr(el, "fill"):
                        el.fill(df)
                    else:
                        el.first.fill(df)
                    preencheu_fim = True
                    break
                except Exception:
                    pass

            # d) Botão aplicar/filtrar (se existir)
            for apply_btn in [
                lambda: page.get_by_role("button", name="Aplicar"),
                lambda: page.get_by_role("button", name="Filtrar"),
                lambda: page.get_by_role("button", name="Buscar"),
                lambda: page.get_by_role("button", name="Atualizar"),
                lambda: page.get_by_text("Aplicar"),
                lambda: page.get_by_text("Filtrar"),
                lambda: page.get_by_text("Buscar"),
                lambda: page.get_by_text("Atualizar"),
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

            # ===== 4) EXPORTAR & DOWNLOAD =====
            try:
                page.get_by_role("button", name="Exportar").click()
            except Exception:
                page.locator('button:has-text("Exportar"), text=Exportar').first.click()

            # Se houver menu de formato:
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
                # botão final para baixar
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

            # Lê bytes sem escrever em disco
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


# ------------- Streamlit UI -------------
st.set_page_config(page_title="Extrato Pagstar", page_icon="📄", layout="centered")
st.title("📄 Extrato Pagstar")

with st.form("login_form"):
    st.write("Informe suas credenciais **apenas para esta sessão**. Elas não serão salvas.")
    col1, col2 = st.columns(2)
    with col1:
        usuario = st.text_input("Usuário", "")
    with col2:
        senha = st.text_input("Senha", "", type="password")

    # Seleção de período — simples: um único dia (início=fim)
    dia = st.date_input("Dia do extrato", value=dt.date.today())
    debug = st.checkbox("Modo diagnóstico (gera screenshot se falhar)", value=True)
    submitted = st.form_submit_button("Baixar extrato")

if submitted:
    if not usuario or not senha:
        st.error("Preencha usuário e senha.")
    else:
        di = df = dia  # mesmo dia para início e fim
        try:
            with st.spinner(f"Gerando relatório de {fmt_br(di)}..."):
                data, fname = baixar_extrato(usuario, senha, di, df, debug=debug)
            if fname.endswith(".png"):
                st.error("Falha durante a execução. Veja o screenshot abaixo para ajustar seletores.")
                st.image(data)
            elif fname.endswith(".txt"):
                st.error("Falha durante a execução. Baixe o diagnóstico e me envie para ajustar os seletores.")
                st.download_button("Baixar diagnóstico (.txt)", data=data, file_name=fname)
            else:
                st.success("Pronto! Seu relatório está disponível para download.")
                st.download_button("⬇️ Baixar arquivo", data=data, file_name=fname, type="primary")
        except PlaywrightTimeout:
            st.error("Tempo de espera excedido. Verifique a conexão e ajuste os seletores.")
        except Exception as e:
            st.error(f"Ocorreu um erro: {e}")

st.caption(
    "Dica: se sua tela usar rótulos diferentes (ex.: 'Data inicial'/'Data final'), envie um screenshot do HTML para ajustarmos os seletores exatamente."
)
