"""Taxi Fare app (Dash) chay sau SSO: truy van SQL qua datanexus duoi quyen user dang nhap.

Port tu vi du Databricks Apps (Dash + databricks-sql-connector) sang datanexus:
- `http_path` = /sql/1.0/connections/<connection_id> (thay cho warehouses/<id>)
- token lay tu header `X-Forwarded-Access-Token` do ingress/forward-auth gan.
"""

import os

import dash
import dash_ag_grid as dag
import dash_bootstrap_components as dbc
import flask
import pandas as pd
import plotly.express as px
from dash import Input, Output, State, dcc, html

from datanexus import apps, sql

HOST = os.environ.get("DATANEXUS_HOST", "")
CONNECTION_ID = os.environ.get("DATANEXUS_CONNECTION_ID", "")
# Chi dung lam ten bang (khong phai input cua user) nen noi vao SQL duoc.
TABLE = os.environ.get("DATANEXUS_TAXI_TABLE", "samples.nyctaxi.trips")
ROW_LIMIT = int(os.environ.get("DATANEXUS_ROW_LIMIT", "5000"))

NUMERIC_COLS = ("trip_distance", "fare_amount", "pickup_zip", "dropoff_zip")


class AppError(Exception):
    """Loi hien thi cho user."""


def _token() -> str:
    token = apps.forwarded_token(flask.request.headers)
    if not token:
        raise AppError("Thiếu X-Forwarded-Access-Token. App phải truy cập qua ingress/forward-auth.")
    return token


def sql_query(query: str, parameters: dict | None = None) -> pd.DataFrame:
    """Chay SQL duoi quyen user dang nhap, tra ve DataFrame."""
    if not (HOST and CONNECTION_ID):
        raise AppError("Thiếu DATANEXUS_HOST hoặc DATANEXUS_CONNECTION_ID.")
    try:
        with sql.connect(
            server_hostname=HOST,
            http_path=f"/sql/1.0/connections/{CONNECTION_ID}",
            access_token=_token(),
        ) as conn, conn.cursor() as cur:
            cur.execute(query, parameters=parameters)
            df = cur.fetchall_arrow().to_pandas()
    except sql.exc.AuthenticationError as exc:
        raise AppError("Phiên đăng nhập hết hạn — tải lại trang.") from exc
    except sql.exc.Error as exc:
        raise AppError(str(exc)) from exc
    for col in NUMERIC_COLS:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


def load_data() -> pd.DataFrame:
    return sql_query(f"SELECT * FROM {TABLE} LIMIT {ROW_LIMIT}")


def predict_fare(pickup: str, dropoff: str) -> str:
    """Gia du doan = fare trung binh cua cac chuyen cung cap zipcode (tinh tren server)."""
    try:
        params = {"pickup": int(pickup), "dropoff": int(dropoff)}
    except (TypeError, ValueError):
        return "Zipcode phải là số."
    df = sql_query(
        f"SELECT AVG(fare_amount) AS fare, COUNT(*) AS trips FROM {TABLE} "
        "WHERE pickup_zip = :pickup AND dropoff_zip = :dropoff",
        parameters=params,
    )
    trips = int(pd.to_numeric(df["trips"]).iloc[0] or 0) if len(df) else 0
    if not trips:
        return "Không có chuyến nào giữa 2 zipcode này."
    fare = float(pd.to_numeric(df["fare"]).iloc[0])
    return f"Predicted Fare: ${fare:.2f} ({trips} chuyến)"


app = dash.Dash(__name__, external_stylesheets=[dbc.themes.BOOTSTRAP], title="Taxi Fare")
server = app.server  # cho gunicorn

app.layout = dbc.Container(
    [
        dcc.Store(id="page-load-trigger", data=0),
        dbc.Row(
            dbc.Col(
                [
                    html.H1("Taxi Fare Distribution", className="mt-3"),
                    html.Div(id="greeting", className="text-muted mb-3"),
                    html.Div(id="error-banner"),
                ],
                width=12,
            )
        ),
        dbc.Row(
            [
                dbc.Col(
                    dcc.Loading(
                        dcc.Graph(id="fare-scatter", style={"height": "400px", "width": "100%"})
                    ),
                    md=8,
                ),
                dbc.Col(
                    [
                        html.H3("Predict Fare"),
                        dbc.Label("From (zipcode)"),
                        dbc.Input(id="from-zipcode", type="text", value="10003"),
                        dbc.Label("To (zipcode)", className="mt-2"),
                        dbc.Input(id="to-zipcode", type="text", value="11238"),
                        dbc.Button(
                            "Predict", id="submit-button", n_clicks=0, color="primary", className="mt-3"
                        ),
                        dcc.Loading(
                            html.Div(
                                id="prediction-output",
                                className="mt-3",
                                style={"fontSize": "24px", "fontWeight": "bold"},
                            )
                        ),
                    ],
                    md=4,
                ),
            ]
        ),
        dbc.Row(
            dbc.Col(
                dag.AgGrid(
                    id="data-grid",
                    defaultColDef={"sortable": True, "filter": True, "resizable": True},
                    dashGridOptions={"pagination": True, "paginationPageSize": 50},
                    className="ag-theme-alpine mt-3",
                ),
                width=12,
            )
        ),
    ],
    fluid=True,
)


@app.callback(
    Output("greeting", "children"),
    Output("fare-scatter", "figure"),
    Output("data-grid", "rowData"),
    Output("data-grid", "columnDefs"),
    Output("error-banner", "children"),
    Input("page-load-trigger", "data"),
)
def update_visuals(_):
    user = apps.forwarded_user(flask.request.headers)
    greeting = (
        f"Xin chào {user} · truy vấn chạy dưới quyền của bạn · connection {CONNECTION_ID}"
        if user
        else "Không có header SSO (X-Forwarded-Email)."
    )
    try:
        data = load_data()
    except AppError as exc:
        return greeting, px.scatter(), [], [], dbc.Alert(str(exc), color="danger")

    fig = px.scatter(
        data,
        x="trip_distance",
        y="fare_amount",
        labels={"fare_amount": "Fare", "trip_distance": "Distance"},
    )
    return (
        greeting,
        fig,
        data.to_dict("records"),
        [{"headerName": c, "field": c} for c in data.columns],
        None,
    )


@app.callback(
    Output("prediction-output", "children"),
    Input("submit-button", "n_clicks"),
    State("from-zipcode", "value"),
    State("to-zipcode", "value"),
)
def render_prediction(_, pickup, dropoff):
    try:
        return predict_fare(pickup, dropoff)
    except AppError as exc:
        return dbc.Alert(str(exc), color="danger", className="fs-6 fw-normal")


if __name__ == "__main__":
    # Debug tat mac dinh; dat DASH_DEBUG=true khi chay local.
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "8501")))
