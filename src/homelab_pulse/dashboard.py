from pathlib import Path
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


def fetch_servers(token: str) -> list[dict[str, Any]]:
    try:
        response = httpx.get(
            f"{settings.api_base_url}/api/v1/servers",
            headers={"Authorization": f"Bearer {token}"},
            timeout=10,
        )
        response.raise_for_status()
    except httpx.HTTPStatusError as error:
        if error.response.status_code == 401:
            raise DashboardApiError("Sua sessão expirou. Entre novamente.") from error
        raise DashboardApiError("Não foi possível carregar os servidores.") from error
    except httpx.HTTPError as error:
        raise DashboardApiError("A API está indisponível no momento.") from error
    return list(response.json())


def create_server(token: str, name: str, host: str, description: str | None) -> None:
    try:
        response = httpx.post(
            f"{settings.api_base_url}/api/v1/servers",
            headers={"Authorization": f"Bearer {token}"},
            json={"name": name, "host": host, "description": description or None},
            timeout=10,
        )
        response.raise_for_status()
    except httpx.HTTPStatusError as error:
        if error.response.status_code == 401:
            message = "Sua sessão expirou. Entre novamente."
        elif error.response.status_code == 409:
            message = "Já existe um servidor com esse nome."
        elif error.response.status_code == 422:
            message = "Revise os dados informados para o servidor."
        else:
            message = "Não foi possível cadastrar o servidor."
        raise DashboardApiError(message) from error
    except httpx.HTTPError as error:
        raise DashboardApiError("A API está indisponível no momento.") from error


def create_service(
    token: str,
    server_id: str,
    name: str,
    kind: str,
    target_url: str,
) -> None:
    try:
        response = httpx.post(
            f"{settings.api_base_url}/api/v1/servers/{server_id}/services",
            headers={"Authorization": f"Bearer {token}"},
            json={"name": name, "kind": kind, "target_url": target_url, "enabled": True},
            timeout=10,
        )
        response.raise_for_status()
    except httpx.HTTPStatusError as error:
        if error.response.status_code == 401:
            message = "Sua sessão expirou. Entre novamente."
        elif error.response.status_code == 409:
            message = "Já existe um serviço com esse nome neste servidor."
        elif error.response.status_code == 422:
            message = "Informe uma URL completa, incluindo http:// ou https://."
        else:
            message = "Não foi possível cadastrar o serviço."
        raise DashboardApiError(message) from error
    except httpx.HTTPError as error:
        raise DashboardApiError("A API está indisponível no momento.") from error


def chart_layout(title: str) -> dict[str, Any]:
    return {
        "title": {"text": title, "font": {"size": 17}},
        "paper_bgcolor": COLORS["surface"],
        "plot_bgcolor": COLORS["surface"],
        "font": {"color": COLORS["text"]},
        "margin": {"l": 40, "r": 24, "t": 55, "b": 45},
        "legend": {"orientation": "h", "y": -0.2},
    }


def empty_figure(title: str, message: str) -> go.Figure:
    figure = go.Figure()
    figure.update_layout(**chart_layout(title))
    figure.update_xaxes(visible=False)
    figure.update_yaxes(visible=False)
    figure.add_annotation(
        text=message,
        x=0.5,
        y=0.5,
        xref="paper",
        yref="paper",
        showarrow=False,
        font={"color": COLORS["muted"], "size": 15},
    )
    return figure


def build_figures(payload: dict[str, Any]) -> tuple[go.Figure, go.Figure, go.Figure]:
    services = payload["services"]
    if not services:
        message = "Cadastre um servidor e o primeiro serviço para começar."
        return (
            empty_figure("Estado atual dos serviços", message),
            empty_figure("Disponibilidade por serviço — 24h", message),
            empty_figure("Latência recente", message),
        )

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
    if checks_by_service:
        latency_figure.update_layout(**chart_layout("Latência recente"))
        latency_figure.update_yaxes(title="ms")
    else:
        latency_figure = empty_figure(
            "Latência recente",
            "A latência aparecerá após a primeira verificação.",
        )
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


def build_services_table(services: list[dict[str, Any]]) -> html.Table | html.Div:
    if not services:
        return html.Div(
            [
                html.Strong("Nenhum serviço cadastrado."),
                html.Span(" Use o formulário acima para começar o monitoramento."),
            ],
            className="hp-empty-state",
        )
    headings = [
        "Serviço",
        "Integração",
        "Estado",
        "Disponibilidade",
        "Latência média",
        "Última verificação",
    ]
    rows = []
    for service in services:
        availability = service["availability_percent"]
        latency = service["average_response_time_ms"]
        integration = service.get("integration_data") or {}
        integration_label = " ".join(
            str(value)
            for value in [integration.get("product"), integration.get("version")]
            if value
        )
        rows.append(
            html.Tr(
                [
                    html.Td(service["name"]),
                    html.Td(integration_label or "—"),
                    html.Td(service["status"] or "sem dados"),
                    html.Td(f"{availability:.1f}%" if availability is not None else "—"),
                    html.Td(f"{latency} ms" if latency is not None else "—"),
                    html.Td(service["last_checked_at"] or "—"),
                ]
            )
        )
    return html.Table(
        [html.Thead(html.Tr([html.Th(heading) for heading in headings])), html.Tbody(rows)],
        className="hp-table",
    )


app = Dash(
    __name__,
    title="HomeLab Pulse",
    update_title="Atualizando...",
    assets_folder=str(Path.cwd() / "assets"),
)
server = app.server
app.layout = html.Main(
    [
        dcc.Store(id="auth-token", storage_type="session"),
        dcc.Store(id="server-revision", data=0),
        dcc.Store(id="service-revision", data=0),
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
                html.H1("HomeLab Pulse", className="hp-login-title"),
                html.P(
                    "Monitore seus serviços e containers em um só lugar.",
                    className="hp-login-description",
                ),
                html.Label("E-mail", htmlFor="email", className="hp-label"),
                dcc.Input(
                    id="email",
                    type="email",
                    placeholder="voce@exemplo.com",
                    className="hp-input",
                ),
                html.Label("Senha", htmlFor="password", className="hp-label"),
                dcc.Input(
                    id="password",
                    type="password",
                    placeholder="Digite sua senha",
                    className="hp-input",
                ),
                html.Button("Entrar", id="login-button", className="hp-button hp-button-primary"),
                html.P(id="login-message", className="hp-message hp-message-error"),
            ],
            id="login-panel",
            style=LOGIN_PANEL_STYLE,
        ),
        html.Section(
            [
                html.Header(
                    [
                        html.Div(
                            [
                                html.P("PAINEL DE MONITORAMENTO", className="hp-eyebrow"),
                                html.H1("HomeLab Pulse", className="hp-dashboard-title"),
                                html.P(id="updated-at", className="hp-updated-at"),
                            ]
                        ),
                        html.Div(
                            [
                                html.Button(
                                    "Atualizar",
                                    id="refresh-button",
                                    className="hp-button hp-button-secondary",
                                ),
                                html.Button(
                                    "Sair",
                                    id="logout-button",
                                    className="hp-button hp-button-ghost",
                                ),
                            ],
                            className="hp-header-actions",
                        ),
                    ],
                    className="hp-header",
                ),
                html.P(id="dashboard-message", className="hp-message hp-message-error"),
                html.Section(
                    [
                        html.Div(
                            [
                                html.P("CONFIGURAÇÃO", className="hp-eyebrow"),
                                html.H2("Cadastrar servidor", className="hp-section-title"),
                                html.P(
                                    "Use um nome e o endereço do equipamento na sua rede.",
                                    className="hp-help",
                                ),
                                html.Label("Nome", htmlFor="server-name", className="hp-label"),
                                dcc.Input(
                                    id="server-name",
                                    placeholder="Servidor de mídia",
                                    className="hp-input",
                                ),
                                html.Label(
                                    "Host ou IP", htmlFor="server-host", className="hp-label"
                                ),
                                dcc.Input(
                                    id="server-host",
                                    placeholder="192.168.1.50",
                                    className="hp-input",
                                ),
                                html.Label(
                                    "Descrição", htmlFor="server-description", className="hp-label"
                                ),
                                dcc.Input(
                                    id="server-description",
                                    placeholder="Opcional",
                                    className="hp-input",
                                ),
                                html.Button(
                                    "Cadastrar servidor",
                                    id="create-server-button",
                                    className="hp-button hp-button-primary",
                                ),
                                html.P(id="server-message", className="hp-message"),
                            ],
                            className="hp-form-card",
                        ),
                        html.Div(
                            [
                                html.P("MONITORAMENTO", className="hp-eyebrow"),
                                html.H2("Cadastrar serviço", className="hp-section-title"),
                                html.P(
                                    "Depois do servidor, informe o endereço do serviço.",
                                    className="hp-help",
                                ),
                                html.Label(
                                    "Servidor", htmlFor="service-server", className="hp-label"
                                ),
                                dcc.Dropdown(
                                    id="service-server",
                                    placeholder="Selecione um servidor",
                                    className="hp-dropdown",
                                    clearable=False,
                                ),
                                html.Label("Nome", htmlFor="service-name", className="hp-label"),
                                dcc.Input(
                                    id="service-name",
                                    placeholder="Jellyfin",
                                    className="hp-input",
                                ),
                                html.Label("Tipo", htmlFor="service-kind", className="hp-label"),
                                dcc.Dropdown(
                                    id="service-kind",
                                    options=[
                                        {"label": "HTTP genérico", "value": "http"},
                                        {"label": "Jellyfin", "value": "jellyfin"},
                                        {"label": "Portainer", "value": "portainer"},
                                        {"label": "Stack arr", "value": "arr"},
                                    ],
                                    value="http",
                                    clearable=False,
                                    className="hp-dropdown",
                                ),
                                html.Label(
                                    "URL do serviço",
                                    htmlFor="service-target-url",
                                    className="hp-label",
                                ),
                                dcc.Input(
                                    id="service-target-url",
                                    placeholder="http://192.168.1.50:8096",
                                    className="hp-input",
                                ),
                                html.Button(
                                    "Cadastrar serviço",
                                    id="create-service-button",
                                    className="hp-button hp-button-primary",
                                ),
                                html.P(id="service-message", className="hp-message"),
                            ],
                            className="hp-form-card",
                        ),
                    ],
                    className="hp-form-grid",
                ),
                html.Div(
                    [
                        kpi_card("Servidores", "servers-total"),
                        kpi_card("Serviços", "services-total"),
                        kpi_card("Disponibilidade 24h", "availability-total"),
                        kpi_card("Latência média", "latency-average"),
                        kpi_card("Incidentes abertos", "incidents-open"),
                    ],
                    className="hp-kpi-grid",
                ),
                html.Div(
                    [dcc.Graph(id="status-chart"), dcc.Graph(id="availability-chart")],
                    className="hp-chart-grid",
                ),
                dcc.Graph(id="latency-chart", style={"marginTop": "14px"}),
                html.H2("Serviços monitorados", className="hp-section-title hp-table-title"),
                html.Div(id="services-table", className="hp-table-wrap"),
            ],
            id="dashboard-panel",
            className="hp-dashboard-panel",
            style={"display": "none"},
        ),
    ],
    className="hp-app",
    style={
        "background": COLORS["background"],
        "color": COLORS["text"],
        "fontFamily": "Inter, system-ui, sans-serif",
        "minHeight": "100vh",
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
    Output("service-server", "options"),
    Output("service-server", "value"),
    Input("auth-token", "data"),
    Input("server-revision", "data"),
    State("service-server", "value"),
)
def update_server_options(
    token: str | None,
    _revision: int,
    selected_server: str | None,
) -> tuple[list[dict[str, str]], str | None]:
    if not token:
        return [], None
    try:
        servers = fetch_servers(token)
    except DashboardApiError:
        return [], None
    options = [{"label": server["name"], "value": server["id"]} for server in servers]
    available_ids = {option["value"] for option in options}
    value = selected_server if selected_server in available_ids else None
    if value is None and options:
        value = options[0]["value"]
    return options, value


@app.callback(
    Output("server-revision", "data"),
    Output("server-message", "children"),
    Output("server-message", "className"),
    Output("server-name", "value"),
    Output("server-host", "value"),
    Output("server-description", "value"),
    Input("create-server-button", "n_clicks"),
    State("auth-token", "data"),
    State("server-revision", "data"),
    State("server-name", "value"),
    State("server-host", "value"),
    State("server-description", "value"),
    prevent_initial_call=True,
)
def submit_server(
    _clicks: int | None,
    token: str | None,
    revision: int,
    name: str | None,
    host: str | None,
    description: str | None,
) -> tuple[int, str, str, str, str, str]:
    if not token:
        return (
            revision,
            "Entre novamente para cadastrar.",
            "hp-message hp-message-error",
            "",
            "",
            "",
        )
    if not name or not host:
        return (
            revision,
            "Informe o nome e o host do servidor.",
            "hp-message hp-message-error",
            name or "",
            host or "",
            description or "",
        )
    try:
        create_server(
            token, name.strip(), host.strip(), description.strip() if description else None
        )
    except DashboardApiError as error:
        return (
            revision,
            str(error),
            "hp-message hp-message-error",
            name,
            host,
            description or "",
        )
    return (
        revision + 1,
        "Servidor cadastrado com sucesso.",
        "hp-message hp-message-success",
        "",
        "",
        "",
    )


@app.callback(
    Output("service-revision", "data"),
    Output("service-message", "children"),
    Output("service-message", "className"),
    Output("service-name", "value"),
    Output("service-target-url", "value"),
    Input("create-service-button", "n_clicks"),
    State("auth-token", "data"),
    State("service-revision", "data"),
    State("service-server", "value"),
    State("service-name", "value"),
    State("service-kind", "value"),
    State("service-target-url", "value"),
    prevent_initial_call=True,
)
def submit_service(
    _clicks: int | None,
    token: str | None,
    revision: int,
    server_id: str | None,
    name: str | None,
    kind: str,
    target_url: str | None,
) -> tuple[int, str, str, str, str]:
    if not token:
        return revision, "Entre novamente para cadastrar.", "hp-message hp-message-error", "", ""
    if not server_id or not name or not target_url:
        return (
            revision,
            "Selecione o servidor e informe nome e URL do serviço.",
            "hp-message hp-message-error",
            name or "",
            target_url or "",
        )
    try:
        create_service(token, server_id, name.strip(), kind, target_url.strip())
    except DashboardApiError as error:
        return (
            revision,
            str(error),
            "hp-message hp-message-error",
            name,
            target_url,
        )
    return (
        revision + 1,
        "Serviço cadastrado com sucesso.",
        "hp-message hp-message-success",
        "",
        "",
    )


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
    Input("server-revision", "data"),
    Input("service-revision", "data"),
)
def refresh_dashboard(
    token: str | None,
    _refresh_clicks: int | None,
    _intervals: int,
    _server_revision: int,
    _service_revision: int,
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
