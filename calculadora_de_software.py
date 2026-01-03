# =========================
# IMPORTS
# =========================
import os
import io
import pandas as pd
import plotly.express as px
import streamlit as st

from dotenv import load_dotenv
from google import genai
from google.genai.errors import APIError

# =========================
# CONFIGURAÇÃO INICIAL
# =========================
st.set_page_config(
    page_title="Gestão Financeira IA",
    layout="wide"
)

st.title("💰 App de Gestão Financeira com IA Gemini")

# =========================
# CARREGAR .ENV
# =========================
load_dotenv()

API_KEY = os.getenv("GEMINI_API_KEY")

if not API_KEY:
    st.error("❌ Variável GEMINI_API_KEY não encontrada no arquivo .env")
    st.stop()

# =========================
# INICIALIZAÇÃO GEMINI
# =========================
try:
    client = genai.Client(api_key=API_KEY)
    MODEL_NAME = "gemini-2.0-flash"
except Exception as e:
    st.error(f"Erro ao inicializar o Gemini: {e}")
    st.stop()

# =========================
# FUNÇÕES
# =========================
@st.cache_data
def processar_upload(uploaded_file):
    """Lê CSV ou Excel e retorna DataFrame padronizado"""
    try:
        if uploaded_file.name.endswith(".csv"):
            df = pd.read_csv(uploaded_file)
        elif uploaded_file.name.endswith((".xlsx", ".xls")):
            df = pd.read_excel(uploaded_file)
        else:
            return pd.DataFrame()

        df = df.rename(columns={
            "Descrição": "Nome",
            "Valor": "Valor",
            "Tipo": "Categoria"
        })

        if "Nome" not in df.columns or "Valor" not in df.columns:
            return pd.DataFrame()

        if "Categoria" not in df.columns:
            df["Categoria"] = "Outros"

        df = df[["Nome", "Valor", "Categoria"]]
        df["Valor"] = pd.to_numeric(df["Valor"], errors="coerce")
        df = df.dropna(subset=["Nome", "Valor"])

        return df

    except Exception:
        return pd.DataFrame()


def converter_para_excel(df):
    """Converte DataFrame para Excel em memória"""
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        df.to_excel(writer, index=False, sheet_name="Despesas")
    return output.getvalue()

# =========================
# SESSION STATE
# =========================
if "despesas" not in st.session_state:
    st.session_state.despesas = []

# =========================
# SIDEBAR
# =========================
st.sidebar.header("⚙️ Configurações")

renda_mensal = st.sidebar.number_input(
    "Renda Mensal (R$)",
    min_value=0.0,
    value=5000.0
)

st.sidebar.subheader("📤 Importar Dados")
arquivo = st.sidebar.file_uploader(
    "Enviar CSV ou Excel",
    type=["csv", "xlsx", "xls"]
)

if arquivo:
    df_importado = processar_upload(arquivo)
    if not df_importado.empty:
        st.session_state.despesas.extend(df_importado.to_dict("records"))
        st.sidebar.success("Dados importados com sucesso!")

with st.sidebar.form("form_manual", clear_on_submit=True):
    st.subheader("➕ Lançamento Manual")
    nome = st.text_input("Nome da despesa")
    valor = st.number_input("Valor (R$)", min_value=0.0)
    categoria = st.selectbox(
        "Categoria",
        [
            "Alimentação",
            "Moradia",
            "Transporte",
            "Lazer",
            "Saúde",
            "Investimento",
            "Outros"
        ]
    )

    if st.form_submit_button("Adicionar"):
        if nome and valor > 0:
            st.session_state.despesas.append({
                "Nome": nome,
                "Valor": valor,
                "Categoria": categoria
            })

# =========================
# DASHBOARD
# =========================
df_despesas = pd.DataFrame(st.session_state.despesas)

total_gastos = df_despesas["Valor"].sum() if not df_despesas.empty else 0
saldo = renda_mensal - total_gastos

c1, c2, c3 = st.columns(3)
c1.metric("💼 Renda", f"R$ {renda_mensal:,.2f}")
c2.metric("💸 Gastos", f"R$ {total_gastos:,.2f}")
c3.metric("💰 Saldo", f"R$ {saldo:,.2f}", delta=saldo)

if not df_despesas.empty:
    col_grafico, col_acoes = st.columns([2, 1])

    with col_grafico:
        fig = px.pie(
            df_despesas,
            values="Valor",
            names="Categoria",
            title="Gastos por Categoria"
        )
        st.plotly_chart(fig, use_container_width=True)

    with col_acoes:
        st.subheader("📥 Ações")
        st.download_button(
            "Baixar Excel",
            data=converter_para_excel(df_despesas),
            file_name="controle_financeiro.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

        if st.button("🗑️ Limpar Tudo"):
            st.session_state.despesas = []
            st.rerun()

    st.subheader("📋 Detalhamento")
    st.dataframe(df_despesas, use_container_width=True)

# =========================
# IA GEMINI
# =========================
st.divider()
st.subheader("🤖 Análise Inteligente")

if st.button("✨ Gerar Insights com IA"):
    if df_despesas.empty:
        st.warning("Adicione despesas antes de gerar insights.")
    else:
        with st.spinner("Analisando seus dados financeiros..."):
            try:
                prompt = f"""
                Renda mensal: R$ {renda_mensal}
                Total de gastos: R$ {total_gastos}
                Saldo: R$ {saldo}

                Despesas:
                {df_despesas.to_string(index=False)}

                Gere 4 dicas financeiras curtas, práticas e objetivas.
                """

                response = client.models.generate_content(
                    model=MODEL_NAME,
                    contents=prompt
                )

                st.success("Insights gerados:")
                st.write(response.text)

            except APIError as e:
                st.error(f"Erro na API Gemini: {e}")
            except Exception as e:
                st.error(f"Erro inesperado: {e}")

