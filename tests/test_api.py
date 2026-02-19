def test_login_and_me(client):
    login = client.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
    assert login.status_code == 200

    api_key = login.json()["api_key"]
    me = client.get("/api/me", headers={"X-API-Key": api_key})
    assert me.status_code == 200
    assert me.json()["role"] == "admin"


def test_viewer_is_read_only(client, viewer_headers):
    response = client.post(
        "/api/items",
        headers=viewer_headers,
        json={
            "sku": "TEST-001",
            "name": "Blocked Item",
            "category": "Testing",
            "details": "should fail",
            "quantity": 10,
            "reorder_threshold": 5,
            "unit_cost": 3.5,
            "status": "in_stock",
        },
    )
    assert response.status_code == 403


def test_manager_can_crud_and_writes_audit(client, manager_headers):
    before_logs = client.get("/api/audit", headers=manager_headers).json()

    created = client.post(
        "/api/items",
        headers=manager_headers,
        json={
            "sku": "TEST-CRUD-1",
            "name": "Test Item",
            "category": "Testing",
            "details": "new item",
            "quantity": 8,
            "reorder_threshold": 4,
            "unit_cost": 9.25,
            "status": "low_stock",
        },
    )
    assert created.status_code == 200
    item_id = created.json()["id"]

    updated = client.put(
        f"/api/items/{item_id}",
        headers=manager_headers,
        json={"quantity": 20, "details": "updated details"},
    )
    assert updated.status_code == 200
    assert updated.json()["quantity"] == 20

    status_change = client.patch(
        f"/api/items/{item_id}/status",
        headers=manager_headers,
        json={"status": "ordered", "note": "supplier confirmed"},
    )
    assert status_change.status_code == 200
    assert status_change.json()["status"] == "ordered"

    deleted = client.delete(f"/api/items/{item_id}", headers=manager_headers)
    assert deleted.status_code == 200

    after_logs = client.get("/api/audit", headers=manager_headers).json()
    assert len(after_logs) > len(before_logs)


def test_search_by_name_category_status(client, viewer_headers):
    response = client.get(
        "/api/items/search",
        headers=viewer_headers,
        params={"q": "Monitor", "category": "Electronics", "status": "in_stock"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] >= 1
    assert any(item["name"] == "27-inch Monitor" for item in payload["items"])


def test_bulk_status_update(client, manager_headers):
    listing = client.get("/api/items", headers=manager_headers)
    assert listing.status_code == 200
    item_ids = [row["id"] for row in listing.json()["items"][:2]]

    result = client.patch(
        "/api/items/status/bulk",
        headers=manager_headers,
        json={"item_ids": item_ids, "status": "ordered", "note": "bulk test"},
    )
    assert result.status_code == 200
    assert result.json()["updated_count"] == len(item_ids)


def test_ai_endpoints_have_graceful_source(client, viewer_headers):
    reorder = client.get("/api/ai/reorder-suggestions", headers=viewer_headers)
    assert reorder.status_code == 200
    assert reorder.json()["source"] in {"ai", "fallback"}

    anomaly = client.get("/api/ai/anomaly-alerts", headers=viewer_headers)
    assert anomaly.status_code == 200
    assert anomaly.json()["source"] in {"ai", "fallback"}

    nl = client.post(
        "/api/ai/natural-language-search",
        headers=viewer_headers,
        json={"query": "low stock electronics under 20"},
    )
    assert nl.status_code == 200
    assert nl.json()["source"] in {"ai", "fallback"}


def test_deleted_item_cannot_be_edited(client, manager_headers):
    created = client.post(
        "/api/items",
        headers=manager_headers,
        json={
            "sku": "TEST-DEL-EDIT-1",
            "name": "Delete Edit Guard",
            "category": "Testing",
            "details": "guard check",
            "quantity": 5,
            "reorder_threshold": 2,
            "unit_cost": 2.5,
            "status": "in_stock",
        },
    )
    assert created.status_code == 200
    item_id = created.json()["id"]

    deleted = client.delete(f"/api/items/{item_id}", headers=manager_headers)
    assert deleted.status_code == 200

    update_attempt = client.put(
        f"/api/items/{item_id}",
        headers=manager_headers,
        json={"name": "Should Fail"},
    )
    assert update_attempt.status_code == 400
    assert "Cannot edit a deleted item" in update_attempt.json()["detail"]


def test_restore_item_via_single_and_bulk_status(client, manager_headers):
    created = client.post(
        "/api/items",
        headers=manager_headers,
        json={
            "sku": "TEST-RESTORE-1",
            "name": "Restore Path",
            "category": "Testing",
            "details": "restore checks",
            "quantity": 3,
            "reorder_threshold": 1,
            "unit_cost": 4.0,
            "status": "in_stock",
        },
    )
    assert created.status_code == 200
    item_id = created.json()["id"]

    deleted = client.delete(f"/api/items/{item_id}", headers=manager_headers)
    assert deleted.status_code == 200

    single_restore = client.patch(
        f"/api/items/{item_id}/status",
        headers=manager_headers,
        json={"status": "in_stock", "note": "single restore"},
    )
    assert single_restore.status_code == 200
    assert single_restore.json()["is_deleted"] is False
    assert single_restore.json()["status"] == "in_stock"

    listed_after_single = client.get("/api/items", headers=manager_headers).json()["items"]
    assert any(item["id"] == item_id for item in listed_after_single)

    bulk_delete = client.patch(
        "/api/items/status/bulk",
        headers=manager_headers,
        json={"item_ids": [item_id], "status": "discontinued", "note": "bulk delete"},
    )
    assert bulk_delete.status_code == 200

    bulk_restore = client.patch(
        "/api/items/status/bulk",
        headers=manager_headers,
        json={"item_ids": [item_id], "status": "ordered", "note": "bulk restore"},
    )
    assert bulk_restore.status_code == 200

    item_after_bulk = client.get(f"/api/items/{item_id}", headers=manager_headers)
    assert item_after_bulk.status_code == 200
    assert item_after_bulk.json()["is_deleted"] is False
    assert item_after_bulk.json()["status"] == "ordered"


def test_create_with_discontinued_status_sets_deleted_flag(client, manager_headers):
    created = client.post(
        "/api/items",
        headers=manager_headers,
        json={
            "sku": "TEST-DISC-CREATE-1",
            "name": "Discontinued On Create",
            "category": "Testing",
            "details": "create consistency",
            "quantity": 0,
            "reorder_threshold": 0,
            "unit_cost": 0.5,
            "status": "discontinued",
        },
    )
    assert created.status_code == 200
    assert created.json()["status"] == "discontinued"
    assert created.json()["is_deleted"] is True


def test_put_with_discontinued_status_marks_deleted_flag(client, manager_headers):
    created = client.post(
        "/api/items",
        headers=manager_headers,
        json={
            "sku": "TEST-DISC-PUT-1",
            "name": "Discontinued Via Put",
            "category": "Testing",
            "details": "put consistency",
            "quantity": 3,
            "reorder_threshold": 1,
            "unit_cost": 1.5,
            "status": "in_stock",
        },
    )
    assert created.status_code == 200
    item_id = created.json()["id"]

    updated = client.put(
        f"/api/items/{item_id}",
        headers=manager_headers,
        json={"status": "discontinued"},
    )
    assert updated.status_code == 200
    assert updated.json()["status"] == "discontinued"
    assert updated.json()["is_deleted"] is True
