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
    initial_sidebar_state="expanded" # Expandido para mostrar o novo menu
)

st.markdown("""
<style>
    a[href*="/edit"] { display: none !important; }
    a[href*="github.com"] { display: none !important; }
</style>
""", unsafe_allow_html=True)

# ============================================================
# CARREGAR DADOS (Google Sheets)
# ============================================================
SHEET_ID = "100LtVtmS76bT2CJd-EIb-bHTgX3F1BVm8Er5vUa-VYQ"

@st.cache_data(ttl=300)
def load_data():
    """Carrega e normaliza todos os dados do Google Sheets"""
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
        texto = unicodedata.normalize('NFKD', str(texto))
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
    df_bi['MŒs'] = df_bi['Data'].dt.month
    df_bi['Ano'] = df_bi['Data'].dt.year
    df_bi['MŒs_Ano'] = df_bi['Data'].dt.to_period('M').astype(str)

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
def gerar_pdf_html(tabela_df, titulo):
    try:
        from weasyprint import HTML
        html_content = f"""
        <html>
        <head><style>
            @page {{ size: A4 landscape; margin: 1cm; }}
            body {{ font-family: Arial; margin: 20px; }}
            table {{ border-collapse: collapse; width: 100%; font-size: 9px; }}
            th {{ background: #1a3a4a; color: white; padding: 6px; border: 1px solid #1a3a4a; }}
            td {{ border: 1px solid #ddd; padding: 4px; text-align: center; }}
        </style></head>
        <body>
            <h1>{titulo}</h1>
            {tabela_df.to_html(index=False, border=1)}
        </body></html>
        """
        pdf_buffer = BytesIO()
        HTML(string=html_content).write_pdf(pdf_buffer)
        return pdf_buffer.getvalue()
    except ImportError:
        return None
    except Exception:
        return None

def aplicar_filtros_comuns(df, incluir_mes=True):
    """Aplicando filtros usando indexação booleana (Otimização 2: sem .copy())"""
    mask = pd.Series(True, index=df.index)

    if pasta_selecionada not in ["Todas", "PVA"]:
        vendedores_pasta = [v for v in df_base['nome_vendedor_base'].unique() if vendedor_pasta.get(v) == pasta_selecionada]
        mask &= df['nome_vendedor'].isin(vendedores_pasta)
    if vendedor_selecionado != "Todos":
        mask &= (df['nome_vendedor'] == vendedor_selecionado)
    if coordenador_selecionado != "Todos":
        mask &= (df['Nome_Coordenador'] == coordenador_selecionado)
    if coligacao_selecionada != "Todas":
        mask &= (df['Cliente_Coligacao'] == coligacao_selecionada)
    if municipio_selecionado:
        mask &= df['Municipio'].isin(municipio_selecionado)
    if canal_selecionado:
        mask &= df['Canal'].isin(canal_selecionado)
    if segmento_selecionado:
        mask &= df['Segmento'].isin(segmento_selecionado)

    if incluir_mes and mes_selecionado != "Todos":
        mes_num = int(mes_selecionado.split(' - ')[0])
        anos_do_mes = df.loc[df['MŒs'] == mes_num, 'Ano'].unique()
        ano_ref = max(anos_do_mes) if len(anos_do_mes) > 0 else df['Ano'].max()
        mask &= (df['MŒs_Ano'] == f"{ano_ref}-{mes_num:02d}")

    if industria_selecionada_lista:
        mask &= df['Nome_Fabricante'].isin(industria_selecionada_lista)
    if categoria_selecionada:
        mask &= df['Categoria'].isin(categoria_selecionada)
    if linha_selecionada:
        mask &= df['Linha_Produto'].isin(linha_selecionada)

    return df[mask]

def calcular_janela_movel(df_historico, mes_selecionado, janela_meses):
    if mes_selecionado == "Todos":
        return df_historico
    mes_num = int(mes_selecionado.split(' - ')[0])
    anos_do_mes = df_historico[df_historico['MŒs'] == mes_num]['Ano'].unique()
    ano_ref = max(anos_do_mes) if len(anos_do_mes) > 0 else df_historico['Ano'].max()

    meses_janela = []
    for i in range(1, janela_meses + 1):
        mes = mes_num - i
        ano = ano_ref
        while mes <= 0:
            mes += 12
            ano -= 1
        meses_janela.append(f"{ano}-{mes:02d}")
    
    return df_historico[df_historico['MŒs_Ano'].isin(meses_janela)]


# ============================================================
# INTERFACE PRINCIPAL E FILTROS
# ============================================================
st.title("📊 Dashboard de Positivação e Cobertura (Teste)")
st.caption(f"4 Elos Distribuidora Ltda. - Atualizado em: {data_dados}")

with st.expander("🎯 Filtros Globais", expanded=False):
    col_eq1, col_eq2, col_eq3 = st.columns(3)
    with col_eq1:
        coordenador_selecionado = st.selectbox("Coordenador", ["Todos"] + sorted(df_base['Nome_Coordenador'].dropna().unique().tolist()))
    with col_eq2:
        vendedores_list = df_base[df_base['Nome_Coordenador'] == coordenador_selecionado]['nome_vendedor_base'].dropna().unique() if coordenador_selecionado != "Todos" else df_base['nome_vendedor_base'].dropna().unique()
        vendedor_selecionado = st.selectbox("Vendedor", ["Todos"] + sorted(vendedores_list))
    with col_eq3:
        pasta_selecionada = st.selectbox("Pasta", ["Todas", "PA", "PV", "PVA"])

    col_prod1, col_prod2, col_prod3 = st.columns(3)
    INDUSTRIAS_DISPONIVEIS = TODAS_INDUSTRIAS if pasta_selecionada in ["Todas", "PVA"] else [i for i in TODAS_INDUSTRIAS if fabricante_pasta.get(i) == pasta_selecionada]
    with col_prod1: industria_selecionada_lista = st.multiselect("Indústria(s)", INDUSTRIAS_DISPONIVEIS)
    with col_prod2: categoria_selecionada = st.multiselect("Categoria(s)", sorted(df_bi['Categoria'].dropna().unique()))
    with col_prod3: linha_selecionada = st.multiselect("Linha(s) de Produto", sorted(df_bi['Linha_Produto'].dropna().unique()))

    col_loc1, col_loc2, col_loc3, col_loc4 = st.columns(4)
    with col_loc1: coligacao_selecionada = st.selectbox("Coligação", ["Todas"] + sorted(df_base['Cliente_Coligacao'].dropna().unique()))
    with col_loc2: canal_selecionado = st.multiselect("Canal", sorted(df_base['Canal'].dropna().unique()))
    with col_loc3: segmento_selecionado = st.multiselect("Segmento", sorted(df_base['Segmento'].dropna().unique()))
    with col_loc4: municipio_selecionado = st.multiselect("Município", sorted(df_base['Municipio'].dropna().unique()))

    col_per1, col_per2, col_per3, col_per4 = st.columns(4)
    meses_disp = sorted(df_merged['MŒs'].dropna().unique())
    meses_nomes = {1:'Jan', 2:'Fev', 3:'Mar', 4:'Abr', 5:'Mai', 6:'Jun', 7:'Jul', 8:'Ago', 9:'Set', 10:'Out', 11:'Nov', 12:'Dez'}
    lista_meses = ["Todos"] + [f"{int(m):02d} - {meses_nomes.get(int(m), '')}" for m in meses_disp]
    
    if 'mes' not in st.session_state: st.session_state['mes'] = lista_meses[-1] if meses_disp else 'Todos'
    
    with col_per1:
        mes_selecionado = st.selectbox("Mês", lista_meses, index=lista_meses.index(st.session_state['mes']))
        st.session_state['mes'] = mes_selecionado
    with col_per2: janela_meses = st.slider("Janela Ativa (meses)", 3, 6, 6)
    with col_per3: meta_ativa = st.number_input("Meta Ativa (%)", 0, 100, 70)
    with col_per4: meta_total = st.number_input("Meta Total (%)", 0, 100, 50)

# Aplicar os filtros aos DataFrames globais
df_filtrado = aplicar_filtros_comuns(df_merged, incluir_mes=True)
df_historico = aplicar_filtros_comuns(df_merged, incluir_mes=False)
df_relatorio_base = aplicar_filtros_comuns(df_merged, incluir_mes=False)
df_historico_janela = calcular_janela_movel(df_historico, mes_selecionado, janela_meses)


# ============================================================
# PÁGINAS (Definidas como Funções - Otimização 3)
# ============================================================

def pagina_visao_geral():
    st.header("🏠 Visão Geral")
    carteira_ativa = df_historico_janela[df_historico_janela['Nome_Fabricante'].notna()]['codigo_cliente'].nunique()
    pos_periodo = df_filtrado[df_filtrado['Nome_Fabricante'].notna()]['codigo_cliente'].nunique()
    
    col1, col2, col3 = st.columns(3)
    col1.metric("Carteira Ativa (Janela)", carteira_ativa)
    col2.metric("Positivados no Mês", pos_periodo)
    col3.metric("% Positivação (Ativa)", f"{(pos_periodo / carteira_ativa * 100) if carteira_ativa else 0:.1f}%")

def pagina_performance_vendedor():
    st.header("👥 Performance por Vendedor")
    
    # OTIMIZAÇÃO 1: Vetorização (groupby) em vez de laço FOR
    # Base de carteira (Aplicando filtros de locação/vendedor na base pura)
    mask_base = pd.Series(True, index=df_base.index)
    if coordenador_selecionado != "Todos": mask_base &= (df_base['Nome_Coordenador'] == coordenador_selecionado)
    if vendedor_selecionado != "Todos": mask_base &= (df_base['nome_vendedor_base'] == vendedor_selecionado)
    if pasta_selecionada != "Todas": mask_base &= df_base['nome_vendedor_base'].map(vendedor_pasta) == pasta_selecionada
    
    df_base_perf = df_base[mask_base]
    
    # 1. Clientes Carteira Total
    carteira = df_base_perf.groupby('nome_vendedor_base')['codigo_cliente'].nunique().reset_index(name='Total_Clientes')
    
    # 2. Clientes Ativos (Janela)
    ativos = df_historico_janela.groupby('nome_vendedor')['codigo_cliente'].nunique().reset_index(name='Clientes_Ativos_Hist')
    
    # 3. Clientes Positivados no Mês
    pos = df_filtrado[df_filtrado['Nome_Fabricante'].notna()].groupby('nome_vendedor')['codigo_cliente'].nunique().reset_index(name='Clientes_Positivados')
    
    # 4. Cobertura (Média e Total)
    cob_base = df_filtrado.dropna(subset=['Nome_Fabricante']).drop_duplicates(['nome_vendedor', 'codigo_cliente', 'Nome_Fabricante'])
    cob_media = cob_base.groupby(['nome_vendedor', 'codigo_cliente']).size().groupby('nome_vendedor').mean().reset_index(name='Cobertura_Media')
    cob_total = cob_base.groupby('nome_vendedor').size().reset_index(name='Cobertura_Total')

    # Merge de todas as métricas vetorizadas
    vendedores = pd.DataFrame({'nome_vendedor': carteira['nome_vendedor_base'].unique()})
    perf = vendedores.merge(carteira, left_on='nome_vendedor', right_on='nome_vendedor_base', how='left')
    perf = perf.merge(ativos, on='nome_vendedor', how='left')
    perf = perf.merge(pos, on='nome_vendedor', how='left')
    perf = perf.merge(cob_media, on='nome_vendedor', how='left')
    perf = perf.merge(cob_total, on='nome_vendedor', how='left').fillna(0)
    
    perf['Pasta'] = perf['nome_vendedor'].map(vendedor_pasta)
    perf['%_Positivação_Ativa'] = (perf['Clientes_Positivados'] / perf['Clientes_Ativos_Hist'] * 100).fillna(0).round(1)
    perf['%_Positivação_Total'] = (perf['Clientes_Positivados'] / perf['Total_Clientes'] * 100).fillna(0).round(1)
    
    perf = perf.sort_values('%_Positivação_Ativa', ascending=False)
    
    # Gráficos e Tabela
    fig_ativa = px.bar(perf, x='nome_vendedor', y='%_Positivação_Ativa', title='% Positivação (Base Ativa)', text_auto='.1f', color='%_Positivação_Ativa', color_continuous_scale='Greens')
    fig_ativa.add_hline(y=meta_ativa, line_dash="dash", line_color="red")
    st.plotly_chart(fig_ativa, use_container_width=True)
    
    st.dataframe(perf, use_container_width=True, hide_index=True)

def pagina_cenoura_bronze():
    st.header("🟤 Foco Estratégico: Cenoura & Bronze")
    df_cenoura = df_relatorio_base[df_relatorio_base['Linha_Produto'] == 'CENOURA & BRONZE']
    
    if df_cenoura.empty:
        st.warning("Sem dados de Cenoura & Bronze para os filtros atuais.")
        return

    # OTIMIZAÇÃO 1: Vetorização (groupby)
    window_df = calcular_janela_movel(df_cenoura, mes_selecionado, janela_meses)
    mes_str = f"{df_cenoura['Ano'].max()}-{int(mes_selecionado.split(' - ')[0]):02d}" if mes_selecionado != "Todos" else window_df['MŒs_Ano'].max()
    
    # 1. Média 6M vetorizada
    clientes_por_mes = window_df.groupby(['nome_vendedor', 'MŒs_Ano'])['codigo_cliente'].nunique().reset_index()
    media_6m = clientes_por_mes.groupby('nome_vendedor')['codigo_cliente'].mean().reset_index(name='Média 6M')
    
    # 2. Mês atual vetorizado
    mes_atual = df_cenoura[df_cenoura['MŒs_Ano'] == mes_str].groupby('nome_vendedor')['codigo_cliente'].nunique().reset_index(name='Mês Atual')
    
    # Merge
    vendedores = pd.DataFrame({'Vendedor': df_cenoura['nome_vendedor'].dropna().unique()})
    cen_df = vendedores.merge(media_6m, left_on='Vendedor', right_on='nome_vendedor', how='left').drop(columns='nome_vendedor')
    cen_df = cen_df.merge(mes_atual, left_on='Vendedor', right_on='nome_vendedor', how='left').drop(columns='nome_vendedor').fillna(0)
    cen_df['% Mês vs Média'] = (cen_df['Mês Atual'] / cen_df['Média 6M'] * 100).fillna(0).round(1)

    fig = px.bar(cen_df, x='Vendedor', y='% Mês vs Média', title='% Mês vs Média 6M', text_auto='.1f')
    st.plotly_chart(fig, use_container_width=True)
    st.dataframe(cen_df, use_container_width=True, hide_index=True)

def pagina_batalha_naval():
    st.header("📋 Batalha Naval")
    meses_batalha = sorted(df_relatorio_base['MŒs_Ano'].dropna().unique())
    if not meses_batalha:
        st.warning("Sem dados disponíveis.")
        return

    c1, c2 = st.columns(2)
    inicio = c1.selectbox("Mês início:", meses_batalha, index=0)
    fim = c2.selectbox("Mês fim:", meses_batalha, index=len(meses_batalha)-1)

    if inicio > fim:
        st.error("Data de início maior que fim.")
        return

    df_rel = df_relatorio_base[(df_relatorio_base['MŒs_Ano'] >= inicio) & (df_relatorio_base['MŒs_Ano'] <= fim)]
    matriz = df_rel.pivot_table(index=['codigo_cliente', 'nome_cliente'], columns='Nome_Fabricante', aggfunc='size', fill_value=0)
    matriz = (matriz > 0).astype(int)
    matriz['Total_Indústrias'] = matriz.sum(axis=1)
    matriz = matriz.reset_index()

    st.dataframe(matriz, use_container_width=True, hide_index=True)

# ============================================================
# ROTEAMENTO DE PÁGINAS (MENU LATERAL)
# ============================================================
menu_opcoes = {
    "🏠 Visão Geral": pagina_visao_geral,
    "👥 Performance Vendedor": pagina_performance_vendedor,
    "🟤 Cenoura & Bronze": pagina_cenoura_bronze,
    "📋 Batalha Naval": pagina_batalha_naval
}

# Aqui criamos o menu lateral nativo (Limpo e Organizado)
with st.sidebar:
    st.title("Navegação")
    escolha = st.radio("Ir para:", list(menu_opcoes.keys()))

# Executa a função correspondente à página escolhida
menu_opcoes[escolha]()
