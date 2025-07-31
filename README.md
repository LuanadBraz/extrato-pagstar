# Extrato Pagstar — Contorno sem variáveis de ambiente (Render Docker)

Este pacote traz um app **Streamlit** que pede Usuário e Senha na interface,
executa o **Playwright** para logar no Pagstar e oferece o **download** do Excel sem
salvar credenciais ou arquivos no servidor.

## Arquivos
- `app.py` — app Streamlit + automação Playwright
- `requirements.txt`
- `Dockerfile` — baseado na imagem oficial do Playwright
- `README.md`

## Rodar localmente (opcional)
```bash
docker build -t extrato-pagstar .
docker run --rm -p 8501:8501 extrato-pagstar
# Abra http://localhost:8501
```

## Render (Web Service Docker)
- **Dockerfile Path**: `./Dockerfile`
- **Docker Command**: deixe **vazio** para usar o `CMD` do Dockerfile
- **Health Check Path**: `/` (raiz), não `/healthz`
- Não precisa de variáveis de ambiente neste contorno.

## Ajustes de seletores
Se sua tela tiver textos diferentes, ajuste em `baixar_extrato()`:
- `get_by_label("Usuário")` / `get_by_label("Senha")`
- `get_by_role("button", name="Entrar")`
- `text=Extrato`, `name="Detalhado"`, `name="Exportar"`, `name="Baixar Relatório"`

Sugestão: teste os seletores com o **Playwright Inspector**.

---
Quando possível, migre para variáveis de ambiente (Environment, Secret Files ou Blueprint),
para que o login não seja digitado manualmente a cada execução.