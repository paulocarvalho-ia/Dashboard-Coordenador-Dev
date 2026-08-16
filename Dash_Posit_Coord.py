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
# 1. CONFIGURAÇÃO DA PÁGINA E ESTILO
# ============================================================
st.set_page_config(
    page_title="Dashboard Coordenador - Batalha Naval",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Esconder elementos desnecessários e estilizar métricas
st.markdown("""
<style>
    a[href*="/edit"], a[href*="github.com"] { display: none !important; }
    .stMetric { background-color: #f8f9fa; padding: 15px; border-radius: 10px; border: 1px solid #e0e0e0; }
    div[data-testid="stExpander"] { border: 1px solid #e0e0e0; border-radius: 10px; }
</style>
""", unsafe_allow_html=True)

# ============================================================
# 2. CARREGAMENTO E NORMALIZAÇÃO DE DADOS
# ============================================================
SHEET_ID = "100LtVtmS76bT2CJd-EIb-bHTgX3F1BVm8Er5vUa-VYQ"

@st.cache_data(ttl=300)
def load_data():
    url_base = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv&sheet="
    try:
        df_base = pd.read_csv(url_base + "BASE")
        df_bi = pd.read_csv(url_base + "BI_Teste")
        df_fabricantes = pd.read_csv(url_base + "FABRICANTE")
        df_vendedores = pd.read_csv(url_base + "VENDEDORES")
    except Exception as e:
        st.error(f"Erro ao carregar dados: {e}"); st.stop()

    def normalizar_texto(texto):
        if not isinstance(texto, str): return ""
        texto = unicodedata.normalize('NFKD', texto).encode('ASCII', 'ignore').decode('ASCII')
        return re.sub(r'\s+', ' ', texto.lower().strip())

    # Normalização DF_BASE
    df_base.columns = [str(col).strip() for col in df_base.columns]
    base_rename = {}
    for col in df_base.columns:
        c = normalizar_texto(col)
        if 'codigo cliente' in c: base_rename[col] = 'codigo_cliente'
        elif c == 'cliente' or ('cliente' in c and 'nome' in c): base_rename[col] = 'nome_cliente'
        elif 'vendedor' in c: base_rename[col] = 'nome_vendedor_base'
        elif 'coligacao' in c or 'coliga' in c: base_rename[col] = 'Cliente_Coligacao'
        elif 'coordenador' in c: base_rename[col] = 'Nome_Coordenador'
        elif 'municipio' in c: base_rename[col] = 'Municipio'
        elif 'canal' in c: base_rename[col] = 'Canal'
        elif 'segmento' in c: base_rename[col] = 'Segmento'
    df_base = df_base.rename(columns=base_rename)

    # Normalização DF_BI
    df_bi.columns = [str(col).strip() for col in df_bi.columns]
    bi_rename = {}
    for col in df_bi.columns:
        c = normalizar_texto(col)
        if 'codigo cliente' in c: bi_rename[col] = 'codigo_cliente'
        elif 'vendedor' in c and 'ajustado' in c: bi_rename[col] = 'nome_vendedor_bi'
        elif 'ano' in c and 'mes' in c: bi_rename[col] = 'Ano_e_Mes'
        elif 'fabricante' in c: bi_rename[col] = 'Nome_Fabricante'
        elif 'linha de produto' in c: bi_rename[col] = 'Linha_Produto'
        elif 'categoria' in c: bi_rename[col] = 'Categoria'
        elif 'valor das vendas' in c: bi_rename[col] = 'Valor_Vendas'
    df_bi = df_bi.rename(columns=bi_rename)

    # Processar Datas
    df_bi['Data'] = pd.to_datetime(df_bi['Ano_e_Mes'] + '-01', errors='coerce')
    df_bi['MŒs'] = df_bi['Data'].dt.month
    df_bi['Ano'] = df_bi['Data'].dt.year
    df_bi['MŒs_Ano'] = df_bi['Data'].dt.to_period('M').astype(str)

    # Merge
    df_base_dedup = df_base.drop_duplicates(subset=['codigo_cliente'], keep='first')
    df_merged = df_bi.merge(
        df_base_dedup[['codigo_cliente', 'nome_cliente', 'nome_vendedor_base', 'Cliente_Coligacao', 
                       'Nome_Coordenador', 'Municipio', 'Canal', 'Segmento']],
        left_on=['codigo_cliente', 'nome_vendedor_bi'],
        right_on=['codigo_cliente', 'nome_vendedor_base'],
        how='left'
    )

    # Fallback Map
    for col in ['nome_cliente', 'Cliente_Coligacao', 'Nome_Coordenador', 'Municipio', 'Canal', 'Segmento']:
        f_map = df_base_dedup.set_index('codigo_cliente')[col].to_dict()
        df_merged[col] = df_merged[col].fillna(df_merged['codigo_cliente'].map(f_map))

    df_merged['nome_vendedor'] = df_merged['nome_vendedor_bi']
    fab_pasta = dict(zip(df_fabricantes['Nome Fabricante'], df_fabricantes['Pasta']))
    vend_pasta = dict(zip(df_vendedores['Vendedor'], df_vendedores['Pasta']))
    
    return df_base, df_bi, df_merged, fab_pasta, vend_pasta

df_base, df_bi, df_merged, fab_pasta, vend_pasta = load_data()
TODAS_IND = sorted([i for i in df_bi['Nome_Fabricante'].dropna().unique() if str(i).strip() != ''])

# ============================================================
# 3. FUNÇÕES DE APOIO (LÓGICA MANTIDA)
# ============================================================
def aplicar_filtros_comuns(df, incluir_mes=True):
    dff = df.copy()
    if pasta_selecionada not in ["Todas", "PVA"]:
        v_pasta = [v for v in df_base['nome_vendedor_base'].unique() if vend_pasta.get(v) == pasta_selecionada]
        dff = dff[dff['nome_vendedor'].isin(v_pasta)]
    if vendedor_selecionado != "Todos": dff = dff[dff['nome_vendedor'] == vendedor_selecionado]
    if coordenador_selecionado != "Todos": dff = dff[dff['Nome_Coordenador'] == coordenador_selecionado]
    if coligacao_selecionada != "Todas": dff = dff[dff['Cliente_Coligacao'] == coligacao_selecionada]
    if municipio_selecionado: dff = dff[dff['Municipio'].isin(municipio_selecionado)]
    if canal_selecionado: dff = dff[dff['Canal'].isin(canal_selecionado)]
    if segmento_selecionado: dff = dff[dff['Segmento'].isin(segmento_selecionado)]
    
    if incluir_mes and mes_selecionado != "Todos":
        m_num = int(mes_selecionado.split(' - ')[0])
        ano_r = dff[dff['MŒs'] == m_num]['Ano'].max() if not dff[dff['MŒs'] == m_num].empty else dff['Ano'].max()
        dff = dff[dff['MŒs_Ano'] == f"{ano_r}-{m_num:02d}"]
        
    if ind_sel_lista: dff = dff[dff['Nome_Fabricante'].isin(ind_sel_lista)]
    if cat_sel: dff = dff[dff['Categoria'].isin(cat_sel)]
    if lin_sel: dff = dff[dff['Linha_Produto'].isin(lin_sel)]
    return dff

def calcular_janela_movel(df_h, mes_sel, janela):
    if mes_sel == "Todos": return df_h.copy()
    m_num = int(mes_sel.split(' - ')[0])
    ano_r = df_h[df_h['MŒs'] == m_num]['Ano'].max() if not df_h[df_h['MŒs'] == m_num].empty else df_h['Ano'].max()
    datas_j = []
    for i in range(1, janela + 1):
        m, a = m_num - i, ano_r
        while m <= 0: m += 12; a -= 1
        datas_j.append(f"{a}-{m:02d}")
    return df_h[df_h['MŒs_Ano'].isin(datas_j)]

def download_excel(df, label, filename):
    out = BytesIO()
    with pd.ExcelWriter(out, engine='openpyxl') as w: df.to_excel(w, index=False)
    st.download_button(label, out.getvalue(), f"{filename}.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

# ============================================================
# 4. FILTROS DA INTERFACE
# ============================================================
with st.expander("🎯 Painel de Filtros", expanded=True):
    c1, c2, c3 = st.columns(3)
    coordenador_selecionado = c1.selectbox("Coordenador", ["Todos"] + sorted(df_base['Nome_Coordenador'].dropna().unique().tolist()))
    v_base = df_base[df_base['Nome_Coordenador'] == coordenador_selecionado]['nome_vendedor_base'].unique() if coordenador_selecionado != "Todos" else df_base['nome_vendedor_base'].unique()
    vendedor_selecionado = c2.selectbox("Vendedor", ["Todos"] + sorted(v_base))
    pasta_selecionada = c3.selectbox("Pasta", ["Todas", "PA", "PV", "PVA"])

    c4, c5, c6 = st.columns(3)
    ind_disp = TODAS_IND if pasta_selecionada in ["Todas", "PVA"] else [i for i in TODAS_IND if fab_pasta.get(i) == pasta_selecionada]
    ind_sel_lista = c4.multiselect("Indústria(s)", options=ind_disp)
    cat_sel = c5.multiselect("Categoria(s)", options=sorted(df_bi['Categoria'].dropna().unique()))
    lin_sel = c6.multiselect("Linha(s)", options=sorted(df_bi['Linha_Produto'].dropna().unique()))

    c7, c8, c9, c10 = st.columns(4)
    m_nomes = {1:'Janeiro', 2:'Fevereiro', 3:'Março', 4:'Abril', 5:'Maio', 6:'Junho', 7:'Julho', 8:'Agosto', 9:'Setembro', 10:'Outubro', 11:'Novembro', 12:'Dezembro'}
    m_disp = sorted(df_merged['MŒs'].dropna().unique())
    l_meses = ["Todos"] + [f"{int(m):02d} - {m_nomes.get(int(m))}" for m in m_disp]
    mes_selecionado = c7.selectbox("Mês", l_meses, index=len(l_meses)-1)
    janela_meses = c8.slider("Janela Ativa (meses)", 3, 6, 6)
    meta_ativa = c9.number_input("Meta Ativa %", 0, 100, 70)
    meta_total = c10.number_input("Meta Carteira %", 0, 100, 50)

    c11, c12, c13 = st.columns(3)
    coligacao_selecionada = c11.selectbox("Coligação", ["Todas"] + sorted(df_base['Cliente_Coligacao'].dropna().unique()))
    canal_selecionado = c12.multiselect("Canais", sorted(df_base['Canal'].dropna().unique()))
    municipio_selecionado = c13.multiselect("Municípios", sorted(df_base['Municipio'].dropna().unique()))
    segmento_selecionado = None # Para brevidade, mas segue a mesma lógica se quiser adicionar

# Aplicação dos Filtros
df_filtrado = aplicar_filtros_comuns(df_merged, incluir_mes=True)
df_historico = aplicar_filtros_comuns(df_merged, incluir_mes=False)
df_historico_janela = calcular_janela_movel(df_historico, mes_selecionado, janela_meses)

# ============================================================
# 5. NAVEGAÇÃO
# ============================================================
st.markdown("---")
paginas = ["🏠 Visão Geral", "👥 Performance", "📋 Batalha Naval", "🟢 Softys Falcon", "🟠 Kenvue Perfumaria", "🔍 Ficha Cliente"]
opcao = st.radio("Selecione a página:", paginas, horizontal=True)

# ============================================================
# PÁGINA: VISÃO GERAL
# ============================================================
if opcao == "🏠 Visão Geral":
    c_ativos = df_historico_janela['codigo_cliente'].nunique()
    c_pos = df_filtrado['codigo_cliente'].nunique()
    
    st.subheader("📊 Resumo de Positivação")
    m1, m2, m3 = st.columns(3)
    m1.metric(f"Carteira Ativa ({janela_meses}m)", c_ativos)
    m2.metric("Positivados no Mês", c_pos)
    m3.metric("% Positivação Ativa", f"{(c_pos/c_ativos*100 if c_ativos > 0 else 0):.1f}%")

    # --- LÓGICA GRÁFICO MENSAL + YTD ---
    if mes_selecionado != "Todos":
        m_ref = int(mes_selecionado.split(' - ')[0])
        ano_ref = df_historico[df_historico['MŒs'] == m_ref]['Ano'].max()
    else:
        ano_ref = df_historico['Ano'].max()
        m_ref = 12

    df_ano = df_historico[df_historico['Ano'] == ano_ref]
    # Mensal
    mensal = df_ano.groupby(['MŒs', 'MŒs_Ano'])['codigo_cliente'].nunique().reset_index()
    mensal.columns = ['Num', 'Mês', 'Clientes']
    mensal = mensal.sort_values('Num')
    
    # YTD (Acumulado do ano até o mês de referência)
    ytd_count = df_ano[df_ano['MŒs'] <= m_ref]['codigo_cliente'].nunique()

    # Preparar Dados do Gráfico
    labels = list(mensal['Mês']) + [f"YTD {ano_ref}"]
    valores = list(mensal['Clientes']) + [ytd_count]
    cores = ['#2E8B57'] * len(mensal) + ['#EF8633'] # Verde para meses, Laranja para YTD

    fig = go.Figure(go.Bar(
        x=labels, y=valores,
        marker_color=cores,
        text=valores, textposition='auto'
    ))
    fig.update_layout(title=f"Positivação Mensal vs Acumulado YTD ({ano_ref})", xaxis_title="Período", yaxis_title="Clientes")
    st.plotly_chart(fig, use_container_width=True)

    # Carteira Total
    st.markdown("---")
    st.subheader("📋 Carteira Total")
    # Lógica de cálculo da carteira total simplificada (baseada na sua original)
    total_base = df_base['codigo_cliente'].nunique()
    st.columns(3)[0].metric("Total Carteira", total_base)

# ============================================================
# PÁGINA: PERFORMANCE VENDEDOR
# ============================================================
elif opcao == "👥 Performance":
    vends = df_filtrado['nome_vendedor'].dropna().unique()
    perf = []
    for v in vends:
        c_cart = df_base[df_base['nome_vendedor_base'] == v]['codigo_cliente'].nunique()
        c_ativa = df_historico_janela[df_historico_janela['nome_vendedor'] == v]['codigo_cliente'].nunique()
        c_pos = df_filtrado[df_filtrado['nome_vendedor'] == v]['codigo_cliente'].nunique()
        perf.append({
            "Vendedor": v, "Carteira": c_cart, "Ativos": c_ativa, "Positivados": c_pos,
            "% Ativa": round((c_pos/c_ativa*100 if c_ativa > 0 else 0), 1)
        })
    df_perf = pd.DataFrame(perf).sort_values("% Ativa", ascending=False)
    st.dataframe(df_perf, use_container_width=True, hide_index=True)
    download_excel(df_perf, "📥 Baixar Performance", "performance_vendedores")

# ============================================================
# PÁGINA: BATALHA NAVAL
# ============================================================
elif opcao == "📋 Batalha Naval":
    st.subheader("Matriz de Cobertura")
    matriz = df_filtrado.pivot_table(index=['codigo_cliente', 'nome_cliente'], columns='Nome_Fabricante', aggfunc='size', fill_value=0)
    matriz_bin = (matriz > 0).astype(int).reset_index()
    
    # Estilização
    def style_bn(val):
        if isinstance(val, int):
            return 'background-color: #c6efce; color: #006100' if val == 1 else 'background-color: #ffc7ce; color: #9c0006'
        return ''

    cols_fab = matriz_bin.columns[2:]
    st.dataframe(matriz_bin.style.applymap(style_bn, subset=cols_fab), use_container_width=True)
    download_excel(matriz_bin, "📥 Baixar Batalha Naval", "batalha_naval")

# ============================================================
# PÁGINA: SOFTYS FALCON
# ============================================================
elif opcao == "🟢 Softys Falcon":
    df_s = df_historico[df_historico['Nome_Fabricante'] == 'SOFTYS FALCON']
    if not df_s.empty:
        st.subheader("🟢 Foco Estratégico: Softys Falcon")
        resumo = df_s.groupby('Categoria')['codigo_cliente'].nunique().reset_index()
        st.dataframe(resumo, use_container_width=True)
        download_excel(df_s, "📥 Baixar Dados Softys", "softys_falcon")
    else:
        st.warning("Sem dados Softys para os filtros atuais.")

# ============================================================
# PÁGINA: KENVUE PERFUMARIA
# ============================================================
elif opcao == "🟠 Kenvue Perfumaria":
    df_k = df_filtrado[(df_filtrado['Nome_Fabricante'] == 'KENVUE') & (df_filtrado['Canal'] == 'PERFUMARIA')]
    st.subheader("🟠 Kenvue no Canal Perfumaria")
    st.metric("Clientes Atendidos", df_k['codigo_cliente'].nunique())
    st.dataframe(df_k[['codigo_cliente', 'nome_cliente', 'Municipio', 'nome_vendedor']].drop_duplicates(), use_container_width=True)

# ============================================================
# PÁGINA: FICHA CLIENTE
# ============================================================
elif opcao == "🔍 Ficha Cliente":
    busca = st.text_input("Busque por Nome ou Código do Cliente")
    if busca:
        mask = (df_base['nome_cliente'].str.contains(busca, case=False, na=False)) | (df_base['codigo_cliente'].astype(str).str.contains(busca))
        match = df_base[mask]
        if not match.empty:
            st.dataframe(match)
            c_id = match.iloc[0]['codigo_cliente']
            hist = df_merged[df_merged['codigo_cliente'] == c_id]
            st.write("### Histórico de Compras")
            st.dataframe(hist[['MŒs_Ano', 'Nome_Fabricante', 'Valor_Vendas']].sort_values('MŒs_Ano', ascending=False))
        else:
            st.error("Cliente não encontrado.")

st.markdown("---")
st.caption(f"Gerado em: {datetime.now(ZoneInfo('America/Sao_Paulo')).strftime('%d/%m/%Y %H:%M')}")
