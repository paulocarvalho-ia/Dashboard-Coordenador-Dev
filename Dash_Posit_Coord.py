# DataFrame combinado para o gráfico
graph_softys = monthly_totals.copy()
graph_softys = pd.concat([graph_softys, pd.DataFrame([{'Mês': 'YTD', 'Clientes': ytd_total}])], ignore_index=True)
graph_softys['Tipo'] = np.where(graph_softys['Mês'] == 'YTD', 'YTD', 'Mensal')

# Ordenar categorias
categorias_softys = sorted(monthly_totals['Mês'].unique()) + ['YTD']
graph_softys['Mês'] = pd.Categorical(graph_softys['Mês'], categories=categorias_softys, ordered=True)
graph_softys = graph_softys.sort_values('Mês')

fig_softys = px.bar(
    graph_softys,
    x='Mês',
    y='Clientes',
    color='Tipo',
    color_discrete_map={'Mensal': '#2E8B57', 'YTD': '#1a3a4a'},
    text='Clientes',
    title='Positivação Softys Falcon (Mensal + YTD)'
)
fig_softys.update_traces(textposition='outside')
fig_softys.update_layout(barmode='group', uniformtext_minsize=8)
