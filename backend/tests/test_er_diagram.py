"""F05: the ER diagram in docs/DATA_MODEL.md must match the ORM metadata.

F05's second acceptance item is an ER diagram covering every database entity.
A picture of the schema goes stale the moment a table, column, constraint, or
foreign key is added without redrawing it, so these tests fail loudly when that
happens. They read the tracked document and compare it with `Base.metadata`,
which the model imports build, so they need no database and still run when
nothing is listening on 5432.

They depend on the diagram's shape, so keep new rows in the same form:

    table_name {
        <type> <column> [PK|FK|UK] ["comment"]
    }
    parent ||--o{ child : "label"

Everything the parser ignores on purpose: blank lines, `%%` comments, the
`erDiagram` header, and anything after the first double quote on a line.
"""

import re
from pathlib import Path

from sqlalchemy import UniqueConstraint

from app.models import Base

DATA_MODEL = Path(__file__).resolve().parents[2] / "docs" / "DATA_MODEL.md"

ENTITY_OPEN = re.compile(r"^([a-z_][a-z0-9_]*)\s*\{$")
RELATIONSHIP = re.compile(
    r"^([a-z_][a-z0-9_]*)\s+([|}{o-]+)\s+([a-z_][a-z0-9_]*)\s*:"
)
KEY_TOKENS = {"PK", "FK", "UK"}


def _mermaid_lines() -> list[str]:
    """Every line inside a ```mermaid fence, minus comments and blanks."""
    lines: list[str] = []
    inside = False
    for raw in DATA_MODEL.read_text(encoding="utf-8").splitlines():
        if raw.strip().startswith("```"):
            inside = raw.strip().strip("`").strip() == "mermaid"
            continue
        if not inside:
            continue
        line = raw.strip()
        if not line or line.startswith("%%") or line == "erDiagram":
            continue
        if '"' in line:  # drop the label or attribute comment
            line = line.split('"', 1)[0].rstrip()
        lines.append(line)
    return lines


def _parse() -> tuple[dict[str, dict[str, set[str]]], list[tuple[str, str, str]]]:
    """Return {entity: {"columns": ..., "keys": {column: {PK, FK, UK}}}} and
    the drawn relationships as (left entity, cardinality, right entity)."""
    entities: dict[str, dict[str, set[str]]] = {}
    relationships: list[tuple[str, str, str]] = []
    current: str | None = None
    for line in _mermaid_lines():
        if line == "}":
            current = None
            continue
        opened = ENTITY_OPEN.match(line)
        if opened:
            current = opened.group(1)
            entities[current] = {"columns": set(), "keys": {}}
            continue
        relates = RELATIONSHIP.match(line)
        if relates and "--" in relates.group(2):
            relationships.append(
                (relates.group(1), relates.group(2), relates.group(3))
            )
            continue
        assert current is not None, f"attribute outside an entity block: {line!r}"
        _type, column, *rest = line.split()
        entities[current]["columns"].add(column)
        keys = {token for token in rest if token in KEY_TOKENS}
        entities[current]["keys"][column] = keys
    assert entities, "docs/DATA_MODEL.md has no mermaid erDiagram block"
    return entities, relationships


def test_every_model_table_is_drawn_with_every_column() -> None:
    entities, _ = _parse()
    tables = Base.metadata.tables
    assert set(entities) == set(tables), (
        "the ER diagram and the models disagree about which tables exist: "
        f"only in diagrams {sorted(set(entities) - set(tables))}, "
        f"only in models {sorted(set(tables) - set(entities))}"
    )
    for name, table in tables.items():
        assert entities[name]["columns"] == set(table.columns.keys()), (
            f"{name}: diagram {sorted(entities[name]['columns'])} "
            f"vs model {sorted(table.columns.keys())}"
        )


def test_key_markers_match_the_metadata() -> None:
    entities, _ = _parse()
    for name, table in Base.metadata.tables.items():
        marked = entities[name]["keys"]
        assert {c for c, keys in marked.items() if "PK" in keys} == {
            column.name for column in table.primary_key.columns
        }, f"{name}: primary key marker disagrees with the model"
        assert {c for c, keys in marked.items() if "FK" in keys} == {
            column.name for column in table.columns if column.foreign_keys
        }, f"{name}: foreign key marker disagrees with the model"
        assert {c for c, keys in marked.items() if "UK" in keys} == {
            next(iter(constraint.columns)).name
            for constraint in table.constraints
            if isinstance(constraint, UniqueConstraint) and len(constraint.columns) == 1
        }, f"{name}: unique marker disagrees with the model"


def test_relationship_lines_cover_every_foreign_key() -> None:
    """Counted per table pair, because users-to-tickets is drawn twice."""
    entities, relationships = _parse()
    drawn: dict[frozenset[str], int] = {}
    for left, _cardinality, right in relationships:
        pair = frozenset({left, right})
        drawn[pair] = drawn.get(pair, 0) + 1

    expected: dict[frozenset[str], int] = {}
    for name, table in Base.metadata.tables.items():
        for column in table.columns:
            for foreign_key in column.foreign_keys:
                pair = frozenset({name, foreign_key.column.table.name})
                expected[pair] = expected.get(pair, 0) + 1

    assert drawn == expected, (
        "a foreign key has no drawn relationship, or the diagram draws one the "
        f"models do not have: drawn {sorted(map(sorted, drawn))} vs "
        f"expected {sorted(map(sorted, expected))}"
    )


def test_nullable_foreign_keys_are_drawn_zero_or_one() -> None:
    """A nullable pointer is `|o` on the referenced side, not `||`."""
    entities, relationships = _parse()
    for name, table in Base.metadata.tables.items():
        for column in table.columns:
            for foreign_key in column.foreign_keys:
                parent = foreign_key.column.table.name
                expected = "||" if not column.nullable else "|o"
                matches = [
                    cardinality
                    for left, cardinality, right in relationships
                    if {left, right} == {name, parent}
                ]
                assert matches, f"{name}.{column.name} is not drawn at all"
                sides = [match.split("--") for match in matches]
                drawn = {
                    side[0] if left == parent else side[1]
                    for (left, _c, _r), side in zip(
                        [r for r in relationships if {r[0], r[2]} == {name, parent}],
                        sides,
                    )
                }
                assert expected in drawn, (
                    f"{name}.{column.name} -> {parent} is "
                    f"{'nullable' if column.nullable else 'required'} but no drawn "
                    f"relationship says {expected!r} on the {parent} side"
                )
