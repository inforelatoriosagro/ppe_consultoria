# =================================================================================
# ======================= PRÊMIOS DE EXPORTAÇÃO (refatorado) =====================
# =================================================================================

import pandas as pd
import re

TAB_SOJA   = "soja"
TAB_MILHO  = "milho"
TAB_NDF    = "ndf"

def _fix_mes(label: str) -> str:
    """Converte 'ago./25' -> 'Ago/25' e padroniza 3 letras."""
    if not isinstance(label, str):
        return label
    s = re.sub(r"\.", "", label.strip())
    mapa = {
        'jan':'Jan','fev':'Fev','mar':'Mar','abr':'Abr','mai':'Mai','jun':'Jun',
        'jul':'Jul','ago':'Ago','set':'Set','out':'Out','nov':'Nov','dez':'Dez'
    }
    m = re.match(r"([A-Za-z]{3,})[\/\s\-]?(\d{2}|\d{4})$", s, flags=re.IGNORECASE)
    if not m:  # se vier fora do padrão, devolve como está
        return label
    mes_raw, ano2 = m.group(1), m.group(2)
    mes = mapa.get(mes_raw.lower()[:3], mes_raw.title()[:3])
    return f"{mes}/{ano2}"

def _clean_df(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    df = df.copy()
    df.columns = [
        c.strip()
         .lower()
         .replace("ã","a").replace("í","i").replace("é","e").replace("ê","e")
         .replace("ó","o").replace("ô","o").replace("ú","u")
         .replace("ç","c") for c in df.columns
    ]
    ren = {}
    for c in df.columns:
        if c == "mes":
            ren[c] = "Mes"
        if c == "premio":
            ren[c] = "Premio"
    df = df.rename(columns=ren)
    df = df[["Mes", "Premio"]]
    df["Mes"] = df["Mes"].astype(str).apply(_fix_mes)
    df["Premio"] = (
        df["Premio"].astype(str)
        .str.replace("+", "", regex=False)
        .str.replace(",", ".", regex=False)
        .str.strip()
    )
    df["Premio"] = pd.to_numeric(df["Premio"], errors="coerce")
    df = df.dropna(subset=["Mes", "Premio"]).reset_index(drop=True)
    return df

def process_soja(df_raw: pd.DataFrame):
    df = _clean_df(df_raw)
    soja_dados = {
        "Mês": df["Mes"].tolist(),
        "Prêmio": df["Premio"].astype(int).tolist()
    }
    return df, soja_dados

def process_milho(df_raw: pd.DataFrame):
    df = _clean_df(df_raw)
    milho_dados = {
        "Mês": df["Mes"].tolist(),
        "Prêmio": df["Premio"].astype(int).tolist()
    }
    return df, milho_dados

def process_ndf(df_raw: pd.DataFrame):
    if df_raw.empty:
        return df_raw, {}
    
    df = df_raw.copy()
    
    # Normaliza nomes das colunas: tira espaços, coloca em minúsculas e remove acentos
    df.columns = [
        c.strip()
         .lower()
         .replace("ú", "u").replace("í", "i").replace("é", "e")
         .replace("ó", "o").replace("â", "a").replace("ã", "a")
         .replace("ç", "c") for c in df.columns
    ]
    ren = {}
    for c in df.columns:
        if c == "vencimento":
            ren[c] = "Vencimento"
        if c in ["ndf", "ultimo"]:
            ren[c] = "NDF"
    df = df.rename(columns=ren)
    
    print("Colunas após renomeação (debug):", df.columns)  # pode remover após testar
    
    df = df[["Vencimento", "NDF"]].copy()

    def _fix_ndf(v):
        try:
            v_str = str(v).strip().replace(' ', '').replace(',', '.')
            v = float(v_str)
        except Exception:
            try:
                v = float(v)
            except Exception:
                return pd.NA
        while v >= 20:
            v /= 10.0
        return round(v, 2)

    df["NDF"] = df["NDF"].apply(_fix_ndf)
    df = df.dropna(subset=["Vencimento", "NDF"]).reset_index(drop=True)

    # converter para formato Out/25, Jan/26 etc.
    try:
        df["Vencimento"] = pd.to_datetime(df["Vencimento"]).dt.strftime('%b/%y')
        trad = {'Jan': 'Jan', 'Feb': 'Fev', 'Mar': 'Mar', 'Apr': 'Abr', 'May': 'Mai',
                'Jun': 'Jun', 'Jul': 'Jul', 'Aug': 'Ago', 'Sep': 'Set', 'Oct': 'Out',
                'Nov': 'Nov', 'Dec': 'Dez'}
        df["Vencimento"] = df["Vencimento"].apply(lambda x: trad.get(x[:3], x[:3]) + x[3:])
    except Exception:
        pass

    ndf_vencimentos = {row["Vencimento"]: float(row["NDF"]) for _, row in df.iterrows()}
    return df, ndf_vencimentos


#=======================================================================================#

"""
================================================================================
PREMIOS DE EXPORTAÇÃO — Guia rápido (uso em VS Code, sem Streamlit)
Arquivo: premios_export_soja_milho.py
================================================================================

O QUE ESTE SCRIPT FAZ
- Lê, em modo SOMENTE LEITURA, duas abas (“soja” e “milho”) de um Google Sheets (SHEET_ID).
- Padroniza colunas/formatos: “Mes” (ex.: “ago./25” → “Ago/25”) e “Premio” (remove “+”, troca vírgula por ponto).
- Converte “Premio” para número e elimina linhas inválidas.
- Entrega 2 DataFrames prontos (df_soja, df_milho) e 2 dicionários (soja_dados, milho_dados).
- Imprime as tabelas no terminal.

ENTRADAS / REQUISITOS
1) Credenciais: colocar o JSON do Service Account em secrets/gsheets-key.json (caminho já absoluto).
2) Permissão: compartilhar a planilha com o e-mail client_email do JSON como EDITOR (mesmo para leitura via API).
3) Pacotes: gspread, google-auth, pandas.

PASSO A PASSO (como funciona)
1) Constantes (SHEET_ID, abas, caminho do JSON e SCOPES somente leitura).
2) _open_sheet(): carrega credenciais e abre a planilha por ID.
3) _fix_mes(): normaliza rótulos de mês (ex.: “ago./25” → “Ago/25”).
4) _clean_df(): renomeia colunas, seleciona [“Mes”, “Premio”], limpa símbolos e converte tipos.
5) _read_tab(tab): lê a aba via gspread, aplica limpeza e trata erro 403 com mensagem clara.
6) Carrega df_soja/df_milho; monta soja_dados/milho_dados; imprime os DataFrames.

SAÍDAS
- df_soja, df_milho: DataFrames com colunas [“Mes”, “Premio”].
- soja_dados, milho_dados: dicionários {“Mês”: [...], “Prêmio”: [...]} (por padrão, inteiros).
- Prints no terminal confirmando leitura.

O QUE VOCÊ PODE MODIFICAR (e como)
1) Planilha/abas: troque SHEET_ID; ajuste TAB_SOJA/TAB_MILHO para outros nomes de abas.
2) Credenciais: se o JSON estiver em outro local, altere GSHEETS_KEY_PATH; para escrita, mude SCOPES.
3) Meses: edite o dict ‘mapa’ em _fix_mes; se usar ano com 4 dígitos (“Ago/2025”), ajuste o regex (\d{4}) e a formatação.
4) Colunas: se a planilha usar nomes diferentes, altere o bloco ‘ren’ e a seleção df[[“Mes”, “Premio”]] em _clean_df.
5) Números: para manter decimais, remova .astype(int) nos dicionários; para arredondar, use .round(n).
6) Integração: em vez de print(), retorne os DataFrames (ex.: `return df_soja, df_milho`) ao importar este módulo; ou salve CSVs com .to_csv().
7) Tratamento de erros: personalize mensagens de FileNotFoundError/PermissionError; adicione retries/backoff se necessário.

ERROS COMUNS
- FileNotFoundError: JSON ausente em secrets/gsheets-key.json → coloque o arquivo ou ajuste o caminho.
- 403 (permissão): compartilhe a planilha com o client_email do JSON como EDITOR.
- Colunas não encontradas: revise nomes na planilha e o mapeamento em _clean_df.
- NaN em “Premio”: refine o replace/regex se houver símbolos/textos fora do padrão.
"""
