# Funcionando, mas a tabela é unidirecional

import streamlit as st
import pandas as pd
import json
from pathlib import Path
import sys
from io import BytesIO

# Adiciona a pasta 'codigos' ao path para importar módulos
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR / "codigos"))

ASSETS_DIR = BASE_DIR / "configs"
LOGO_MAIN = ASSETS_DIR / "Logo_Pine.webp"

import ppe_engine

# Configuração da página
st.set_page_config(
    page_title="PPE - Preço Paridade Exportação",
    page_icon="📊",
    layout="wide"
)

st.sidebar.image(str(LOGO_MAIN))

# Carrega configuração de clientes
CONFIG_PATH = BASE_DIR / "configs" / "clientes.json"

def load_clientes():
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

# Função de autenticação
def authenticate():
    if 'authenticated' not in st.session_state:
        st.session_state.authenticated = False
        st.session_state.cliente_nome = None
    
    if not st.session_state.authenticated:
        st.title("🔐 Login - PPE")
        
        clientes = load_clientes()
        
        with st.form("login_form"):
            senha = st.text_input("Digite sua senha:", type="password")
            submit = st.form_submit_button("Entrar")
            
            if submit:
                # Busca cliente pela senha
                cliente_encontrado = None
                for nome, dados in clientes.items():
                    if dados.get("senha") == senha:
                        cliente_encontrado = nome
                        break
                
                if cliente_encontrado:
                    st.session_state.authenticated = True
                    st.session_state.cliente_nome = cliente_encontrado
                    st.rerun()
                else:
                    st.error("❌ Senha incorreta!")
        
        st.stop()

# Função para formatar DataFrame com cores
def style_dataframe(df, produto):
    """Aplica estilo visual ao DataFrame"""
    
    # Define cores por produto
    cores = {
        "soja": {"header": "#2E7D32", "row1": "#E8F5E9", "row2": "#F1F8E9"},
        "milho": {"header": "#F57C00", "row1": "#FFF3E0", "row2": "#FFECB3"}
    }
    
    cor = cores.get(produto.lower(), cores["soja"])
    
    # Colunas numéricas para formatar
    numeric_cols = df.select_dtypes(include=['float64', 'int64']).columns
    
    def format_number(val):
        if pd.isna(val):
            return ""
        return f"{val:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    
    # Aplica formatação
    styled = df.style.format(
        {col: format_number for col in numeric_cols}
    )
    
    # Destaca linhas alternadas
    styled = styled.set_properties(**{
        'background-color': cor['row1'],
        'color': 'black',
        'border': '1px solid #ddd',
        'text-align': 'center'
    }, subset=pd.IndexSlice[::2, :])
    
    styled = styled.set_properties(**{
        'background-color': cor['row2'],
        'color': 'black',
        'border': '1px solid #ddd',
        'text-align': 'center'
    }, subset=pd.IndexSlice[1::2, :])
    
    # Estilo do header
    styled = styled.set_table_styles([
        {'selector': 'th',
         'props': [('background-color', cor['header']),
                   ('color', 'white'),
                   ('font-weight', 'bold'),
                   ('text-align', 'center'),
                   ('border', '1px solid white')]}
    ])
    
    return styled

# Main app
authenticate()

# Header
st.title("📊 PPE - Preço Paridade Exportação")
st.markdown(f"**Cliente:** {st.session_state.cliente_nome}")

# Botão de logout
col1, col2, col3 = st.columns([6, 1, 1])
with col3:
    if st.button("🚪 Sair"):
        st.session_state.authenticated = False
        st.session_state.cliente_nome = None
        st.rerun()

st.markdown("---")

# Sidebar com inputs
st.sidebar.header("⚙️ Parâmetros de Cálculo")

# Seleção de produto
produto_opcoes = ["Soja", "Milho", "Soja e Milho"]
produto_selecionado = st.sidebar.selectbox(
    "Selecione o produto:",
    produto_opcoes,
    index=2
)

st.sidebar.markdown("---")

# Inputs editáveis
fobbings = st.sidebar.number_input(
    "FOB Bings (R$/ton):",
    min_value=0.0,
    value=40.0,
    step=1.0,
    format="%.2f"
)

frete_dom = st.sidebar.number_input(
    "Frete Doméstico (R$/ton):",
    min_value=0.0,
    value=342.0,
    step=1.0,
    format="%.2f"
)

st.sidebar.markdown("---")

# Botão para recalcular
if st.sidebar.button("🔄 Recalcular PPE", type="primary"):
    with st.spinner("Calculando PPE..."):
        try:
            # Executa cálculo
            df_soja, df_milho = ppe_engine.calcular_ppe(
                fobbings=fobbings,
                frete_dom=frete_dom
            )
            
            # Salva nos arquivos do cliente
            clientes = load_clientes()
            cliente_data = clientes[st.session_state.cliente_nome]
            
            output_dir = BASE_DIR / "outputs" / cliente_data["pasta"]
            output_dir.mkdir(parents=True, exist_ok=True)
            
            df_soja.to_excel(output_dir / "PPE_SOJA.xlsx", index=False)
            df_milho.to_excel(output_dir / "PPE_MILHO.xlsx", index=False)
            
            st.session_state.df_soja = df_soja
            st.session_state.df_milho = df_milho
            st.session_state.recalculado = True
            
            st.success("✅ PPE recalculado com sucesso!")
            
        except Exception as e:
            st.error(f"❌ Erro ao calcular: {str(e)}")

# Carrega dados do cliente (se já existirem)
if 'df_soja' not in st.session_state or 'df_milho' not in st.session_state:
    clientes = load_clientes()
    cliente_data = clientes[st.session_state.cliente_nome]
    output_dir = BASE_DIR / "outputs" / cliente_data["pasta"]
    
    try:
        if (output_dir / "PPE_SOJA.xlsx").exists():
            st.session_state.df_soja = pd.read_excel(output_dir / "PPE_SOJA.xlsx")
        if (output_dir / "PPE_MILHO.xlsx").exists():
            st.session_state.df_milho = pd.read_excel(output_dir / "PPE_MILHO.xlsx")
    except Exception as e:
        st.info("ℹ️ Nenhum dado disponível. Clique em 'Recalcular PPE' para gerar.")

# Exibe tabelas
st.markdown("---")

if produto_selecionado in ["Soja", "Soja e Milho"]:
    if 'df_soja' in st.session_state:
        st.subheader("🌱 PPE - SOJA")
        
        # Seleção de colunas para exibir
        colunas_exibir = st.multiselect(
            "Selecione colunas para exibir:",
            options=st.session_state.df_soja.columns.tolist(),
            default=["Vencimento", "Preço", "Premio", "NDF", "FOB (c$/bu)", 
                     "FOB (R$/ton)", "EXW", "PPE Preço saca origem (R$/sc)"],
            key="colunas_soja"
        )
        
        df_display = st.session_state.df_soja[colunas_exibir]
        st.dataframe(
            style_dataframe(df_display, "soja"),
            use_container_width=True,
            height=400
        )
        
        from io import BytesIO

        # Cria buffer de memória
        buffer_soja = BytesIO()
        with pd.ExcelWriter(buffer_soja, engine='openpyxl') as writer:
            st.session_state.df_soja.to_excel(writer, index=False, sheet_name='PPE_Soja')
        buffer_soja.seek(0)

        st.download_button(
            label="📥 Download Excel - Soja",
            data=buffer_soja,
            file_name=f"PPE_SOJA_{st.session_state.cliente_nome}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        
        st.markdown("---")

if produto_selecionado in ["Milho", "Soja e Milho"]:
    if 'df_milho' in st.session_state:
        st.subheader("🌽 PPE - MILHO")
        
        colunas_exibir = st.multiselect(
            "Selecione colunas para exibir:",
            options=st.session_state.df_milho.columns.tolist(),
            default=["Vencimento", "Preço", "Premio", "NDF", "FOB (c$/bu)", 
                     "FOB (R$/ton)", "EXW", "PPE Preço saca origem (R$/sc)"],
            key="colunas_milho"
        )
        
        df_display = st.session_state.df_milho[colunas_exibir]
        st.dataframe(
            style_dataframe(df_display, "milho"),
            use_container_width=True,
            height=400
        )
        
        # Cria buffer de memória
        buffer_milho = BytesIO()
        with pd.ExcelWriter(buffer_milho, engine='openpyxl') as writer:
            st.session_state.df_milho.to_excel(writer, index=False, sheet_name='PPE_Milho')
        buffer_milho.seek(0)

        st.download_button(
            label="📥 Download Excel - Milho",
            data=buffer_milho,
            file_name=f"PPE_MILHO_{st.session_state.cliente_nome}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

# Footer
st.markdown("---")
st.caption("Sistema PPE - Preço Paridade Exportação | Desenvolvido para análise de commodities agrícolas")