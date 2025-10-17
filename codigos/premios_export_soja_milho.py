# =================================================================================
# ========================== PRÊMIOS DE EXPORTAÇÃO ================================
# =================================================================================

# ==== Google Sheets: leitura robusta (somente leitura) ====
from pathlib import Path
import re
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd


# IDs / abas
SHEET_ID   = "1TxP2D1tH0ACNMfWWdUvV1Dy9KiEdyI2Pj8xagGBx-w8"
TAB_SOJA   = "soja"
TAB_MILHO  = "milho"

# Escopos de SOMENTE LEITURA
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets.readonly",
    "https://www.googleapis.com/auth/drive.readonly",
]

def _open_sheet():
    import streamlit as st
    
    try:
        # Tenta carregar do Streamlit Secrets (Cloud)
        if "gsheets" in st.secrets:
            gsheets_secrets = dict(st.secrets["gsheets"])
            creds = Credentials.from_service_account_info(gsheets_secrets, scopes=SCOPES)
            gc = gspread.authorize(creds)
            return gc.open_by_key(SHEET_ID)
    except Exception as e:
        print(f"[DEBUG] Falha ao carregar do st.secrets: {e}")
    
    # Fallback para desenvolvimento local (arquivo JSON)
    BASE_DIR = Path(_file_).resolve().parent.parent
    GSHEETS_KEY_PATH = BASE_DIR / "secrets" / "gsheets-key.json"
    
    if not GSHEETS_KEY_PATH.exists():
        raise FileNotFoundError(
            f"Credencial não encontrada: {GSHEETS_KEY_PATH}. "
            f"Coloque o JSON do Service Account nessa pasta ou ajuste o caminho."
        )
    
    creds = Credentials.from_service_account_file(str(GSHEETS_KEY_PATH), scopes=SCOPES)
    gc = gspread.authorize(creds)
    return gc.open_by_key(SHEET_ID)

def _fix_mes(label: str) -> str:
    """Converte 'ago./25' -> 'Ago/25' e padroniza 3 letras."""
    if not isinstance(label, str):
        return label
    s = re.sub(r"\.", "", label.strip())
    mapa = {
        'jan':'Jan','fev':'Fev','mar':'Mar','abr':'Abr','mai':'Mai','jun':'Jun',
        'jul':'Jul','ago':'Ago','set':'Set','out':'Out','nov':'Nov','dez':'Dez'
    }
    m = re.match(r"([A-Za-z]{3,})[\/\s\-]?(\d{2})$", s, flags=re.IGNORECASE)
    if not m:  # se vier fora do padrão, devolve como está
        return label
    mes_raw, ano2 = m.group(1), m.group(2)
    mes = mapa.get(mes_raw.lower()[:3], mes_raw.title()[:3])
    return f"{mes}/{ano2}"

def _clean_df(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    df = df.copy()
    df.columns = [c.strip() for c in df.columns]
    ren = {}
    for c in df.columns:
        if c.lower() == "mes": ren[c] = "Mes"
        if c.lower() == "premio": ren[c] = "Premio"
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

def _read_tab(tab: str) -> pd.DataFrame:
    try:
        sh = _open_sheet()
        ws = sh.worksheet(tab)
        rows = ws.get_all_records()  # usa cabeçalho da linha 1
        return _clean_df(pd.DataFrame(rows))
    except gspread.exceptions.APIError as e:
        # Mensagem amigável para 403
        if "403" in str(e):
            raise PermissionError(
                "Permissão insuficiente no Google Sheets. "
                "Abra o arquivo 'secrets/gsheets-key.json', copie o 'client_email' "
                "e compartilhe a planilha 'premios_exportacao' com esse e‑mail como EDITOR."
            ) from e
        raise

# >>> CARGA EFETIVA <<<
df_soja  = _read_tab(TAB_SOJA)
df_milho = _read_tab(TAB_MILHO)

# Se o seu app ainda usa dicionários:
soja_dados  = {"Mês": df_soja["Mes"].tolist(),  "Prêmio": df_soja["Premio"].astype(int).tolist()}
milho_dados = {"Mês": df_milho["Mes"].tolist(), "Prêmio": df_milho["Premio"].astype(int).tolist()}

print("Prêmios de exportação: Soja (c$/bu):")
print(df_soja)
print("Prêmios de exportação:Milho (c$/bu):")
print(df_milho)

# =================================================================================
# ========================== NDF (Google Sheets) ==================================
# =================================================================================

def _read_tab_ndf() -> pd.DataFrame:
    """Lê aba 'ndf' com colunas: Vencimento (texto 'Mês/AAAA') e NDF (número)."""
    sh = _open_sheet()  # usa a mesma função que você já tem para abrir a planilha
    ws = sh.worksheet("ndf")
    rows = ws.get_all_records()
    df = pd.DataFrame(rows)

    # padroniza nomes
    df.columns = [c.strip() for c in df.columns]
    ren = {}
    for c in df.columns:
        if c.lower() == "vencimento": ren[c] = "Vencimento"
        if c.lower() == "ndf": ren[c] = "NDF"
    df = df.rename(columns=ren)

    # mantém só as colunas relevantes
    df = df[["Vencimento", "NDF"]].copy()

    # --- PATCH SIMPLES: corrige vírgula/escala independentemente de como o Sheets entregou ---
    import re
    def _fix_ndf(v):
        # 1) tenta respeitar vírgula caso venha como string
        try:
            v_str = str(v).strip().replace(' ', '').replace(',', '.')
            v = float(v_str)
        except Exception:
            try:
                v = float(v)
            except Exception:
                return pd.NA

        # 2) guarda de escala: se veio 54, 543, 804 etc., traz para 5.4, 5.43, 8.04
        while v >= 20:
            v /= 10.0

        return round(v, 2)

    df["NDF"] = df["NDF"].apply(_fix_ndf)
    # -----------------------------------------------------------------------------------------

    df = df.dropna(subset=["Vencimento", "NDF"]).reset_index(drop=True)
    return df

df_ndf = _read_tab_ndf()
ndf_vencimentos = {row["Vencimento"]: float(row["NDF"]) for _, row in df_ndf.iterrows()}
print("NDF (topo):")
print(df_ndf)



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
