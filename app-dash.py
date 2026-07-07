# Learn more about Dash on Domino:
#   https://docs.dominodatalab.com/en/latest/user_guide/de2589/publish-a-dash-app/

import os

import dash
import pandas as pd
import plotly
from dash import dash_table, dcc, html, Input, Output, State

user = os.environ.get("DOMINO_PROJECT_OWNER")
project = os.environ.get("DOMINO_PROJECT_NAME")
run_id = os.environ.get("DOMINO_RUN_ID")

# Configure the url pathname prefix where the Dash app is served under
requests_pathname_prefix = os.environ.get("DOMINO_RUN_HOST_PATH")

app = dash.Dash(
    __name__,
    requests_pathname_prefix=requests_pathname_prefix,
)

app.scripts.config.serve_locally = True
# app.css.config.serve_locally = True

DF_GAPMINDER = pd.read_csv(
    'https://raw.githubusercontent.com/plotly/datasets/master/gapminderDataFiveYear.csv'
)
DF_GAPMINDER = DF_GAPMINDER[DF_GAPMINDER['year'] == 2007]
# Re-order columns
DF_GAPMINDER = DF_GAPMINDER.reindex(
    ['country', 'continent', 'lifeExp', 'gdpPercap', 'pop', 'year'], axis=1
)

app.layout = html.Div([
    html.H4('Gapminder DataTable'),
    dash_table.DataTable(
        id='datatable-gapminder',
        columns=[{"name": col, "id": col} for col in DF_GAPMINDER.columns],
        data=DF_GAPMINDER.to_dict('records'),
        editable=True,
        filter_action="native",
        sort_action="native",
        row_selectable="multi",
        selected_rows=[],
        fixed_rows={
            'headers': True,
        },
        style_table={
            'maxHeight': '400px',
            'overflowY': 'auto',
        },
        style_header={
            'fontWeight': 'bold',
            'textAlign': 'center',
        },
        style_cell={
            'textAlign': 'right',
            'width': '15%',
        },
        style_cell_conditional=[
            {'if': {'column_id': 'country'}, 'width': '20%'},
            {'if': {'column_id': 'country'}, 'textAlign': 'left'},
            {'if': {'column_id': 'continent'}, 'textAlign': 'center'},
            {'if': {'column_id': 'year'}, 'textAlign': 'center'}
        ]
    ),
    html.Div(id='selected-rows'),
    dcc.Graph(
        id='graph-gapminder'
    ),
], className="container", style={
    "margin-left": "20px",
    "margin-right": "20px",
})


@app.callback(
    Output('datatable-gapminder', 'selected_rows'),
    [Input('graph-gapminder', 'clickData')],
    [State('datatable-gapminder', 'selected_rows')])
def update_selected_rows(clickData, selected_rows):
    if clickData:
        for point in clickData['points']:
            if point['pointNumber'] in selected_rows:
                selected_rows.remove(point['pointNumber'])
            else:
                selected_rows.append(point['pointNumber'])
    return selected_rows


@app.callback(
    Output('graph-gapminder', 'figure'),
    [Input('datatable-gapminder', 'data'),
     Input('datatable-gapminder', 'selected_rows')])
def update_figure(rows, selected_rows):
    dff = pd.DataFrame(rows)
    fig = plotly.tools.make_subplots(
        rows=3, cols=1,
        subplot_titles=('Life Expectancy', 'GDP Per Capita', 'Population'),
        shared_xaxes=True)
    marker = {'color': ['#0074D9'] * len(dff)}
    for i in (selected_rows or []):
        marker['color'][i] = '#FF851B'
    fig.append_trace({
        'x': dff['country'],
        'y': dff['lifeExp'],
        'type': 'bar',
        'marker': marker
    }, 1, 1)
    fig.append_trace({
        'x': dff['country'],
        'y': dff['gdpPercap'],
        'type': 'bar',
        'marker': marker
    }, 2, 1)
    fig.append_trace({
        'x': dff['country'],
        'y': dff['pop'],
        'type': 'bar',
        'marker': marker
    }, 3, 1)
    fig['layout']['showlegend'] = False
    fig['layout']['height'] = 800
    fig['layout']['margin'] = {
        'l': 40,
        'r': 10,
        't': 60,
        'b': 200
    }
    fig['layout']['yaxis3']['type'] = 'log'
    return fig


app.css.append_css({
    'external_url': 'https://codepen.io/chriddyp/pen/bWLwgP.css'
})

if __name__ == '__main__':
    app.run_server(host='0.0.0.0', port=8888)  # Domino hosts all apps at 0.0.0.0:8888