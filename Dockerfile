# Imagem Playwright com Python + Chromium pré-instalado
FROM mcr.microsoft.com/playwright/python:v1.45.0-jammy

WORKDIR /app

# Dependências Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Código da aplicação
COPY . .

ENV PYTHONUNBUFFERED=1

# Streamlit deve escutar na porta fornecida pelo Render ($PORT)
CMD ["bash", "-lc", "streamlit run app.py --server.port $PORT --server.address 0.0.0.0"]
