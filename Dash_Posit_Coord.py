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
st.set_page_config(
    page_title="Dashboard Coordenador (Teste) - Batalha Naval",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed"
)

st.markdown("""
<style>
    a[href*="/edit"] { display: none !important; }
    a[href*="github.com"] { display: none !important; }
    
    div.stButton > button {
        width: 100%;
        height: 3.2rem;
        white-space: normal;
        font-size: 14px;
        padding: 0.4rem 0.6rem;
    }
</style>
""", unsafe_allow_html=True)

st.title("📊 Dashboard de Positivação e Cobertura (Teste)")
st.caption("4 Elos Distribuidora Ltda. - Centro de Custo 622")

# ============================================================
# CARREGAR DADOS (Google Sheets)
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
        st.error(f"Erro ao carregar dados: {str(e)}")
        st.stop()

    data_dados = datetime.now(ZoneInfo('America/Sao_Paulo')).strftime('%d/%m/%Y %H:%M')

    def normalizar_texto(texto):
        texto = unicodedata.normalize('NFKD', texto)
        texto = texto.encode('ASCII', 'ignore').decode('ASCII')
        texto = texto.lower().strip()
        texto = re.sub(r'\s+', ' ', texto)
        return texto

    df_base.columns = [str(col).strip() for col in df_base.columns]
    base_rename = {}

    for col in df_base.columns:
        col_norm = normalizar_texto(col)
        if 'codigo cliente' in col_norm or ('codigo' in col_norm and 'cliente' in col_norm):
            base_rename[col] = 'codigo_cliente'
        elif col_norm == 'cliente' or ('cliente' in col_norm and 'nome' in col_norm):
            base_rename[col] = 'nome_cliente'
        elif 'vendedor' in col_norm:
            base_rename[col] = 'nome_vendedor_base'
        elif 'coligacao' in col_norm or 'coliga' in col_norm:
            base_rename[col] = 'Cliente_Coligacao'
        elif 'coordenador' in col_norm:
            base_rename[col] = 'Nome_Coordenador'
        elif 'municipio' in col_norm:
            base_rename[col] = 'Municipio'
        elif 'canal' in col_norm:
            base_rename[col] = 'Canal'
        elif 'segmento' in col_norm:
            base_rename[col] = 'Segmento'

    df_base = df_base.rename(columns=base_rename)

    if 'nome_cliente' not in df_base.columns:
        for col in df_base.columns:
            if normalizar_texto(col) == 'cliente':
                df_base.rename(columns={col: 'nome_cliente'}, inplace=True)
                break

    df_bi.columns = [str(col).strip() for col in df_bi.columns]
    bi_rename = {}

    for col in df_bi.columns:
        col_norm = normalizar_texto(col)
        if 'codigo cliente' in col_norm:
            bi_rename[col] = 'codigo_cliente'
        elif 'vendedor' in col_norm and 'ajustado' in col_norm:
            bi_rename[col] = 'nome_vendedor_bi'
        elif 'ano' in col_norm and 'mes' in col_norm:
            bi_rename[col] = 'Ano_e_Mes'
        elif 'fabricante' in col_norm:
            bi_rename[col] = 'Nome_Fabricante'
        elif 'linha de produto' in col_norm:
            bi_rename[col] = 'Linha_Produto'
        elif 'categoria' in col_norm:
            bi_rename[col] = 'Categoria'
        elif 'valor das vendas' in col_norm:
            bi_rename[col] = 'Valor_Vendas'

    df_bi = df_bi.rename(columns=bi_rename)

    if 'Ano_e_Mes' not in df_bi.columns:
        for col in df_bi.columns:
            if 'ano' in col.lower() and 'mes' in col.lower():
                df_bi.rename(columns={col: 'Ano_e_Mes'}, inplace=True)
                break

    df_bi['Data'] = pd.to_datetime(df_bi['Ano_e_Mes'] + '-01', errors='coerce')
    df_bi['Mes_Num'] = df_bi['Data'].dt.month
    df_bi['Ano'] = df_bi['Data'].dt.year
    df_bi['Mes_Ano'] = df_bi['Data'].dt.to_period('M').astype(str)

    df_base_dedup = df_base.drop_duplicates(subset=['codigo_cliente'], keep='first')

    df_merged = df_bi.merge(
        df_base[['codigo_cliente', 'nome_cliente', 'nome_vendedor_base', 'Cliente_Coligacao', 
                 'Nome_Coordenador', 'Municipio', 'Canal', 'Segmento']],
        left_on=['codigo_cliente', 'nome_vendedor_bi'],
        right_on=['codigo_cliente', 'nome_vendedor_base'],
        how='left'
    )

    for col in ['nome_cliente', 'Cliente_Coligacao', 'Nome_Coordenador', 'Municipio', 'Canal', 'Segmento']:
        if col in df_base.columns:
            fallback_map = df_base_dedup.set_index('codigo_cliente')[col].to_dict()
            df_merged[col] = df_merged[col].fillna(df_merged['codigo_cliente'].map(fallback_map))

    df_merged['nome_vendedor'] = df_merged['nome_vendedor_bi']

    fabricante_pasta = dict(zip(df_fabricantes['Nome Fabricante'], df_fabricantes['Pasta']))
    vendedor_pasta = dict(zip(df_vendedores['Vendedor'], df_vendedores['Pasta']))

    return df_base, df_bi, df_merged, data_dados, fabricante_pasta, vendedor_pasta

df_base, df_bi, df_merged, data_dados, fabricante_pasta, vendedor_pasta = load_data()

TODAS_INDUSTRIAS = sorted([i for i in df_bi['Nome_Fabricante'].dropna().unique() if str(i).strip() != ''])

# ============================================================
# FUNÇÕES AUXILIARES
# ============================================================
def aplicar_filtros_comuns(df, incluir_mes=True):
    df = df.copy()

    if pasta_selecionada not in ["Todas", "PVA"]:
        vendedores_pasta = [v for v in df_base['nome_vendedor_base'].unique() 
                           if vendedor_pasta.get(v) == pasta_selecionada]
        df = df[df['nome_vendedor'].isin(vendedores_pasta)]

    if vendedor_selecionado != "Todos":
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

    if incluir_mes and mes_selecionado != "Todos":
        mes_num = int(mes_selecionado.split(' - ')[0])
        anos_do_mes = df[df['Mes_Num'] == mes_num]['Ano'].unique()
        ano_ref = max(anos_do_mes) if len(anos_do_mes) > 0 else df['Ano'].max()
        mes_ano_ref = f"{ano_ref}-{mes_num:02d}"
        df = df[df['Mes_Ano'] == mes_ano_ref]

    if industria_selecionada_lista:
        df = df[df['Nome_Fabricante'].isin(industria_selecionada_lista)]
    if categoria_selecionada:
        df = df[df['Categoria'].isin(categoria_selecionada)]
    if linha_selecionada:
        df = df[df['Linha_Produto'].isin(linha_selecionada)]

    return df

def calcular_janela_movel(df_historico, mes_selecionado, janela_meses):
    if mes_selecionado == "Todos":
        return df_historico.copy()

    mes_num = int(mes_selecionado.split(' - ')[0])
    anos_do_mes = df_historico[df_historico['Mes_Num'] == mes_num]['Ano'].unique()
    ano_ref = max(anos_do_mes) if len(anos_do_mes) > 0 else df_historico['Ano'].max()

    meses_janela = []
    for i in range(1, janela_meses + 1):
        mes = mes_num - i
        ano = ano_ref
        while mes <= 0:
            mes += 12
            ano -= 1
        meses_janela.append((ano, mes))

    cond_janela = pd.Series(False, index=df_historico.index)
    for a, m in meses_janela:
        cond_janela |= (df_historico['Ano'] == a) & (df_historico['Mes_Num'] == m)

    return df_historico[cond_janela]

# ============================================================
# FILTROS
# ============================================================
with st.expander("🎯 Filtros", expanded=True):
    st.markdown("**Equipe de Vendas**")
    col_eq1, col_eq2, col_eq3 = st.columns(3)

    with col_eq1:
        lista_coordenadores = ["Todos"] + sorted(df_base['Nome_Coordenador'].dropna().unique().tolist())
        coordenador_selecionado = st.selectbox("Coordenador", lista_coordenadores, key='coord_top')

    with col_eq2:
        if coordenador_selecionado != "Todos":
            vendedores_base = df_base[df_base['Nome_Coordenador'] == coordenador_selecionado]['nome_vendedor_base'].dropna().unique()
        else:
            vendedores_base = df_base['nome_vendedor_base'].dropna().unique()
        lista_vendedores = ["Todos"] + sorted(vendedores_base)
        vendedor_selecionado = st.selectbox("Vendedor", lista_vendedores, key='vend_top')

    with col_eq3:
        lista_pastas = ["Todas", "PA", "PV", "PVA"]
        pasta_selecionada = st.selectbox("Pasta", lista_pastas, key='pasta_top')

        if pasta_selecionada in ["Todas", "PVA"]:
            INDUSTRIAS_PERMITIDAS = TODAS_INDUSTRIAS.copy()
        else:
            INDUSTRIAS_PERMITIDAS = [ind for ind in TODAS_INDUSTRIAS if fabricante_pasta.get(ind) == pasta_selecionada]

    st.markdown("**Produto**")
    col_prod1, col_prod2, col_prod3 = st.columns(3)

    with col_prod1:
        INDUSTRIAS_DISPONIVEIS = TODAS_INDUSTRIAS.copy() if pasta_selecionada in ["Todas", "PVA"] else [ind for ind in TODAS_INDUSTRIAS if fabricante_pasta.get(ind) == pasta_selecionada]
        industria_selecionada_lista = st.multiselect("Indústria(s)", options=INDUSTRIAS_DISPONIVEIS, key='ind_top')

    with col_prod2:
        categoria_selecionada = st.multiselect("Categoria(s)", options=sorted(df_bi['Categoria'].dropna().unique()), key='cat_top')

    with col_prod3:
        linha_selecionada = st.multiselect("Linha(s) de Produto", options=sorted(df_bi['Linha_Produto'].dropna().unique()), key='linha_top')

    st.markdown("**Localização**")
    col_loc1, col_loc2, col_loc3, col_loc4 = st.columns(4)

    with col_loc1:
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
        coligacao_selecionada = st.selectbox("Coligação", lista_coligacoes, key='colig_top')

    with col_loc2:
        canal_selecionado = st.multiselect("Canal(is)", options=sorted(df_base['Canal'].dropna().unique()), key='canal_top')

    with col_loc3:
        segmento_selecionado = st.multiselect("Segmento(s)", options=sorted(df_base['Segmento'].dropna().unique()), key='seg_top')

    with col_loc4:
        municipio_selecionado = st.multiselect("Município(s)", options=sorted(df_base['Municipio'].dropna().unique()), key='muni_top')

    st.markdown("**Período e Metas**")
    col_per1, col_per2, col_per3, col_per4 = st.columns(4)

    with col_per1:
        meses_disponiveis = sorted(df_merged['Mes_Num'].dropna().unique())
        meses_nomes = {1:'Janeiro', 2:'Fevereiro', 3:'Março', 4:'Abril', 5:'Maio', 6:'Junho', 
                       7:'Julho', 8:'Agosto', 9:'Setembro', 10:'Outubro', 11:'Novembro', 12:'Dezembro'}
        lista_meses = ["Todos"] + [f"{int(m):02d} - {meses_nomes.get(int(m), '')}" for m in meses_disponiveis]

        if 'mes' not in st.session_state or st.session_state['mes'] not in lista_meses:
            if meses_disponiveis:
                ultimo_mes = max(meses_disponiveis)
                st.session_state['mes'] = f"{int(ultimo_mes):02d} - {meses_nomes.get(int(ultimo_mes), '')}"
            else:
                st.session_state['mes'] = 'Todos'

        indice_atual = lista_meses.index(st.session_state['mes']) if st.session_state['mes'] in lista_meses else 0
        mes_selecionado = st.selectbox("Mês", lista_meses, index=indice_atual, key='mes_top')
        st.session_state['mes'] = mes_selecionado

    with col_per2:
        janela_meses = st.slider("Janela da Base Ativa (meses)", 3, 6, 6, key='janela_top')

    with col_per3:
        meta_ativa = st.number_input("Meta Base Ativa (%)", 0, 100, 70, key='meta_ativa_top')

    with col_per4:
        meta_total = st.number_input("Meta Carteira Total (%)", 0, 100, 50, key='meta_total_top')

# ============================================================
# APLICAR FILTROS
# ============================================================
df_filtrado = aplicar_filtros_comuns(df_merged, incluir_mes=True)
df_historico = aplicar_filtros_comuns(df_merged, incluir_mes=False)
df_relatorio_base = aplicar_filtros_comuns(df_merged, incluir_mes=False)
df_historico_janela = calcular_janela_movel(df_historico, mes_selecionado, janela_meses)

# ============================================================
# NAVEGAÇÃO ORGANIZADA (BOTÕES DE MESMA LARGURA E ALTURA)
# ============================================================
st.markdown("---")
st.markdown("### 🧭 Navegação de Módulos")

opcoes_linha_1 = [
    "🏠 Visão Geral",
    "👥 Performance Vendedor",
    "📍 Positivação por Município",
    "🏷️ Positivação por Segmento",
    "🔀 Oportunidades Cruzadas"
]

opcoes_linha_2 = [
    "🟢 Softys Falcon",
    "🟠 Kenvue Perfumaria",
    "🟤 Cenoura & Bronze",
    "📋 Batalha Naval",
    "🔍 Ficha do Cliente"
]

if 'nav' not in st.session_state:
    st.session_state['nav'] = "🏠 Visão Geral"

cols_1 = st.columns(len(opcoes_linha_1))
for i, nome_op in enumerate(opcoes_linha_1):
    with cols_1[i]:
        tipo_botao = "primary" if st.session_state['nav'] == nome_op else "secondary"
        if st.button(nome_op, use_container_width=True, type=tipo_botao, key=f"btn_l1_{i}"):
            st.session_state['nav'] = nome_op
            st.rerun()

cols_2 = st.columns(len(opcoes_linha_2))
for i, nome_op in enumerate(opcoes_linha_2):
    with cols_2[i]:
        tipo_botao = "primary" if st.session_state['nav'] == nome_op else "secondary"
        if st.button(nome_op, use_container_width=True, type=tipo_botao, key=f"btn_l2_{i}"):
            st.session_state['nav'] = nome_op
            st.rerun()

st.markdown("---")
opcao = st.session_state['nav']

# ============================================================
# PÁGINA: VISÃO GERAL
# ============================================================
if opcao == "🏠 Visão Geral":
    carteira_ativa_total = df_historico_janela[df_historico_janela['Nome_Fabricante'].notna()]['codigo_cliente'].nunique()
    positivados_periodo = df_filtrado[df_filtrado['Nome_Fabricante'].notna()]['codigo_cliente'].nunique()
    pct_ativa = (positivados_periodo / carteira_ativa_total * 100) if carteira_ativa_total > 0 else 0

    st.subheader("📅 Carteira Ativa (Janela Móvel)")
    col_a1, col_a2, col_a3 = st.columns(3)
    col_a1.metric("Carteira Ativa (últimos {} meses)".format(janela_meses), carteira_ativa_total)
    col_a2.metric("Positivados no Mês", positivados_periodo)
    col_a3.metric("% Positivação (Ativa)", f"{pct_ativa:.1f}%")

    if mes_selecionado != "Todos" and ' - ' in str(mes_selecionado):
        try:
            mes_num = int(mes_selecionado.split(' - ')[0])
        except ValueError:
            mes_num = 12
        
        anos_do_mes = df_historico[df_historico['Mes_Num'] == mes_num]['Ano'].unique() if not df_historico.empty else []
        ano_ytd = int(max(anos_do_mes)) if len(anos_do_mes) > 0 else (int(df_historico['Ano'].max()) if not df_historico.empty and pd.notna(df_historico['Ano'].max()) else datetime.now().year)
    else:
        ano_ytd = int(df_historico['Ano'].max()) if not df_historico.empty and pd.notna(df_historico['Ano'].max()) else datetime.now().year
        mes_num = 12

    df_historico_ano = df_historico[df_historico['Ano'] == ano_ytd].copy()
    df_mensal_ativos = df_historico_ano[df_historico_ano['Nome_Fabricante'].notna()]
    
    mensal_pos = df_mensal_ativos.groupby('Mes_Ano')['codigo_cliente'].nunique().reset_index()
    mensal_pos.columns = ['Mês', 'Clientes Positivados']

    df_ytd = df_historico_ano[
        (df_historico_ano['Mes_Num'] <= mes_num) & 
        (df_historico_ano['Nome_Fabricante'].notna())
    ]
    ytd_total = int(df_ytd['codigo_cliente'].nunique())

    lista_meses_grafico = list(mensal_pos['Mês']) if not mensal_pos.empty else []
    lista_valores_grafico = list(mensal_pos['Clientes Positivados']) if not mensal_pos.empty else []

    if 'YTD' in lista_meses_grafico:
        idx_ytd = lista_meses_grafico.index('YTD')
        lista_valores_grafico[idx_ytd] = ytd_total
    else:
        lista_meses_grafico.append('YTD')
        lista_valores_grafico.append(ytd_total)

    chart_data = pd.DataFrame({
        'Mês': [str(m) for m in lista_meses_grafico],
        'Clientes Positivados': lista_valores_grafico
    })

    colors = ['#2E8B57' if str(mes) != 'YTD' else '#D9534F' for mes in chart_data['Mês']]

    fig = go.Figure(go.Bar(
        x=chart_data['Mês'],
        y=chart_data['Clientes Positivados'],
        text=chart_data['Clientes Positivados'],
        textposition='outside',
        marker_color=colors
    ))
    
    max_val = chart_data['Clientes Positivados'].max() if not chart_data.empty else 1
    if pd.isna(max_val) or max_val == 0:
        max_val = 1

    fig.update_layout(
        title=f'Positivação Carteira Ativa (Mensal + YTD {ano_ytd} - YTD em destaque vermelho)', 
        yaxis_title='Clientes Positivados',
        yaxis_range=[0, max_val * 1.15],
        xaxis_type='category'
    )
    st.plotly_chart(fig, use_container_width=True)

# ============================================================
# PÁGINA: PERFORMANCE VENDEDOR
# ============================================================
elif opcao == "👥 Performance Vendedor":
    df_base_perf = df_base.copy()
    if coordenador_selecionado != "Todos":
        df_base_perf = df_base_perf[df_base_perf['Nome_Coordenador'] == coordenador_selecionado]
    if vendedor_selecionado != "Todos":
        df_base_perf = df_base_perf[df_base_perf['nome_vendedor_base'] == vendedor_selecionado]
    if pasta_selecionada != "Todas":
        vendedores_da_pasta = [v for v in df_base_perf['nome_vendedor_base'].unique() 
                               if vendedor_pasta.get(v) == pasta_selecionada]
        df_base_perf = df_base_perf[df_base_perf['nome_vendedor_base'].isin(vendedores_da_pasta)]

    vendedores_base = [vendedor_selecionado] if vendedor_selecionado != "Todos" else df_filtrado['nome_vendedor'].dropna().unique()

    perf_list = []
    for vendedor in vendedores_base:
        pasta_v = vendedor_pasta.get(vendedor, "")
        clientes_carteira = df_base_perf[df_base_perf['nome_vendedor_base'] == vendedor]['codigo_cliente'].nunique()
        clientes_ativos_hist = df_historico_janela[df_historico_janela['nome_vendedor'] == vendedor]['codigo_cliente'].nunique()
        df_bi_vendedor = df_filtrado[df_filtrado['nome_vendedor'] == vendedor]
        clientes_pos = df_bi_vendedor[df_bi_vendedor['Nome_Fabricante'].notna()]['codigo_cliente'].nunique()
        pct_ativa_vend = (clientes_pos / clientes_ativos_hist * 100) if clientes_ativos_hist > 0 else 0
        pct_total_vend = (clientes_pos / clientes_carteira * 100) if clientes_carteira > 0 else 0
        perf_list.append({
            'Vendedor': vendedor, 'Pasta': pasta_v,
            'Total_Clientes': clientes_carteira, 'Clientes_Ativos_Hist': clientes_ativos_hist,
            'Clientes_Positivados': clientes_pos,
            '%_Positivação_Ativa': round(pct_ativa_vend, 1), '%_Positivação_Total': round(pct_total_vend, 1)
        })
    perf_vendedor = pd.DataFrame(perf_list).sort_values('%_Positivação_Ativa', ascending=False)

    fig_ativa = px.bar(perf_vendedor, x='Vendedor', y='%_Positivação_Ativa', title='% Positivação (Base Ativa)',
                       text=perf_vendedor['%_Positivação_Ativa'].apply(lambda x: f'{x:.1f}%'),
                       color='%_Positivação_Ativa', color_continuous_scale='Greens')
    fig_ativa.add_hline(y=meta_ativa, line_dash="dash", line_color="red", annotation_text=f"Meta {meta_ativa}%")
    fig_ativa.update_traces(textposition='outside')
    fig_ativa.update_layout(xaxis_title="", yaxis_title="% Positivação", yaxis_range=[0, 105])
    st.plotly_chart(fig_ativa, use_container_width=True)

# ============================================================
# PÁGINA: POSITIVAÇÃO POR MUNICÍPIO
# ============================================================
elif opcao == "📍 Positivação por Município":
    st.subheader("📍 Positivação por Município")
    df_munic = df_filtrado.groupby('Municipio')['codigo_cliente'].nunique().reset_index()
    df_munic.columns = ['Município', 'Clientes Positivados']
    df_munic = df_munic.sort_values('Clientes Positivados', ascending=False)
    st.dataframe(df_munic, use_container_width=True, hide_index=True)

# ============================================================
# PÁGINA: POSITIVAÇÃO POR SEGMENTO
# ============================================================
elif opcao == "🏷️ Positivação por Segmento":
    st.subheader("🏷️ Positivação por Segmento")
    df_seg = df_filtrado.groupby('Segmento')['codigo_cliente'].nunique().reset_index()
    df_seg.columns = ['Segmento', 'Clientes Positivados']
    df_seg = df_seg.sort_values('Clientes Positivados', ascending=False)
    st.dataframe(df_seg, use_container_width=True, hide_index=True)

# ============================================================
# PÁGINA: OPORTUNIDADES CRUZADAS
# ============================================================
elif opcao == "🔀 Oportunidades Cruzadas":
    st.subheader("🔀 Oportunidades Cruzadas")
    st.info("Módulo ativo.")

# ============================================================
# PÁGINA: SOFTYS FALCON (COM COLUNA YTD CORRIGIDA)
# ============================================================
elif opcao == "🟢 Softys Falcon":
    df_softys = df_relatorio_base[df_relatorio_base['Nome_Fabricante'] == 'SOFTYS FALCON'].copy()

    if not df_softys.empty:
        st.subheader("🟢 Foco Estratégico: Softys Falcon")

        ano_atual = df_softys['Ano'].max()
        df_softys_ano = df_softys[df_softys['Ano'] == ano_atual]

        pivot_mensal = df_softys_ano.pivot_table(index='Categoria', columns='Mes_Ano', 
                                                  values='codigo_cliente', aggfunc='nunique', fill_value=0)
        ytd_series = df_softys_ano.groupby('Categoria')['codigo_cliente'].nunique()
        
        tabela = pivot_mensal.copy()
        tabela['YTD'] = ytd_series.fillna(0)
        tabela = tabela.reset_index()

        st.markdown("**Positivação por Categoria (Mensal + YTD)**")
        st.dataframe(tabela, use_container_width=True, hide_index=True)
    else:
        st.warning("Nenhum dado da Softys Falcon para os filtros atuais.")

# ============================================================
# PÁGINA: KENVUE PERFUMARIA (COM META DE 50%)
# ============================================================
elif opcao == "🟠 Kenvue Perfumaria":
    vendedores_kenvue = [v for v in df_base['nome_vendedor_base'].unique()
                         if vendedor_pasta.get(v) in ['PA', 'PVA']]

    df_perfumarias_ativas = df_historico_janela[
        (df_historico_janela['Canal'] == 'PERFUMARIA') &
        (df_historico_janela['nome_vendedor'].isin(vendedores_kenvue))
    ].copy()

    if not df_perfumarias_ativas.empty:
        df_kenvue_mes = df_filtrado[
            (df_filtrado['Nome_Fabricante'] == 'KENVUE') &
            (df_filtrado['Canal'] == 'PERFUMARIA') &
            (df_filtrado['nome_vendedor'].isin(vendedores_kenvue))
        ].copy()

        if not df_kenvue_mes.empty:
            clientes_kenvue_mes = df_kenvue_mes['codigo_cliente'].unique()
            total_perfumarias_ativas = df_perfumarias_ativas['codigo_cliente'].nunique()
            atendidos = len(clientes_kenvue_mes)
            pct_atendido = (atendidos / total_perfumarias_ativas * 100) if total_perfumarias_ativas > 0 else 0

            st.subheader("🟠 Foco Estratégico: Kenvue no Canal Perfumaria")
            st.metric("Perfumarias Ativas", total_perfumarias_ativas)
            st.metric("Atendidas com Kenvue", f"{atendidos} ({pct_atendido:.1f}%)", 
                      delta=f"{pct_atendido - 50:.1f}% vs Meta 50%", 
                      delta_color="normal" if pct_atendido >= 50 else "inverse")

# ============================================================
# PÁGINA: CENOURA & BRONZE (COM GRÁFICO E TABELA EXPANSÍVEL)
# ============================================================
elif opcao == "🟤 Cenoura & Bronze":
    df_cenoura = df_relatorio_base[df_relatorio_base['Linha_Produto'] == 'CENOURA & BRONZE'].copy()

    if not df_cenoura.empty:
        st.subheader("🟤 Foco Estratégico: Linha Cenoura & Bronze")
        
        df_evolucao = df_cenoura.groupby('Mes_Ano')['codigo_cliente'].nunique().reset_index()
        df_evolucao.columns = ['Mês', 'Clientes']
        
        fig_cenoura = go.Figure(go.Bar(
            x=df_evolucao['Mês'], y=df_evolucao['Clientes'], 
            marker_color='#CD853F', text=df_evolucao['Clientes'], textposition='outside'
        ))
        fig_cenoura.update_layout(title='Evolução de Clientes (Cenoura & Bronze)', yaxis_title='Clientes')
        st.plotly_chart(fig_cenoura, use_container_width=True)

        with st.expander("Ver Tabela Detalhada"):
            st.dataframe(df_evolucao, use_container_width=True, hide_index=True)
    else:
        st.warning("Nenhum dado de Cenoura & Bronze.")

# ============================================================
# PÁGINA: BATALHA NAVAL
# ============================================================
elif opcao == "📋 Batalha Naval":
    st.subheader("📋 Batalha Naval")

# ============================================================
# PÁGINA: FICHA DO CLIENTE
# ============================================================
elif opcao == "🔍 Ficha do Cliente":
    st.subheader("🔍 Ficha do Cliente")
