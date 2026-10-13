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
    "display": "flex",
    "margin": "8vh auto",
    "maxWidth": "900px",
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


def register_user(name: str, email: str, password: str) -> str:
    try:
        response = httpx.post(
            f"{settings.api_base_url}/api/v1/auth/register",
            json={"name": name, "email": email, "password": password},
            timeout=10,
        )
        response.raise_for_status()
    except httpx.HTTPStatusError as error:
        if error.response.status_code == 409:
            message = "Este e-mail já está cadastrado."
        elif error.response.status_code == 422:
            message = "Revise o nome, o e-mail e a senha informados."
        else:
            message = "Não foi possível criar a conta."
        raise DashboardApiError(message) from error
    except httpx.HTTPError as error:
        raise DashboardApiError("Não foi possível conectar à API.") from error
    return authenticate(email, password)


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


def fetch_services(token: str, server_id: str) -> list[dict[str, Any]]:
    try:
        response = httpx.get(
            f"{settings.api_base_url}/api/v1/servers/{server_id}/services",
            headers={"Authorization": f"Bearer {token}"},
            timeout=10,
        )
        response.raise_for_status()
    except httpx.HTTPStatusError as error:
        if error.response.status_code == 401:
            raise DashboardApiError("Sua sessão expirou. Entre novamente.") from error
        raise DashboardApiError("Não foi possível carregar os serviços.") from error
    except httpx.HTTPError as error:
        raise DashboardApiError("A API está indisponível no momento.") from error
    return list(response.json())


def fetch_all_services(token: str, servers: list[dict[str, Any]]) -> list[dict[str, Any]]:
    services: list[dict[str, Any]] = []
    for server in servers:
        server_services = fetch_services(token, server["id"])
        for service in server_services:
            service["server_name"] = server["name"]
        services.extend(server_services)
    return services


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


def update_server_resource(
    token: str,
    server_id: str,
    name: str,
    host: str,
    description: str | None,
) -> None:
    try:
        response = httpx.patch(
            f"{settings.api_base_url}/api/v1/servers/{server_id}",
            headers={"Authorization": f"Bearer {token}"},
            json={"name": name, "host": host, "description": description or None},
            timeout=10,
        )
        response.raise_for_status()
    except httpx.HTTPStatusError as error:
        if error.response.status_code == 409:
            message = "Já existe um servidor com esse nome."
        elif error.response.status_code == 422:
            message = "Revise os dados informados para o servidor."
        else:
            message = "Não foi possível atualizar o servidor."
        raise DashboardApiError(message) from error
    except httpx.HTTPError as error:
        raise DashboardApiError("A API está indisponível no momento.") from error


def delete_server_resource(token: str, server_id: str) -> None:
    try:
        response = httpx.delete(
            f"{settings.api_base_url}/api/v1/servers/{server_id}",
            headers={"Authorization": f"Bearer {token}"},
            timeout=10,
        )
        response.raise_for_status()
    except httpx.HTTPError as error:
        raise DashboardApiError("Não foi possível excluir o servidor.") from error


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


def update_service_resource(
    token: str,
    service_id: str,
    name: str,
    kind: str,
    target_url: str,
    enabled: bool,
) -> None:
    try:
        response = httpx.patch(
            f"{settings.api_base_url}/api/v1/services/{service_id}",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "name": name,
                "kind": kind,
                "target_url": target_url,
                "enabled": enabled,
            },
            timeout=10,
        )
        response.raise_for_status()
    except httpx.HTTPStatusError as error:
        if error.response.status_code == 409:
            message = "Já existe um serviço com esse nome neste servidor."
        elif error.response.status_code == 422:
            message = "Informe uma URL completa, incluindo http:// ou https://."
        else:
            message = "Não foi possível atualizar o serviço."
        raise DashboardApiError(message) from error
    except httpx.HTTPError as error:
        raise DashboardApiError("A API está indisponível no momento.") from error


def delete_service_resource(token: str, service_id: str) -> None:
    try:
        response = httpx.delete(
            f"{settings.api_base_url}/api/v1/services/{service_id}",
            headers={"Authorization": f"Bearer {token}"},
            timeout=10,
        )
        response.raise_for_status()
    except httpx.HTTPError as error:
        raise DashboardApiError("Não foi possível excluir o serviço.") from error


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
        dcc.Store(id="servers-data", data=[]),
        dcc.Store(id="services-data", data=[]),
        dcc.Store(id="auth-view", data="login"),
        dcc.Store(id="active-view", data="dashboard"),
        dcc.Interval(id="refresh-interval", interval=30_000),
        html.Section(
            [
                html.Div(
                    [
                        html.Div("HP", className="hp-logo"),
                        html.H1("HomeLab Pulse", className="hp-login-title"),
                        html.P(
                            "Entre para gerenciar e monitorar seu homelab.",
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
                        html.Button(
                            "Entrar",
                            id="login-button",
                            className="hp-button hp-button-primary",
                        ),
                        html.P(id="login-message", className="hp-message hp-message-error"),
                        html.Button(
                            "Criar uma conta",
                            id="show-register-button",
                            className="hp-auth-link",
                        ),
                    ],
                    id="login-form-card",
                    className="hp-auth-card",
                ),
                html.Div(
                    [
                        html.P("PRIMEIRO ACESSO", className="hp-eyebrow"),
                        html.H2("Criar conta", className="hp-section-title"),
                        html.P(
                            "Seus servidores e serviços ficam isolados dos outros usuários.",
                            className="hp-login-description",
                        ),
                        html.Label("Nome", htmlFor="register-name", className="hp-label"),
                        dcc.Input(
                            id="register-name",
                            placeholder="Seu nome",
                            className="hp-input",
                        ),
                        html.Label("E-mail", htmlFor="register-email", className="hp-label"),
                        dcc.Input(
                            id="register-email",
                            type="email",
                            placeholder="voce@exemplo.com",
                            className="hp-input",
                        ),
                        html.Label("Senha", htmlFor="register-password", className="hp-label"),
                        dcc.Input(
                            id="register-password",
                            type="password",
                            placeholder="Mínimo de 8 caracteres",
                            className="hp-input",
                        ),
                        html.Label(
                            "Confirmar senha",
                            htmlFor="register-password-confirmation",
                            className="hp-label",
                        ),
                        dcc.Input(
                            id="register-password-confirmation",
                            type="password",
                            placeholder="Repita a senha",
                            className="hp-input",
                        ),
                        html.Button(
                            "Criar conta",
                            id="register-button",
                            className="hp-button hp-button-secondary",
                        ),
                        html.P(id="register-message", className="hp-message"),
                        html.Button(
                            "Já tenho uma conta",
                            id="show-login-button",
                            className="hp-auth-link",
                        ),
                    ],
                    id="register-form-card",
                    style={"display": "none"},
                    className="hp-auth-card",
                ),
            ],
            id="login-panel",
            style=LOGIN_PANEL_STYLE,
            className="hp-auth-shell",
        ),
        html.Section(
            [
                html.Header(
                    [
                        html.Div(
                            [
                                html.P(
                                    "PAINEL DE MONITORAMENTO",
                                    id="view-eyebrow",
                                    className="hp-eyebrow",
                                ),
                                html.H1(
                                    "HomeLab Pulse",
                                    id="view-title",
                                    className="hp-dashboard-title",
                                ),
                                html.P(id="updated-at", className="hp-updated-at"),
                            ]
                        ),
                        html.Div(
                            [
                                html.Button(
                                    "Dashboard",
                                    id="show-dashboard-button",
                                    className="hp-button hp-button-ghost",
                                ),
                                html.Button(
                                    "Servidores e serviços",
                                    id="show-resources-button",
                                    className="hp-button hp-button-ghost",
                                ),
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
                html.Div(
                    [
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
                                        html.Label(
                                            "Nome", htmlFor="server-name", className="hp-label"
                                        ),
                                        dcc.Input(
                                            id="server-name",
                                            placeholder="Servidor de mídia",
                                            className="hp-input",
                                        ),
                                        html.Label(
                                            "Host ou IP",
                                            htmlFor="server-host",
                                            className="hp-label",
                                        ),
                                        dcc.Input(
                                            id="server-host",
                                            placeholder="192.168.1.50",
                                            className="hp-input",
                                        ),
                                        html.Label(
                                            "Descrição",
                                            htmlFor="server-description",
                                            className="hp-label",
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
                                            "Servidor",
                                            htmlFor="service-server",
                                            className="hp-label",
                                        ),
                                        dcc.Dropdown(
                                            id="service-server",
                                            placeholder="Selecione um servidor",
                                            className="hp-dropdown",
                                            clearable=False,
                                        ),
                                        html.Label(
                                            "Nome", htmlFor="service-name", className="hp-label"
                                        ),
                                        dcc.Input(
                                            id="service-name",
                                            placeholder="Jellyfin",
                                            className="hp-input",
                                        ),
                                        html.Label(
                                            "Tipo", htmlFor="service-kind", className="hp-label"
                                        ),
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
                        html.H2(
                            "Gerenciar recursos", className="hp-section-title hp-management-title"
                        ),
                        html.Section(
                            [
                                html.Div(
                                    [
                                        html.P("SERVIDORES", className="hp-eyebrow"),
                                        html.Label(
                                            "Servidor para editar",
                                            htmlFor="manage-server",
                                            className="hp-label",
                                        ),
                                        dcc.Dropdown(
                                            id="manage-server",
                                            placeholder="Selecione um servidor",
                                            className="hp-dropdown",
                                            clearable=False,
                                        ),
                                        html.Label(
                                            "Nome", htmlFor="edit-server-name", className="hp-label"
                                        ),
                                        dcc.Input(id="edit-server-name", className="hp-input"),
                                        html.Label(
                                            "Host ou IP",
                                            htmlFor="edit-server-host",
                                            className="hp-label",
                                        ),
                                        dcc.Input(id="edit-server-host", className="hp-input"),
                                        html.Label(
                                            "Descrição",
                                            htmlFor="edit-server-description",
                                            className="hp-label",
                                        ),
                                        dcc.Input(
                                            id="edit-server-description", className="hp-input"
                                        ),
                                        html.Div(
                                            [
                                                html.Button(
                                                    "Salvar servidor",
                                                    id="save-server-button",
                                                    className="hp-button hp-button-primary",
                                                ),
                                                dcc.ConfirmDialogProvider(
                                                    html.Button(
                                                        "Excluir",
                                                        id="delete-server-button",
                                                        className="hp-button hp-button-danger",
                                                    ),
                                                    message=(
                                                        "Excluir o servidor e todos "
                                                        "os seus serviços? "
                                                        "Esta ação não pode ser desfeita."
                                                    ),
                                                ),
                                            ],
                                            className="hp-form-actions",
                                        ),
                                        html.P(id="manage-server-message", className="hp-message"),
                                    ],
                                    className="hp-form-card",
                                ),
                                html.Div(
                                    [
                                        html.P("SERVIÇOS", className="hp-eyebrow"),
                                        html.Label(
                                            "Serviço para editar",
                                            htmlFor="manage-service",
                                            className="hp-label",
                                        ),
                                        dcc.Dropdown(
                                            id="manage-service",
                                            placeholder="Selecione um serviço",
                                            className="hp-dropdown",
                                            clearable=False,
                                        ),
                                        html.Label(
                                            "Nome",
                                            htmlFor="edit-service-name",
                                            className="hp-label",
                                        ),
                                        dcc.Input(id="edit-service-name", className="hp-input"),
                                        html.Label(
                                            "Tipo",
                                            htmlFor="edit-service-kind",
                                            className="hp-label",
                                        ),
                                        dcc.Dropdown(
                                            id="edit-service-kind",
                                            options=[
                                                {"label": "HTTP genérico", "value": "http"},
                                                {"label": "Jellyfin", "value": "jellyfin"},
                                                {"label": "Portainer", "value": "portainer"},
                                                {"label": "Stack arr", "value": "arr"},
                                            ],
                                            clearable=False,
                                            className="hp-dropdown",
                                        ),
                                        html.Label(
                                            "URL do serviço",
                                            htmlFor="edit-service-target-url",
                                            className="hp-label",
                                        ),
                                        dcc.Input(
                                            id="edit-service-target-url", className="hp-input"
                                        ),
                                        dcc.Checklist(
                                            id="edit-service-enabled",
                                            options=[
                                                {
                                                    "label": " Monitoramento ativo",
                                                    "value": "enabled",
                                                }
                                            ],
                                            value=["enabled"],
                                            className="hp-checklist",
                                        ),
                                        html.Div(
                                            [
                                                html.Button(
                                                    "Salvar serviço",
                                                    id="save-service-button",
                                                    className="hp-button hp-button-primary",
                                                ),
                                                dcc.ConfirmDialogProvider(
                                                    html.Button(
                                                        "Excluir",
                                                        id="delete-service-button",
                                                        className="hp-button hp-button-danger",
                                                    ),
                                                    message=(
                                                        "Excluir este serviço e seu histórico? "
                                                        "Esta ação não pode ser desfeita."
                                                    ),
                                                ),
                                            ],
                                            className="hp-form-actions",
                                        ),
                                        html.P(id="manage-service-message", className="hp-message"),
                                    ],
                                    className="hp-form-card",
                                ),
                            ],
                            className="hp-form-grid hp-management-grid",
                        ),
                    ],
                    id="resources-view",
                    style={"display": "none"},
                ),
                html.Div(
                    [
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
                            [
                                dcc.Graph(id="status-chart"),
                                dcc.Graph(id="availability-chart"),
                            ],
                            className="hp-chart-grid",
                        ),
                        dcc.Graph(id="latency-chart", style={"marginTop": "14px"}),
                        html.H2(
                            "Serviços monitorados",
                            className="hp-section-title hp-table-title",
                        ),
                        html.Div(id="services-table", className="hp-table-wrap"),
                    ],
                    id="dashboard-view",
                ),
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
    Output("register-message", "children"),
    Input("login-button", "n_clicks"),
    Input("register-button", "n_clicks"),
    Input("logout-button", "n_clicks"),
    State("email", "value"),
    State("password", "value"),
    State("register-name", "value"),
    State("register-email", "value"),
    State("register-password", "value"),
    State("register-password-confirmation", "value"),
    prevent_initial_call=True,
)
def update_session(
    _login_clicks: int | None,
    _register_clicks: int | None,
    _logout_clicks: int | None,
    email: str | None,
    password: str | None,
    register_name: str | None,
    register_email: str | None,
    register_password: str | None,
    register_password_confirmation: str | None,
) -> tuple[str | None, str, str]:
    if ctx.triggered_id == "logout-button":
        return None, "", ""
    if ctx.triggered_id == "register-button":
        if not register_name or not register_email or not register_password:
            return None, "", "Preencha nome, e-mail e senha."
        if register_password != register_password_confirmation:
            return None, "", "As senhas não coincidem."
        try:
            token = register_user(register_name.strip(), register_email.strip(), register_password)
        except DashboardApiError as error:
            return None, "", str(error)
        return token, "", "Conta criada com sucesso."
    if not email or not password:
        return None, "Informe e-mail e senha.", ""
    try:
        token = authenticate(email, password)
    except DashboardApiError as error:
        return None, str(error), ""
    return token, "", ""


@app.callback(
    Output("auth-view", "data"),
    Input("show-register-button", "n_clicks"),
    Input("show-login-button", "n_clicks"),
    prevent_initial_call=True,
)
def select_auth_view(
    _show_register_clicks: int | None,
    _show_login_clicks: int | None,
) -> str:
    if ctx.triggered_id == "show-register-button":
        return "register"
    return "login"


@app.callback(
    Output("login-form-card", "style"),
    Output("register-form-card", "style"),
    Input("auth-view", "data"),
)
def update_auth_view(view: str | None) -> tuple[dict[str, str], dict[str, str]]:
    if view == "register":
        return {"display": "none"}, {"display": "flex"}
    return {"display": "flex"}, {"display": "none"}


@app.callback(
    Output("active-view", "data"),
    Input("show-dashboard-button", "n_clicks"),
    Input("show-resources-button", "n_clicks"),
    Input("auth-token", "data"),
)
def select_active_view(
    _show_dashboard_clicks: int | None,
    _show_resources_clicks: int | None,
    _token: str | None,
) -> str:
    if ctx.triggered_id == "show-resources-button":
        return "resources"
    return "dashboard"


@app.callback(
    Output("dashboard-view", "style"),
    Output("resources-view", "style"),
    Output("view-title", "children"),
    Output("view-eyebrow", "children"),
    Input("active-view", "data"),
)
def update_active_view(
    view: str | None,
) -> tuple[dict[str, str], dict[str, str], str, str]:
    if view == "resources":
        return (
            {"display": "none"},
            {"display": "block"},
            "Servidores e serviços",
            "CONFIGURAÇÃO DO HOMELAB",
        )
    return (
        {"display": "block"},
        {"display": "none"},
        "HomeLab Pulse",
        "PAINEL DE MONITORAMENTO",
    )


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
    Output("servers-data", "data"),
    Output("services-data", "data"),
    Input("auth-token", "data"),
    Input("server-revision", "data"),
    Input("service-revision", "data"),
)
def load_resource_data(
    token: str | None,
    _server_revision: int,
    _service_revision: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if not token:
        return [], []
    try:
        servers = fetch_servers(token)
        services = fetch_all_services(token, servers)
    except DashboardApiError:
        return [], []
    return servers, services


def keep_available_value(options: list[dict[str, str]], selected_value: str | None) -> str | None:
    available_values = {option["value"] for option in options}
    if selected_value in available_values:
        return selected_value
    return options[0]["value"] if options else None


@app.callback(
    Output("service-server", "options"),
    Output("service-server", "value"),
    Output("manage-server", "options"),
    Output("manage-server", "value"),
    Output("manage-service", "options"),
    Output("manage-service", "value"),
    Input("servers-data", "data"),
    Input("services-data", "data"),
    State("service-server", "value"),
    State("manage-server", "value"),
    State("manage-service", "value"),
)
def update_resource_options(
    servers: list[dict[str, Any]],
    services: list[dict[str, Any]],
    create_server_value: str | None,
    manage_server_value: str | None,
    manage_service_value: str | None,
) -> tuple[Any, ...]:
    options = [{"label": server["name"], "value": server["id"]} for server in servers]
    service_options = [
        {
            "label": f"{service['server_name']} — {service['name']}",
            "value": service["id"],
        }
        for service in services
    ]
    return (
        options,
        keep_available_value(options, create_server_value),
        options,
        keep_available_value(options, manage_server_value),
        service_options,
        keep_available_value(service_options, manage_service_value),
    )


@app.callback(
    Output("edit-server-name", "value"),
    Output("edit-server-host", "value"),
    Output("edit-server-description", "value"),
    Input("manage-server", "value"),
    Input("servers-data", "data"),
)
def populate_server_form(
    server_id: str | None, servers: list[dict[str, Any]]
) -> tuple[str, str, str]:
    server = next((item for item in servers if item["id"] == server_id), None)
    if server is None:
        return "", "", ""
    return server["name"], server["host"], server.get("description") or ""


@app.callback(
    Output("edit-service-name", "value"),
    Output("edit-service-kind", "value"),
    Output("edit-service-target-url", "value"),
    Output("edit-service-enabled", "value"),
    Input("manage-service", "value"),
    Input("services-data", "data"),
)
def populate_service_form(
    service_id: str | None, services: list[dict[str, Any]]
) -> tuple[str, str | None, str, list[str]]:
    service = next((item for item in services if item["id"] == service_id), None)
    if service is None:
        return "", None, "", []
    return (
        service["name"],
        str(service["kind"]).lower(),
        service["target_url"],
        ["enabled"] if service["enabled"] else [],
    )


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
    Output("server-revision", "data", allow_duplicate=True),
    Output("manage-server-message", "children"),
    Output("manage-server-message", "className"),
    Input("save-server-button", "n_clicks"),
    Input("delete-server-button", "n_clicks"),
    State("auth-token", "data"),
    State("server-revision", "data"),
    State("manage-server", "value"),
    State("edit-server-name", "value"),
    State("edit-server-host", "value"),
    State("edit-server-description", "value"),
    prevent_initial_call=True,
)
def manage_server_resource(
    _save_clicks: int | None,
    _delete_clicks: int | None,
    token: str | None,
    revision: int,
    server_id: str | None,
    name: str | None,
    host: str | None,
    description: str | None,
) -> tuple[int, str, str]:
    error_class = "hp-message hp-message-error"
    if not token or not server_id:
        return revision, "Selecione um servidor.", error_class
    try:
        if ctx.triggered_id == "delete-server-button":
            delete_server_resource(token, server_id)
            message = "Servidor e serviços vinculados excluídos."
        else:
            if not name or not host:
                return revision, "Informe o nome e o host do servidor.", error_class
            update_server_resource(
                token,
                server_id,
                name.strip(),
                host.strip(),
                description.strip() if description else None,
            )
            message = "Servidor atualizado com sucesso."
    except DashboardApiError as error:
        return revision, str(error), error_class
    return revision + 1, message, "hp-message hp-message-success"


@app.callback(
    Output("service-revision", "data", allow_duplicate=True),
    Output("manage-service-message", "children"),
    Output("manage-service-message", "className"),
    Input("save-service-button", "n_clicks"),
    Input("delete-service-button", "n_clicks"),
    State("auth-token", "data"),
    State("service-revision", "data"),
    State("manage-service", "value"),
    State("edit-service-name", "value"),
    State("edit-service-kind", "value"),
    State("edit-service-target-url", "value"),
    State("edit-service-enabled", "value"),
    prevent_initial_call=True,
)
def manage_service_resource(
    _save_clicks: int | None,
    _delete_clicks: int | None,
    token: str | None,
    revision: int,
    service_id: str | None,
    name: str | None,
    kind: str | None,
    target_url: str | None,
    enabled_values: list[str],
) -> tuple[int, str, str]:
    error_class = "hp-message hp-message-error"
    if not token or not service_id:
        return revision, "Selecione um serviço.", error_class
    try:
        if ctx.triggered_id == "delete-service-button":
            delete_service_resource(token, service_id)
            message = "Serviço excluído com sucesso."
        else:
            if not name or not kind or not target_url:
                return revision, "Informe nome, tipo e URL do serviço.", error_class
            update_service_resource(
                token,
                service_id,
                name.strip(),
                kind,
                target_url.strip(),
                "enabled" in enabled_values,
            )
            message = "Serviço atualizado com sucesso."
    except DashboardApiError as error:
        return revision, str(error), error_class
    return revision + 1, message, "hp-message hp-message-success"


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
