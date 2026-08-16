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

    def normalizar_texto(texto):
        """Remove acentos, caracteres especiais e transforma em minúsculas."""
        texto = unicodedata.normalize('NFKD', str(texto))
        texto = texto.encode('ASCII', 'ignore').decode('ASCII')
        texto = texto.lower().strip()
        texto = re.sub(r'\s+', ' ', texto)
        return texto

    # ============================================================
    # NORMALIZAR DF_BASE
    # ============================================================
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

    # ============================================================
    # NORMALIZAR DF_BI
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

    df_bi['Data'] = pd.to_datetime(df_bi['Ano_e_Mes'] + '-01', errors='coerce')
    df_bi['MŒs'] = df_bi['Data'].dt.month
    df_bi['Ano'] = df_bi['Data'].dt.year
    df_bi['MŒs_Ano'] = df_bi['Data'].dt.to_period('M').astype(str)

    # ============================================================
    # MERGE
    # ============================================================
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
        html_content = f"<html><body><h1>{titulo}</h1>{tabela_df.to_html(index=False)}</body></html>"
        pdf_buffer = BytesIO()
        HTML(string=html_content).write_pdf(pdf_buffer)
        pdf_buffer.seek(0)
        return pdf_buffer.getvalue()
    except Exception as e:
        return None

def aplicar_filtros_comuns(df, incluir_mes=True):
    df = df.copy()
    if pasta_selecionada not in ["Todas", "PVA"]:
        vendedores_pasta = [v for v in df_base['nome_vendedor_base'].unique() if vendedor_pasta.get(v) == pasta_selecionada]
        df = df[df['nome_vendedor'].isin(vendedores_pasta)]
    if vendedor_selecionado != "Todos": df = df[df['nome_vendedor'] == vendedor_selecionado]
    if coordenador_selecionado != "Todos": df = df[df['Nome_Coordenador'] == coordenador_selecionado]
    if coligacao_selecionada != "Todas": df = df[df['Cliente_Coligacao'] == coligacao_selecionada]
    if municipio_selecionado: df = df[df['Municipio'].isin(municipio_selecionado)]
    if canal_selecionado: df = df[df['Canal'].isin(canal_selecionado)]
    if segmento_selecionado: df = df[df['Segmento'].isin(segmento_selecionado)]

    if incluir_mes and mes_selecionado != "Todos":
        mes_num = int(mes_selecionado.split(' - ')[0])
        anos_do_mes = df[df['MŒs'] == mes_num]['Ano'].unique()
        ano_ref = max(anos_do_mes) if len(anos_do_mes) > 0 else df['Ano'].max()
        df = df[df['MŒs_Ano'] == f"{ano_ref}-{mes_num:02d}"]
    if industria_selecionada_lista: df = df[df['Nome_Fabricante'].isin(industria_selecionada_lista)]
    if categoria_selecionada: df = df[df['Categoria'].isin(categoria_selecionada)]
    if linha_selecionada: df = df[df['Linha_Produto'].isin(linha_selecionada)]
    return df

def calcular_janela_movel(df_historico, mes_selecionado, janela_meses):
    if mes_selecionado == "Todos": return df_historico.copy()
    mes_num = int(mes_selecionado.split(' - ')[0])
    ano_ref = df_historico[df_historico['MŒs'] == mes_num]['Ano'].max() if not df_historico[df_historico['MŒs'] == mes_num].empty else df_historico['Ano'].max()
    meses_janela = []
    for i in range(1, janela_meses + 1):
        m, a = mes_num - i, ano_ref
        while m <= 0: m += 12; a -= 1
        meses_janela.append(f"{a}-{m:02d}")
    return df_historico[df_historico['MŒs_Ano'].isin(meses_janela)]

# ============================================================
# FILTROS
# ============================================================
with st.expander("🎯 Filtros", expanded=True):
    col_eq1, col_eq2, col_eq3 = st.columns(3)
    coordenador_selecionado = col_eq1.selectbox("Coordenador", ["Todos"] + sorted(df_base['Nome_Coordenador'].dropna().unique().tolist()))
    vendedores_base = df_base[df_base['Nome_Coordenador'] == coordenador_selecionado]['nome_vendedor_base'].dropna().unique() if coordenador_selecionado != "Todos" else df_base['nome_vendedor_base'].dropna().unique()
    vendedor_selecionado = col_eq2.selectbox("Vendedor", ["Todos"] + sorted(vendedores_base))
    pasta_selecionada = col_eq3.selectbox("Pasta", ["Todas", "PA", "PV", "PVA"])

    col_prod1, col_prod2, col_prod3 = st.columns(3)
    INDUSTRIAS_DISPONIVEIS = TODAS_INDUSTRIAS if pasta_selecionada in ["Todas", "PVA"] else [i for i in TODAS_INDUSTRIAS if fabricante_pasta.get(i) == pasta_selecionada]
    industria_selecionada_lista = col_prod1.multiselect("Indústria(s)", options=INDUSTRIAS_DISPONIVEIS)
    categoria_selecionada = col_prod2.multiselect("Categoria(s)", options=sorted(df_bi['Categoria'].dropna().unique()))
    linha_selecionada = col_prod3.multiselect("Linha(s)", options=sorted(df_bi['Linha_Produto'].dropna().unique()))

    col_loc1, col_loc2, col_loc3, col_loc4 = st.columns(4)
    coligacao_selecionada = col_loc1.selectbox("Coligação", ["Todas"] + sorted(df_base['Cliente_Coligacao'].dropna().unique()))
    canal_selecionado = col_loc2.multiselect("Canal(is)", options=sorted(df_base['Canal'].dropna().unique()))
    segmento_selecionado = col_loc3.multiselect("Segmento(s)", options=sorted(df_base['Segmento'].dropna().unique()))
    municipio_selecionado = col_loc4.multiselect("Município(s)", options=sorted(df_base['Municipio'].dropna().unique()))

    col_per1, col_per2, col_per3, col_per4 = st.columns(4)
    meses_disp = sorted(df_merged['MŒs'].dropna().unique())
    meses_nomes = {1:'Janeiro', 2:'Fevereiro', 3:'Março', 4:'Abril', 5:'Maio', 6:'Junho', 7:'Julho', 8:'Agosto', 9:'Setembro', 10:'Outubro', 11:'Novembro', 12:'Dezembro'}
    lista_meses = ["Todos"] + [f"{int(m):02d} - {meses_nomes.get(int(m))}" for m in meses_disp]
    mes_selecionado = col_per1.selectbox("Mês", lista_meses, index=len(lista_meses)-1)
    janela_meses = col_per2.slider("Janela da Base Ativa (meses)", 3, 6, 6)
    meta_ativa = col_per3.number_input("Meta Base Ativa (%)", 0, 100, 70)
    meta_total = col_per4.number_input("Meta Carteira Total (%)", 0, 100, 50)

# Aplicar Filtros
df_filtrado = aplicar_filtros_comuns(df_merged, incluir_mes=True)
df_historico = aplicar_filtros_comuns(df_merged, incluir_mes=False)
df_relatorio_base = aplicar_filtros_comuns(df_merged, incluir_mes=False)
df_historico_janela = calcular_janela_movel(df_historico, mes_selecionado, janela_meses)

# ============================================================
# NAVEGAÇÃO
# ============================================================
st.markdown("---")
opcoes_paginas = ["🏠 Visão Geral", "👥 Performance Vendedor", "📍 Positivação por Município", "🏷️ Positivação por Segmento", "🔀 Oportunidades Cruzadas", "🟢 Softys Falcon", "🟠 Kenvue Perfumaria", "🟤 Cenoura & Bronze", "📋 Batalha Naval", "🔍 Ficha do Cliente"]
opcao = st.radio("Selecione a página:", opcoes_paginas, horizontal=True)

# ============================================================
# PÁGINA: VISÃO GERAL (LOGICA YTD COLORIDA)
# ============================================================
if opcao == "🏠 Visão Geral":
    carteira_ativa_total = df_historico_janela[df_historico_janela['Nome_Fabricante'].notna()]['codigo_cliente'].nunique()
    positivados_periodo = df_filtrado[df_filtrado['Nome_Fabricante'].notna()]['codigo_cliente'].nunique()
    pct_ativa = (positivados_periodo / carteira_ativa_total * 100) if carteira_ativa_total > 0 else 0

    st.subheader("📅 Carteira Ativa (Janela Móvel)")
    col_a1, col_a2, col_a3 = st.columns(3)
    col_a1.metric(f"Carteira Ativa ({janela_meses} meses)", carteira_ativa_total)
    col_a2.metric("Positivados no Mês", positivados_periodo)
    col_a3.metric("% Positivação (Ativa)", f"{pct_ativa:.1f}%")

    if mes_selecionado != "Todos":
        mes_num = int(mes_selecionado.split(' - ')[0])
        ano_ref = df_historico[df_historico['MŒs'] == mes_num]['Ano'].max() if not df_historico[df_historico['MŒs'] == mes_num].empty else df_historico['Ano'].max()
    else:
        ano_ref = df_historico['Ano'].max()
        mes_num = 12

    # Dados mensais do ano atual
    df_ano_atual = df_historico[df_historico['Ano'] == ano_ref]
    mensal_pos = df_ano_atual.groupby('MŒs_Ano')['codigo_cliente'].nunique().reset_index()
    mensal_pos.columns = ['Mês', 'Clientes Positivados']

    # Cálculo YTD (Acumulado único do ano até o mês de referência)
    ytd_total = df_ano_atual[df_ano_atual['MŒs'] <= mes_num]['codigo_cliente'].nunique()

    # Montagem do gráfico customizado
    chart_labels = list(mensal_pos['Mês']) + [f"YTD {ano_ref}"]
    chart_values = list(mensal_pos['Clientes Positivados']) + [ytd_total]
    chart_colors = ['#2E8B57'] * len(mensal_pos) + ['#1a3a4a'] # Verde para os meses, Azul Escuro para YTD

    fig = go.Figure(go.Bar(
        x=chart_labels, y=chart_values, marker_color=chart_colors,
        text=chart_values, textposition='auto'
    ))
    fig.update_layout(title='Positivação Carteira Ativa (Mensal + YTD)', yaxis_title='Clientes Positivados')
    st.plotly_chart(fig, use_container_width=True)

    # Carteira Total
    total_clientes_base = df_base['codigo_cliente'].nunique()
    pct_total = (positivados_periodo / total_clientes_base * 100) if total_clientes_base > 0 else 0
    st.subheader("📋 Carteira Total")
    col1, col2, col3 = st.columns(3)
    col1.metric("Clientes na Carteira", total_clientes_base)
    col2.metric("Clientes Positivados", positivados_periodo)
    col3.metric("% Positivação (Carteira Total)", f"{pct_total:.1f}%")

# ============================================================
# PÁGINA: PERFORMANCE VENDEDOR
# ============================================================
elif opcao == "👥 Performance Vendedor":
    df_base_perf = df_base.copy()
    if coordenador_selecionado != "Todos": df_base_perf = df_base_perf[df_base_perf['Nome_Coordenador'] == coordenador_selecionado]
    if vendedor_selecionado != "Todos": df_base_perf = df_base_perf[df_base_perf['nome_vendedor_base'] == vendedor_selecionado]
    
    vendedores_base = [vendedor_selecionado] if vendedor_selecionado != "Todos" else df_filtrado['nome_vendedor'].dropna().unique()
    perf_list = []
    for vendedor in vendedores_base:
        pasta_v = vendedor_pasta.get(vendedor, "")
        clientes_carteira = df_base_perf[df_base_perf['nome_vendedor_base'] == vendedor]['codigo_cliente'].nunique()
        clientes_ativos_hist = df_historico_janela[df_historico_janela['nome_vendedor'] == vendedor]['codigo_cliente'].nunique()
        clientes_pos = df_filtrado[df_filtrado['nome_vendedor'] == vendedor]['codigo_cliente'].nunique()
        cob = df_filtrado[df_filtrado['nome_vendedor'] == vendedor].groupby('codigo_cliente')['Nome_Fabricante'].nunique()
        perf_list.append({
            'Vendedor': vendedor, 'Pasta': pasta_v, 'Total_Clientes': clientes_carteira, 'Clientes_Ativos_Hist': clientes_ativos_hist,
            'Clientes_Positivados': clientes_pos, '%_Positivação_Ativa': round((clientes_pos/clientes_ativos_hist*100 if clientes_ativos_hist > 0 else 0),1),
            'Cobertura_Media': round(cob.mean() if not cob.empty else 0, 1)
        })
    perf_vendedor = pd.DataFrame(perf_list).sort_values('%_Positivação_Ativa', ascending=False)
    st.plotly_chart(px.bar(perf_vendedor, x='Vendedor', y='%_Positivação_Ativa', title='% Positivação (Base Ativa)', text='%_Positivação_Ativa'), use_container_width=True)
    st.dataframe(perf_vendedor, use_container_width=True, hide_index=True)

# ============================================================
# PÁGINA: POSITIVAÇÃO POR MUNICÍPIO
# ============================================================
elif opcao == "📍 Positivação por Município":
    df_munic = df_filtrado.groupby('Municipio')['codigo_cliente'].nunique().reset_index().sort_values('codigo_cliente', ascending=False)
    st.plotly_chart(px.bar(df_munic, x='Municipio', y='codigo_cliente', text='codigo_cliente'), use_container_width=True)
    st.dataframe(df_munic, use_container_width=True)

# ============================================================
# PÁGINA: POSITIVAÇÃO POR SEGMENTO
# ============================================================
elif opcao == "🏷️ Positivação por Segmento":
    df_seg = df_filtrado.groupby('Segmento')['codigo_cliente'].nunique().reset_index().sort_values('codigo_cliente', ascending=False)
    st.plotly_chart(px.bar(df_seg, x='Segmento', y='codigo_cliente', text='codigo_cliente'), use_container_width=True)
    st.dataframe(df_seg, use_container_width=True)

# ============================================================
# PÁGINA: OPORTUNIDADES CRUZADAS
# ============================================================
elif opcao == "🔀 Oportunidades Cruzadas":
    st.subheader("🔀 Oportunidades Cruzadas")
    meses_op = sorted(df_relatorio_base['MŒs_Ano'].dropna().unique())
    m_ini = st.selectbox("Mês início:", meses_op, index=0)
    m_fim = st.selectbox("Mês fim:", meses_op, index=len(meses_op)-1)
    
    col_op1, col_op2 = st.columns(2)
    base_op = col_op1.multiselect("Comprou de:", INDUSTRIAS_DISPONIVEIS)
    comp_op = col_op2.multiselect("NÃO comprou de:", INDUSTRIAS_DISPONIVEIS)

    if base_op and comp_op:
        df_an = df_relatorio_base[(df_relatorio_base['MŒs_Ano'] >= m_ini) & (df_relatorio_base['MŒs_Ano'] <= m_fim)]
        clientes_com_base = set(df_an[df_an['Nome_Fabricante'].isin(base_op)]['codigo_cliente'].unique())
        clientes_com_comp = set(df_an[df_an['Nome_Fabricante'].isin(comp_op)]['codigo_cliente'].unique())
        op_list = list(clientes_com_base - clientes_com_comp)
        st.write(f"🔎 {len(op_list)} oportunidades encontradas.")
        st.dataframe(df_base[df_base['codigo_cliente'].isin(op_list)][['codigo_cliente', 'nome_cliente', 'nome_vendedor_base']], use_container_width=True)

# ============================================================
# PÁGINA: SOFTYS FALCON
# ============================================================
elif opcao == "🟢 Softys Falcon":
    df_s = df_relatorio_base[df_relatorio_base['Nome_Fabricante'] == 'SOFTYS FALCON']
    if not df_s.empty:
        st.subheader("🟢 Softys Falcon")
        resumo = df_s.groupby('Categoria')['codigo_cliente'].nunique().reset_index()
        st.dataframe(resumo, use_container_width=True)
        # Batalha Naval Softys
        bn_s = df_s.pivot_table(index=['codigo_cliente', 'nome_cliente', 'Municipio'], columns='Categoria', aggfunc='size', fill_value=0)
        st.write("Batalha Naval Softys")
        st.dataframe((bn_s > 0).astype(int), use_container_width=True)
    else: st.warning("Sem dados.")

# ============================================================
# PÁGINA: KENVUE PERFUMARIA
# ============================================================
elif opcao == "🟠 Kenvue Perfumaria":
    df_ken = df_filtrado[(df_filtrado['Nome_Fabricante'] == 'KENVUE') & (df_filtrado['Canal'] == 'PERFUMARIA')]
    st.subheader("🟠 Kenvue - Canal Perfumaria")
    st.metric("Clientes Positivados", df_ken['codigo_cliente'].nunique())
    st.dataframe(df_ken[['codigo_cliente', 'nome_cliente', 'Municipio', 'nome_vendedor']].drop_duplicates(), use_container_width=True)

# ============================================================
# PÁGINA: CENOURA & BRONZE
# ============================================================
elif opcao == "🟤 Cenoura & Bronze":
    df_cb = df_relatorio_base[df_relatorio_base['Linha_Produto'] == 'CENOURA & BRONZE']
    if not df_cb.empty:
        st.subheader("🟤 Cenoura & Bronze")
        st.dataframe(df_cb.groupby('nome_vendedor')['codigo_cliente'].nunique().reset_index(), use_container_width=True)
    else: st.warning("Sem dados.")

# ============================================================
# PÁGINA: BATALHA NAVAL (GERAL)
# ============================================================
elif opcao == "📋 Batalha Naval":
    st.subheader("📋 Batalha Naval")
    bn = df_filtrado.pivot_table(index=['codigo_cliente', 'nome_cliente'], columns='Nome_Fabricante', aggfunc='size', fill_value=0)
    st.dataframe((bn > 0).astype(int).reset_index(), use_container_width=True)

# ============================================================
# PÁGINA: FICHA DO CLIENTE
# ============================================================
elif opcao == "🔍 Ficha do Cliente":
    st.subheader("🔍 Ficha do Cliente")
    busca = st.text_input("Código ou Nome")
    if busca:
        mask = (df_base['codigo_cliente'].astype(str).str.contains(busca)) | (df_base['nome_cliente'].str.contains(busca, case=False))
        st.dataframe(df_base[mask], use_container_width=True)
