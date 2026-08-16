import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
from io import BytesIO
from zoneinfo import ZoneInfo
import unicodedata
import re

# ============================================================
# CONFIGURAÇÃO DA PÁGINA
# ============================================================
st.set_page_config(page_title="Dashboard Coordenador - Batalha Naval", page_icon="📊", layout="wide")

st.markdown("""
<style>
    a[href*="/edit"] { display: none !important; }
    div.stButton > button { width: 100%; height: 3.2rem; font-size: 14px; }
</style>
""", unsafe_allow_html=True)

# [CÓDIGO DE CARGA DE DADOS MANTIDO IGUAL AO ANTERIOR PARA ECONOMIZAR ESPAÇO]
# ... (Funções de load_data, aplicar_filtros, calcular_janela_movel permanecem idênticas) ...
# Assumindo que você já tem o load_data e filtros definidos no seu ambiente.

# --- [INSERIR AQUI O CÓDIGO DE CARGA E FILTROS DO SEU SCRIPT ANTERIOR] ---

# ============================================================
# PÁGINAS CORRIGIDAS
# ============================================================

# 🟢 PÁGINA: SOFTYS FALCON
if opcao == "🟢 Softys Falcon":
    df_softys = df_relatorio_base[df_relatorio_base['Nome_Fabricante'] == 'SOFTYS FALCON'].copy()
    if not df_softys.empty:
        st.subheader("🟢 Foco Estratégico: Softys Falcon")
        
        # Lógica de cálculo YTD
        ano_atual = df_softys['Ano'].max()
        df_softys_ano = df_softys[df_softys['Ano'] == ano_atual]
        
        pivot_mensal = df_softys_ano.pivot_table(index='Categoria', columns='Mes_Ano', values='codigo_cliente', aggfunc='nunique', fill_value=0)
        ytd_series = df_softys_ano.groupby('Categoria')['codigo_cliente'].nunique()
        
        tabela = pivot_mensal.copy()
        tabela['YTD'] = ytd_series.fillna(0) # Força a coluna YTD
        tabela = tabela.reset_index()

        st.markdown("**Positivação por Categoria (Mensal + YTD)**")
        st.dataframe(tabela, use_container_width=True, hide_index=True)
    else:
        st.warning("Sem dados.")

# 🟠 PÁGINA: KENVUE PERFUMARIA
elif opcao == "🟠 Kenvue Perfumaria":
    # ... (lógica de filtro kenvue igual)
    if not df_kenvue_mes.empty:
        pct_atendido = (atendidos / total_perfumarias_ativas * 100) if total_perfumarias_ativas > 0 else 0
        
        st.subheader("🟠 Foco Estratégico: Kenvue no Canal Perfumaria")
        # Visual de Meta (50%)
        st.metric("Perfumarias Ativas", total_perfumarias_ativas)
        st.metric("Atendidas com Kenvue", f"{atendidos} ({pct_atendido:.1f}%)", 
                  delta=f"{pct_atendido - 50:.1f}% vs Meta 50%", 
                  delta_color="normal" if pct_atendido >= 50 else "inverse")

# 🟤 PÁGINA: CENOURA & BRONZE
elif opcao == "🟤 Cenoura & Bronze":
    df_cenoura = df_relatorio_base[df_relatorio_base['Linha_Produto'] == 'CENOURA & BRONZE'].copy()
    if not df_cenoura.empty:
        st.subheader("🟤 Foco Estratégico: Linha Cenoura & Bronze")
        
        # Gráfico Principal
        df_evolucao = df_cenoura.groupby('Mes_Ano')['codigo_cliente'].nunique().reset_index()
        fig_cenoura = go.Figure(go.Bar(
            x=df_evolucao['Mes_Ano'], y=df_evolucao['codigo_cliente'], 
            marker_color='#CD853F', text=df_evolucao['codigo_cliente'], textposition='outside'
        ))
        fig_cenoura.update_layout(title='Evolução de Clientes', yaxis_title='Qtd Clientes')
        st.plotly_chart(fig_cenoura, use_container_width=True)

        # Tabela expansível
        with st.expander("Ver Tabela Detalhada"):
            st.dataframe(df_evolucao, use_container_width=True, hide_index=True)
    else:
        st.warning("Nenhum dado.")

# ============================================================
# [RESTANTE DO CÓDIGO PERMANECE IGUAL]
# ============================================================
