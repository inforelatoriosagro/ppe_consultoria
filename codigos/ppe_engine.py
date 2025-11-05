"""
Motor de cálculo PPE - Versão modularizada
Extrai a lógica de cálculo do PPE_completo.py para ser reutilizada
"""

import pandas as pd
import re
from datetime import datetime
from zoneinfo import ZoneInfo
from pathlib import Path

# Importa os módulos de dados
import cotacoes_tradingview_cepea as cot
import premios_export_soja_milho as premios

# Constantes e mapeamentos (copiados do PPE_completo.py)
MONTH_CODE_TO_NUM = {
    "F": 1, "G": 2, "H": 3, "J": 4, "K": 5, "M": 6,
    "N": 7, "Q": 8, "U": 9, "V": 10, "X": 11, "Z": 12,
}

LISTED_MONTHS = {
    "ZC": [3, 5, 7, 9, 12],
    "ZS": [1, 3, 5, 7, 8, 9, 11],
}

MONTH_NUM_TO_CODE = {
    1: "F", 2: "G", 3: "H", 4: "J", 5: "K", 6: "M",
    7: "N", 8: "Q", 9: "U", 10: "V", 11: "X", 12: "Z",
}

_MES_PT_TO_NUM = {
    "Jan": 1, "Fev": 2, "Mar": 3, "Abr": 4, "Mai": 5, "Jun": 6,
    "Jul": 7, "Ago": 8, "Set": 9, "Out": 10, "Nov": 11, "Dez": 12,
}

_MES_PT3_TO_NUM = {
    "Jan":1, "Fev":2, "Mar":3, "Abr":4, "Mai":5, "Jun":6,
    "Jul":7, "Ago":8, "Set":9, "Out":10, "Nov":11, "Dez":12
}

# Funções auxiliares (copiadas do PPE_completo.py)
def add_months(year: int, month: int, n: int = 1):
    total = (year * 12 + (month - 1)) + n
    y = total // 12
    m = total % 12 + 1
    return y, m

def generate_month_grid(start_year: int, start_month: int, horizon: int = 10):
    out = []
    y, m = start_year, start_month
    for _ in range(horizon):
        out.append((y, m))
        y, m = add_months(y, m, 1)
    return out

def choose_start_month(symbol: str, from_year: int, from_month: int):
    listed = LISTED_MONTHS[symbol]
    candidates = [(from_year, m) for m in listed if m >= from_month]
    base = candidates[0] if candidates else (from_year + 1, listed[0])
    return base

def generate_explicit_tickers(symbol: str, start_year: int, start_month: int, n: int):
    listed = LISTED_MONTHS[symbol]
    y0, m0 = choose_start_month(symbol, start_year, start_month)
    
    if m0 in listed:
        idx = listed.index(m0)
    else:
        idx = 0
        for j, lm in enumerate(listed):
            if lm >= m0:
                idx = j
                break
    
    out = []
    y, pos = y0, idx
    for _ in range(n):
        m = listed[pos]
        code = MONTH_NUM_TO_CODE[m]
        out.append(f"{symbol}{code}{y}")
        pos += 1
        if pos >= len(listed):
            pos = 0
            y += 1
    return out

def parse_explicit_ticker(tk: str):
    s = tk.strip().strip("()").upper()
    m = re.fullmatch(r"(ZC|ZS)([FGHJKMNQUVXZ])(\d{4})", s)
    if not m:
        return None
    sym, code, year = m.group(1), m.group(2), int(m.group(3))
    month_num = MONTH_CODE_TO_NUM.get(code)
    if month_num is None:
        return None
    return sym, year, month_num

def build_price_map_from_explicit(explicit_prices: dict):
    price_map = {}
    units_map = {"ZC": "c$/bu", "ZS": "c$/bu"}
    
    for tk, px in explicit_prices.items():
        if px is None:
            continue
        parsed = parse_explicit_ticker(tk)
        if not parsed:
            continue
        sym, y, m = parsed
        price_map[(sym, y, m)] = float(px)
    
    return price_map, units_map

def build_monthly_series(symbol: str, month_grid: list, price_map: dict, units_map: dict):
    listed = set(LISTED_MONTHS[symbol])
    
    listed_nodes = sorted(
        [(y, m) for (sym, y, m) in price_map.keys() if sym == symbol],
        key=lambda x: (x[0], x[1])
    )
    
    def find_next_future_price(y0, m0):
        for (y, m) in listed_nodes:
            if (y > y0) or (y == y0 and m >= m0):
                return price_map.get((symbol, y, m))
        return None
    
    rows = []
    last_price = None
    
    for (y, m) in month_grid:
        if m in listed and (symbol, y, m) in price_map:
            price_to_use = price_map[(symbol, y, m)]
            last_price = price_to_use
        else:
            next_price = find_next_future_price(y, m)
            if next_price is not None:
                price_to_use = next_price
            else:
                price_to_use = last_price
        
        rows.append({
            "Ativo": symbol,
            "Ano": y,
            "Mês": m,
            "Vencimento": f"{m:02d}/{y}",
            "Preço": price_to_use,
            "Unidade": units_map.get(symbol, "c$/bu")
        })
    
    return pd.DataFrame(rows)

def _parse_mes_pt(label: str):
    mes_abbr, ano2 = label.split("/")
    m = _MES_PT_TO_NUM[mes_abbr.strip().title()]
    y = 2000 + int(ano2)
    return y, m

def _parse_venc_mm_yyyy(v: str):
    mm, yyyy = v.split("/")
    return int(yyyy), int(mm)

def _parse_ndf_venc(label: str):
    mes_txt, ano_txt = str(label).strip().split("/")
    mes3 = mes_txt.strip().title()[:3]
    y = int(ano_txt.strip())
    m = _MES_PT3_TO_NUM[mes3]
    return y, m

def calcular_ppe(df_soja, df_milho, df_ndf, fobbings=40.0, frete_dom=342.0):
    """
    Função principal que executa todo o cálculo do PPE
    
    Args:
        fobbings: Custo FOB Bings em R$/ton
        frete_dom: Frete doméstico em R$/ton
        frete_int_santos_asia: Frete internacional Santos-Ásia em $/ton
    
    Returns:
        tuple: (df_ppe_soja, df_ppe_milho)
    """
    
    # Determina data atual
    tz = ZoneInfo("America/Sao_Paulo")
    today = datetime.now(tz)
    start_year, start_month = today.year, today.month
    month_grid = generate_month_grid(start_year, start_month, horizon=10)
    
    # Gera tickers e busca preços
    NUM_CONTRACTS_PER_SYMBOL = 6
    zc_tickers = generate_explicit_tickers("ZC", start_year, start_month, NUM_CONTRACTS_PER_SYMBOL)
    zs_tickers = generate_explicit_tickers("ZS", start_year, start_month, NUM_CONTRACTS_PER_SYMBOL)
    
    explicit_prices = {}
    for tk in zc_tickers + zs_tickers:
        try:
            explicit_prices[tk] = float(cot.fetch_eua(tk))
        except Exception:
            explicit_prices[tk] = None
    
    # Constrói mapa de preços
    price_map, units_map = build_price_map_from_explicit(explicit_prices)
    
    # Monta séries mensais
    df_zc = build_monthly_series("ZC", month_grid, price_map, units_map)
    df_zs = build_monthly_series("ZS", month_grid, price_map, units_map)
    
    # Cria DataFrames base para PPE
    df_ppe_soja = df_zs[["Ativo", "Vencimento", "Preço"]].copy()
    df_ppe_milho = df_zc[["Ativo", "Vencimento", "Preço"]].copy()
    
    # --- Adiciona Prêmios ---
    df_premio_soja = df_soja.copy()
    df_premio_milho = df_milho.copy()
    df_ndf = df_ndf.copy()
    
    df_premio_soja[["Ano", "MesNum"]] = df_premio_soja["Mes"].apply(lambda s: pd.Series(_parse_mes_pt(s)))
    df_premio_milho[["Ano", "MesNum"]] = df_premio_milho["Mes"].apply(lambda s: pd.Series(_parse_mes_pt(s)))
    df_premio_soja["Chave"] = df_premio_soja["MesNum"].astype(int).map(lambda x: f"{x:02d}") + "/" + df_premio_soja["Ano"].astype(int).astype(str)
    df_premio_milho["Chave"] = df_premio_milho["MesNum"].astype(int).map(lambda x: f"{x:02d}") + "/" + df_premio_milho["Ano"].astype(int).astype(str)
    
    prem_soja_sorted = df_premio_soja.sort_values(["Ano", "MesNum"]).reset_index(drop=True)
    prem_milho_sorted = df_premio_milho.sort_values(["Ano", "MesNum"]).reset_index(drop=True)
    
    def _next_or_last_premio(y: int, m: int, prem_sorted: pd.DataFrame):
        fut = prem_sorted[(prem_sorted["Ano"] > y) | ((prem_sorted["Ano"] == y) & (prem_sorted["MesNum"] >= m))]
        if not fut.empty:
            row = fut.iloc[0]
            return row["Premio"], row["Chave"]
        past = prem_sorted[(prem_sorted["Ano"] < y) | ((prem_sorted["Ano"] == y) & (prem_sorted["MesNum"] <= m))]
        if not past.empty:
            row = past.iloc[-1]
            return row["Premio"], row["Chave"]
        return None, None
    
    # Aplica prêmios na soja
    df_ppe_soja[["Ano", "MesNum"]] = df_ppe_soja["Vencimento"].apply(lambda s: pd.Series(_parse_venc_mm_yyyy(s)))
    premios_soja_vals, premios_soja_src = [], []
    for y, m in zip(df_ppe_soja["Ano"], df_ppe_soja["MesNum"]):
        val, src = _next_or_last_premio(y, m, prem_soja_sorted)
        premios_soja_vals.append(val)
        premios_soja_src.append(src)
    df_ppe_soja["Premio"] = premios_soja_vals
    df_ppe_soja["PremioData"] = premios_soja_src
    
    # Aplica prêmios no milho
    df_ppe_milho[["Ano", "MesNum"]] = df_ppe_milho["Vencimento"].apply(lambda s: pd.Series(_parse_venc_mm_yyyy(s)))
    premios_milho_vals, premios_milho_src = [], []
    for y, m in zip(df_ppe_milho["Ano"], df_ppe_milho["MesNum"]):
        val, src = _next_or_last_premio(y, m, prem_milho_sorted)
        premios_milho_vals.append(val)
        premios_milho_src.append(src)
    df_ppe_milho["Premio"] = premios_milho_vals
    df_ppe_milho["PremioData"] = premios_milho_src
    
    # --- Adiciona NDF ---
    df_ndf = premios._read_tab_ndf().copy()
    df_ndf[["Ano","MesNum"]] = df_ndf["Vencimento"].apply(lambda s: pd.Series(_parse_ndf_venc(s)))
    df_ndf["Chave"] = df_ndf["MesNum"].astype(int).map(lambda x: f"{x:02d}") + "/" + df_ndf["Ano"].astype(int).astype(str)
    ndf_sorted = df_ndf.sort_values(["Ano","MesNum"]).reset_index(drop=True)
    
    def _next_or_last_ndf(y: int, m: int):
        fut = ndf_sorted[(ndf_sorted["Ano"] > y) | ((ndf_sorted["Ano"] == y) & (ndf_sorted["MesNum"] >= m))]
        if not fut.empty:
            row = fut.iloc[0]
            return float(row["NDF"]), row["Chave"]
        past = ndf_sorted[(ndf_sorted["Ano"] < y) | ((ndf_sorted["Ano"] == y) & (ndf_sorted["MesNum"] <= m))]
        if not past.empty:
            row = past.iloc[-1]
            return float(row["NDF"]), row["Chave"]
        return None, None
    
    # Aplica NDF na soja
    ndf_vals, ndf_src = [], []
    for y, m in zip(df_ppe_soja["Ano"], df_ppe_soja["MesNum"]):
        val, src = _next_or_last_ndf(y, m)
        ndf_vals.append(val)
        ndf_src.append(src)
    df_ppe_soja["NDF"] = ndf_vals
    df_ppe_soja["NDFFonte"] = ndf_src
    
    # Aplica NDF no milho
    ndf_vals, ndf_src = [], []
    for y, m in zip(df_ppe_milho["Ano"], df_ppe_milho["MesNum"]):
        val, src = _next_or_last_ndf(y, m)
        ndf_vals.append(val)
        ndf_src.append(src)
    df_ppe_milho["NDF"] = ndf_vals
    df_ppe_milho["NDFFonte"] = ndf_src
    
    # --- Cálculos finais do PPE ---
    # Soja
    df_ppe_soja["FOB (c$/bu)"] = df_ppe_soja["Preço"] + df_ppe_soja["Premio"]
    df_ppe_soja["FOB ($/ton)"] = df_ppe_soja["FOB (c$/bu)"] * 0.367437
    df_ppe_soja["FOB (R$/ton)"] = df_ppe_soja["FOB ($/ton)"] * df_ppe_soja["NDF"]
    df_ppe_soja["Sobre rodas"] = df_ppe_soja["FOB (R$/ton)"] - fobbings
    df_ppe_soja["EXW"] = df_ppe_soja["Sobre rodas"] - frete_dom
    df_ppe_soja["PPE Preço saca origem (R$/sc)"] = df_ppe_soja["EXW"] * 0.06
    df_ppe_soja["Basis Praça-CBOT (c$/bu)"] = ((df_ppe_soja["PPE Preço saca origem (R$/sc)"] / df_ppe_soja["NDF"]) / 2.204 - df_ppe_soja["Preço"]/100)*100
    
    # Milho
    df_ppe_milho["FOB (c$/bu)"] = df_ppe_milho["Preço"] + df_ppe_milho["Premio"]
    df_ppe_milho["FOB ($/ton)"] = df_ppe_milho["FOB (c$/bu)"] * 0.393687
    df_ppe_milho["FOB (R$/ton)"] = df_ppe_milho["FOB ($/ton)"] * df_ppe_milho["NDF"]
    df_ppe_milho["Sobre rodas"] = df_ppe_milho["FOB (R$/ton)"] - fobbings
    df_ppe_milho["EXW"] = df_ppe_milho["Sobre rodas"] - frete_dom
    df_ppe_milho["PPE Preço saca origem (R$/sc)"] = df_ppe_milho["EXW"] * 0.06
    df_ppe_milho["Basis Praça-CBOT (c$/bu)"] = ((df_ppe_milho["PPE Preço saca origem (R$/sc)"] / df_ppe_milho["NDF"]) / 2.204 - df_ppe_milho["Preço"]/100)*100
    
    # Seleciona colunas finais
    df_ppe_soja = df_ppe_soja[["Ativo", "Vencimento", "Preço", "Premio", "NDF", "FOB (c$/bu)", 
                                "FOB ($/ton)", "FOB (R$/ton)", "Sobre rodas", "EXW", 
                                "PPE Preço saca origem (R$/sc)", "Basis Praça-CBOT (c$/bu)"]]
    df_ppe_milho = df_ppe_milho[["Ativo", "Vencimento", "Preço", "Premio", "NDF", "FOB (c$/bu)", 
                                  "FOB ($/ton)", "FOB (R$/ton)", "Sobre rodas", "EXW", 
                                  "PPE Preço saca origem (R$/sc)", "Basis Praça-CBOT (c$/bu)"]]
    
    return df_ppe_soja.round(2), df_ppe_milho.round(2)