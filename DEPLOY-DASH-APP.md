# Building & Serving a Dash App in Domino — from scratch

Self-contained guide to create a Plotly Dash app in a clean Domino project and publish it.
Every file you need is included in full below — copy each block into a file of the given name.

---

## How it fits together

A Domino **App** is a long-running web server that Domino starts and exposes behind its
reverse proxy. Three files make this work:

| File                    | Role                                                       |
|-------------------------|------------------------------------------------------------|
| `app-dash.py`           | The Dash application code (the web server itself)          |
| `app.sh`                | The launch command Domino runs to start the app           |
| `requirements_apps.txt` | Extra Python packages the app needs                        |

**The contract:** Domino runs `app.sh`, and `app.sh` must start a web server listening on
`0.0.0.0:8888`. Domino's proxy always forwards traffic to that host and port.

Two things in `app-dash.py` are what make it work behind the proxy:

- **URL path prefix:** `requests_pathname_prefix = os.environ.get("DOMINO_RUN_HOST_PATH")`
  Domino serves the app under a sub-path (not the domain root) and injects that path via the
  `DOMINO_RUN_HOST_PATH` environment variable. Without this, the page loads blank and all
  assets/callbacks return 404.
- **Host and port:** `app.run_server(host='0.0.0.0', port=8888)`
  Binding anywhere else makes the app invisible to the proxy.

---

## Part A — Create the files

Create all three files in the **root** of your project.

### File 1 of 3 — `app-dash.py`

The Dash application. Note the two proxy-critical pieces (path prefix near the top, and the
`0.0.0.0:8888` bind at the bottom) — keep them exactly as written.

```python
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
```

### File 2 of 3 — `app.sh`

The launch script. This is the entry point Domino runs. **Only one app command may be active.**
The version below launches the Dash app and nothing else.

> `app.sh` must be in the project **root** and named exactly `app.sh` — that filename is fixed.

```bash
#!/usr/bin/env bash

# This is the bash script Domino runs when you publish an App.
# It installs dependencies, then starts the Dash web server on 0.0.0.0:8888.

pip install -r requirements_apps.txt --user
python app-dash.py
```

### File 3 of 3 — `requirements_apps.txt`

The Python packages the app needs. `app.sh` installs these at launch.

```
flask~=2.3.2
dash~=2.0
pandas~=2.0
```

> Installing at launch is convenient but slows startup. For a production app, bake these
> packages into the Compute Environment instead and drop the `pip install` line from `app.sh`.

---

## Part B — Publish in the Domino UI

### Step 1. Create/prepare the project

Create a new Domino project (or open an existing one) and add the three files above to its root.
If you're editing in a Workspace, use **File → Sync** (or the Git sync controls) so the project's
stored files include them.

### Step 2. Confirm the Compute Environment

Go to **Project Settings → Hardware & Environment**. Use a Domino Standard Environment (or one
that can `pip install` Dash/pandas/plotly). Combined with `requirements_apps.txt`, this covers
the app's needs.

### Step 3. Open the App publishing page

In the left nav of your project, click **App** (may appear under **Publish → App**).

### Step 4. Configure and publish

- Enter a **title** (and optional description).
- Pick a **Hardware Tier** — a small tier is fine for this demo.
- You do **not** select a Python file directly; Domino uses `app.sh` as the entry point, and
  `app.sh` decides what runs.
- Set **permissions** (private / collaborators / anyone with the link), per your deployment's policy.
- Click **Publish**.

### Step 5. Wait for status = Running

The App tab shows **Pending → Running**. The first launch is slower because of the `pip install`
step. Once it reads **Running**, click **View App** (or **Open in new tab**) to load the dashboard.

### Step 6. If something goes wrong

Use **View Logs** on the App page. That's where `pip` failures or a wrong bind address show up.

### Step 7. To update later

Change your code → re-sync → click **Republish** / **Restart** on the App tab.

---

## What happens at runtime

1. You click **Publish** in the UI.
2. Domino spins up a container using your project's Compute Environment and mounts your files.
3. Domino sets environment variables (`DOMINO_RUN_HOST_PATH`, `DOMINO_PROJECT_OWNER`, etc.).
4. Domino runs `app.sh` → `pip install` runs, then `python app-dash.py`.
5. Dash starts listening on `0.0.0.0:8888`.
6. Domino's reverse proxy detects the server and exposes it at your app's URL.

---

## Troubleshooting checklist

- [ ] `app.sh` has **only** the Dash commands active (no Flask/R/Shiny lines).
- [ ] `app.sh` is in the project **root** and named exactly `app.sh`.
- [ ] `app-dash.py` reads `DOMINO_RUN_HOST_PATH` into `requests_pathname_prefix`
      (fixes blank page / 404 assets).
- [ ] `app-dash.py` binds `host='0.0.0.0', port=8888` (fixes app unreachable by proxy).
- [ ] `dash`, `pandas`, `flask` are installable (in `requirements_apps.txt` or the environment).

---

## Reference

- Publish a Dash app: https://docs.dominodatalab.com/en/latest/user_guide/de2589/publish-a-dash-app/
- Environment management: https://docs.dominodatalab.com/en/latest/reference/environments/Environment_management.html
