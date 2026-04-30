from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel


class GraphNode(BaseModel):
    """Узел графа: либо Person, либо Union."""

    id: str  # "p_{id}" или "u_{id}"
    type: Literal["person", "union"]
    person_id: Optional[int] = None
    url: Optional[str] = None

    # Для Person
    display_name: Optional[str] = None  # "Иван Иванов (1980)"
    name: Optional[str] = None  # "Иван Иванов"
    gender: Literal["male", "female", "unknown"] = "unknown"
    birth_year: Optional[int] = None
    death_year: Optional[int] = None
    is_alive: Optional[bool] = None
    avatar_url: Optional[str] = None

    # Для Union
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    is_active: Optional[bool] = None

    # Временные метки
    valid_from: Optional[str] = None
    valid_to: Optional[str] = None


class GraphEdge(BaseModel):
    """Ребро графа."""

    id: str  # "e_{source}_{target}_{type}"
    source: str  # node id
    target: str  # node id
    type: Literal["partner", "child"]
    meta: Dict[str, Any] = {}  # {"union_type": "legal"} и т.п.
    valid_from: Optional[str] = None
    valid_to: Optional[str] = None
    is_active_for_year: Optional[bool] = None


class FamilyGraph(BaseModel):
    """Полный граф семьи."""

    nodes: List[GraphNode]
    edges: List[GraphEdge]
