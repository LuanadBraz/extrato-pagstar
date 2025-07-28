#!/bin/bash

echo "Instalando dependências..."
pip install -r requirements.txt

echo "Instalando navegador Chromium do Playwright..."
playwright install chromium
