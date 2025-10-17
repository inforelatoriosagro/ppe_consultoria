#.\venv\Scripts\Activate

#INSTRUIÇÕES:
# 1. Pra rodas esse código, são usados os arquivos cotacoes_tradingview_cepea.py e premios_export_soja_milho.py
# 1. Nesse arquivos são pegos os valores das cotações da bolsa de valores, premios de exportação e NDF do dólar
#User input pro cálculo de PPE#
fobbings=40.0         #R$/ton
frete_dom = 342.0     # R$/ton   
frete_int_santos_asia = 38.04   # $/ton
frete_int_eua_asia = 53.89
frete_int_bahiablanca_asia = 44.50

# --- Importa bibliotecas padrão e timezone ---
from datetime import datetime
from zoneinfo import ZoneInfo
import pandas as pd
import re
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
OUTPUTS_DIR = BASE_DIR / "outputs"
OUTPUTS_DIR.mkdir(exist_ok=True)

# --- Importa os módulos existentes (cotações e prêmios) ---
import cotacoes_tradingview_cepea as cot
# import premios_export_soja_milho as premios  # (importado agora; integração virá nas próximas etapas)

# --- Define mapeamentos fixos de código de mês (letra) -> número e meses listados por ativo ---
# Para CBOT: ZC (milho) lista Mar(H), Mai(K), Jul(N), Set(U), Dez(Z).
#            ZS (soja)  lista Jan(F), Mar(H), Mai(K), Jul(N), Ago(Q), Set(U), Nov(X).
MONTH_CODE_TO_NUM = {
    "F": 1,  # Jan
    "G": 2,  # Feb  (não listado em ZC/ZS)
    "H": 3,  # Mar
    "J": 4,  # Apr  (não listado em ZC/ZS)
    "K": 5,  # May
    "M": 6,  # Jun  (não listado em ZC/ZS)
    "N": 7,  # Jul
    "Q": 8,  # Aug
    "U": 9,  # Sep
    "V": 10, # Oct (não listado em ZC/ZS)
    "X": 11, # Nov
    "Z": 12, # Dec
}

# --- Conjuntos de meses listados por símbolo ---
LISTED_MONTHS = {
    "ZC": [3, 5, 7, 9, 12],               # H, K, N, U, Z
    "ZS": [1, 3, 5, 7, 8, 9, 11],         # F, H, K, N, Q, U, X
}

# --- Inverso: número do mês -> letra do código CBOT ---
# Comentário: este mapa permite gerar 'ZCH2026', 'ZCZ2025' etc. a partir de (ano, mês).
MONTH_NUM_TO_CODE = {
    1: "F",  # Jan
    2: "G",  # Feb
    3: "H",  # Mar
    4: "J",  # Apr
    5: "K",  # May
    6: "M",  # Jun
    7: "N",  # Jul
    8: "Q",  # Aug
    9: "U",  # Sep
    10: "V", # Oct
    11: "X", # Nov
    12: "Z", # Dec
}

# --- Função auxiliar: próximo mês/ano dado um par (ano, mês) ---
def add_months(year: int, month: int, n: int = 1):
    """Retorna (year, month) avançando n meses."""
    total = (year * 12 + (month - 1)) + n
    y = total // 12
    m = total % 12 + 1
    return y, m


# --- Função auxiliar: gera lista contínua de (ano, mês) por 'horizon' meses a partir de (ano0, mes0) ---
def generate_month_grid(start_year: int, start_month: int, horizon: int = 10):
    """Gera [(ano, mês)] contínuo a partir do mês/ano inicial por 'horizon' meses."""
    out = []
    y, m = start_year, start_month
    for _ in range(horizon):
        out.append((y, m))
        y, m = add_months(y, m, 1)
    return out


# --- Função auxiliar: obtém (ano, mês) dos dois front-months listados a partir de hoje para um símbolo ---
def next_two_listed_months(symbol: str, from_year: int, from_month: int):
    """Retorna [(ano, mês)] dos dois próximos meses listados (>= mês atual) para o símbolo (ZC ou ZS)."""
    listed = LISTED_MONTHS[symbol]
    # 1) Encontrar o primeiro mês listado >= mês atual; se não houver neste ano, vai para o próximo ano
    # 2) O segundo é o próximo listado após o primeiro (girando de ano se necessário)
    # primeiro
    candidates = [(from_year, m) for m in listed if m >= from_month]
    if not candidates:
        first = (from_year + 1, listed[0])
    else:
        first = candidates[0]
    # segundo
    y2, m2 = first
    # índice do mês listado do 'first'
    idx = listed.index(m2)
    if idx + 1 < len(listed):
        second = (y2, listed[idx + 1])
    else:
        second = (y2 + 1, listed[0])
    return [first, second]


# --- Função auxiliar: tenta extrair (símbolo, ano, mês) de strings como 'ZCH2026', 'ZSF2026' ---
def parse_explicit_contract(produto: str):
    """
    Recebe strings como '(ZCH2026)' e retorna ('ZC', 2026, 3) se reconhecer.
    Caso não reconheça o padrão com letra+ano, retorna None.
    """
    s = produto.strip().strip("()").upper()
    # Padrão: ZC? + [F|G|H|J|K|M|N|Q|U|V|X|Z] + YYYY
    m = re.fullmatch(r"(ZC|ZS)([FGHJKMNQUVXZ])(\d{4})", s)
    if not m:
        return None
    sym, code, year = m.group(1), m.group(2), int(m.group(3))
    month_num = MONTH_CODE_TO_NUM.get(code)
    if month_num is None:
        return None
    return sym, year, month_num

# --- Função auxiliar: extrai (símbolo, ano, mês) de strings como 'ZCH2026', 'ZSF2026' (com ou sem parênteses) ---
# Comentário: usada para transformar 'ZCH2026' -> ('ZC', 2026, 3) com base no código de mês CBOT.
import re

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

# --- Constrói price_map a partir de preços explícitos (ex.: {'ZCZ2025': 495.0, 'ZCH2026': 502.0, ...}) ---
# Comentário: converte cada ticker explícito em (símbolo, ano, mês) e popula o dicionário de preços.
def build_price_map_from_explicit(explicit_prices: dict[str, float | None]):
    price_map = {}
    units_map = {"ZC": "c$/bu", "ZS": "c$/bu"}  # mantém unidade consistente para CBOT

    for tk, px in explicit_prices.items():
        if px is None:
            continue  # se falhou o fetch, deixa para o carry preencher depois
        parsed = parse_explicit_ticker(tk)
        if not parsed:
            continue
        sym, y, m = parsed
        price_map[(sym, y, m)] = float(px)

    return price_map, units_map


# --- Define o primeiro mês listado a partir da data atual, com preferência de benchmark quando aplicável ---
# Comentário: regra para ZC (milho) — entre Ago e Nov, o mercado costuma ancorar no Dezembro (Z).
def choose_start_month(symbol: str, from_year: int, from_month: int):
    listed = LISTED_MONTHS[symbol]

    # Caso geral: pega o primeiro mês listado >= mês atual; se não houver, vira para o próximo ano.
    candidates = [(from_year, m) for m in listed if m >= from_month]
    base = candidates[0] if candidates else (from_year + 1, listed[0])

    return base


# --- Gera N tickers explícitos (ex.: 'ZCZ2025', 'ZCH2026', ...) a partir do mês inicial escolhido ---
# Comentário: segue a sequência oficial de meses listados por símbolo.
def generate_explicit_tickers(symbol: str, start_year: int, start_month: int, n: int):
    listed = LISTED_MONTHS[symbol]
    y0, m0 = choose_start_month(symbol, start_year, start_month)

    # Acha o índice do m0 dentro dos 'listed'; se m0 não estiver (ex.: ajuste ZC para Dez),
    # começa na posição correspondente do 'listed' mais próxima ao m0 para manter a sequência sazonal.
    if m0 in listed:
        idx = listed.index(m0)
    else:
        # escolhe o primeiro mês listado >= m0; se não houver, gira para o primeiro
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
        # avança
        pos += 1
        if pos >= len(listed):
            pos = 0
            y += 1
    return out


# --- Função principal: constrói mapa de preços por (símbolo, ano, mês) usando o DataFrame de cotações ---
def build_price_map(df_cot: pd.DataFrame, today_year: int, today_month: int):
    """
    Retorna:
      - price_map: dict {('ZC'|'ZS', ano, mês): preço}
      - units_map: dict {('ZC'|'ZS'): unidade}  (assume c$/bu)
    Preenche:
      * Meses explícitos: ZCH2026, ZSK2026, etc.
      * Fronts: ZC1, ZC2, ZS1, ZS2 mapeados para os dois próximos meses listados a partir de hoje.
    """
    price_map = {}
    units_map = {"ZC": "c$/bu", "ZS": "c$/bu"}

    # 1) Mapeia contratos explícitos (com letra e ano)
    df_explicit = df_cot[df_cot["Produto"].str.contains(r"ZC[FGHJKMNQUVXZ]\d{4}|ZS[FGHJKMNQUVXZ]\d{4}", regex=True)].copy()
    for _, row in df_explicit.iterrows():
        parsed = parse_explicit_contract(row["Produto"])
        if parsed:
            sym, y, m = parsed
            price_map[(sym, y, m)] = float(row["Preço"])

    # 2) Mapeia front-months (ZC1, ZC2, ZS1, ZS2) para os próximos dois listados a partir de hoje
    for sym in ["ZC", "ZS"]:
        # identifica linhas (ZC1) / (ZC2) / (ZS1) / (ZS2)
        for i, slot in enumerate([1, 2], start=1):
            mask = df_cot["Produto"].str.fullmatch(fr"\({sym}{slot}\)", case=False)
            if not mask.any():
                continue
            price = float(df_cot.loc[mask, "Preço"].iloc[0])
            (y1, m1), (y2, m2) = next_two_listed_months(sym, today_year, today_month)
            target = (y1, m1) if i == 1 else (y2, m2)
            # Só preenche se ainda não houver preço mais específico
            price_map.setdefault((sym, target[0], target[1]), price)

    return price_map, units_map


# --- Função: preenche preços para cada mês calendário carregando do próximo listado disponível ---
def build_monthly_series(symbol: str, month_grid: list[tuple[int, int]], price_map: dict, units_map: dict):
    """
    Para cada (ano, mês) do grid:
      - se for mês listado e houver preço no price_map, usa esse preço
      - se não for listado OU não houver preço explícito, usa o preço do PRÓXIMO mês listado futuro
    Caso não exista preço futuro (ex.: último mês do grid), repete o último preço válido.
    Retorna DataFrame com colunas: ['Ativo', 'Ano', 'Mês', 'Vencimento', 'Preço', 'Unidade'].
    """
    listed = set(LISTED_MONTHS[symbol])

    # 1) Monta timeline de nós listados que já têm preço (ordena por data)
    listed_nodes = sorted(
        [(y, m) for (sym, y, m) in price_map.keys() if sym == symbol],
        key=lambda x: (x[0], x[1])
    )

    def find_next_future_price(y0, m0):
        """Retorna preço do próximo mês listado >= (y0, m0)."""
        for (y, m) in listed_nodes:
            if (y > y0) or (y == y0 and m >= m0):
                return price_map.get((symbol, y, m))
        return None

    rows = []
    last_price = None

    for (y, m) in month_grid:
        # Se o mês é listado e tem preço explícito, usa diretamente
        if m in listed and (symbol, y, m) in price_map:
            price_to_use = price_map[(symbol, y, m)]
            last_price = price_to_use
        else:
            # Caso contrário, busca o próximo preço futuro
            next_price = find_next_future_price(y, m)
            if next_price is not None:
                price_to_use = next_price
            else:
                # Se não houver futuro (fim da linha), repete o último preço conhecido
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



# --- Passo 1: Determinar 'hoje' (timezone São Paulo) e construir grade de 10 meses a partir do mês atual ---
tz = ZoneInfo("America/Sao_Paulo")
today = datetime.now(tz)
start_year, start_month = today.year, today.month
month_grid = generate_month_grid(start_year, start_month, horizon=10)

# --- Passo 2 (dinâmico): Gerar tickers explícitos e buscar preços no TradingView ---
# Comentário: cria automaticamente a lista de próximos contratos explícitos para ZC e ZS, e busca preços via cot.fetch_eua.

# Quantos contratos explícitos você quer buscar por símbolo (ex.: 6 cobre ~1 a 1,5 anos à frente)
NUM_CONTRACTS_PER_SYMBOL = 6

# Gera as listas de tickers começando do mês/ano atuais, conforme regras por símbolo
zc_tickers = generate_explicit_tickers("ZC", start_year, start_month, NUM_CONTRACTS_PER_SYMBOL)
zs_tickers = generate_explicit_tickers("ZS", start_year, start_month, NUM_CONTRACTS_PER_SYMBOL)

# Busca os preços com tratamento de exceção (não derruba se algum ticker falhar)
explicit_prices = {}  # dict[str, float|None]
for tk in zc_tickers + zs_tickers:
    try:
        explicit_prices[tk] = float(cot.fetch_eua(tk))
    except Exception as e:
        explicit_prices[tk] = None  # registra falha; o "carry" de preços cobrirá lacunas depois

# (Opcional) Exiba quais tickers foram buscados e quais falharam — ajuda no debug
print("Tickers gerados (ZC):", zc_tickers)
print("Tickers gerados (ZS):", zs_tickers)
print("Falhas/Faltantes:", [k for k, v in explicit_prices.items() if v is None])


# --- Passo 3 (novo): Construir price_map a partir de explicit_prices (sem depender do DF de cotações) ---
# Comentário: agora o mapa de preços vem direto dos tickers explícitos gerados no Passo 2.
price_map, units_map = build_price_map_from_explicit(explicit_prices)


# --- Passo 4: Montar séries mensais de ZC e ZS aplicando a regra de carregar preço até o próximo listado ---
df_zc = build_monthly_series("ZC", month_grid, price_map, units_map)
df_zs = build_monthly_series("ZS", month_grid, price_map, units_map)

# --- Passo 5: Unir em uma única tabela organizada e exibir ---
df_final = pd.concat([df_zc, df_zs], ignore_index=True)
#print("Tabela (10 meses a partir de hoje) — cotações CBOT carregadas até o próximo vencimento listado:")
#print(df_final.to_string(index=False))

#-----PARTE 1 DA TABELA: INICIO DA CRIAÇÃO DA TABELA FINAL DO PPE: COLOCAR O ATIVO, O VIMENTO E O PREÇO EM c$/bu-----
df_ppe_soja = df_zs[["Ativo", "Vencimento", "Preço"]].copy()
df_ppe_milho = df_zc[["Ativo", "Vencimento", "Preço"]].copy()
#print(df_ppe_soja)
#print(df_ppe_milho)

#==============================================================
# Importar e tratar os premios de exportação do arquivo premios_export_soja_milho.py
#==============================================================

# --- Importa os prêmios de exportação (lê Google Sheets via módulo existente) ---
import premios_export_soja_milho as premios  # df_soja e df_milho já vêm prontos com colunas ["Mes", "Premio"]

# --- Mapa de meses PT-BR -> número (para normalizar 'Set/25' em (2025, 9)) ---
_MES_PT_TO_NUM = {
"Jan": 1, "Fev": 2, "Mar": 3, "Abr": 4, "Mai": 5, "Jun": 6,
"Jul": 7, "Ago": 8, "Set": 9, "Out": 10, "Nov": 11, "Dez": 12,
}

# --- Função auxiliar: converte rótulo 'Mes' tipo 'Set/25' em (ano, mes) inteiros, formato YYYY, M ---
def _parse_mes_pt(label: str) -> tuple[int, int]:
    mes_abbr, ano2 = label.split("/")
    m = _MES_PT_TO_NUM[mes_abbr.strip().title()]
    y = 2000 + int(ano2)  # assume século 2000+
    return y, m

# --- Normaliza DataFrames de prêmios para chaves comparáveis com 'Vencimento' (MM/YYYY) ---
df_premio_soja = premios.df_soja.copy()
df_premio_milho = premios.df_milho.copy()

# --- Adiciona colunas (Ano, MesNum) a partir de 'Mes' e uma chave 'MM/YYYY' padronizada ---
df_premio_soja[["Ano", "MesNum"]] = df_premio_soja["Mes"].apply(lambda s: pd.Series(_parse_mes_pt(s)))
df_premio_milho[["Ano", "MesNum"]] = df_premio_milho["Mes"].apply(lambda s: pd.Series(_parse_mes_pt(s)))
df_premio_soja["Chave"] = df_premio_soja["MesNum"].astype(int).map(lambda x: f"{x:02d}") + "/" + df_premio_soja["Ano"].astype(int).astype(str)
df_premio_milho["Chave"] = df_premio_milho["MesNum"].astype(int).map(lambda x: f"{x:02d}") + "/" + df_premio_milho["Ano"].astype(int).astype(str)

# --- Cria estruturas ordenadas por (Ano, MesNum) para buscar o próximo prêmio futuro ---
prem_soja_sorted = df_premio_soja.sort_values(["Ano", "MesNum"]).reset_index(drop=True)
prem_milho_sorted = df_premio_milho.sort_values(["Ano", "MesNum"]).reset_index(drop=True)

# --- Função: dado (ano, mês) procura o prêmio do PRÓXIMO vencimento disponível (>= alvo). Se não houver, usa o último conhecido (fallback) ---
def _next_or_last_premio(y: int, m: int, prem_sorted: pd.DataFrame) -> tuple[int | float | None, str | None]:
    # varre para frente (>= alvo)
    fut = prem_sorted[(prem_sorted["Ano"] > y) | ((prem_sorted["Ano"] == y) & (prem_sorted["MesNum"] >= m))]
    if not fut.empty:
        row = fut.iloc[0]
        return row["Premio"], row["Chave"]  # retorna valor e de qual chave veio
    # se não existe futuro, usa o último disponível (<= alvo)
    past = prem_sorted[(prem_sorted["Ano"] < y) | ((prem_sorted["Ano"] == y) & (prem_sorted["MesNum"] <= m))]
    if not past.empty:
        row = past.iloc[-1]
        return row["Premio"], row["Chave"]
    # nenhum prêmio disponível
    return None, None

# --- Extrai (Ano, Mes) de 'Vencimento' (MM/YYYY) para poder comparar com a curva de prêmios ---
def _parse_venc_mm_yyyy(v: str) -> tuple[int, int]:
    mm, yyyy = v.split("/")
    return int(yyyy), int(mm)

# --- Aplica a regra do “próximo prêmio” em df_ppe_soja (ZS) ---
df_ppe_soja = df_ppe_soja.copy()
df_ppe_soja[["Ano", "MesNum"]] = df_ppe_soja["Vencimento"].apply(lambda s: pd.Series(_parse_venc_mm_yyyy(s)))
premios_soja_vals = []
premios_soja_src = []
for y, m in zip(df_ppe_soja["Ano"].tolist(), df_ppe_soja["MesNum"].tolist()):
    val, src = _next_or_last_premio(y, m, prem_soja_sorted)
    premios_soja_vals.append(val)
    premios_soja_src.append(src)
df_ppe_soja["Premio"] = premios_soja_vals
df_ppe_soja["PremioData"] = premios_soja_src  # opcional p/ auditoria (de qual mês veio o prêmio)

# --- Aplica a regra do “próximo prêmio” em df_ppe_milho (ZC) ---
df_ppe_milho = df_ppe_milho.copy()
df_ppe_milho[["Ano", "MesNum"]] = df_ppe_milho["Vencimento"].apply(lambda s: pd.Series(_parse_venc_mm_yyyy(s)))
premios_milho_vals = []
premios_milho_src = []
for y, m in zip(df_ppe_milho["Ano"].tolist(), df_ppe_milho["MesNum"].tolist()):
    val, src = _next_or_last_premio(y, m, prem_milho_sorted)
    premios_milho_vals.append(val)
    premios_milho_src.append(src)
df_ppe_milho["Premio"] = premios_milho_vals
df_ppe_milho["PremioData"] = premios_milho_src  # opcional p/ auditoria

# --- PARTE 2 DA TABELA: ADICIONA A COLUNA DE PREMIO E O MÊS DE REFERÊNCIA DO PRÊMIO  ---
df_ppe_soja = df_ppe_soja[["Ativo", "Vencimento", "Preço", "Premio", "PremioData"]]
df_ppe_milho = df_ppe_milho[["Ativo", "Vencimento", "Preço", "Premio", "PremioData"]]
#print("\nPPE – Soja (com prêmio aplicado por carry para frente):")
#print(df_ppe_soja.to_string(index=False))
#print("\nPPE – Milho (com prêmio aplicado por carry para frente):")
#print(df_ppe_milho.to_string(index=False))


#==============================================================
# Importar NDF DE DÓLAR do arquivo premios_export_soja_milho.py
#==============================================================

# --- Importa NDF do mesmo módulo de prêmios (aba 'ndf' do Google Sheets) ---
import premios_export_soja_milho as premios_ndf

# --- Mapa PT-BR de mês (três letras) -> número (funciona para nomes completos via .title()[:3]) ---
_MES_PT3_TO_NUM = {"Jan":1,"Fev":2,"Mar":3,"Abr":4,"Mai":5,"Jun":6,"Jul":7,"Ago":8,"Set":9,"Out":10,"Nov":11,"Dez":12}

# --- Normaliza 'Vencimento' do NDF (ex.: 'setembro/2025' -> (2025, 9)) ---
def _parse_ndf_venc(label: str) -> tuple[int,int]:
    mes_txt, ano_txt = str(label).strip().split("/")
    mes3 = mes_txt.strip().title()[:3]  # 'Setembro' -> 'Set'
    y = int(ano_txt.strip())
    m = _MES_PT3_TO_NUM[mes3]
    return y, m

# --- Constrói DF NDF ordenado e com chave 'MM/YYYY' para auditoria/join simples ---
df_ndf = premios_ndf._read_tab_ndf().copy()  # já sanitizado no módulo
df_ndf[["Ano","MesNum"]] = df_ndf["Vencimento"].apply(lambda s: pd.Series(_parse_ndf_venc(s)))
df_ndf["Chave"] = df_ndf["MesNum"].astype(int).map(lambda x: f"{x:02d}") + "/" + df_ndf["Ano"].astype(int).astype(str)
ndf_sorted = df_ndf.sort_values(["Ano","MesNum"]).reset_index(drop=True)

# --- Utilitário: dado (ano, mês), retorna NDF do PRÓXIMO disponível; se não houver, usa o último passado ---
def _next_or_last_ndf(y: int, m: int) -> tuple[float|None, str|None]:
    fut = ndf_sorted[(ndf_sorted["Ano"] > y) | ((ndf_sorted["Ano"] == y) & (ndf_sorted["MesNum"] >= m))]
    if not fut.empty:
        row = fut.iloc[0]
        return float(row["NDF"]), row["Chave"]
    past = ndf_sorted[(ndf_sorted["Ano"] < y) | ((ndf_sorted["Ano"] == y) & (ndf_sorted["MesNum"] <= m))]
    if not past.empty:
        row = past.iloc[-1]
        return float(row["NDF"]), row["Chave"]
    return None, None

# --- Helper para extrair (Ano, Mes) de 'Vencimento' (MM/YYYY) já existente em df_ppe_* ---
def _parse_venc_mm_yyyy(v: str) -> tuple[int,int]:
    mm, yyyy = v.split("/")
    return int(yyyy), int(mm)

# --- Aplica NDF (forward-carry) na SOJA ---
df_ppe_soja = df_ppe_soja.copy()
df_ppe_soja[["Ano","MesNum"]] = df_ppe_soja["Vencimento"].apply(lambda s: pd.Series(_parse_venc_mm_yyyy(s)))
ndf_vals, ndf_src = [], []
for y, m in zip(df_ppe_soja["Ano"], df_ppe_soja["MesNum"]):
    val, src = _next_or_last_ndf(y, m)
    ndf_vals.append(val); ndf_src.append(src)
df_ppe_soja["NDF"] = ndf_vals
df_ppe_soja["NDFFonte"] = ndf_src

# --- Aplica NDF (forward-carry) no MILHO ---
df_ppe_milho = df_ppe_milho.copy()
df_ppe_milho[["Ano","MesNum"]] = df_ppe_milho["Vencimento"].apply(lambda s: pd.Series(_parse_venc_mm_yyyy(s)))
ndf_vals, ndf_src = [], []
for y, m in zip(df_ppe_milho["Ano"], df_ppe_milho["MesNum"]):
    val, src = _next_or_last_ndf(y, m)
    ndf_vals.append(val); ndf_src.append(src)
df_ppe_milho["NDF"] = ndf_vals
df_ppe_milho["NDFFonte"] = ndf_src

# --- PARTE 2 DA TABELA: ADICIONA A COLUNA DE NDF ) ---
df_ppe_soja = df_ppe_soja[["Ativo","Vencimento","Preço","Premio","NDF","NDFFonte"]]
df_ppe_milho = df_ppe_milho[["Ativo","Vencimento","Preço","Premio","NDF", "NDFFonte"]]
#print("\nPPE – Soja (com Prêmio + NDF):")
#print(df_ppe_soja.to_string(index=False))
#print("\nPPE – Milho (com Prêmio + NDF):")
#print(df_ppe_milho.to_string(index=False))

#==============================================================
# Calcular demais colunas do PPE por praça
#==============================================================

df_ppe_soja ["FOB (c$/bu)"] = df_ppe_soja["Preço"] + df_ppe_soja["Premio"]
df_ppe_milho ["FOB (c$/bu)"] = df_ppe_milho["Preço"] + df_ppe_milho["Premio"]
df_ppe_soja ["FOB ($/ton)"] = df_ppe_soja["FOB (c$/bu)"] * 0.367437
df_ppe_milho ["FOB ($/ton)"] = df_ppe_milho["FOB (c$/bu)"] * 0.393687
df_ppe_soja["FOB (R$/ton)"] = df_ppe_soja["FOB ($/ton)"] * df_ppe_soja["NDF"] 
df_ppe_milho["FOB (R$/ton)"] = df_ppe_milho["FOB ($/ton)"] * df_ppe_milho["NDF"]
df_ppe_soja["Sobre rodas"] = df_ppe_soja["FOB (R$/ton)"] - fobbings
df_ppe_milho["Sobre rodas"] = df_ppe_milho["FOB (R$/ton)"] - fobbings
df_ppe_soja["EXW"] = df_ppe_soja["Sobre rodas"] - frete_dom
df_ppe_milho["EXW"] = df_ppe_milho["Sobre rodas"] - frete_dom
df_ppe_soja["PPE Preço saca origem (R$/sc)"] = df_ppe_soja["EXW"] * 0.06
df_ppe_milho["PPE Preço saca origem (R$/sc)"] = df_ppe_milho["EXW"] * 0.06
df_ppe_soja["Basis Praça-CBOT (c$/bu)"] = ((df_ppe_soja["PPE Preço saca origem (R$/sc)"] / df_ppe_soja["NDF"]) / 2.204 - df_ppe_soja["Preço"]/100)*100 
df_ppe_milho["Basis Praça-CBOT (c$/bu)"] = ((df_ppe_milho["PPE Preço saca origem (R$/sc)"] / df_ppe_milho["NDF"]) / 2.204 - df_ppe_milho["Preço"]/100)*100

#print(df_ppe_soja.round(2).to_string(index=False))
#print(df_ppe_milho.round(2).to_string(index=False))
df_ppe_soja.to_excel(OUTPUTS_DIR / "PPE_SOJA.xlsx", index=False)
df_ppe_milho.to_excel(OUTPUTS_DIR  / "PPE_MILHO.xlsx", index=False)
#==============================================================
# PPE PORTO, CFR CHINA
#==============================================================
cfr_chinabrasil_milho = df_ppe_milho ["FOB ($/ton)"] + frete_int_santos_asia     # $/ton
basiscfr_chinabrasil_milho = cfr_chinabrasil_milho/0.393683 - df_ppe_milho["Preço"]  #c$/bu

# =============================================================================
# DESCRIÇÃO DO SCRIPT PPE_UNDERLINE_COMPLETO.PY
# =============================================================================
#
# O QUE ESTE SCRIPT FAZ
# ---------------------
# - Importa cotações da CBOT (soja ZS e milho ZC) do arquivo cotacoes_tradingview_cepea.py.
# - Importa prêmios de exportação (soja e milho) e valores de NDF do dólar do arquivo premios_export_soja_milho.py.
# - Constrói curvas mensais para soja e milho (10 meses a partir da data atual), 
#   preenchendo meses sem contrato ou prêmio com o próximo valor disponível.
# - Calcula colunas derivadas do PPE:
#     * FOB em c$/bu
#     * FOB em $/ton
#     * FOB em R$/ton (multiplicando pelo NDF do mês)
#     * Sobre rodas (FOB R$/ton - fobbings)
#     * EXW (Sobre rodas - frete doméstico)
#     * PPE Preço saca origem (R$/sc)
#     * Basis Praça-CBOT (c$/bu)
# - Exibe no console duas tabelas finais: df_ppe_soja e df_ppe_milho, cada uma com 
#   todas as colunas acima.
#
# OUTPUTS
# -------
# 1) df_ppe_soja: DataFrame da soja com colunas:
#    Ativo, Vencimento, Preço, Premio, NDF, FOB (c$/bu), FOB ($/ton), 
#    FOB (R$/ton), Sobre rodas, EXW, PPE Preço saca origem (R$/sc), Basis Praça-CBOT (c$/bu).
# 2) df_ppe_milho: DataFrame do milho com a mesma estrutura de colunas.
#
# O QUE O USUÁRIO PODE MUDAR
# --------------------------
# - fobbings (linha inicial): valor em R$/ton usado no cálculo "Sobre rodas".
# - frete_dom (linha inicial): valor do frete doméstico em R$/ton.
# - NUM_CONTRACTS_PER_SYMBOL: quantidade de contratos futuros buscados (mais meses à frente).
# - Horizonte da grade de meses (horizon=10 em generate_month_grid).
# - Fórmulas de conversão (fatores 0.367437 para soja e 0.393687 para milho).
# - Colunas finais selecionadas para exibir no print.
#
# O QUE PODE AFETAR ESTE SCRIPT SE OUTROS ARQUIVOS FOREM ALTERADOS
# ---------------------------------------------------------------
# - cotacoes_tradingview_cepea.py:
#     * Se mudar nomes de funções (ex.: fetch_eua), o import quebrará.
#     * Se mudar símbolos buscados (ex.: ZCH2026), ajuste o gerador de tickers.
# - premios_export_soja_milho.py:
#     * Se mudar o formato da coluna "Mes" (ex.: "Set/25" → "Set/2025"), ajuste o parser _parse_mes_pt.
#     * Se mudar a aba "ndf" (nomes das colunas ou formato "setembro/2025"), ajuste o parser _parse_ndf_venc.
#     * Se mudar nomes das colunas (Premio, NDF), atualize os blocos de renomeação.
#
# =============================================================================
