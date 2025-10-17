# Sistema PPE - Streamlit

streamlit run codigos/streamlit_app.py

## 📁 Estrutura de Arquivos

```
PPE/
├── codigos/
│   ├── streamlit_app.py          # Interface Streamlit (NOVO)
│   ├── ppe_engine.py              # Motor de cálculo (NOVO)
│   ├── PPE_completo.py            # Script original (manter)
│   ├── cotacoes_tradingview_cepea.py
│   └── premios_export_soja_milho.py
├── configs/
│   ├── .env
│   └── clientes.json              # Cadastro de clientes (NOVO)
├── outputs/
│   ├── cliente_a/                 # Pastas por cliente (NOVO)
│   ├── cliente_b/
│   └── cliente_teste/
└── secrets/
    └── gsheets-key.json
```

## 🚀 Como Rodar

### 1. Instalar Streamlit
```bash
pip install streamlit
```

### 2. Rodar o aplicativo
```bash
cd codigos
streamlit run streamlit_app.py
```

### 3. Acessar no navegador
O Streamlit abrirá automaticamente em `http://localhost:8501`

## 🔐 Gerenciamento de Clientes

### Adicionar novo cliente

Edite o arquivo `configs/clientes.json`:

```json
{
  "Nome_Cliente": {
    "senha": "senha_do_cliente",
    "pasta": "nome_pasta_outputs",
    "descricao": "Descrição opcional"
  }
}
```

**Exemplo prático:**
```json
{
  "Fazenda_XYZ": {
    "senha": "xyz2025",
    "pasta": "fazenda_xyz",
    "descricao": "Cliente desde 2024"
  }
}
```

### Remover cliente
Simplesmente delete a entrada correspondente no JSON.

## 🎨 Recursos da Interface

### Login
- Cada cliente acessa com sua senha única
- Sem usuário, apenas senha (mais simples)
- Botão "Sair" no canto superior direito

### Parâmetros Editáveis
- **Produto:** Soja | Milho | Soja e Milho
- **FOB Bings (R$/ton)**
- **Frete Doméstico (R$/ton)**
- **Frete Internacional Santos-Ásia ($/ton)**

### Tabelas
- **Cores diferentes:** Verde para soja, laranja para milho
- **Linhas alternadas** para facilitar leitura
- **Seleção de colunas:** Escolha quais colunas exibir
- **Download CSV:** Botão para baixar dados

### Recálculo em Tempo Real
- Botão "🔄 Recalcular PPE"
- Atualiza automaticamente quando inputs mudam
- Salva resultados na pasta do cliente

## 📊 Dados Gerados

Para cada cliente, são criados:
- `outputs/[pasta_cliente]/PPE_SOJA.xlsx`
- `outputs/[pasta_cliente]/PPE_MILHO.xlsx`

## ⚠️ Importante

1. **Credenciais Trading View:** Mantenha o arquivo `configs/.env` atualizado
2. **Google Sheets:** O arquivo `secrets/gsheets-key.json` deve estar presente
3. **Senhas em produção:** Use senhas fortes e considere criptografia
4. **Backup:** Faça backup regular do `clientes.json`

## 🔧 Customização

### Mudar cores das tabelas
Edite em `streamlit_app.py`, função `style_dataframe()`:
```python
cores = {
    "soja": {"header": "#2E7D32", "row1": "#E8F5E9", "row2": "#F1F8E9"},
    "milho": {"header": "#F57C00", "row1": "#FFF3E0", "row2": "#FFECB3"}
}
```

### Adicionar novos inputs
No `streamlit_app.py`, adicione na sidebar:
```python
novo_parametro = st.sidebar.number_input(
    "Novo Parâmetro:",
    value=100.0
)
```

E passe para o cálculo:
```python
df_soja, df_milho = ppe_engine.calcular_ppe(
    fobbings=fobbings,
    frete_dom=frete_dom,
    novo_parametro=novo_parametro  # adicione aqui
)
```

### Mudar número de meses exibidos
Em `ppe_engine.py`, linha do `generate_month_grid`:
```python
month_grid = generate_month_grid(start_year, start_month, horizon=10)  # mude 10
```

## 🐛 Troubleshooting

**Erro de autenticação:**
- Verifique se `clientes.json` existe e está bem formatado
- Confirme que a senha está correta

**Dados não aparecem:**
- Clique em "Recalcular PPE" na primeira vez
- Verifique se os arquivos Excel foram gerados em `outputs/`

**Erro ao buscar cotações:**
- Confirme credenciais do Trading View em `configs/.env`
- Verifique conexão com internet

**Erro Google Sheets:**
- Confirme que `secrets/gsheets-key.json` existe
- Verifique se o email do service account tem permissão na planilha

## 📝 Notas de Desenvolvimento

- `ppe_engine.py` é uma cópia modularizada do `PPE_completo.py`
- Mantive `PPE_completo.py` intacto para não quebrar workflows existentes
- O Streamlit usa `ppe_engine.py` para não duplicar lógica
- Cada cliente tem sua pasta isolada em `outputs/`