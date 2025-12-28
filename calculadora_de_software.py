import streamlit as st
import pandas as pd
import io
import plotly.express as px  # Adicionado para os gráficos
from google import genai
from google.genai.errors import APIError

# --- 1. CONFIGURAÇÃO DA CHAVE E CLIENTE GEMINI ---
try:
    # Tenta carregar a chave do arquivo .streamlit/secrets.toml ou Configurações do Cloud
    api_key = st.secrets["GEMINI_API_KEY"]
except KeyError:
    st.error("Erro: A chave 'GEMINI_API_KEY' não encontrada. Configure-a no Streamlit Secrets.")
    st.stop()

try:
    # Inicializa o cliente - Versão correta do SDK google-genai
    client = genai.Client(api_key=api_key)
    # Ajustado para uma versão existente (2.0 ou 1.5)
    MODEL_NAME = 'gemini-2.0-flash' 
except Exception as e:
    st.error(f"Erro ao inicializar o cliente Gemini: {e}")
    st.stop()

# --- FUNÇÕES ---

@st.cache_data
def processar_upload(uploaded_file):
    """Lê o arquivo CSV ou Excel e retorna um DataFrame."""
    try:
        if uploaded_file.name.endswith('.csv'):
            df = pd.read_csv(uploaded_file)
        elif uploaded_file.name.endswith(('.xlsx', '.xls')):
            df = pd.read_excel(uploaded_file)
        else:
            st.error("Formato de arquivo não suportado.")
            return pd.DataFrame()

        # Padronização de colunas
        df = df.rename(columns={
            'Descrição': 'Nome',
            'Valor': 'Valor',
            'Tipo': 'Categoria'
        })

        if 'Nome' in df.columns and 'Valor' in df.columns:
            df = df[['Nome', 'Valor', 'Categoria' if 'Categoria' in df.columns else 'Outros']].dropna(subset=['Nome', 'Valor'])
            df['Valor'] = pd.to_numeric(df['Valor'], errors='coerce')
            return df
        return pd.DataFrame()
    except Exception as e:
        st.error(f"Erro ao processar o arquivo: {e}")
        return pd.DataFrame()

def convert_df_to_excel(df):
    """Converte o DataFrame para Excel em memória."""
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Lançamentos')
    return output.getvalue()

# --- INTERFACE ---
st.set_page_config(page_title="Gestão Financeira IA", layout="wide")
st.title("💰 App de Gestão Financeira com IA Gemini")

if 'despesas' not in st.session_state:
    st.session_state.despesas = []

# --- BARRA LATERAL ---
st.sidebar.header("Configurações")
renda_mensal = st.sidebar.number_input("Renda Mensal (R$):", min_value=0.0, value=5000.0)

st.sidebar.subheader("Importar Dados")
uploaded_file = st.sidebar.file_uploader("Subir Excel/CSV", type=['csv', 'xlsx'])

if uploaded_file:
    df_upload = processar_upload(uploaded_file)
    if not df_upload.empty:
        st.session_state.despesas.extend(df_upload.to_dict('records'))
        st.sidebar.success("Dados importados!")

with st.sidebar.form("manual_form", clear_on_submit=True):
    st.subheader("Lançamento Manual")
    n = st.text_input("Nome:")
    v = st.number_input("Valor:", min_value=0.0)
    c = st.selectbox("Categoria:", ["Alimentação", "Moradia", "Transporte", "Lazer", "Saúde", "Investimento", "Outros"])
    if st.form_submit_button("Adicionar") and n and v > 0:
        st.session_state.despesas.append({'Nome': n, 'Valor': v, 'Categoria': c})

# --- DASHBOARD ---
df_despesas = pd.DataFrame(st.session_state.despesas)
total_gastos = df_despesas['Valor'].sum() if not df_despesas.empty else 0
saldo = renda_mensal - total_gastos

c1, c2, c3 = st.columns(3)
c1.metric("Renda", f"R$ {renda_mensal:.2f}")
c2.metric("Gastos", f"R$ {total_gastos:.2f}")
c3.metric("Saldo", f"R$ {saldo:.2f}", delta=float(saldo))

if not df_despesas.empty:
    col_chart, col_actions = st.columns([2, 1])
    
    with col_chart:
        fig = px.pie(df_despesas, values='Valor', names='Categoria', title="Gastos por Categoria")
        st.plotly_chart(fig, use_container_width=True)
    
    with col_actions:
        st.write("### Ações")
        st.download_button("📥 Baixar Excel", data=convert_df_to_excel(df_despesas), 
                           file_name="financeiro.xlsx", mime="application/vnd.ms-excel")
        if st.button("🗑️ Limpar Tudo"):
            st.session_state.despesas = []
            st.rerun()

    st.subheader("Detalhamento")
    st.table(df_despesas)

# --- IA GEMINI ---
st.divider()
if st.button("✨ Gerar Insights com IA"):
    if df_despesas.empty:
        st.warning("Adicione dados primeiro.")
    else:
        with st.spinner("Analisando..."):
            try:
                prompt = f"Renda: {renda_mensal}. Gastos: {total_gastos}. Saldo: {saldo}. Detalhes: {df_despesas.to_string()}. Dê 4 dicas financeiras curtas."
                response = client.models.generate_content(model=MODEL_NAME, contents=prompt)
                st.info(response.text)
            except Exception as e:
                st.error(f"Erro na IA: {e}")
