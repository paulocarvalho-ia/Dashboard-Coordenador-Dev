import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import numpy as np
from datetime import datetime
from io import BytesIO
from zoneinfo import ZoneInfo

# ============================================================
# CONFIGURAÇÃO DA PÁGINA
# ============================================================
st.set_page_config(
    page_title="Dashboard Coordenador (Teste) - Batalha Naval",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
    a[href*="/edit"] { display: none !important; }
    a[href*="github.com"] { display: none !important; }
</style>
""", unsafe_allow_html=True)

st.title("📊 Dashboard de Positivação e Cobertura (Teste)")
st.caption("4 Elos Distribuidora Ltda. - Centro de Custo 622")

# ============================================================
# CONEXÃO COM GOOGLE SHEETS (BASE produção + BI_Teste)
# ============================================================
SHEET_ID = "100LtVtmS76bT2CJd-EIb-bHTgX3F1BVm8Er5vUa-VYQ"

@st.cache_data(ttl=300)
def load_data():
    url_base = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv&sheet="

    df_base = pd.read_csv(url_base + "BASE")
    df_bi   = pd.read_csv(url_base + "BI_Teste")
    df_fabricantes = pd.read_csv(url_base + "FABRICANTE")
    df_vendedores  = pd.read_csv(url_base + "VENDEDORES")

    data_dados = datetime.now(ZoneInfo('America/Sao_Paulo')).strftime('%d/%m/%Y %H:%M')

    # Normalizar nomes de colunas da BASE
    df_base.columns = [str(col).strip() for col in df_base.columns]

    df_base = df_base.rename(columns={
        'Código Cliente': 'codigo_cliente',
        'Cliente': 'nome_cliente',
        'Vendedor': 'nome_vendedor_base',
        'Coligação': 'Cliente_Coligacao',
        'Coordenador': 'Nome_Coordenador',
        'Municipio': 'Municipio',
        'Canal': 'Canal',
        'Segmento': 'Segmento'
    })

    # Normalizar nomes de colunas da BI_Teste
    df_bi.columns = [str(col).strip().lower() for col in df_bi.columns]

    bi_rename = {}
    for col in df_bi.columns:
        if 'código cliente' in col or 'codigo cliente' in col:
            bi_rename[col] = 'codigo_cliente'
        elif 'vendedor' in col and 'ajustado' in col:
            bi_rename[col] = 'nome_vendedor_bi'
        elif 'ano e mês' in col or 'ano e mes' in col:
            bi_rename[col] = 'Ano_e_Mes'
        elif 'fabricante' in col:
            bi_rename[col] = 'Nome_Fabricante'
        elif 'linha de produto' in col:
            bi_rename[col] = 'Linha_Produto'
        elif 'categoria' in col:
            bi_rename[col] = 'Categoria'
        elif 'valor das vendas' in col:
            bi_rename[col] = 'Valor_Vendas'

    df_bi = df_bi.rename(columns=bi_rename)

    # Datas
    df_bi['Data'] = pd.to_datetime(df_bi['Ano_e_Mes'] + '-01', errors='coerce')
    df_bi['Mês'] = df_bi['Data'].dt.month
    df_bi['Ano'] = df_bi['Data'].dt.year
    df_bi['Mês_Ano'] = df_bi['Data'].dt.to_period('M').astype(str)

    # Merge
    df_merged = df_bi.merge(
        df_base[['codigo_cliente', 'nome_cliente', 'nome_vendedor_base', 'Cliente_Coligacao', 'Nome_Coordenador',
                 'Municipio', 'Canal', 'Segmento']],
        left_on=['codigo_cliente', 'nome_vendedor_bi'],
        right_on=['codigo_cliente', 'nome_vendedor_base'],
        how='left'
    )
    df_fallback = df_bi.merge(
        df_base[['codigo_cliente', 'nome_cliente', 'nome_vendedor_base', 'Cliente_Coligacao', 'Nome_Coordenador',
                 'Municipio', 'Canal', 'Segmento']],
        on='codigo_cliente',
        how='left',
        suffixes=('', '_fb')
    )
    for col in ['nome_cliente', 'Cliente_Coligacao', 'Nome_Coordenador', 'Municipio', 'Canal', 'Segmento']:
        if col in df_merged.columns and f'{col}_fb' in df_fallback.columns:
            df_merged[col] = df_merged[col].fillna(df_fallback[f'{col}_fb'])

    df_merged['nome_vendedor'] = df_merged['nome_vendedor_bi']

    fabricante_pasta = dict(zip(df_fabricantes['Nome Fabricante'], df_fabricantes['Pasta']))
    vendedor_pasta = dict(zip(df_vendedores['Vendedor'], df_vendedores['Pasta']))

    return df_base, df_bi, df_merged, data_dados, fabricante_pasta, vendedor_pasta

# ============================================================
# BOTÃO ATUALIZAR DADOS AGORA
# ============================================================
if st.sidebar.button("🔄 Atualizar Dados Agora"):
    st.cache_data.clear()
    st.session_state.pop('mes', None)
    st.session_state.pop('ano', None)
    st.rerun()

df_base, df_bi, df_merged, data_dados, fabricante_pasta, vendedor_pasta = load_data()

TODAS_INDUSTRIAS = sorted(df_bi['Nome_Fabricante'].dropna().unique())
TODAS_INDUSTRIAS = [i for i in TODAS_INDUSTRIAS if i.strip() != '']

# ============================================================
# FILTROS
# ============================================================
st.sidebar.header("🎯 Filtros")

st.sidebar.markdown(
    """
    <form action="" method="get" style="margin-bottom: 10px;">
        <button type="submit" style="
            width: 100%; padding: 8px 12px; border-radius: 8px; 
            border: 1px solid #555; background-color: #333; color: #f0f0f0; 
            cursor: pointer; font-size: 14px; font-family: 'Source Sans Pro', sans-serif;
            display: flex; align-items: center; justify-content: center; gap: 8px;">
        🧹 Limpar Filtros
        </button>
    </form>
    """,
    unsafe_allow_html=True
)
if not st.query_params:
    for key in ['pasta', 'coordenador', 'vendedor', 'coligacao', 'ano', 'mes', 'industria_filtro', 'meta_ativa', 'meta_total', 'janela_meses',
                'municipio_filtro', 'canal_filtro', 'segmento_filtro', 'categoria_filtro', 'linha_filtro']:
        st.session_state.pop(key, None)

lista_pastas = ["Todas", "PA", "PV", "PVA"]
if 'pasta' not in st.session_state: st.session_state['pasta'] = 'Todas'
pasta_selecionada = st.sidebar.selectbox("Pasta", lista_pastas, index=lista_pastas.index(st.session_state['pasta']) if st.session_state['pasta'] in lista_pastas else 0, key='pasta_select')
st.session_state['pasta'] = pasta_selecionada

if pasta_selecionada in ["Todas", "PVA"]:
    INDUSTRIAS_PERMITIDAS = TODAS_INDUSTRIAS.copy()
else:
    INDUSTRIAS_PERMITIDAS = [ind for ind in TODAS_INDUSTRIAS if fabricante_pasta.get(ind) == pasta_selecionada]

lista_coordenadores = ["Todos"] + sorted(df_base['Nome_Coordenador'].dropna().unique().tolist())
if 'coordenador' not in st.session_state: st.session_state['coordenador'] = 'Todos'
coordenador_selecionado = st.sidebar.selectbox("Coordenador", lista_coordenadores, index=lista_coordenadores.index(st.session_state['coordenador']), key='coordenador_select')
st.session_state['coordenador'] = coordenador_selecionado

if coordenador_selecionado != "Todos":
    vendedores_base = df_base[df_base['Nome_Coordenador'] == coordenador_selecionado]['nome_vendedor_base'].dropna().unique()
else:
    vendedores_base = df_base['nome_vendedor_base'].dropna().unique()
if pasta_selecionada != "Todas":
    vendedores_base = [v for v in vendedores_base if vendedor_pasta.get(v) == pasta_selecionada]
lista_vendedores = ["Todos"] + sorted(vendedores_base)
if 'vendedor' not in st.session_state: st.session_state['vendedor'] = 'Todos'
vendedor_selecionado = st.sidebar.selectbox("Vendedor", lista_vendedores, index=lista_vendedores.index(st.session_state['vendedor']), key='vendedor_select')
st.session_state['vendedor'] = vendedor_selecionado

if vendedor_selecionado != "Todos":
    clientes_do_vendedor = df_base[df_base['nome_vendedor_base'] == vendedor_selecionado]['codigo_cliente'].unique()
    coligacoes_filtradas = df_base[df_base['codigo_cliente'].isin(clientes_do_vendedor)]['Cliente_Coligacao'].dropna().unique()
elif coordenador_selecionado != "Todos":
    vendedores_do_coord = df_base[df_base['Nome_Coordenador'] == coordenador_selecionado]['nome_vendedor_base'].unique()
    clientes_do_coord = df_base[df_base['nome_vendedor_base'].isin(vendedores_do_coord)]['codigo_cliente'].unique()
    coligacoes_filtradas = df_base[df_base['codigo_cliente'].isin(clientes_do_coord)]['Cliente_Coligacao'].dropna().unique()
else:
    coligacoes_filtradas = df_base['Cliente_Coligacao'].dropna().unique()
lista_coligacoes = ["Todas"] + sorted(coligacoes_filtradas)
if 'coligacao' not in st.session_state: st.session_state['coligacao'] = 'Todas'
coligacao_selecionada = st.sidebar.selectbox("Coligação", lista_coligacoes, index=lista_coligacoes.index(st.session_state['coligacao']), key='coligacao_select')
st.session_state['coligacao'] = coligacao_selecionada

if 'municipio_filtro' not in st.session_state: st.session_state['municipio_filtro'] = []
municipio_opcoes = sorted(df_base['Municipio'].dropna().unique())
municipio_selecionado = st.sidebar.multiselect("Município(s)", options=municipio_opcoes, default=st.session_state['municipio_filtro'], placeholder="Selecione...")
st.session_state['municipio_filtro'] = municipio_selecionado

if 'canal_filtro' not in st.session_state: st.session_state['canal_filtro'] = []
canal_opcoes = sorted(df_base['Canal'].dropna().unique())
canal_selecionado = st.sidebar.multiselect("Canal(is)", options=canal_opcoes, default=st.session_state['canal_filtro'], placeholder="Selecione...")
st.session_state['canal_filtro'] = canal_selecionado

if 'segmento_filtro' not in st.session_state: st.session_state['segmento_filtro'] = []
segmento_opcoes = sorted(df_base['Segmento'].dropna().unique())
segmento_selecionado = st.sidebar.multiselect("Segmento(s)", options=segmento_opcoes, default=st.session_state['segmento_filtro'], placeholder="Selecione...")
st.session_state['segmento_filtro'] = segmento_selecionado

anos_disponiveis = sorted(df_merged['Ano'].dropna().unique())
lista_anos = ["Todos"] + [str(int(a)) for a in anos_disponiveis]
if 'ano' not in st.session_state:
    st.session_state['ano'] = str(int(anos_disponiveis[-1])) if anos_disponiveis else 'Todos'
if st.session_state['ano'] not in lista_anos: st.session_state['ano'] = 'Todos'
ano_selecionado = st.sidebar.selectbox("Ano", lista_anos, index=lista_anos.index(st.session_state['ano']), key='ano_select')
st.session_state['ano'] = ano_selecionado

if ano_selecionado != "Todos":
    meses_disponiveis = sorted(df_merged[df_merged['Ano'] == int(ano_selecionado)]['Mês'].dropna().unique())
else:
    meses_disponiveis = sorted(df_merged['Mês'].dropna().unique())
meses_nomes = {1:'Janeiro',2:'Fevereiro',3:'Março',4:'Abril',5:'Maio',6:'Junho',7:'Julho',8:'Agosto',9:'Setembro',10:'Outubro',11:'Novembro',12:'Dezembro'}
lista_meses = ["Todos"] + [f"{int(m):02d} - {meses_nomes[int(m)]}" for m in meses_disponiveis]
if 'mes' not in st.session_state:
    if meses_disponiveis:
        ultimo_mes = meses_disponiveis[-1]
        st.session_state['mes'] = f"{ultimo_mes:02d} - {meses_nomes.get(ultimo_mes, '')}"
    else:
        st.session_state['mes'] = 'Todos'
if st.session_state['mes'] not in lista_meses: st.session_state['mes'] = 'Todos'
mes_selecionado = st.sidebar.selectbox("Mês", lista_meses, index=lista_meses.index(st.session_state['mes']), key='mes_select')
st.session_state['mes'] = mes_selecionado

st.sidebar.divider()
st.sidebar.header("📆 Janela da Base Ativa")
if 'janela_meses' not in st.session_state:
    st.session_state['janela_meses'] = 6
janela_meses = st.sidebar.slider("Nº de meses anteriores", min_value=3, max_value=6, value=st.session_state['janela_meses'], step=1, key='janela_slider')
st.session_state['janela_meses'] = janela_meses

st.sidebar.divider()
st.sidebar.header("🏭 Filtro por Indústria")
if pasta_selecionada in ["Todas", "PVA"]:
    INDUSTRIAS_DISPONIVEIS = TODAS_INDUSTRIAS.copy()
else:
    INDUSTRIAS_DISPONIVEIS = [ind for ind in TODAS_INDUSTRIAS if fabricante_pasta.get(ind) == pasta_selecionada]
if 'industria_filtro' not in st.session_state: st.session_state['industria_filtro'] = []
industria_selecionada_lista = st.sidebar.multiselect("Indústria(s)", options=INDUSTRIAS_DISPONIVEIS, default=st.session_state['industria_filtro'], placeholder="Digite para buscar...", key='industria_multiselect')
st.session_state['industria_filtro'] = industria_selecionada_lista

if 'categoria_filtro' not in st.session_state: st.session_state['categoria_filtro'] = []
categoria_opcoes = sorted(df_bi['Categoria'].dropna().unique())
categoria_selecionada = st.sidebar.multiselect("Categoria(s)", options=categoria_opcoes, default=st.session_state['categoria_filtro'], placeholder="Selecione...")
st.session_state['categoria_filtro'] = categoria_selecionada

if 'linha_filtro' not in st.session_state: st.session_state['linha_filtro'] = []
linha_opcoes = sorted(df_bi['Linha_Produto'].dropna().unique())
linha_selecionada = st.sidebar.multiselect("Linha(s) de Produto", options=linha_opcoes, default=st.session_state['linha_filtro'], placeholder="Selecione...")
st.session_state['linha_filtro'] = linha_selecionada

st.sidebar.divider()
st.sidebar.header("🎯 Metas")
if 'meta_ativa' not in st.session_state: st.session_state['meta_ativa'] = 70
meta_ativa = st.sidebar.number_input("Meta Base Ativa (%)", min_value=0, max_value=100, value=st.session_state['meta_ativa'], step=1, key='meta_ativa_input')
st.session_state['meta_ativa'] = meta_ativa

if 'meta_total' not in st.session_state: st.session_state['meta_total'] = 50
meta_total = st.sidebar.number_input("Meta Carteira Total (%)", min_value=0, max_value=100, value=st.session_state['meta_total'], step=1, key='meta_total_input')
st.session_state['meta_total'] = meta_total

# ============================================================
# FUNÇÃO PARA APLICAR FILTROS COMUNS
# ============================================================
def aplicar_filtros_comuns(df, incluir_mes=True):
    df = df.copy()
    df = df[df['Nome_Fabricante'].isin(INDUSTRIAS_PERMITIDAS)]

    if pasta_selecionada != "Todas":
        vendedores_pasta = [v for v in df_base['nome_vendedor_base'].unique() if vendedor_pasta.get(v) == pasta_selecionada]
        df = df[df['nome_vendedor'].isin(vendedores_pasta)]
    elif vendedor_selecionado != "Todos":
        df = df[df['nome_vendedor'] == vendedor_selecionado]

    if coordenador_selecionado != "Todos":
        df = df[df['Nome_Coordenador'] == coordenador_selecionado]
    if coligacao_selecionada != "Todas":
        df = df[df['Cliente_Coligacao'] == coligacao_selecionada]
    if municipio_selecionado:
        df = df[df['Municipio'].isin(municipio_selecionado)]
    if canal_selecionado:
        df = df[df['Canal'].isin(canal_selecionado)]
    if segmento_selecionado:
        df = df[df['Segmento'].isin(segmento_selecionado)]
    if ano_selecionado != "Todos":
        df = df[df['Ano'] == int(ano_selecionado)]
    if incluir_mes and mes_selecionado != "Todos":
        mes_num = int(mes_selecionado.split(' - ')[0])
        df = df[df['Mês'] == mes_num]
    if industria_selecionada_lista:
        df = df[df['Nome_Fabricante'].isin(industria_selecionada_lista)]
    if categoria_selecionada:
        df = df[df['Categoria'].isin(categoria_selecionada)]
    if linha_selecionada:
        df = df[df['Linha_Produto'].isin(linha_selecionada)]
    return df

df_filtrado = aplicar_filtros_comuns(df_merged, incluir_mes=True)
df_historico = aplicar_filtros_comuns(df_merged, incluir_mes=False)
df_relatorio_base = aplicar_filtros_comuns(df_merged, incluir_mes=False)

# Aplicar janela móvel
if mes_selecionado != "Todos":
    if ano_selecionado != "Todos":
        ano_ref = int(ano_selecionado)
    else:
        ano_ref = df_historico['Ano'].max()
    mes_atual = int(mes_selecionado.split(' - ')[0])
    meses_janela = []
    for i in range(1, janela_meses + 1):
        mes = mes_atual - i
        ano = ano_ref
        while mes <= 0:
            mes += 12
            ano -= 1
        meses_janela.append((ano, mes))
    cond_janela = pd.Series(False, index=df_historico.index)
    for a, m in meses_janela:
        cond_janela |= (df_historico['Ano'] == a) & (df_historico['Mês'] == m)
    df_historico_janela = df_historico[cond_janela]
else:
    df_historico_janela = df_historico

# ============================================================
# CARTEIRA ATIVA (JANELA MÓVEL)
# ============================================================
carteira_ativa_total = df_historico_janela[df_historico_janela['Nome_Fabricante'].notna()]['codigo_cliente'].nunique()
positivados_periodo = df_filtrado[df_filtrado['Nome_Fabricante'].notna()]['codigo_cliente'].nunique()
pct_ativa = (positivados_periodo / carteira_ativa_total * 100) if carteira_ativa_total > 0 else 0

clientes_ativos_ids = df_historico_janela[df_historico_janela['Nome_Fabricante'].notna()]['codigo_cliente'].unique()
clientes_positivados_ids = df_filtrado[df_filtrado['Nome_Fabricante'].notna()]['codigo_cliente'].unique()
clientes_sem_venda_ativos = [c for c in clientes_ativos_ids if c not in clientes_positivados_ids]

st.subheader("📅 Carteira Ativa (Janela Móvel)")
col_a1, col_a2, col_a3 = st.columns(3)
col_a1.metric("Carteira Ativa (últimos {} meses)".format(janela_meses), carteira_ativa_total)
col_a2.metric("Positivados no Mês", positivados_periodo)
col_a3.metric("% Positivação (Ativa)", f"{pct_ativa:.1f}%")

st.markdown("**Clientes positivados por mês (Carteira Ativa)**")
df_mensal_ativos = df_historico[df_historico['Nome_Fabricante'].notna()]
mensal_pos = df_mensal_ativos.groupby('Mês_Ano')['codigo_cliente'].nunique().reset_index()
mensal_pos.columns = ['Mês', 'Clientes Positivados']
meses_unicos = sorted(df_historico['Mês_Ano'].dropna().unique())
meses_presentes = [m for m in meses_unicos if m in mensal_pos['Mês'].values]
mensal_pos['Mês'] = pd.Categorical(mensal_pos['Mês'], categories=meses_presentes, ordered=True)
mensal_pos = mensal_pos.sort_values('Mês')
if not mensal_pos.empty:
    fig_pos_mes = px.bar(mensal_pos, x='Mês', y='Clientes Positivados', text='Clientes Positivados', color_discrete_sequence=['#2E8B57'])
    fig_pos_mes.update_traces(textposition='outside')
    fig_pos_mes.update_layout(xaxis_title="", yaxis_title="Nº de clientes", xaxis=dict(type='category', categoryorder='array', categoryarray=meses_presentes))
    st.plotly_chart(fig_pos_mes, use_container_width=True)
else:
    st.info("Sem dados mensais para exibir.")

if clientes_sem_venda_ativos:
    df_sem_venda_ativos = df_base[df_base['codigo_cliente'].isin(clientes_sem_venda_ativos)][['codigo_cliente', 'nome_cliente', 'Cliente_Coligacao']]
    df_sem_venda_ativos.columns = ['Código', 'Nome', 'Coligação']
    with st.expander(f"🔴 {len(clientes_sem_venda_ativos)} clientes sem venda no mês (Carteira Ativa)"):
        st.dataframe(df_sem_venda_ativos, use_container_width=True, hide_index=True)

    output_ativa = BytesIO()
    with pd.ExcelWriter(output_ativa, engine='openpyxl') as writer:
        df_sem_venda_ativos.to_excel(writer, index=False, sheet_name='Sem Venda Ativa')
    st.download_button("📥 Baixar Excel (Sem Venda Ativa)", data=output_ativa.getvalue(),
                       file_name=f'sem_venda_ativa_{vendedor_selecionado if vendedor_selecionado != "Todos" else "geral"}_{datetime.now().strftime("%Y%m%d_%H%M")}.xlsx',
                       mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', use_container_width=True)

st.divider()

# ============================================================
# CARTEIRA TOTAL
# ============================================================
if vendedor_selecionado != "Todos":
    total_clientes_base = df_base[df_base['nome_vendedor_base'] == vendedor_selecionado]['codigo_cliente'].nunique()
elif coordenador_selecionado != "Todos":
    vendedores_do_coord = df_base[df_base['Nome_Coordenador'] == coordenador_selecionado]['nome_vendedor_base'].unique()
    total_clientes_base = df_base[df_base['nome_vendedor_base'].isin(vendedores_do_coord)]['codigo_cliente'].nunique()
else:
    total_clientes_base = df_base['codigo_cliente'].nunique()

total_positivados = len(clientes_positivados_ids)
pct_total = (total_positivados / total_clientes_base * 100) if total_clientes_base > 0 else 0
cobertura_media = df_filtrado.groupby('codigo_cliente')['Nome_Fabricante'].nunique().mean()
cobertura_total = df_filtrado[['codigo_cliente', 'Nome_Fabricante']].dropna().drop_duplicates().shape[0]

todos_ids_carteira = df_base['codigo_cliente'].unique()
if vendedor_selecionado != "Todos":
    todos_ids_carteira = df_base[df_base['nome_vendedor_base'] == vendedor_selecionado]['codigo_cliente'].unique()
elif coordenador_selecionado != "Todos":
    vendedores_do_coord = df_base[df_base['Nome_Coordenador'] == coordenador_selecionado]['nome_vendedor_base'].unique()
    todos_ids_carteira = df_base[df_base['nome_vendedor_base'].isin(vendedores_do_coord)]['codigo_cliente'].unique()
clientes_sem_venda_carteira = [c for c in todos_ids_carteira if c not in clientes_positivados_ids]

st.subheader("📋 Carteira Total")
col1, col2, col3 = st.columns(3)
col1.metric("Clientes na Carteira", total_clientes_base)
col2.metric("Clientes Positivados", total_positivados)
col3.metric("% Positivação (Carteira Total)", f"{pct_total:.1f}%")
col4, col5 = st.columns(2)
col4.metric("Cobertura Média", f"{cobertura_media:.1f} ind/cliente")
col5.metric("Cobertura Total", f"{cobertura_total} coberturas")

if clientes_sem_venda_carteira:
    df_sem_venda_total = df_base[df_base['codigo_cliente'].isin(clientes_sem_venda_carteira)][['codigo_cliente', 'nome_cliente', 'Cliente_Coligacao']]
    df_sem_venda_total.columns = ['Código', 'Nome', 'Coligação']
    with st.expander(f"🔴 {len(clientes_sem_venda_carteira)} clientes sem venda (Carteira Total)"):
        st.dataframe(df_sem_venda_total, use_container_width=True, hide_index=True)

    output_total = BytesIO()
    with pd.ExcelWriter(output_total, engine='openpyxl') as writer:
        df_sem_venda_total.to_excel(writer, index=False, sheet_name='Sem Venda Total')
    st.download_button("📥 Baixar Excel (Sem Venda Total)", data=output_total.getvalue(),
                       file_name=f'sem_venda_total_{vendedor_selecionado if vendedor_selecionado != "Todos" else "geral"}_{datetime.now().strftime("%Y%m%d_%H%M")}.xlsx',
                       mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', use_container_width=True)

st.divider()

# ============================================================
# PERFORMANCE POR VENDEDOR
# ============================================================
st.subheader("👥 Performance por Vendedor")

df_base_perf = df_base.copy()
if coordenador_selecionado != "Todos":
    df_base_perf = df_base_perf[df_base_perf['Nome_Coordenador'] == coordenador_selecionado]
if vendedor_selecionado != "Todos":
    df_base_perf = df_base_perf[df_base_perf['nome_vendedor_base'] == vendedor_selecionado]
if pasta_selecionada != "Todas":
    vendedores_da_pasta = [v for v in df_base_perf['nome_vendedor_base'].unique() if vendedor_pasta.get(v) == pasta_selecionada]
    df_base_perf = df_base_perf[df_base_perf['nome_vendedor_base'].isin(vendedores_da_pasta)]
if municipio_selecionado:
    df_base_perf = df_base_perf[df_base_perf['Municipio'].isin(municipio_selecionado)]
if canal_selecionado:
    df_base_perf = df_base_perf[df_base_perf['Canal'].isin(canal_selecionado)]
if segmento_selecionado:
    df_base_perf = df_base_perf[df_base_perf['Segmento'].isin(segmento_selecionado)]

if vendedor_selecionado != "Todos":
    vendedores_base = [vendedor_selecionado]
else:
    vendedores_base = df_filtrado['nome_vendedor'].dropna().unique()

perf_list = []
for vendedor in vendedores_base:
    pasta_v = vendedor_pasta.get(vendedor, "")
    clientes_carteira = df_base_perf[df_base_perf['nome_vendedor_base'] == vendedor]['codigo_cliente'].nunique()
    clientes_ativos_hist = df_historico_janela[df_historico_janela['nome_vendedor'] == vendedor]['codigo_cliente'].nunique()
    df_bi_vendedor = df_filtrado[df_filtrado['nome_vendedor'] == vendedor]
    clientes_pos = df_bi_vendedor[df_bi_vendedor['Nome_Fabricante'].notna()]['codigo_cliente'].nunique()
    cobertura = df_bi_vendedor.groupby('codigo_cliente')['Nome_Fabricante'].nunique()
    cobertura_media_vend = cobertura.mean() if len(cobertura) > 0 else 0
    cobertura_total_vend = df_bi_vendedor[['codigo_cliente', 'Nome_Fabricante']].dropna().drop_duplicates().shape[0]
    pct_ativa_vend = (clientes_pos / clientes_ativos_hist * 100) if clientes_ativos_hist > 0 else 0
    pct_total_vend = (clientes_pos / clientes_carteira * 100) if clientes_carteira > 0 else 0
    perf_list.append({
        'Vendedor': vendedor, 'Pasta': pasta_v,
        'Total_Clientes': clientes_carteira, 'Clientes_Ativos_Hist': clientes_ativos_hist,
        'Clientes_Positivados': clientes_pos,
        '%_Positivação_Ativa': round(pct_ativa_vend, 1), '%_Positivação_Total': round(pct_total_vend, 1),
        'Cobertura_Media': round(cobertura_media_vend, 1), 'Cobertura_Total': cobertura_total_vend
    })

perf_vendedor = pd.DataFrame(perf_list).sort_values('%_Positivação_Ativa', ascending=False)

fig_ativa = px.bar(perf_vendedor, x='Vendedor', y='%_Positivação_Ativa',
                   title='% Positivação (Base Ativa)',
                   text=perf_vendedor['%_Positivação_Ativa'].apply(lambda x: f'{x:.1f}%'),
                   color='%_Positivação_Ativa', color_continuous_scale='Greens')
fig_ativa.add_hline(y=meta_ativa, line_dash="dash", line_color="red", annotation_text=f"Meta {meta_ativa}%")
fig_ativa.update_traces(textposition='outside')
fig_ativa.update_layout(xaxis_title="", yaxis_title="% Positivação", yaxis_range=[0, 105])
st.plotly_chart(fig_ativa, use_container_width=True)

fig_total = px.bar(perf_vendedor, x='Vendedor', y='%_Positivação_Total',
                   title='% Positivação (Carteira Total)',
                   text=perf_vendedor['%_Positivação_Total'].apply(lambda x: f'{x:.1f}%'),
                   color='%_Positivação_Total', color_continuous_scale='Blues')
fig_total.add_hline(y=meta_total, line_dash="dash", line_color="red", annotation_text=f"Meta {meta_total}%")
fig_total.update_traces(textposition='outside')
fig_total.update_layout(xaxis_title="", yaxis_title="% Positivação", yaxis_range=[0, 105])
st.plotly_chart(fig_total, use_container_width=True)

fig_cob = px.bar(perf_vendedor, x='Vendedor', y='Cobertura_Media',
                 title='Cobertura Média por Vendedor',
                 text=perf_vendedor['Cobertura_Media'].apply(lambda x: f'{x:.1f}'),
                 color='Cobertura_Media', color_continuous_scale='Oranges')
fig_cob.update_traces(textposition='outside')
fig_cob.update_layout(xaxis_title="", yaxis_title="Indústrias/Cliente")
st.plotly_chart(fig_cob, use_container_width=True)

st.dataframe(perf_vendedor[['Vendedor', 'Pasta', 'Total_Clientes', 'Clientes_Ativos_Hist', 'Clientes_Positivados',
                            '%_Positivação_Ativa', '%_Positivação_Total', 'Cobertura_Media', 'Cobertura_Total']],
             use_container_width=True, hide_index=True)
st.divider()

# ============================================================
# FOCOS ESTRATÉGICOS
# ============================================================

# ---------- 1. SOFTYS FALCON ----------
st.subheader("🟢 Foco Estratégico: Softys Falcon")

df_softys = df_relatorio_base[df_relatorio_base['Nome_Fabricante'] == 'SOFTYS FALCON'].copy()

if not df_softys.empty:
    # Determinar meses da janela e ano de referência
    if mes_selecionado != "Todos":
        if ano_selecionado != "Todos":
            ano_ref = int(ano_selecionado)
        else:
            ano_ref = df_softys['Ano'].max()
        mes_atual_num = int(mes_selecionado.split(' - ')[0])

        months_window = []
        for i in range(1, janela_meses + 1):
            mes = mes_atual_num - i
            ano = ano_ref
            while mes <= 0:
                mes += 12
                ano -= 1
            months_window.append(f"{ano}-{mes:02d}")

        months_window = sorted(months_window)
        current_month_str = f"{ano_ref}-{mes_atual_num:02d}"
    else:
        months_window = sorted(df_softys['Mês_Ano'].unique())
        current_month_str = months_window[-1] if months_window else None

    df_softys_window = df_softys[df_softys['Mês_Ano'].isin(months_window)].copy()

    # ---- GRÁFICO: Positivação mensal + YTD ----
    st.markdown("**Positivação Mensal e YTD (Softys Falcon)**")

    monthly_totals = df_softys_window.groupby('Mês_Ano')['codigo_cliente'].nunique().reset_index()
    monthly_totals.columns = ['Mês', 'Clientes']

    if mes_selecionado != "Todos":
        ano_ref_ytd = ano_ref
        mes_ytd = mes_atual_num
    else:
        ano_ref_ytd = df_softys['Ano'].max()
        mes_ytd = df_softys['Mês'].max()
    df_softys_ytd = df_softys[(df_softys['Ano'] == ano_ref_ytd) & (df_softys['Mês'] <= mes_ytd)]
    ytd_total = df_softys_ytd['codigo_cliente'].nunique()

    # Montar DataFrame do gráfico sem append
    graph_df = monthly_totals.copy()
    ytd_row = pd.DataFrame([{'Mês': 'YTD', 'Clientes': ytd_total}])
    graph_df = pd.concat([graph_df, ytd_row], ignore_index=True)

    fig_softys = go.Figure()
    mensal_df = graph_df[graph_df['Mês'] != 'YTD']
    fig_softys.add_trace(go.Bar(
        x=mensal_df['Mês'],
        y=mensal_df['Clientes'],
        name='Mensal',
        marker_color='#2E8B57'
    ))
    ytd_df = graph_df[graph_df['Mês'] == 'YTD']
    if not ytd_df.empty:
        fig_softys.add_trace(go.Bar(
            x=ytd_df['Mês'],
            y=ytd_df['Clientes'],
            name='YTD',
            marker_color='#1a3a4a'
        ))
    fig_softys.update_layout(
        title='Positivação Softys Falcon (Mensal + YTD)',
        xaxis_title='',
        yaxis_title='Clientes únicos',
        barmode='group'
    )
    st.plotly_chart(fig_softys, use_container_width=True)

    # ---- TABELA MENSAL POR CATEGORIA (com YTD) ----
    st.markdown("**Positivação por Categoria (mês a mês + YTD)**")

    pivot_mensal = df_softys_window.pivot_table(
        index='Categoria',
        columns='Mês_Ano',
        values='codigo_cliente',
        aggfunc='nunique',
        fill_value=0
    )
    if months_window:
        pivot_mensal = pivot_mensal.reindex(columns=[c for c in months_window if c in pivot_mensal.columns], fill_value=0)

    ytd_series = df_softys_ytd.groupby('Categoria')['codigo_cliente'].nunique()
    tabela_mensal = pivot_mensal.copy()
    tabela_mensal['YTD'] = ytd_series
    tabela_mensal = tabela_mensal.reset_index()
    tabela_mensal = tabela_mensal.fillna(0)

    ordered_cols = ['Categoria'] + [c for c in months_window if c in tabela_mensal.columns] + ['YTD']
    tabela_mensal = tabela_mensal[ordered_cols]

    st.dataframe(tabela_mensal, use_container_width=True, hide_index=True)

    output_softys_mensal = BytesIO()
    with pd.ExcelWriter(output_softys_mensal, engine='openpyxl') as writer:
        tabela_mensal.to_excel(writer, index=False, sheet_name='Softys Mensal')
    st.download_button("📥 Baixar Excel (Mensal)", data=output_softys_mensal.getvalue(),
                       file_name=f'softys_mensal_{datetime.now().strftime("%Y%m%d")}.xlsx',
                       mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', use_container_width=True)

    html_softys_mensal = f"""
    <html><head><meta charset="UTF-8"><style>
        body {{ font-family: Arial, sans-serif; margin: 20px; }}
        h1 {{ font-size: 16px; }}
        table {{ border-collapse: collapse; width: 100%; font-size: 10px; }}
        th {{ background-color: #1a3a4a; color: white; padding: 5px; }}
        td {{ padding: 4px; border: 1px solid #ddd; }}
    </style></head><body>
        <h1>Positivação Softys Falcon - mês a mês + YTD</h1>
        {tabela_mensal.to_html(index=False)}
    </body></html>
    """
    st.download_button("📥 Baixar PDF (Mensal)", data=html_softys_mensal.encode('utf-8'),
                       file_name=f'softys_mensal_{datetime.now().strftime("%Y%m%d")}.html',
                       mime='text/html', use_container_width=True)
    st.caption("💡 Abra o HTML e salve como PDF (Ctrl+P)")

    # ---- BATALHA NAVAL SOFTYS FALCON ----
    st.markdown("**Batalha Naval Softys Falcon — Clientes que compraram**")

    df_softys_clientes = df_softys[['codigo_cliente', 'nome_cliente', 'Municipio', 'Cliente_Coligacao', 'nome_vendedor', 'Categoria']].drop_duplicates()
    clientes_pivot = df_softys_clientes.pivot_table(
        index=['codigo_cliente', 'nome_cliente', 'Municipio', 'Cliente_Coligacao', 'nome_vendedor'],
        columns='Categoria',
        values='codigo_cliente',
        aggfunc='nunique',
        fill_value=0
    ).reset_index()

    cat_cols = [c for c in clientes_pivot.columns if c not in ['codigo_cliente', 'nome_cliente', 'Municipio', 'Cliente_Coligacao', 'nome_vendedor']]
    clientes_pivot[cat_cols] = (clientes_pivot[cat_cols] > 0).astype(int)
    clientes_pivot['Total'] = clientes_pivot[cat_cols].sum(axis=1)

    with st.expander("👁️ Visualizar Batalha Naval Softys Falcon"):
        st.dataframe(clientes_pivot, use_container_width=True, hide_index=True)

    output_softys_bn = BytesIO()
    with pd.ExcelWriter(output_softys_bn, engine='openpyxl') as writer:
        clientes_pivot.to_excel(writer, index=False, sheet_name='Batalha Naval Softys')
    st.download_button("📥 Baixar Excel (Batalha Naval Softys)", data=output_softys_bn.getvalue(),
                       file_name=f'batalha_naval_softys_{datetime.now().strftime("%Y%m%d")}.xlsx',
                       mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', use_container_width=True)

    html_softys_bn = f"""
    <html><head><meta charset="UTF-8"><style>
        body {{ font-family: Arial, sans-serif; margin: 20px; }}
        h1 {{ font-size: 16px; }}
        table {{ border-collapse: collapse; width: 100%; font-size: 10px; }}
        th {{ background-color: #1a3a4a; color: white; padding: 5px; }}
        td {{ padding: 4px; border: 1px solid #ddd; }}
    </style></head><body>
        <h1>Batalha Naval Softys Falcon</h1>
        {clientes_pivot.to_html(index=False)}
    </body></html>
    """
    st.download_button("📥 Baixar PDF (Batalha Naval Softys)", data=html_softys_bn.encode('utf-8'),
                       file_name=f'batalha_naval_softys_{datetime.now().strftime("%Y%m%d")}.html',
                       mime='text/html', use_container_width=True)
    st.caption("💡 Abra o HTML e salve como PDF (Ctrl+P)")

else:
    st.warning("Nenhum dado da Softys Falcon para os filtros atuais.")

st.divider()

# ---------- 2. KENVUE (CANAL PERFUMARIA) ----------
st.subheader("🟠 Foco Estratégico: Kenvue no Canal Perfumaria")

df_perfumarias_ativas = df_historico_janela[df_historico_janela['Canal'] == 'PERFUMARIA'].copy()

if not df_perfumarias_ativas.empty:
    df_kenvue_mes = df_filtrado[(df_filtrado['Nome_Fabricante'] == 'KENVUE') & (df_filtrado['Canal'] == 'PERFUMARIA')].copy()

    if not df_kenvue_mes.empty:
        clientes_kenvue_mes = df_kenvue_mes['codigo_cliente'].unique()
        total_perfumarias_ativas = df_perfumarias_ativas['codigo_cliente'].nunique()
        atendidos = len(clientes_kenvue_mes)
        pct_atendido = (atendidos / total_perfumarias_ativas * 100) if total_perfumarias_ativas > 0 else 0

        st.metric("Perfumarias Ativas (janela móvel)", total_perfumarias_ativas)
        st.metric("Atendidas com Kenvue (mês atual)", f"{atendidos} ({pct_atendido:.1f}%)")
        st.progress(min(pct_atendido / 100, 1.0), text="Meta: 50%")

        st.markdown("**Onde chegamos / Onde não chegamos (Perfumarias ativas)**")

        clientes_nao_atendidos = [c for c in df_perfumarias_ativas['codigo_cliente'].unique() if c not in clientes_kenvue_mes]

        col_ken1, col_ken2 = st.columns(2)
        with col_ken1:
            st.markdown(f"✅ **Chegamos** ({atendidos})")
            df_chegamos = df_base[df_base['codigo_cliente'].isin(clientes_kenvue_mes)][['codigo_cliente', 'nome_cliente', 'Municipio', 'Cliente_Coligacao', 'nome_vendedor_base']]
            df_chegamos.columns = ['Código', 'Nome', 'Município', 'Coligação', 'Vendedor']
            st.dataframe(df_chegamos, use_container_width=True, hide_index=True)

            output_ken_cheg = BytesIO()
            with pd.ExcelWriter(output_ken_cheg, engine='openpyxl') as writer:
                df_chegamos.to_excel(writer, index=False, sheet_name='Chegamos')
            st.download_button("📥 Baixar Excel (Chegamos)", data=output_ken_cheg.getvalue(),
                               file_name=f'kenvue_chegamos_{datetime.now().strftime("%Y%m%d")}.xlsx',
                               mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', use_container_width=True)
            html_ken_cheg = f"""<html><head><meta charset="UTF-8"><style>body {{ font-family: Arial; margin:20px; }} table {{ border-collapse: collapse; width:100%; font-size:10px; }} th {{ background:#1a3a4a; color:white; padding:5px; }} td {{ border:1px solid #ddd; padding:4px; }}</style></head><body><h1>Kenvue - Chegamos</h1>{df_chegamos.to_html(index=False)}</body></html>"""
            st.download_button("📥 Baixar PDF (Chegamos)", data=html_ken_cheg.encode('utf-8'),
                               file_name=f'kenvue_chegamos_{datetime.now().strftime("%Y%m%d")}.html',
                               mime='text/html', use_container_width=True)

        with col_ken2:
            st.markdown(f"❌ **Não chegamos** ({len(clientes_nao_atendidos)})")
            df_nao_chegamos = df_base[df_base['codigo_cliente'].isin(clientes_nao_atendidos)][['codigo_cliente', 'nome_cliente', 'Municipio', 'Cliente_Coligacao', 'nome_vendedor_base']]
            df_nao_chegamos.columns = ['Código', 'Nome', 'Município', 'Coligação', 'Vendedor']
            st.dataframe(df_nao_chegamos, use_container_width=True, hide_index=True)

            output_ken_nao = BytesIO()
            with pd.ExcelWriter(output_ken_nao, engine='openpyxl') as writer:
                df_nao_chegamos.to_excel(writer, index=False, sheet_name='Nao Chegamos')
            st.download_button("📥 Baixar Excel (Não Chegamos)", data=output_ken_nao.getvalue(),
                               file_name=f'kenvue_nao_chegamos_{datetime.now().strftime("%Y%m%d")}.xlsx',
                               mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', use_container_width=True)
            html_ken_nao = f"""<html><head><meta charset="UTF-8"><style>body {{ font-family: Arial; margin:20px; }} table {{ border-collapse: collapse; width:100%; font-size:10px; }} th {{ background:#1a3a4a; color:white; padding:5px; }} td {{ border:1px solid #ddd; padding:4px; }}</style></head><body><h1>Kenvue - Não Chegamos</h1>{df_nao_chegamos.to_html(index=False)}</body></html>"""
            st.download_button("📥 Baixar PDF (Não Chegamos)", data=html_ken_nao.encode('utf-8'),
                               file_name=f'kenvue_nao_chegamos_{datetime.now().strftime("%Y%m%d")}.html',
                               mime='text/html', use_container_width=True)

        st.markdown("**Meta por Vendedor (50% das perfumarias ativas)**")
        vendedores_perf = df_perfumarias_ativas['nome_vendedor_base'].dropna().unique()
        lista_kenvue_vend = []
        for vend in vendedores_perf:
            total_vend = df_perfumarias_ativas[df_perfumarias_ativas['nome_vendedor_base'] == vend]['codigo_cliente'].nunique()
            atend_vend = df_kenvue_mes[df_kenvue_mes['nome_vendedor'] == vend]['codigo_cliente'].nunique()
            pct_vend = (atend_vend / total_vend * 100) if total_vend > 0 else 0
            lista_kenvue_vend.append({
                'Vendedor': vend,
                'Perfumarias Ativas': total_vend,
                'Atendidas Kenvue': atend_vend,
                '% Atendido': round(pct_vend, 1)
            })
        df_kenvue_vend = pd.DataFrame(lista_kenvue_vend)
        st.dataframe(df_kenvue_vend, use_container_width=True, hide_index=True)

        output_ken_vend = BytesIO()
        with pd.ExcelWriter(output_ken_vend, engine='openpyxl') as writer:
            df_kenvue_vend.to_excel(writer, index=False, sheet_name='Meta Kenvue Vendedor')
        st.download_button("📥 Baixar Excel (Meta por Vendedor)", data=output_ken_vend.getvalue(),
                           file_name=f'kenvue_meta_vendedor_{datetime.now().strftime("%Y%m%d")}.xlsx',
                           mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', use_container_width=True)

        html_ken_vend = f"""<html><head><meta charset="UTF-8"><style>body {{ font-family: Arial; margin:20px; }} table {{ border-collapse: collapse; width:100%; font-size:10px; }} th {{ background:#1a3a4a; color:white; padding:5px; }} td {{ border:1px solid #ddd; padding:4px; }}</style></head><body><h1>Meta Kenvue por Vendedor</h1>{df_kenvue_vend.to_html(index=False)}</body></html>"""
        st.download_button("📥 Baixar PDF (Meta por Vendedor)", data=html_ken_vend.encode('utf-8'),
                           file_name=f'kenvue_meta_vendedor_{datetime.now().strftime("%Y%m%d")}.html',
                           mime='text/html', use_container_width=True)
    else:
        st.warning("Nenhuma venda de Kenvue no mês atual para o canal Perfumaria.")
else:
    st.warning("Nenhuma perfumaria ativa na janela móvel.")

st.divider()

# ---------- 3. LINHA CENOURA & BRONZE ----------
st.subheader("🟤 Foco Estratégico: Linha Cenoura & Bronze")

df_cenoura = df_relatorio_base[df_relatorio_base['Linha_Produto'] == 'CENOURA & BRONZE'].copy()

if not df_cenoura.empty:
    if mes_selecionado != "Todos":
        if ano_selecionado != "Todos":
            ano_ref = int(ano_selecionado)
        else:
            ano_ref = df_cenoura['Ano'].max()
        mes_atual_num = int(mes_selecionado.split(' - ')[0])
        months_window = [f"{a}-{m:02d}" for a, m in meses_janela]
        months_window = sorted(months_window)
        current_month_str = f"{ano_ref}-{mes_atual_num:02d}"
    else:
        months_window = sorted(df_cenoura['Mês_Ano'].unique())
        current_month_str = months_window[-1] if months_window else None

    df_cenoura_window = df_cenoura[df_cenoura['Mês_Ano'].isin(months_window)].copy()
    df_cenoura_mes_atual = df_cenoura[df_cenoura['Mês_Ano'] == current_month_str].copy() if current_month_str else pd.DataFrame()

    vendedores_cen = df_cenoura['nome_vendedor'].dropna().unique()
    lista_cen = []
    for vend in vendedores_cen:
        df_vend_window = df_cenoura_window[df_cenoura_window['nome_vendedor'] == vend]
        media_6m = df_vend_window.groupby('Mês_Ano')['codigo_cliente'].nunique().mean() if not df_vend_window.empty else 0

        df_vend_mes = df_cenoura_mes_atual[df_cenoura_mes_atual['nome_vendedor'] == vend] if not df_cenoura_mes_atual.empty else pd.DataFrame()
        clientes_mes = df_vend_mes['codigo_cliente'].nunique() if not df_vend_mes.empty else 0

        pct = (clientes_mes / media_6m * 100) if media_6m > 0 else 0

        lista_cen.append({
            'Vendedor': vend,
            'Média 6M': round(media_6m, 1),
            'Mês Atual': clientes_mes,
            '% Mês vs Média': round(pct, 1)
        })
    df_cen_vend = pd.DataFrame(lista_cen)

    fig_cen_media = px.bar(df_cen_vend, x='Vendedor', y='Média 6M',
                           title='Positivação Média (6 meses) - Cenoura & Bronze',
                           text='Média 6M', color='Média 6M', color_continuous_scale='Blues')
    fig_cen_media.update_traces(textposition='outside')
    fig_cen_media.update_layout(xaxis_title="", yaxis_title="Média de clientes")
    st.plotly_chart(fig_cen_media, use_container_width=True)

    fig_cen_mes = px.bar(df_cen_vend, x='Vendedor', y='Mês Atual',
                         title='Positivação no Mês - Cenoura & Bronze',
                         text='Mês Atual', color='Mês Atual', color_continuous_scale='Oranges')
    fig_cen_mes.update_traces(textposition='outside')
    fig_cen_mes.update_layout(xaxis_title="", yaxis_title="Clientes")
    st.plotly_chart(fig_cen_mes, use_container_width=True)

    st.dataframe(df_cen_vend, use_container_width=True, hide_index=True)

    output_cen = BytesIO()
    with pd.ExcelWriter(output_cen, engine='openpyxl') as writer:
        df_cen_vend.to_excel(writer, index=False, sheet_name='Cenoura Bronze')
    st.download_button("📥 Baixar Excel (Resumo)", data=output_cen.getvalue(),
                       file_name=f'cenoura_bronze_{datetime.now().strftime("%Y%m%d")}.xlsx',
                       mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', use_container_width=True)

    html_cen_resumo = f"""<html><head><meta charset="UTF-8"><style>body {{ font-family: Arial; margin:20px; }} table {{ border-collapse: collapse; width:100%; font-size:10px; }} th {{ background:#1a3a4a; color:white; padding:5px; }} td {{ border:1px solid #ddd; padding:4px; }}</style></head><body><h1>Cenoura & Bronze - Resumo</h1>{df_cen_vend.to_html(index=False)}</body></html>"""
    st.download_button("📥 Baixar PDF (Resumo)", data=html_cen_resumo.encode('utf-8'),
                       file_name=f'cenoura_bronze_resumo_{datetime.now().strftime("%Y%m%d")}.html',
                       mime='text/html', use_container_width=True)

    st.markdown("**Clientes atendidos nos 6 meses, mas não no mês atual**")
    clientes_janela = df_cenoura_window['codigo_cliente'].unique()
    clientes_mes = df_cenoura_mes_atual['codigo_cliente'].unique() if not df_cenoura_mes_atual.empty else []
    clientes_ausentes = [c for c in clientes_janela if c not in clientes_mes]

    if clientes_ausentes:
        df_cen_ausentes = df_base[df_base['codigo_cliente'].isin(clientes_ausentes)][['codigo_cliente', 'nome_cliente', 'Municipio', 'Cliente_Coligacao', 'nome_vendedor_base']]
        df_cen_ausentes.columns = ['Código', 'Nome', 'Município', 'Coligação', 'Vendedor']
        st.dataframe(df_cen_ausentes, use_container_width=True, hide_index=True)

        output_cen_ausentes = BytesIO()
        with pd.ExcelWriter(output_cen_ausentes, engine='openpyxl') as writer:
            df_cen_ausentes.to_excel(writer, index=False, sheet_name='Ausentes')
        st.download_button("📥 Baixar Excel (Clientes Ausentes)", data=output_cen_ausentes.getvalue(),
                           file_name=f'cenoura_ausentes_{datetime.now().strftime("%Y%m%d")}.xlsx',
                           mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', use_container_width=True)
        html_cen_ausentes = f"""<html><head><meta charset="UTF-8"><style>body {{ font-family: Arial; margin:20px; }} table {{ border-collapse: collapse; width:100%; font-size:10px; }} th {{ background:#1a3a4a; color:white; padding:5px; }} td {{ border:1px solid #ddd; padding:4px; }}</style></head><body><h1>Cenoura & Bronze - Clientes Ausentes no Mês</h1>{df_cen_ausentes.to_html(index=False)}</body></html>"""
        st.download_button("📥 Baixar PDF (Clientes Ausentes)", data=html_cen_ausentes.encode('utf-8'),
                           file_name=f'cenoura_ausentes_{datetime.now().strftime("%Y%m%d")}.html',
                           mime='text/html', use_container_width=True)
    else:
        st.info("Todos os clientes atendidos na janela compraram no mês atual.")
else:
    st.warning("Nenhum dado da Linha Cenoura & Bronze para os filtros atuais.")

st.divider()

# ============================================================
# RELATÓRIO BATALHA NAVAL (COM SELETOR DE PERÍODO)
# ============================================================
st.subheader("📋 Relatório Batalha Naval")

meses_batalha = sorted(df_relatorio_base['Mês_Ano'].dropna().unique())
if not meses_batalha:
    st.warning("Nenhum dado disponível para o relatório.")
    st.stop()

col_bat1, col_bat2 = st.columns(2)
with col_bat1:
    mes_bat_inicio = st.selectbox("Mês início:", options=meses_batalha, index=0, key='mes_bat_inicio')
with col_bat2:
    mes_bat_fim = st.selectbox("Mês fim:", options=meses_batalha, index=len(meses_batalha)-1, key='mes_bat_fim')

if mes_bat_inicio <= mes_bat_fim:
    df_relatorio = df_relatorio_base[(df_relatorio_base['Mês_Ano'] >= mes_bat_inicio) & (df_relatorio_base['Mês_Ano'] <= mes_bat_fim)]
else:
    st.warning("Mês início deve ser menor ou igual ao mês fim.")
    st.stop()

matriz = df_relatorio.pivot_table(index='codigo_cliente', columns='Nome_Fabricante', aggfunc='size', fill_value=0)
mapa_nomes = df_relatorio[['codigo_cliente', 'nome_cliente']].drop_duplicates('codigo_cliente')
mapa_nomes_dict = dict(zip(mapa_nomes['codigo_cliente'], mapa_nomes['nome_cliente']))
matriz_bin = (matriz > 0).astype(int)
matriz_bin['Nome_Cliente'] = matriz.index.map(lambda x: mapa_nomes_dict.get(x, 'N/A'))
matriz_bin['Total_Indústrias'] = matriz_bin.drop(columns=['Nome_Cliente']).sum(axis=1)
matriz_bin = matriz_bin.reset_index().rename(columns={'codigo_cliente': 'Código'})
colunas_fabricantes = [c for c in matriz_bin.columns if c not in ['Código', 'Nome_Cliente', 'Total_Indústrias']]
matriz_bin = matriz_bin[['Código', 'Nome_Cliente'] + colunas_fabricantes + ['Total_Indústrias']]

st.metric("📊 Total de Clientes no Relatório", len(matriz_bin))

col1, col2 = st.columns(2)
with col1:
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        matriz_bin.to_excel(writer, index=False, sheet_name='Batalha Naval')
    st.download_button("📥 Baixar Excel", data=output.getvalue(),
                       file_name=f'batalha_naval_{datetime.now().strftime("%Y%m%d")}.xlsx',
                       mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', use_container_width=True)
with col2:
    html_pdf = f"""
    <html><head><meta charset="UTF-8"><style>
        body {{ font-family: Arial, sans-serif; margin: 20px; }}
        h1 {{ text-align: center; color: #1a3a4a; font-size: 18px; }}
        h2 {{ text-align: center; color: #666; font-size: 12px; font-weight: normal; }}
        table {{ border-collapse: collapse; width: 100%; font-size: 8px; }}
        th {{ background-color: #1a3a4a; color: white; padding: 6px 4px; text-align: center; }}
        td {{ padding: 4px; text-align: center; border: 1px solid #ddd; }}
        tr:nth-child(even) {{ background-color: #f9f9f9; }}
        .positivo {{ background-color: #0F5220; color: white; }}
        .negativo {{ background-color: #8B0000; color: white; }}
        .footer {{ text-align: center; font-size: 10px; color: #999; margin-top: 20px; }}
    </style></head><body>
        <h1>Relatório Batalha Naval</h1>
        <h2>4 Elos Distribuidora Ltda. - Centro de Custo 622 | Gerado em: {datetime.now().strftime('%d/%m/%Y %H:%M')}</h2>
        <table><thead><tr><th>Código</th><th>Cliente</th>"""
    for col in colunas_fabricantes:
        html_pdf += f"<th>{col}</th>"
    html_pdf += "<th>Total</th></tr></thead><tbody>"
    for _, row in matriz_bin.iterrows():
        html_pdf += "<tr>"
        html_pdf += f"<td>{row['Código']}</td><td style='text-align:left;'>{row['Nome_Cliente']}</td>"
        for col in colunas_fabricantes:
            valor = row[col]
            classe = "positivo" if valor == 1 else "negativo"
            html_pdf += f"<td class='{classe}'>{valor}</td>"
        html_pdf += f"<td><strong>{row['Total_Indústrias']}</strong></td></tr>"
    html_pdf += f"</tbody></table><div class='footer'>4 Elos Distribuidora Ltda. - Centro de Custo 622 | Total: {len(matriz_bin)} clientes | Cobertura Total: {matriz_bin['Total_Indústrias'].sum()} coberturas</div></body></html>"
    st.download_button("📥 Baixar PDF (HTML)", data=html_pdf.encode('utf-8'),
                       file_name=f'batalha_naval_{datetime.now().strftime("%Y%m%d")}.html',
                       mime='text/html', use_container_width=True)
    st.caption("💡 Abra o arquivo HTML e salve como PDF (Ctrl+P)")

with st.expander("👁️ Visualizar tabela"):
    st.dataframe(matriz_bin, use_container_width=True, hide_index=True)
st.divider()

# ============================================================
# FICHA DO CLIENTE (COM SELETOR DE PERÍODO)
# ============================================================
st.subheader("🔍 Ficha do Cliente")

meses_ficha = sorted(df_relatorio_base['Mês_Ano'].dropna().unique())
if not meses_ficha:
    st.warning("Nenhum dado disponível para a ficha.")
    st.stop()

col_fich1, col_fich2 = st.columns(2)
with col_fich1:
    mes_ficha_inicio = st.selectbox("Mês início:", options=meses_ficha, index=0, key='mes_ficha_inicio')
with col_fich2:
    mes_ficha_fim = st.selectbox("Mês fim:", options=meses_ficha, index=len(meses_ficha)-1, key='mes_ficha_fim')

if mes_ficha_inicio <= mes_ficha_fim:
    df_ficha = df_relatorio_base[(df_relatorio_base['Mês_Ano'] >= mes_ficha_inicio) & (df_relatorio_base['Mês_Ano'] <= mes_ficha_fim)]
else:
    st.warning("Mês início deve ser menor ou igual ao mês fim.")
    st.stop()

try:
    df_clientes_unicos = df_ficha[['codigo_cliente', 'nome_cliente']].drop_duplicates().dropna()
    df_clientes_unicos['cliente_label'] = df_clientes_unicos['codigo_cliente'].astype(str) + ' - ' + df_clientes_unicos['nome_cliente'].astype(str)
    lista_clientes = sorted(df_clientes_unicos['cliente_label'].unique())
except:
    lista_clientes = []

if lista_clientes:
    cliente_sel = st.selectbox("Selecione um cliente:", lista_clientes, key='ficha_cliente')
    if cliente_sel:
        codigo = cliente_sel.split(' - ')[0].strip()
        df_cliente = df_ficha[df_ficha['codigo_cliente'].astype(str).str.strip() == codigo]
        if not df_cliente.empty:
            st.write(f"**Código:** {codigo}")
            st.write(f"**Nome:** {df_cliente['nome_cliente'].iloc[0]}")
            st.write(f"**Coligação:** {df_cliente['Cliente_Coligacao'].iloc[0]}")
            st.write(f"**Vendedor:** {df_cliente['nome_vendedor'].iloc[0]}")
            st.write(f"**Coordenador:** {df_cliente['Nome_Coordenador'].iloc[0]}")

            st.write("**Positivação por Indústria e Mês:**")
            meses_disp = sorted(df_cliente['Mês_Ano'].dropna().unique())
            if meses_disp:
                tabela = []
                for ind in (INDUSTRIAS_PERMITIDAS if pasta_selecionada != "Todas" else TODAS_INDUSTRIAS):
                    linha = {'Indústria': ind}
                    for m in meses_disp:
                        linha[m] = '✅' if ((df_cliente['Nome_Fabricante'] == ind) & (df_cliente['Mês_Ano'] == m)).any() else '❌'
                    linha['Total'] = sum(1 for m in meses_disp if linha[m] == '✅')
                    tabela.append(linha)
                df_tab = pd.DataFrame(tabela)
                st.dataframe(df_tab, use_container_width=True, hide_index=True)

                output_ficha = BytesIO()
                with pd.ExcelWriter(output_ficha, engine='openpyxl') as writer:
                    df_tab.to_excel(writer, index=False, sheet_name='Ficha Cliente')
                st.download_button("📥 Baixar Excel (Ficha do Cliente)", data=output_ficha.getvalue(),
                                   file_name=f'ficha_cliente_{codigo}_{datetime.now().strftime("%Y%m%d_%H%M")}.xlsx',
                                   mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', use_container_width=True)

                pos_industrias = sum(1 for l in tabela if l['Total'] > 0)
                st.metric("Indústrias Positivadas", f"{pos_industrias} de {len(tabela)}")
                st.metric("Cobertura Total do Cliente", df_cliente[['codigo_cliente', 'Nome_Fabricante']].dropna().drop_duplicates().shape[0])
            else:
                st.warning("Nenhum dado mensal.")
        else:
            st.warning("Cliente não encontrado.")
else:
    st.warning("Nenhum cliente encontrado.")
