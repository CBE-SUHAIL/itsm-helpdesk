"""G03: `/docs` covers every route, and the documented shapes match the contract.

No database and no HTTP: this reads the OpenAPI document FastAPI generates from
the routes and their response models. It is the executable half of the contract's
"FastAPI's generated OpenAPI page at `/docs` must match the implemented
contract", of G03's "every endpoint has useful request, response, and
authentication details", and of F06's requirement that both people can confirm
the frontend and backend shapes agree.

The shape assertions are deliberately exact. A field added to a response model
without a contract change fails here, and so does dropping one.
"""

from app.main import app

SPEC = app.openapi()

# The only routes the contract leaves public.
PUBLIC = {
    ("post", "/api/v1/auth/login"),
    ("post", "/api/v1/auth/refresh"),
    ("get", "/api/v1/health"),
}

# docs/API_CONTRACT.md, "Response shapes used below", for every shape implemented
# so far. The list is the contract's, not the models'.
CONTRACT_SHAPES = {
    "UserOut": {"id", "name", "email", "role", "is_active", "created_at", "updated_at"},
    "CategoryOut": {
        "id", "name", "description", "is_active", "created_at", "updated_at",
    },
    "TicketOut": {
        "id", "title", "description", "category_id", "creator_id", "assignee_id",
        "status", "priority", "response_due_at", "resolution_due_at",
        "first_response_at", "resolved_at", "response_overdue",
        "resolution_overdue", "created_at", "updated_at",
    },
    "TicketHistoryOut": {
        "id", "ticket_id", "actor_id", "field", "old_value", "new_value",
        "reason", "created_at",
    },
    "CommentOut": {"id", "ticket_id", "author_id", "body", "created_at"},
    "AttachmentOut": {
        "id", "ticket_id", "uploader_id", "file_name", "content_type",
        "size_bytes", "created_at",
    },
    "NotificationOut": {
        "id", "recipient_id", "ticket_id", "type", "message", "read_at",
        "dismissed_at", "created_at",
    },
    "AuditLogOut": {
        "id", "actor_id", "action", "entity_type", "entity_id", "old_value",
        "new_value", "created_at",
    },
}


def operations():
    for path, methods in SPEC["paths"].items():
        for method, operation in methods.items():
            yield path, method, operation


def test_every_operation_is_summarised_and_tagged() -> None:
    declared = {tag["name"] for tag in SPEC.get("tags", [])}
    assert declared, "openapi_tags must be declared so /docs groups the routes"
    for path, method, operation in operations():
        label = f"{method.upper()} {path}"
        assert path.startswith("/api/v1"), label
        assert operation.get("summary"), f"{label} has no summary"
        assert operation.get("tags"), f"{label} has no tag"
        assert set(operation["tags"]) <= declared, f"{label} uses an undeclared tag"
        # Something must describe the outcome: a body, a file, or a bare 204.
        assert {200, 201, 204} & {int(code) for code in operation["responses"]}, label


def test_only_the_three_public_routes_skip_authentication() -> None:
    scheme = SPEC["components"]["securitySchemes"]["HTTPBearer"]
    assert scheme["scheme"] == "bearer"
    for path, method, operation in operations():
        label = f"{method.upper()} {path}"
        if (method, path) in PUBLIC:
            assert not operation.get("security"), f"{label} should not require a token"
        else:
            assert operation.get("security") == [{"HTTPBearer": []}], (
                f"{label} does not declare the bearer token"
            )


def test_documented_shapes_match_the_contract_exactly() -> None:
    schemas = SPEC["components"]["schemas"]
    for name, expected in CONTRACT_SHAPES.items():
        assert name in schemas, f"{name} is missing from /docs"
        assert set(schemas[name]["properties"]) == expected, name


def test_page_shapes_are_items_and_total() -> None:
    schemas = SPEC["components"]["schemas"]
    pages = {name: schema for name, schema in schemas.items() if name.endswith("Page")}
    assert pages, "the paginated routes must document a Page schema"
    for name, schema in pages.items():
        assert set(schema["properties"]) == {"items", "total"}, name


def test_paginated_routes_document_limit_and_offset() -> None:
    seen = 0
    for path, method, operation in operations():
        for response in operation["responses"].values():
            schema = (
                response.get("content", {})
                .get("application/json", {})
                .get("schema", {})
            )
            if str(schema.get("$ref", "")).endswith("Page"):
                seen += 1
                names = {param["name"] for param in operation.get("parameters", [])}
                assert {"limit", "offset"} <= names, f"{method.upper()} {path}"
    assert seen >= 7, "the paginated routes disappeared from the document"


def test_nothing_in_v1_deletes_a_record() -> None:
    """No hard deletion in v1: the audit log and notifications included."""
    for path, methods in SPEC["paths"].items():
        assert "delete" not in methods, path
    assert set(SPEC["paths"]["/api/v1/audit-logs"]) == {"get"}
    assert set(SPEC["paths"]["/api/v1/notifications/{notification_id}/read"]) == {"patch"}
    assert set(SPEC["paths"]["/api/v1/notifications/{notification_id}/dismiss"]) == {"patch"}


def test_the_api_description_explains_auth_errors_and_paging() -> None:
    description = SPEC["info"]["description"]
    for expected in ("Authentication", "403", "404", "422", "limit", "offset"):
        assert expected in description, expected
