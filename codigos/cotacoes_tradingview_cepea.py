# tabela_cmdty.py
# pip install --upgrade --no-cache-dir git+https://github.com/rongardF/tvdatafeed.git
# pip install python-dotenv
import pandas as pd, requests, io, time
from tvDatafeed import TvDatafeed, Interval
from datetime import date
from dotenv import load_dotenv
import os


# ---------- B3 Futures ----------
# cria a sessão autenticada

import streamlit as st

# Tenta carregar do Streamlit Secrets (Cloud) ou .env (local)
try:
    TV_USERNAME = st.secrets["tradingview"]["TV_USERNAME"]
    TV_PASSWORD = st.secrets["tradingview"]["TV_PASSWORD"]
except Exception:
    # Fallback para desenvolvimento local
    load_dotenv(dotenv_path=os.path.join("configs", ".env"))
    TV_USERNAME = os.getenv("TV_USERNAME")
    TV_PASSWORD = os.getenv("TV_PASSWORD")

# Validação simples das credenciais
if not TV_USERNAME or not TV_PASSWORD:
    raise RuntimeError("Credenciais do TradingView não encontradas. Preencha configs/.env com TV_USERNAME e TV_PASSWORD.")

tv = TvDatafeed(username=TV_USERNAME, password=TV_PASSWORD)
max_attempts = 3
delay = 2

def fetch_b3(symbol):
    for _ in range(max_attempts):
        try:
            df = tv.get_hist(symbol=symbol, exchange='BMFBOVESPA', interval=Interval.in_15_minute, n_bars=4)
            if df is not None and not df.empty and len(df) >= 2:
                return df.iloc[-2, 4].round(1)
        except Exception:
            time.sleep(delay)
    raise RuntimeError(f"Falha ao obter dados do símbolo {symbol}")

def fetch_eua(symbol):
    for _ in range(max_attempts):
        try:
            df = tv.get_hist(symbol=symbol, exchange='CBOT', interval=Interval.in_15_minute, n_bars=4)
            if df is not None and not df.empty and len(df) >= 2:
                return df.iloc[-2, 4].round(1)
        except Exception:
            time.sleep(delay)
    raise RuntimeError(f"Falha ao obter dados do símbolo {symbol}")


# Escolher os tickers que desejar baixar, basta apenas adicionar ou remover da lista
ccm = fetch_b3('CCMN2025')
sjc = fetch_b3('SJC1!')
zc1 = fetch_eua('ZC1!')
zc2 = fetch_eua('ZC2!')
zc3 = fetch_eua('ZCH2026')
zc4 = fetch_eua('ZCK2026')
zc5 = fetch_eua('ZCN2026')
zc6 = fetch_eua('ZCU2026')
zs1 = fetch_eua('ZS1!')
zs2 = fetch_eua('ZS2!')
zs3 = fetch_eua('ZSF2026')
zs4 = fetch_eua('ZSH2026') 
zs5 = fetch_eua('ZSK2026')
zs6 = fetch_eua('ZSN2026')

# ---------- Monta DataFrame ----------
dados = [
    ["(SJC)",  sjc,         "US$/sc"],
    ["(CCM)",  ccm,      "R$/sc"],
    ["(ZC1)", zc1,         "c$/bu"],
    ["(ZC2)", zc2,         "c$/bu"],
    ["(ZC3)",  zc3,         "c$/bu"],
    ["(ZC4)", zc4,         "c$/bu"],
    ["(ZC5)", zc5,         "c$/bu"],
    ["(ZC6)", zc6,        "c$/bu"],
    ["(ZS1)", zs1,         "c$/bu"],
    ["(ZS2)", zs2,         "c$/bu"],
    ["(ZS3)", zs3,         "c$/bu"],
    ["(ZS4)", zs4,         "c$/bu"],
    ["(ZS5)", zs5,         "c$/bu"],
    ["(ZS6)", zs6,         "c$/bu"],
]

df_cmdty = pd.DataFrame(dados, columns=[ "Produto", "Preço", "Unidade"])

df = df_cmdty.round(2)
#Se quiser printas do dados = []
#print(df.to_string(index=False))


# =================================================
#DESCRIÇÃO DO SCRIPT

# 1. FAZ O lOGIN COM USERNAME E SENHA NO TRADINGVIEW USANDO OS DADOS NO ARQUIVO CONFIG/.ENV
# 2. Entra no trading view e baixa cotações de ativos financeiros

# O QUE O USUÁRIO PODE MUDAR:
# - Colocar suas credenciais do trading view no arquivo configs/.env
# - Escolher os ativos pra pegar as informações: Mudar os símbolos dos ativos na função fetch_b3 e fetch_eua
# - Mudar o número de tentativas e o delay entre elas (max_attempts e delay)
# - Mudar o intervalo de tempo (Interval.in_15_minute) e o número de barras (n_bars=4) dentro da def fetch_b3 e fetch_eua
# - Mudar o formato do DataFrame final (colunas, arredondamento, etc)
# =========================================================================