from collections import deque
from typing import Dict, Tuple, Set, Literal, Optional

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models import Person, PersonI18n, Union, UnionChild
from app.schemas.family_graph import FamilyGraph, GraphNode, GraphEdge


NodeKey = Tuple[str, int]  # ("person" | "union", id)


def make_person_id(person_id: int) -> str:
    return f"p_{person_id}"


def make_union_id(union_id: int) -> str:
    return f"u_{union_id}"


def make_edge_id(source: str, target: str, edge_type: str) -> str:
    return f"e_{source}_{target}_{edge_type}"


def extract_birth_year(birth_date: Optional[str]) -> Optional[int]:
    if not birth_date:
        return None
    try:
        return int(birth_date.split("-")[0])
    except (IndexError, ValueError):
        return None


def extract_year(date_value: Optional[str]) -> Optional[int]:
    """Extract year from either YYYY-MM-DD or DD.MM.YYYY string."""
    if not date_value:
        return None
    s = str(date_value).strip()
    try:
        if "." in s:
            # DD.MM.YYYY
            return int(s.split(".")[-1])
        elif "-" in s:
            # YYYY-MM-DD
            return int(s.split("-")[0])
        else:
            return int(s)
    except (IndexError, ValueError, TypeError):
        return None


def is_active_for_year(
    year: Optional[int],
    valid_from: Optional[str],
    valid_to: Optional[str],
) -> Optional[bool]:
    if year is None:
        return None

    from_year = extract_year(valid_from)
    to_year = extract_year(valid_to)

    if from_year is None and to_year is None:
        return None
    if from_year is not None and year < from_year:
        return False
    if to_year is not None and year > to_year:
        return False
    return True


def is_union_active_for_year(union: Union, year: Optional[int]) -> bool:
    if year is None:
        return True

    start_value = union.start_date or getattr(union, "valid_from", None)
    end_value = union.end_date or getattr(union, "valid_to", None)
    start_year = extract_year(start_value)
    end_year = extract_year(end_value)

    if start_year is not None and year < start_year:
        return False
    if end_year is not None and year > end_year:
        return False
    return True


def is_edge_active_for_year(
    *,
    union: Union,
    year: Optional[int],
    valid_from: Optional[str] = None,
    valid_to: Optional[str] = None,
) -> bool:
    if year is None:
        return True

    if not is_union_active_for_year(union, year):
        return False

    relation_active = is_active_for_year(year, valid_from, valid_to)
    if relation_active is None:
        return True
    return relation_active


def is_live_visible_person(person: Person) -> bool:
    return (person.record_status or "active") == "active"


def get_person(session: Session, person_id: int) -> Optional[Person]:
    return (
        session.query(Person)
        .filter(
            Person.person_id == person_id,
            Person.record_status == "active",
        )
        .first()
    )


def get_person_i18n(
    session: Session, person_id: int, lang_code: str = "ru"
) -> Optional[PersonI18n]:
    return session.query(PersonI18n).filter(
        PersonI18n.person_id == person_id,
        PersonI18n.lang_code == lang_code,
    ).first()


def get_unions_for_partner(session: Session, person_id: int) -> list[Union]:
    return session.query(Union).filter(
        or_(Union.partner1_id == person_id, Union.partner2_id == person_id)
    ).all()


def get_unions_for_child(session: Session, person_id: int) -> list[Union]:
    return session.query(Union).join(
        UnionChild, UnionChild.union_id == Union.id
    ).filter(
        UnionChild.child_id == person_id
    ).all()


def get_union_partners(session: Session, union_id: int) -> list[Person]:
    union = session.query(Union).filter(Union.id == union_id).first()
    if not union:
        return []
    partner_ids = [pid for pid in (union.partner1_id, union.partner2_id) if pid is not None]
    if not partner_ids:
        return []
    return session.query(Person).filter(Person.person_id.in_(partner_ids)).all()


def get_union_children(session: Session, union_id: int) -> list[Person]:
    return session.query(Person).join(
        UnionChild, UnionChild.child_id == Person.person_id
    ).filter(
        UnionChild.union_id == union_id
    ).all()


def build_person_name(person: Person, i18n: Optional[PersonI18n]) -> str:
    if i18n and (i18n.first_name or i18n.last_name):
        parts = [i18n.first_name, i18n.last_name]
        return " ".join(p for p in parts if p).strip() or "Неизвестный"
    return "Неизвестный"


def person_to_node(session: Session, person: Person) -> GraphNode:
    i18n = get_person_i18n(session, person.person_id, "ru")
    name = build_person_name(person, i18n)
    birth_year = extract_birth_year(person.birth_date)
    death_year = extract_year(person.death_date)
    display_name = name
    if birth_year:
        display_name = f"{name} ({birth_year})"

    gender: Literal["male", "female", "unknown"] = "unknown"
    if person.gender == "M":
        gender = "male"
    elif person.gender == "F":
        gender = "female"

    avatar_url = person.avatar_url or None
    is_alive = bool(person.is_alive) if person.is_alive is not None else None

    return GraphNode(
        id=make_person_id(person.person_id),
        type="person",
        person_id=person.person_id,
        url=f"/family/person/{person.person_id}",
        display_name=display_name,
        name=name,
        gender=gender,
        birth_year=birth_year,
        death_year=death_year,
        is_alive=is_alive,
        avatar_url=avatar_url,
        start_date=None,
        end_date=None,
        is_active=None,
        valid_from=None,
        valid_to=None,
    )


def union_to_node(union: Union, year: Optional[int] = None) -> GraphNode:
    is_union_active = is_union_active_for_year(union, year)
    return GraphNode(
        id=make_union_id(union.id),
        type="union",
        display_name=None,
        name=None,
        gender="unknown",
        birth_year=None,
        death_year=None,
        is_alive=None,
        avatar_url=None,
        start_date=union.start_date,
        end_date=union.end_date,
        is_active=is_union_active,
        valid_from=None,
        valid_to=None,
    )


def build_family_graph(
    root_person_id: int,
    depth: int,
    session: Session,
    year: Optional[int] = None,
) -> FamilyGraph:
    root_person = get_person(session, root_person_id)
    if not root_person:
        raise ValueError(f"Person {root_person_id} not found")

    nodes: Dict[NodeKey, GraphNode] = {}
    edges: Dict[str, GraphEdge] = {}
    visited: Set[NodeKey] = set()
    queue: deque[tuple[NodeKey, int]] = deque()

    root_key: NodeKey = ("person", root_person.person_id)
    nodes[root_key] = person_to_node(session, root_person)
    visited.add(root_key)
    queue.append((root_key, 0))

    while queue:
        (node_type, node_db_id), dist = queue.popleft()
        if dist >= depth:
            continue

        if node_type == "person":
            person = get_person(session, node_db_id)
            if not person:
                continue

            for union in get_unions_for_partner(session, person.person_id):
                union_key: NodeKey = ("union", union.id)
                if union_key not in nodes:
                    nodes[union_key] = union_to_node(union, year)

                source_id = make_person_id(person.person_id)
                target_id = make_union_id(union.id)
                edge_id = make_edge_id(source_id, target_id, "partner")
                if edge_id not in edges:
                    edges[edge_id] = GraphEdge(
                        id=edge_id,
                        source=source_id,
                        target=target_id,
                        type="partner",
                        meta={"union_type": "unknown"},
                        valid_from=union.start_date,
                        valid_to=union.end_date,
                        is_active_for_year=is_edge_active_for_year(
                            union=union,
                            year=year,
                            valid_from=union.start_date,
                            valid_to=union.end_date,
                        ),
                    )
                if union_key not in visited:
                    visited.add(union_key)
                    queue.append((union_key, dist + 1))

            for union in get_unions_for_child(session, person.person_id):
                union_key: NodeKey = ("union", union.id)
                if union_key not in nodes:
                    nodes[union_key] = union_to_node(union, year)

                source_id = make_union_id(union.id)
                target_id = make_person_id(person.person_id)
                edge_id = make_edge_id(source_id, target_id, "child")
                if edge_id not in edges:
                    edges[edge_id] = GraphEdge(
                        id=edge_id,
                        source=source_id,
                        target=target_id,
                        type="child",
                        meta={},
                        valid_from=person.birth_date,
                        valid_to=None,
                        is_active_for_year=is_edge_active_for_year(
                            union=union,
                            year=year,
                            valid_from=person.birth_date,
                            valid_to=None,
                        ),
                    )
                if union_key not in visited:
                    visited.add(union_key)
                    queue.append((union_key, dist + 1))

        elif node_type == "union":
            union = session.query(Union).filter(Union.id == node_db_id).first()
            if not union:
                continue

            for partner in get_union_partners(session, union.id):
                if not is_live_visible_person(partner):
                    continue
                p_birth = extract_birth_year(partner.birth_date)
                if year is not None and p_birth is not None and year < p_birth:
                    continue
                person_key: NodeKey = ("person", partner.person_id)
                if person_key not in nodes:
                    nodes[person_key] = person_to_node(session, partner)

                source_id = make_person_id(partner.person_id)
                target_id = make_union_id(union.id)
                edge_id = make_edge_id(source_id, target_id, "partner")
                if edge_id not in edges:
                    edges[edge_id] = GraphEdge(
                        id=edge_id,
                        source=source_id,
                        target=target_id,
                        type="partner",
                        meta={"union_type": "unknown"},
                        valid_from=union.start_date,
                        valid_to=union.end_date,
                        is_active_for_year=is_edge_active_for_year(
                            union=union,
                            year=year,
                            valid_from=union.start_date,
                            valid_to=union.end_date,
                        ),
                    )
                if person_key not in visited:
                    visited.add(person_key)
                    queue.append((person_key, dist + 1))

            for child in get_union_children(session, union.id):
                if not is_live_visible_person(child):
                    continue
                c_birth = extract_birth_year(child.birth_date)
                if year is not None and c_birth is not None and year < c_birth:
                    continue
                child_key: NodeKey = ("person", child.person_id)
                if child_key not in nodes:
                    nodes[child_key] = person_to_node(session, child)

                source_id = make_union_id(union.id)
                target_id = make_person_id(child.person_id)
                edge_id = make_edge_id(source_id, target_id, "child")
                if edge_id not in edges:
                    edges[edge_id] = GraphEdge(
                        id=edge_id,
                        source=source_id,
                        target=target_id,
                        type="child",
                        meta={},
                        valid_from=child.birth_date,
                        valid_to=None,
                        is_active_for_year=is_edge_active_for_year(
                            union=union,
                            year=year,
                            valid_from=child.birth_date,
                            valid_to=None,
                        ),
                    )
                if child_key not in visited:
                    visited.add(child_key)
                    queue.append((child_key, dist + 1))

    return FamilyGraph(nodes=list(nodes.values()), edges=list(edges.values()))
