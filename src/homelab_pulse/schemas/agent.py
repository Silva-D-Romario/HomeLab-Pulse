from pydantic import BaseModel


class ContainerSummary(BaseModel):
    id: str
    name: str
    image: str
    state: str
    status: str


class AgentHealth(BaseModel):
    component: str = "docker-agent"
    status: str = "UP"

