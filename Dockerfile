
# Imagem oficial do Playwright com Python e navegadores já instalados
FROM mcr.microsoft.com/playwright/python:v1.45.0-jammy

WORKDIR /app

ENV PIP_NO_CACHE_DIR=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Copia o arquivo requirements.txt e instala as dependências
COPY requirements.txt /app/requirements.txt
RUN python -m pip install --upgrade pip wheel setuptools \
    && pip install -r /app/requirements.txt

# Copia o restante do código
COPY . /app

# Porta do Streamlit
EXPOSE 8000

# Comando para iniciar o app
CMD ["streamlit", "run", "app.py", "--server.port", "8000", "--server.address", "0.0.0.0"]
