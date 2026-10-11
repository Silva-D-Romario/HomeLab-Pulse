from typing import Any

import httpx
import plotly.graph_objects as go
from dash import Dash, Input, Output, State, ctx, dcc, html
from dash.exceptions import PreventUpdate

from homelab_pulse.config import get_settings

settings = get_settings()
COLORS = {
    "background": "#071713",
    "surface": "#102722",
    "surface_alt": "#17352e",
    "text": "#f2f7f4",
    "muted": "#9eb5ad",
    "green": "#b7f34a",
    "red": "#ff6b6b",
    "amber": "#ffc857",
    "blue": "#61a5ff",
}
LOGIN_PANEL_STYLE = {
    "background": COLORS["surface"],
    "borderRadius": "18px",
    "display": "flex",
    "flexDirection": "column",
    "gap": "14px",
    "margin": "12vh auto",
    "maxWidth": "380px",
    "padding": "32px",
}


class DashboardApiError(RuntimeError):
    pass


def authenticate(email: str, password: str) -> str:
    try:
        response = httpx.post(
            f"{settings.api_base_url}/api/v1/auth/login",
            json={"email": email, "password": password},
            timeout=10,
        )
        response.raise_for_status()
    except httpx.HTTPStatusError as error:
        if error.response.status_code == 401:
            raise DashboardApiError("E-mail ou senha inválidos.") from error
        raise DashboardApiError("A API recusou o acesso ao dashboard.") from error
    except httpx.HTTPError as error:
        raise DashboardApiError("Não foi possível conectar à API.") from error
    return str(response.json()["access_token"])


def fetch_dashboard(token: str) -> dict[str, Any]:
    try:
        response = httpx.get(
            f"{settings.api_base_url}/api/v1/dashboard",
            headers={"Authorization": f"Bearer {token}"},
            timeout=10,
        )
        response.raise_for_status()
    except httpx.HTTPStatusError as error:
        if error.response.status_code == 401:
            raise DashboardApiError("Sua sessão expirou. Entre novamente.") from error
        raise DashboardApiError("Não foi possível carregar os indicadores.") from error
    except httpx.HTTPError as error:
        raise DashboardApiError("A API está indisponível no momento.") from error
    return dict(response.json())


def chart_layout(title: str) -> dict[str, Any]:
    return {
        "title": {"text": title, "font": {"size": 17}},
        "paper_bgcolor": COLORS["surface"],
        "plot_bgcolor": COLORS["surface"],
        "font": {"color": COLORS["text"]},
        "margin": {"l": 40, "r": 24, "t": 55, "b": 45},
        "legend": {"orientation": "h", "y": -0.2},
    }


def build_figures(payload: dict[str, Any]) -> tuple[go.Figure, go.Figure, go.Figure]:
    status_figure = go.Figure(
        go.Pie(
            labels=["Online", "Offline", "Sem dados"],
            values=[
                payload["services_up"],
                payload["services_down"],
                payload["services_unknown"],
            ],
            hole=0.68,
            marker={"colors": [COLORS["green"], COLORS["red"], COLORS["muted"]]},
        )
    )
    status_figure.update_layout(**chart_layout("Estado atual dos serviços"))

    services = payload["services"]
    availability_figure = go.Figure(
        go.Bar(
            x=[service["name"] for service in services],
            y=[service["availability_percent"] or 0 for service in services],
            marker_color=COLORS["green"],
            hovertemplate="%{x}: %{y:.1f}%<extra></extra>",
        )
    )
    availability_figure.update_layout(**chart_layout("Disponibilidade por serviço — 24h"))
    availability_figure.update_yaxes(range=[0, 100], ticksuffix="%")

    latency_figure = go.Figure()
    checks_by_service: dict[str, list[dict[str, Any]]] = {}
    for check in payload["recent_checks"]:
        if check["response_time_ms"] is not None:
            checks_by_service.setdefault(check["service_name"], []).append(check)
    for service_name, checks in checks_by_service.items():
        latency_figure.add_trace(
            go.Scatter(
                name=service_name,
                x=[check["checked_at"] for check in checks],
                y=[check["response_time_ms"] for check in checks],
                mode="lines+markers",
            )
        )
    latency_figure.update_layout(**chart_layout("Latência recente"))
    latency_figure.update_yaxes(title="ms")
    return status_figure, availability_figure, latency_figure


def kpi_card(label: str, element_id: str) -> html.Div:
    return html.Div(
        [html.Span(label, style={"color": COLORS["muted"]}), html.Strong("—", id=element_id)],
        style={
            "background": COLORS["surface"],
            "border": f"1px solid {COLORS['surface_alt']}",
            "borderRadius": "14px",
            "display": "flex",
            "flexDirection": "column",
            "gap": "10px",
            "padding": "20px",
            "fontSize": "26px",
        },
    )


def build_services_table(services: list[dict[str, Any]]) -> html.Table:
    headings = ["Serviço", "Estado", "Disponibilidade", "Latência média", "Última verificação"]
    rows = []
    for service in services:
        availability = service["availability_percent"]
        latency = service["average_response_time_ms"]
        rows.append(
            html.Tr(
                [
                    html.Td(service["name"]),
                    html.Td(service["status"] or "sem dados"),
                    html.Td(f"{availability:.1f}%" if availability is not None else "—"),
                    html.Td(f"{latency} ms" if latency is not None else "—"),
                    html.Td(service["last_checked_at"] or "—"),
                ]
            )
        )
    return html.Table(
        [html.Thead(html.Tr([html.Th(heading) for heading in headings])), html.Tbody(rows)],
        style={"background": COLORS["surface"], "width": "100%", "padding": "12px"},
    )


app = Dash(__name__, title="HomeLab Pulse", update_title="Atualizando...")
server = app.server
app.layout = html.Main(
    [
        dcc.Store(id="auth-token", storage_type="session"),
        dcc.Interval(id="refresh-interval", interval=30_000),
        html.Section(
            [
                html.Div(
                    "HP",
                    style={
                        "background": COLORS["green"],
                        "borderRadius": "50%",
                        "color": COLORS["background"],
                        "display": "grid",
                        "fontWeight": "800",
                        "height": "42px",
                        "placeItems": "center",
                        "width": "42px",
                    },
                ),
                html.H1("HomeLab Pulse", style={"margin": 0}),
                html.P("Entre para visualizar somente os seus serviços."),
                dcc.Input(
                    id="email",
                    type="email",
                    placeholder="E-mail",
                    style={"padding": "12px"},
                ),
                dcc.Input(
                    id="password",
                    type="password",
                    placeholder="Senha",
                    style={"padding": "12px"},
                ),
                html.Button("Entrar", id="login-button", style={"padding": "12px"}),
                html.P(id="login-message", style={"color": COLORS["red"]}),
            ],
            id="login-panel",
            style=LOGIN_PANEL_STYLE,
        ),
        html.Section(
            [
                html.Header(
                    [
                        html.Div([html.H1("HomeLab Pulse"), html.P(id="updated-at")]),
                        html.Div(
                            [
                                html.Button("Atualizar", id="refresh-button"),
                                html.Button("Sair", id="logout-button"),
                            ],
                            style={"display": "flex", "gap": "10px"},
                        ),
                    ],
                    style={
                        "display": "flex",
                        "justifyContent": "space-between",
                        "alignItems": "center",
                    },
                ),
                html.P(id="dashboard-message", style={"color": COLORS["red"]}),
                html.Div(
                    [
                        kpi_card("Servidores", "servers-total"),
                        kpi_card("Serviços", "services-total"),
                        kpi_card("Disponibilidade 24h", "availability-total"),
                        kpi_card("Latência média", "latency-average"),
                        kpi_card("Incidentes abertos", "incidents-open"),
                    ],
                    style={
                        "display": "grid",
                        "gridTemplateColumns": "repeat(auto-fit, minmax(170px, 1fr))",
                        "gap": "14px",
                    },
                ),
                html.Div(
                    [dcc.Graph(id="status-chart"), dcc.Graph(id="availability-chart")],
                    style={
                        "display": "grid",
                        "gridTemplateColumns": "repeat(auto-fit, minmax(320px, 1fr))",
                        "gap": "14px",
                        "marginTop": "14px",
                    },
                ),
                dcc.Graph(id="latency-chart", style={"marginTop": "14px"}),
                html.H2("Serviços monitorados"),
                html.Div(id="services-table", style={"overflowX": "auto"}),
            ],
            id="dashboard-panel",
            style={"display": "none"},
        ),
    ],
    style={
        "background": COLORS["background"],
        "color": COLORS["text"],
        "fontFamily": "Inter, system-ui, sans-serif",
        "minHeight": "100vh",
        "padding": "24px clamp(16px, 4vw, 64px)",
    },
)


@app.callback(
    Output("auth-token", "data"),
    Output("login-message", "children"),
    Input("login-button", "n_clicks"),
    Input("logout-button", "n_clicks"),
    State("email", "value"),
    State("password", "value"),
    prevent_initial_call=True,
)
def update_session(
    _login_clicks: int | None,
    _logout_clicks: int | None,
    email: str | None,
    password: str | None,
) -> tuple[str | None, str]:
    if ctx.triggered_id == "logout-button":
        return None, ""
    if not email or not password:
        return None, "Informe e-mail e senha."
    try:
        token = authenticate(email, password)
    except DashboardApiError as error:
        return None, str(error)
    return token, ""


@app.callback(
    Output("login-panel", "style"),
    Output("dashboard-panel", "style"),
    Input("auth-token", "data"),
)
def update_visibility(token: str | None) -> tuple[dict[str, str], dict[str, str]]:
    if token:
        return {**LOGIN_PANEL_STYLE, "display": "none"}, {"display": "block"}
    return LOGIN_PANEL_STYLE, {"display": "none"}


@app.callback(
    Output("servers-total", "children"),
    Output("services-total", "children"),
    Output("availability-total", "children"),
    Output("latency-average", "children"),
    Output("incidents-open", "children"),
    Output("status-chart", "figure"),
    Output("availability-chart", "figure"),
    Output("latency-chart", "figure"),
    Output("services-table", "children"),
    Output("updated-at", "children"),
    Output("dashboard-message", "children"),
    Input("auth-token", "data"),
    Input("refresh-button", "n_clicks"),
    Input("refresh-interval", "n_intervals"),
)
def refresh_dashboard(
    token: str | None,
    _refresh_clicks: int | None,
    _intervals: int,
) -> tuple[Any, ...]:
    if not token:
        raise PreventUpdate
    try:
        payload = fetch_dashboard(token)
    except DashboardApiError as error:
        empty = go.Figure()
        return "—", "—", "—", "—", "—", empty, empty, empty, None, "", str(error)

    status_figure, availability_figure, latency_figure = build_figures(payload)
    services_table = build_services_table(payload["services"])
    availability = payload["availability_percent"]
    average_latency = payload["average_response_time_ms"]
    return (
        payload["servers_total"],
        payload["services_total"],
        f"{availability:.1f}%" if availability is not None else "—",
        f"{average_latency} ms" if average_latency is not None else "—",
        payload["open_incidents"],
        status_figure,
        availability_figure,
        latency_figure,
        services_table,
        f"Atualizado em {payload['generated_at']}",
        "",
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=settings.dashboard_port, debug=False)
