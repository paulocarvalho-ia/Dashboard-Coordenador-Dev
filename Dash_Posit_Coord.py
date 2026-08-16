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

# Esconder links do Streamlit
st.markdown("""
<style>
    a[href*="/edit"] { display: none !important; }
    a[href*="github.com"] { display: none !important; }
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

    # Função para normalizar texto (remove acentos, caracteres especiais)
    def normalizar_texto(texto):
        """Remove acentos, caracteres especiais e transforma em minúsculas."""
        texto = unicodedata.normalize('NFKD', texto)
        texto = texto.encode('ASCII', 'ignore').decode('ASCII')
        texto = texto.lower().strip()
        texto = re.sub(r'\s+', ' ', texto)
        return texto

    # ============================================================
    # NORMALIZAR DF_BASE (com detecção robusta)
    # ============================================================
    df_base.columns = [str(col).strip() for col in df_base.columns]
    base_rename = {}

    for col in df_base.columns:
        col_norm = normalizar_texto(col)
        if 'codigo cliente' in col_norm or 'codigo' in col_norm and 'cliente' in col_norm:
            base_rename[col] = 'codigo_cliente'
        elif 'cliente' in col_norm and 'nome' in col_norm:
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

    # Verificar se colunas essenciais existem
    required_base_cols = ['codigo_cliente', 'nome_cliente', 'nome_vendedor_base',
                          'Cliente_Coligacao', 'Nome_Coordenador', 'Municipio', 'Canal', 'Segmento']
    missing_base = [col for col in required_base_cols if col not in df_base.columns]
    if missing_base:
        st.error(f"Colunas essenciais não encontradas no DataFrame BASE: {missing_base}")
        st.write("Colunas disponíveis:", df_base.columns.tolist())
        st.stop()

    # ============================================================
    # NORMALIZAR DF_BI (com detecção robusta)
    # ============================================================
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

    # Fallback: se ainda não achou a coluna de período, procura diretamente
    if 'Ano_e_Mes' not in df_bi.columns:
        for col in df_bi.columns:
            if 'ano' in col.lower() and 'mes' in col.lower():
                df_bi.rename(columns={col: 'Ano_e_Mes'}, inplace=True)
                break

    if 'Ano_e_Mes' not in df_bi.columns:
        st.error("Não foi possível identificar a coluna de Ano/Mês no DataFrame BI_Teste.")
        st.write("Colunas disponíveis:", df_bi.columns.tolist())
        st.stop()

    # Processar datas
    df_bi['Data'] = pd.to_datetime(df_bi['Ano_e_Mes'] + '-01', errors='coerce')
    df_bi['MŒs'] = df_bi['Data'].dt.month
    df_bi['Ano'] = df_bi['Data'].dt.year
    df_bi['MŒs_Ano'] = df_bi['Data'].dt.to_period('M').astype(str)

    # ============================================================
    # MERGE
    # ============================================================
    df_base_dedup = df_base.drop_duplicates(subset=['codigo_cliente'], keep='first')

    # Merge principal (por cliente + vendedor)
    df_merged = df_bi.merge(
        df_base[['codigo_cliente', 'nome_cliente', 'nome_vendedor_base', 'Cliente_Coligacao', 
                 'Nome_Coordenador', 'Municipio', 'Canal', 'Segmento']],
        left_on=['codigo_cliente', 'nome_vendedor_bi'],
        right_on=['codigo_cliente', 'nome_vendedor_base'],
        how='left'
    )

    # Fallback SEGURO usando map
    for col in ['nome_cliente', 'Cliente_Coligacao', 'Nome_Coordenador', 'Municipio', 'Canal', 'Segmento']:
        if col in df_base.columns:
            fallback_map = df_base_dedup.set_index('codigo_cliente')[col].to_dict()
            df_merged[col] = df_merged[col].fillna(df_merged['codigo_cliente'].map(fallback_map))

    df_merged['nome_vendedor'] = df_merged['nome_vendedor_bi']

    # Mapear pastas
    fabricante_pasta = dict(zip(df_fabricantes['Nome Fabricante'], df_fabricantes['Pasta']))
    vendedor_pasta = dict(zip(df_vendedores['Vendedor'], df_vendedores['Pasta']))

    return df_base, df_bi, df_merged, data_dados, fabricante_pasta, vendedor_pasta

# Carregar dados
df_base, df_bi, df_merged, data_dados, fabricante_pasta, vendedor_pasta = load_data()

TODAS_INDUSTRIAS = sorted([i for i in df_bi['Nome_Fabricante'].dropna().unique() if str(i).strip() != ''])

# ============================================================
# FUNÇÕES AUXILIARES
# ============================================================
def gerar_pdf_html(tabela_df, titulo):
    """Gera PDF a partir de DataFrame usando HTML + CSS"""
    try:
        from weasyprint import HTML

        html_content = f"""
        <html>
        <head>
            <meta charset="UTF-8">
            <style>
                @page {{ size: A4 landscape; margin: 1cm; }}
                body {{ font-family: Arial, sans-serif; margin: 20px; }}
                h1 {{ color: #1a3a4a; font-size: 18px; margin-bottom: 15px; }}
                table {{ border-collapse: collapse; width: 100%; font-size: 9px; }}
                th {{ background: #1a3a4a; color: white; padding: 6px 4px; border: 1px solid #1a3a4a; font-weight: bold; }}
                td {{ border: 1px solid #ddd; padding: 4px; text-align: center; }}
                tr:nth-child(even) {{ background: #f9f9f9; }}
                tr:hover {{ background: #f0f0f0; }}
                .footer {{ margin-top: 20px; font-size: 8px; color: #666; text-align: right; }}
            </style>
        </head>
        <body>
            <h1>{titulo}</h1>
            {tabela_df.to_html(index=False, border=1, classes='dataframe')}
            <div class="footer">Gerado em: {datetime.now().strftime('%d/%m/%Y %H:%M')}</div>
        </body>
        </html>
        """

        pdf_buffer = BytesIO()
        HTML(string=html_content).write_pdf(pdf_buffer)
        pdf_buffer.seek(0)
        return pdf_buffer.getvalue()
    except ImportError:
        st.error("Biblioteca 'weasyprint' não instalada. Execute: pip install weasyprint")
        return None
    except Exception as e:
        st.error(f"Erro ao gerar PDF: {str(e)}")
        return None

def aplicar_filtros_comuns(df, incluir_mes=True):
    """Aplica todos os filtros comuns aos dados"""
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
        anos_do_mes = df[df['MŒs'] == mes_num]['Ano'].unique()
        ano_ref = max(anos_do_mes) if len(anos_do_mes) > 0 else df['Ano'].max()
        mes_ano_ref = f"{ano_ref}-{mes_num:02d}"
        df = df[df['MŒs_Ano'] == mes_ano_ref]

    if industria_selecionada_lista:
        df = df[df['Nome_Fabricante'].isin(industria_selecionada_lista)]
    if categoria_selecionada:
        df = df[df['Categoria'].isin(categoria_selecionada)]
    if linha_selecionada:
        df = df[df['Linha_Produto'].isin(linha_selecionada)]

    return df

def calcular_janela_movel(df_historico, mes_selecionado, janela_meses):
    """Calcula a janela móvel de meses anteriores"""
    if mes_selecionado == "Todos":
        return df_historico.copy()

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
        meses_janela.append((ano, mes))

    cond_janela = pd.Series(False, index=df_historico.index)
    for a, m in meses_janela:
        cond_janela |= (df_historico['Ano'] == a) & (df_historico['MŒs'] == m)

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
        if pasta_selecionada in ["Todas", "PVA"]:
            INDUSTRIAS_DISPONIVEIS = TODAS_INDUSTRIAS.copy()
        else:
            INDUSTRIAS_DISPONIVEIS = [ind for ind in TODAS_INDUSTRIAS if fabricante_pasta.get(ind) == pasta_selecionada]
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
            clientes_do_coord = df_base[df_base['codigo_cliente'].isin(vendedores_do_coord)]['codigo_cliente'].unique()
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
        meses_disponiveis = sorted(df_merged['MŒs'].dropna().unique())
        meses_nomes = {1:'Janeiro', 2:'Fevereiro', 3:'Março', 4:'Abril', 5:'Maio', 6:'Junho', 
                       7:'Julho', 8:'Agosto', 9:'Setembro', 10:'Outubro', 11:'Novembro', 12:'Dezembro'}
        lista_meses = ["Todos"] + [f"{int(m):02d} - {meses_nomes.get(int(m), '')}" for m in meses_disponiveis]

        if 'mes' not in st.session_state:
            if meses_disponiveis:
                ultimo_mes = max(meses_disponiveis)
                st.session_state['mes'] = f"{int(ultimo_mes):02d} - {meses_nomes.get(int(ultimo_mes), '')}"
            else:
                st.session_state['mes'] = 'Todos'

        mes_selecionado = st.selectbox("Mês", lista_meses, index=lista_meses.index(st.session_state['mes']), key='mes_top')
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
# NAVEGAÇÃO
# ============================================================
st.markdown("---")
opcoes_paginas = [
    "🏠 Visão Geral",
    "👥 Performance Vendedor",
    "📍 Positivação por Município",
    "🏷️ Positivação por Segmento",
    "🔀 Oportunidades Cruzadas",
    "🟢 Softys Falcon",
    "🟠 Kenvue Perfumaria",
    "🟤 Cenoura & Bronze",
    "📋 Batalha Naval",
    "🔍 Ficha do Cliente"
]
opcao = st.radio("Selecione a página:", opcoes_paginas, horizontal=True, key='nav')

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

    if mes_selecionado != "Todos":
        mes_num = int(mes_selecionado.split(' - ')[0])
        anos_do_mes = df_historico[df_historico['MŒs'] == mes_num]['Ano'].unique()
        ano_ytd = max(anos_do_mes) if len(anos_do_mes) > 0 else df_historico['Ano'].max()
    else:
        ano_ytd = df_historico['Ano'].max()
        mes_num = df_historico['MŒs'].max()

    df_historico_ano = df_historico[df_historico['Ano'] == ano_ytd]
    df_mensal_ativos = df_historico_ano[df_historico_ano['Nome_Fabricante'].notna()]
    mensal_pos = df_mensal_ativos.groupby('MŒs_Ano')['codigo_cliente'].nunique().reset_index()
    mensal_pos.columns = ['Mês', 'Clientes Positivados']

    df_ytd = df_historico[(df_historico['Ano'] == ano_ytd) & (df_historico['MŒs'] <= mes_num)]
    ytd_total = df_ytd['codigo_cliente'].nunique()

    chart_data = pd.DataFrame({
        'Mês': list(mensal_pos['Mês']) + ['YTD'],
        'Clientes Positivados': list(mensal_pos['Clientes Positivados']) + [ytd_total]
    })

    colors = ['#2E8B57' if mes != 'YTD' else '#1a3a4a' for mes in chart_data['Mês']]

    fig = go.Figure(go.Bar(
        x=chart_data['Mês'],
        y=chart_data['Clientes Positivados'],
        marker_color=colors
    ))
    fig.update_layout(title='Positivação Carteira Ativa (Mensal + YTD)', yaxis_title='Clientes Positivados')
    st.plotly_chart(fig, use_container_width=True)

    if vendedor_selecionado != "Todos":
        total_clientes_base = df_base[df_base['nome_vendedor_base'] == vendedor_selecionado]['codigo_cliente'].nunique()
    elif coordenador_selecionado != "Todos":
        vendedores_do_coord = df_base[df_base['Nome_Coordenador'] == coordenador_selecionado]['nome_vendedor_base'].unique()
        total_clientes_base = df_base[df_base['codigo_cliente'].isin(vendedores_do_coord)]['codigo_cliente'].nunique()
    else:
        total_clientes_base = df_base['codigo_cliente'].nunique()

    total_positivados = len(df_filtrado[df_filtrado['Nome_Fabricante'].notna()]['codigo_cliente'].unique())
    pct_total = (total_positivados / total_clientes_base * 100) if total_clientes_base > 0 else 0

    st.subheader("📋 Carteira Total")
    col1, col2, col3 = st.columns(3)
    col1.metric("Clientes na Carteira", total_clientes_base)
    col2.metric("Clientes Positivados", total_positivados)
    col3.metric("% Positivação (Carteira Total)", f"{pct_total:.1f}%")

# ============================================================
# PÁGINA: PERFORMANCE POR VENDEDOR
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

    fig_ativa = px.bar(perf_vendedor, x='Vendedor', y='%_Positivação_Ativa', title='% Positivação (Base Ativa)',
                       text=perf_vendedor['%_Positivação_Ativa'].apply(lambda x: f'{x:.1f}%'),
                       color='%_Positivação_Ativa', color_continuous_scale='Greens')
    fig_ativa.add_hline(y=meta_ativa, line_dash="dash", line_color="red", annotation_text=f"Meta {meta_ativa}%")
    fig_ativa.update_traces(textposition='outside')
    fig_ativa.update_layout(xaxis_title="", yaxis_title="% Positivação", yaxis_range=[0, 105])
    st.plotly_chart(fig_ativa, use_container_width=True)

    fig_total = px.bar(perf_vendedor, x='Vendedor', y='%_Positivação_Total', title='% Positivação (Carteira Total)',
                       text=perf_vendedor['%_Positivação_Total'].apply(lambda x: f'{x:.1f}%'),
                       color='%_Positivação_Total', color_continuous_scale='Blues')
    fig_total.add_hline(y=meta_total, line_dash="dash", line_color="red", annotation_text=f"Meta {meta_total}%")
    fig_total.update_traces(textposition='outside')
    fig_total.update_layout(xaxis_title="", yaxis_title="% Positivação", yaxis_range=[0, 105])
    st.plotly_chart(fig_total, use_container_width=True)

    fig_cob = px.bar(perf_vendedor, x='Vendedor', y='Cobertura_Media', title='Cobertura Média por Vendedor',
                     text=perf_vendedor['Cobertura_Media'].apply(lambda x: f'{x:.1f}'),
                     color='Cobertura_Media', color_continuous_scale='Oranges')
    fig_cob.update_traces(textposition='outside')
    fig_cob.update_layout(xaxis_title="", yaxis_title="Indústrias/Cliente")
    st.plotly_chart(fig_cob, use_container_width=True)

    st.dataframe(perf_vendedor[['Vendedor', 'Pasta', 'Total_Clientes', 'Clientes_Ativos_Hist', 'Clientes_Positivados',
                                '%_Positivação_Ativa', '%_Positivação_Total', 'Cobertura_Media', 'Cobertura_Total']],
                 use_container_width=True, hide_index=True)

# ============================================================
# PÁGINA: POSITIVAÇÃO POR MUNICÍPIO
# ============================================================
elif opcao == "📍 Positivação por Município":
    st.subheader("📍 Positivação por Município")
    df_munic = df_filtrado.groupby('Municipio')['codigo_cliente'].nunique().reset_index()
    df_munic.columns = ['Município', 'Clientes Positivados']
    df_munic = df_munic.sort_values('Clientes Positivados', ascending=False)

    fig_munic = px.bar(df_munic, x='Município', y='Clientes Positivados', text='Clientes Positivados',
                       color='Clientes Positivados', color_continuous_scale='Blues')
    fig_munic.update_traces(textposition='outside')
    fig_munic.update_layout(xaxis_title="", yaxis_title="Clientes Positivados")
    st.plotly_chart(fig_munic, use_container_width=True)

    st.dataframe(df_munic, use_container_width=True, hide_index=True)

# ============================================================
# PÁGINA: POSITIVAÇÃO POR SEGMENTO
# ============================================================
elif opcao == "🏷️ Positivação por Segmento":
    st.subheader("🏷️ Positivação por Segmento")
    df_seg = df_filtrado.groupby('Segmento')['codigo_cliente'].nunique().reset_index()
    df_seg.columns = ['Segmento', 'Clientes Positivados']
    df_seg = df_seg.sort_values('Clientes Positivados', ascending=False)

    fig_seg = px.bar(df_seg, x='Segmento', y='Clientes Positivados', text='Clientes Positivados',
                     color='Clientes Positivados', color_continuous_scale='Greens')
    fig_seg.update_traces(textposition='outside')
    fig_seg.update_layout(xaxis_title="", yaxis_title="Clientes Positivados")
    st.plotly_chart(fig_seg, use_container_width=True)

    st.dataframe(df_seg, use_container_width=True, hide_index=True)

# ============================================================
# PÁGINA: OPORTUNIDADES CRUZADAS
# ============================================================
elif opcao == "🔀 Oportunidades Cruzadas":
    st.subheader("🔀 Oportunidades Cruzadas")

    col_op1, col_op2 = st.columns(2)
    with col_op1:
        st.markdown("**Indústrias da Base (compradas)**")
        base_op = st.multiselect("Selecione uma ou mais indústrias que o cliente comprou:", 
                                 options=INDUSTRIAS_DISPONIVEIS, key='base_cruzada')
    with col_op2:
        st.markdown("**Indústrias de Comparação (não compradas)**")
        comp_op = st.multiselect("Selecione uma ou mais indústrias que o cliente NÃO comprou:", 
                                 options=INDUSTRIAS_DISPONIVEIS, key='comp_cruzada')

    if base_op and comp_op:
        df_analise = df_filtrado.copy()

        base_sem_vendas = [ind for ind in base_op if df_analise[df_analise['Nome_Fabricante'] == ind].empty]
        if base_sem_vendas:
            st.warning(f"As seguintes indústrias da base não tiveram vendas no período selecionado: {', '.join(base_sem_vendas)}.")
            st.info("Nenhum cliente pode atender aos critérios com essas indústrias.")
        else:
            clientes_base = set(df_analise[df_analise['Nome_Fabricante'] == base_op[0]]['codigo_cliente'].unique())
            for ind in base_op[1:]:
                clientes_base &= set(df_analise[df_analise['Nome_Fabricante'] == ind]['codigo_cliente'].unique())

            clientes_comp = set(df_analise['codigo_cliente'].unique())
            for ind in comp_op:
                clientes_comp -= set(df_analise[df_analise['Nome_Fabricante'] == ind]['codigo_cliente'].unique())

            clientes_oportunidade = clientes_base.intersection(clientes_comp)

            if clientes_oportunidade:
                st.success(f"🔎 {len(clientes_oportunidade)} clientes compraram da(s) indústria(s) selecionada(s) e não compraram da(s) indústria(s) comparada(s).")
                df_op = df_base[df_base['codigo_cliente'].isin(clientes_oportunidade)][
                    ['codigo_cliente', 'nome_cliente', 'Cliente_Coligacao', 'nome_vendedor_base']
                ]
                df_op.columns = ['Código', 'Nome', 'Coligação', 'Vendedor']
                st.dataframe(df_op, use_container_width=True, hide_index=True)

                output_op = BytesIO()
                with pd.ExcelWriter(output_op, engine='openpyxl') as writer:
                    df_op.to_excel(writer, index=False, sheet_name='Oportunidades')
                st.download_button("📥 Baixar Excel (Oportunidades)", data=output_op.getvalue(),
                                   file_name=f'oportunidades_{datetime.now().strftime("%Y%m%d_%H%M")}.xlsx',
                                   mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', 
                                   use_container_width=True)

                # PDF
                pdf_data = gerar_pdf_html(df_op, "Oportunidades Cruzadas")
                if pdf_data:
                    st.download_button("📄 Baixar PDF (Oportunidades)", data=pdf_data,
                                       file_name=f'oportunidades_{datetime.now().strftime("%Y%m%d_%H%M")}.pdf',
                                       mime='application/pdf', use_container_width=True)
            else:
                st.info("Nenhum cliente atende aos critérios de oportunidade cruzada com os filtros atuais.")
    else:
        st.info("Selecione ao menos uma indústria em cada lista para visualizar as oportunidades cruzadas.")

# ============================================================
# PÁGINA: SOFTYS FALCON
# ============================================================
elif opcao == "🟢 Softys Falcon":
    df_softys = df_relatorio_base[df_relatorio_base['Nome_Fabricante'] == 'SOFTYS FALCON'].copy()

    if not df_softys.empty:
        st.subheader("🟢 Foco Estratégico: Softys Falcon")

        if mes_selecionado != "Todos":
            mes_num = int(mes_selecionado.split(' - ')[0])
            anos_do_mes = df_softys[df_softys['MŒs'] == mes_num]['Ano'].unique()
            ano_atual = max(anos_do_mes) if len(anos_do_mes) > 0 else df_softys['Ano'].max()
            mes_atual_num = mes_num
        else:
            ano_atual = df_softys['Ano'].max()
            mes_atual_num = df_softys['MŒs'].max()

        meses_ano = [f"{ano_atual}-{m:02d}" for m in range(1, mes_atual_num + 1)]
        df_softys_ano = df_softys[(df_softys['Ano'] == ano_atual) & (df_softys['MŒs'] <= mes_atual_num)]

        monthly_totals = df_softys_ano.groupby('MŒs_Ano')['codigo_cliente'].nunique().reset_index()
        monthly_totals.columns = ['Mês', 'Clientes']
        monthly_totals = monthly_totals[monthly_totals['Mês'].isin(meses_ano)]

        ytd_total = df_softys_ano['codigo_cliente'].nunique()

        chart_softys = pd.DataFrame({
            'Mês': list(monthly_totals['Mês']) + ['YTD'],
            'Clientes': list(monthly_totals['Clientes']) + [ytd_total]
        })

        colors_softys = ['#2E8B57' if mes != 'YTD' else '#1a3a4a' for mes in chart_softys['Mês']]

        fig_softys = go.Figure(go.Bar(
            x=chart_softys['Mês'],
            y=chart_softys['Clientes'],
            marker_color=colors_softys
        ))
        fig_softys.update_layout(title='Positivação Softys Falcon (Mensal + YTD)', yaxis_title='Clientes')
        st.plotly_chart(fig_softys, use_container_width=True)

        pivot_mensal = df_softys_ano.pivot_table(index='Categoria', columns='MŒs_Ano', 
                                                  values='codigo_cliente', aggfunc='nunique', fill_value=0)
        pivot_mensal = pivot_mensal.reindex(columns=meses_ano, fill_value=0)
        ytd_series = df_softys_ano.groupby('Categoria')['codigo_cliente'].nunique()
        tabela = pivot_mensal.copy()
        tabela['YTD'] = ytd_series
        tabela = tabela.reset_index().fillna(0)

        ordered_cols = ['Categoria'] + meses_ano + ['YTD']
        tabela = tabela[ordered_cols]

        st.markdown("**Positivação por Categoria (todos os meses do ano + YTD)**")
        st.dataframe(tabela, use_container_width=True, hide_index=True)

        # Excel
        output_mensal = BytesIO()
        with pd.ExcelWriter(output_mensal, engine='openpyxl') as writer:
            tabela.to_excel(writer, index=False, sheet_name='Softys Mensal')
        st.download_button("📥 Baixar Excel (Mensal)", data=output_mensal.getvalue(),
                           file_name=f'softys_mensal_{datetime.now().strftime("%Y%m%d")}.xlsx',
                           mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', 
                           use_container_width=True)

        # PDF
        pdf_mensal = gerar_pdf_html(tabela, "Softys Falcon - Mensal + YTD")
        if pdf_mensal:
            st.download_button("📄 Baixar PDF (Mensal)", data=pdf_mensal,
                               file_name=f'softys_mensal_{datetime.now().strftime("%Y%m%d")}.pdf',
                               mime='application/pdf', use_container_width=True)

        st.markdown("**Batalha Naval Softys Falcon — Clientes que compraram**")
        df_softys_clientes = df_softys_ano[['codigo_cliente', 'nome_cliente', 'Municipio', 
                                            'Cliente_Coligacao', 'nome_vendedor', 'Categoria']].drop_duplicates()
        clientes_pivot = df_softys_clientes.pivot_table(
            index=['codigo_cliente', 'nome_cliente', 'Municipio', 'Cliente_Coligacao', 'nome_vendedor'],
            columns='Categoria', aggfunc='size', fill_value=0
        ).reset_index()
        cat_cols = [c for c in clientes_pivot.columns if c not in ['codigo_cliente', 'nome_cliente', 
                                                                    'Municipio', 'Cliente_Coligacao', 'nome_vendedor']]
        clientes_pivot[cat_cols] = (clientes_pivot[cat_cols] > 0).astype(int)
        clientes_pivot['Total'] = clientes_pivot[cat_cols].sum(axis=1)

        with st.expander("Visualizar Batalha Naval"):
            st.dataframe(clientes_pivot, use_container_width=True, hide_index=True)

        # Excel BN
        output_bn = BytesIO()
        with pd.ExcelWriter(output_bn, engine='openpyxl') as writer:
            clientes_pivot.to_excel(writer, index=False, sheet_name='Batalha Naval Softys')
        st.download_button("📥 Baixar Excel (Batalha Naval)", data=output_bn.getvalue(),
                           file_name=f'batalha_naval_softys_{datetime.now().strftime("%Y%m%d")}.xlsx',
                           mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', 
                           use_container_width=True)

        # PDF BN
        pdf_bn = gerar_pdf_html(clientes_pivot, "Batalha Naval Softys Falcon")
        if pdf_bn:
            st.download_button("📄 Baixar PDF (Batalha Naval)", data=pdf_bn,
                               file_name=f'batalha_naval_softys_{datetime.now().strftime("%Y%m%d")}.pdf',
                               mime='application/pdf', use_container_width=True)
    else:
        st.warning("Nenhum dado da Softys Falcon para os filtros atuais.")

# ============================================================
# PÁGINA: KENVUE PERFUMARIA
# ============================================================
elif opcao == "🟠 Kenvue Perfumaria":
    df_perfumarias_ativas = df_historico_janela[df_historico_janela['Canal'] == 'PERFUMARIA'].copy()

    if not df_perfumarias_ativas.empty:
        df_kenvue_mes = df_filtrado[(df_filtrado['Nome_Fabricante'] == 'KENVUE') & 
                                     (df_filtrado['Canal'] == 'PERFUMARIA')].copy()

        if not df_kenvue_mes.empty:
            clientes_kenvue_mes = df_kenvue_mes['codigo_cliente'].unique()
            total_perfumarias_ativas = df_perfumarias_ativas['codigo_cliente'].nunique()
            atendidos = len(clientes_kenvue_mes)
            pct_atendido = (atendidos / total_perfumarias_ativas * 100) if total_perfumarias_ativas > 0 else 0

            st.subheader("🟠 Foco Estratégico: Kenvue no Canal Perfumaria")
            st.metric("Perfumarias Ativas (janela móvel)", total_perfumarias_ativas)
            st.metric("Atendidas com Kenvue (mês atual)", f"{atendidos} ({pct_atendido:.1f}%)")
            st.progress(min(pct_atendido / 100, 1.0), text="Meta: 50%")

            clientes_nao_atendidos = [c for c in df_perfumarias_ativas['codigo_cliente'].unique() 
                                      if c not in clientes_kenvue_mes]

            col_ken1, col_ken2 = st.columns(2)
            with col_ken1:
                st.markdown(f"✅ **Chegamos** ({atendidos})")
                df_chegamos = df_base[df_base['codigo_cliente'].isin(clientes_kenvue_mes)][
                    ['codigo_cliente', 'nome_cliente', 'Municipio', 'Cliente_Coligacao', 'nome_vendedor_base']
                ]
                df_chegamos.columns = ['Código', 'Nome', 'Município', 'Coligação', 'Vendedor']
                st.dataframe(df_chegamos, use_container_width=True, hide_index=True)

                # Excel
                output_cheg = BytesIO()
                with pd.ExcelWriter(output_cheg, engine='openpyxl') as writer:
                    df_chegamos.to_excel(writer, index=False, sheet_name='Chegamos')
                st.download_button("📥 Baixar Excel (Chegamos)", data=output_cheg.getvalue(),
                                   file_name=f'kenvue_chegamos_{datetime.now().strftime("%Y%m%d")}.xlsx',
                                   mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', 
                                   use_container_width=True)

                # PDF
                pdf_cheg = gerar_pdf_html(df_chegamos, "Kenvue - Chegamos")
                if pdf_cheg:
                    st.download_button("📄 Baixar PDF (Chegamos)", data=pdf_cheg,
                                       file_name=f'kenvue_chegamos_{datetime.now().strftime("%Y%m%d")}.pdf',
                                       mime='application/pdf', use_container_width=True)

            with col_ken2:
                st.markdown(f"❌ **Não chegamos** ({len(clientes_nao_atendidos)})")
                df_nao = df_base[df_base['codigo_cliente'].isin(clientes_nao_atendidos)][
                    ['codigo_cliente', 'nome_cliente', 'Municipio', 'Cliente_Coligacao', 'nome_vendedor_base']
                ]
                df_nao.columns = ['Código', 'Nome', 'Município', 'Coligação', 'Vendedor']
                st.dataframe(df_nao, use_container_width=True, hide_index=True)

                # Excel
                output_nao = BytesIO()
                with pd.ExcelWriter(output_nao, engine='openpyxl') as writer:
                    df_nao.to_excel(writer, index=False, sheet_name='Nao Chegamos')
                st.download_button("📥 Baixar Excel (Não Chegamos)", data=output_nao.getvalue(),
                                   file_name=f'kenvue_nao_chegamos_{datetime.now().strftime("%Y%m%d")}.xlsx',
                                   mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', 
                                   use_container_width=True)

                # PDF
                pdf_nao = gerar_pdf_html(df_nao, "Kenvue - Não Chegamos")
                if pdf_nao:
                    st.download_button("📄 Baixar PDF (Não Chegamos)", data=pdf_nao,
                                       file_name=f'kenvue_nao_chegamos_{datetime.now().strftime("%Y%m%d")}.pdf',
                                       mime='application/pdf', use_container_width=True)

            st.markdown("**Meta por Vendedor (50% das perfumarias ativas)**")
            vendedores_perf = df_perfumarias_ativas['nome_vendedor'].dropna().unique()
            lista_ken = []
            for vend in vendedores_perf:
                total_vend = df_perfumarias_ativas[df_perfumarias_ativas['nome_vendedor'] == vend]['codigo_cliente'].nunique()
                atend_vend = df_kenvue_mes[df_kenvue_mes['nome_vendedor'] == vend]['codigo_cliente'].nunique()
                pct_vend = (atend_vend / total_vend * 100) if total_vend > 0 else 0
                lista_ken.append({
                    'Vendedor': vend, 
                    'Perfumarias Ativas': total_vend, 
                    'Atendidas Kenvue': atend_vend, 
                    '% Atendido': round(pct_vend, 1)
                })
            df_ken_vend = pd.DataFrame(lista_ken)
            st.dataframe(df_ken_vend, use_container_width=True, hide_index=True)

            # Excel
            output_kenv = BytesIO()
            with pd.ExcelWriter(output_kenv, engine='openpyxl') as writer:
                df_ken_vend.to_excel(writer, index=False, sheet_name='Meta Kenvue Vendedor')
            st.download_button("📥 Baixar Excel (Meta por Vendedor)", data=output_kenv.getvalue(),
                               file_name=f'kenvue_meta_vendedor_{datetime.now().strftime("%Y%m%d")}.xlsx',
                               mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', 
                               use_container_width=True)

            # PDF
            pdf_kenv = gerar_pdf_html(df_ken_vend, "Meta Kenvue por Vendedor")
            if pdf_kenv:
                st.download_button("📄 Baixar PDF (Meta por Vendedor)", data=pdf_kenv,
                                   file_name=f'kenvue_meta_vendedor_{datetime.now().strftime("%Y%m%d")}.pdf',
                                   mime='application/pdf', use_container_width=True)
        else:
            st.warning("Nenhuma venda de Kenvue no mês atual para o canal Perfumaria.")
    else:
        st.warning("Nenhuma perfumaria ativa na janela móvel.")

# ============================================================
# PÁGINA: CENOURA & BRONZE
# ============================================================
elif opcao == "🟤 Cenoura & Bronze":
    df_cenoura = df_relatorio_base[df_relatorio_base['Linha_Produto'] == 'CENOURA & BRONZE'].copy()

    if not df_cenoura.empty:
        st.subheader("🟤 Foco Estratégico: Linha Cenoura & Bronze")

        if mes_selecionado != "Todos":
            mes_num = int(mes_selecionado.split(' - ')[0])
            anos_do_mes = df_cenoura[df_cenoura['MŒs'] == mes_num]['Ano'].unique()
            ano_atual = max(anos_do_mes) if len(anos_do_mes) > 0 else df_cenoura['Ano'].max()
            mes_atual_num = mes_num
            # Corrigido: usar 'MŒs' em vez de 'Mês'
            months_window = [f"{a}-{m:02d}" for a, m in calcular_janela_movel(df_cenoura, mes_selecionado, janela_meses)[['Ano', 'MŒs']].drop_duplicates().itertuples(index=False, name=None)]
            current_month_str = f"{ano_atual}-{mes_atual_num:02d}"
        else:
            months_window = sorted(df_cenoura['MŒs_Ano'].unique())
            current_month_str = months_window[-1] if months_window else None

        df_cenoura_window = df_cenoura[df_cenoura['MŒs_Ano'].isin(months_window)].copy()
        df_cenoura_mes = df_cenoura[df_cenoura['MŒs_Ano'] == current_month_str].copy() if current_month_str else pd.DataFrame()

        vendedores_cen = df_cenoura['nome_vendedor'].dropna().unique()
        lista_cen = []
        for vend in vendedores_cen:
            df_vend_window = df_cenoura_window[df_cenoura_window['nome_vendedor'] == vend]
            media_6m = df_vend_window.groupby('MŒs_Ano')['codigo_cliente'].nunique().mean() if not df_vend_window.empty else 0
            df_vend_mes = df_cenoura_mes[df_cenoura_mes['nome_vendedor'] == vend] if not df_cenoura_mes.empty else pd.DataFrame()
            clientes_mes = df_vend_mes['codigo_cliente'].nunique() if not df_vend_mes.empty else 0
            pct = (clientes_mes / media_6m * 100) if media_6m > 0 else 0
            lista_cen.append({
                'Vendedor': vend, 
                'Média 6M': round(media_6m, 1), 
                'Mês Atual': clientes_mes, 
                '% Mês vs Média': round(pct, 1)
            })
        df_cen_vend = pd.DataFrame(lista_cen)

        fig_cen_media = px.bar(df_cen_vend, x='Vendedor', y='Média 6M', title='Média 6 meses', 
                               text='Média 6M', color='Média 6M')
        st.plotly_chart(fig_cen_media, use_container_width=True)

        fig_cen_mes = px.bar(df_cen_vend, x='Vendedor', y='Mês Atual', title='Mês Atual', 
                             text='Mês Atual', color='Mês Atual')
        st.plotly_chart(fig_cen_mes, use_container_width=True)

        fig_cen_pct = px.bar(df_cen_vend, x='Vendedor', y='% Mês vs Média', title='% Mês vs Média 6M', 
                             text='% Mês vs Média', color='% Mês vs Média')
        st.plotly_chart(fig_cen_pct, use_container_width=True)

        st.dataframe(df_cen_vend, use_container_width=True, hide_index=True)
    else:
        st.warning("Nenhum dado de Cenoura & Bronze para os filtros atuais.")

# ============================================================
# PÁGINA: BATALHA NAVAL (Geral)
# ============================================================
elif opcao == "📋 Batalha Naval":
    st.subheader("📋 Batalha Naval — Matriz Cliente × Indústria")

    if not df_filtrado.empty:
        df_bn = df_filtrado[['codigo_cliente', 'nome_cliente', 'Municipio', 
                             'Cliente_Coligacao', 'nome_vendedor', 'Nome_Fabricante']].drop_duplicates()

        pivot_bn = df_bn.pivot_table(
            index=['codigo_cliente', 'nome_cliente', 'Municipio', 'Cliente_Coligacao', 'nome_vendedor'],
            columns='Nome_Fabricante', 
            aggfunc='size', 
            fill_value=0
        ).reset_index()

        ind_cols = [c for c in pivot_bn.columns if c not in ['codigo_cliente', 'nome_cliente', 
                                                              'Municipio', 'Cliente_Coligacao', 'nome_vendedor']]
        pivot_bn[ind_cols] = (pivot_bn[ind_cols] > 0).astype(int)
        pivot_bn['Total_Ind'] = pivot_bn[ind_cols].sum(axis=1)

        with st.expander("Visualizar Batalha Naval"):
            st.dataframe(pivot_bn, use_container_width=True, hide_index=True)

        # Excel
        output_bn = BytesIO()
        with pd.ExcelWriter(output_bn, engine='openpyxl') as writer:
            pivot_bn.to_excel(writer, index=False, sheet_name='Batalha Naval')
        st.download_button("📥 Baixar Excel (Batalha Naval)", data=output_bn.getvalue(),
                           file_name=f'batalha_naval_{datetime.now().strftime("%Y%m%d_%H%M")}.xlsx',
                           mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', 
                           use_container_width=True)

        # PDF
        pdf_bn = gerar_pdf_html(pivot_bn, "Batalha Naval - Cliente × Indústria")
        if pdf_bn:
            st.download_button("📄 Baixar PDF (Batalha Naval)", data=pdf_bn,
                               file_name=f'batalha_naval_{datetime.now().strftime("%Y%m%d_%H%M")}.pdf',
                               mime='application/pdf', use_container_width=True)
    else:
        st.info("Nenhum dado para exibir a Batalha Naval com os filtros atuais.")

# ============================================================
# PÁGINA: FICHA DO CLIENTE
# ============================================================
elif opcao == "🔍 Ficha do Cliente":
    st.subheader("🔍 Ficha do Cliente")

    clientes_disponiveis = sorted(df_filtrado['nome_cliente'].dropna().unique().tolist())

    if clientes_disponiveis:
        cliente_selecionado = st.selectbox("Selecione um cliente:", clientes_disponiveis, key='ficha_cliente')

        if cliente_selecionado:
            df_cliente = df_filtrado[df_filtrado['nome_cliente'] == cliente_selecionado].copy()

            if not df_cliente.empty:
                col_f1, col_f2 = st.columns(2)
                with col_f1:
                    st.markdown("**Dados Cadastrais**")
                    codigo = df_cliente['codigo_cliente'].iloc[0]
                    coligacao = df_cliente['Cliente_Coligacao'].iloc[0]
                    municipio = df_cliente['Municipio'].iloc[0]
                    canal = df_cliente['Canal'].iloc[0]
                    segmento = df_cliente['Segmento'].iloc[0]
                    st.write(f"Código: {codigo}")
                    st.write(f"Coligação: {coligacao}")
                    st.write(f"Município: {municipio}")
                    st.write(f"Canal: {canal}")
                    st.write(f"Segmento: {segmento}")

                with col_f2:
                    st.markdown("**Performance no Período**")
                    total_pedidos = len(df_cliente)
                    ind_compradas = df_cliente['Nome_Fabricante'].nunique()
                    categorias = df_cliente['Categoria'].nunique()
                    st.write(f"Total de Pedidos: {total_pedidos}")
                    st.write(f"Indústrias Compradas: {ind_compradas}")
                    st.write(f"Categorias: {categorias}")

                st.markdown("**Histórico de Compras**")
                df_hist = df_cliente.groupby(['MŒs_Ano', 'Nome_Fabricante'])['codigo_cliente'].count().reset_index()
                df_hist.columns = ['Mês', 'Indústria', 'Pedidos']
                st.dataframe(df_hist, use_container_width=True, hide_index=True)
            else:
                st.warning("Nenhum dado encontrado para este cliente.")
    else:
        st.info("Nenhum cliente disponível com os filtros atuais.")
