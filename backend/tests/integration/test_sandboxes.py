"""Песочницы: посетитель видит общий мир и только свои записи; общий мир не меняет; сброс удаляет всё."""

from tests.integration.conftest import Node, online

COMMON = {"device": "dev-iso", "address": "Юнусабад 4, дом 2"}


def test_sandboxes_do_not_see_each_other(node: Node) -> None:
    first, second = node.new_sandbox(), node.new_sandbox()
    node.assess(first, "A", online("34000000000001", "998905550001", **COMMON))
    decision = node.assess(second, "B", online("34000000000002", "998905550001", **COMMON))
    assert decision["level"] == "green"
    assert decision["marked_applications"] == []


def test_sandbox_sees_the_world_but_cannot_change_it(node: Node) -> None:
    node.watermark(node.world_id)
    node.assess(node.world_id, "W", online("34000000000003", "998905550003", **COMMON))
    sandbox = node.new_sandbox()
    decision = node.assess(sandbox, "S", online("34000000000004", "998905550003", **COMMON))
    assert decision["level"] == "red"
    assert decision["marked_applications"] == [], "заявку общего мира посетитель не помечает"
    assert node.sql("SELECT needs_reassessment FROM applications WHERE external_id = 'W'")[0][0] is False


def test_staff_token_is_bound_to_its_sandbox(node: Node) -> None:
    first, second = node.new_sandbox(), node.new_sandbox()
    headers = {**node.staff(first, "analyst-1"), "X-Realm-Id": str(second)}
    assert node.client.get("/v1/auth/me", headers=headers).status_code == 200
    assert node.client.get("/v1/applications/A", headers=headers).status_code == 403


def test_reset_deletes_everything_of_the_sandbox(node: Node) -> None:
    sandbox = node.new_sandbox()
    snap = online("34000000000005", "998905550005")
    node.assess(sandbox, "A", snap)
    node.permit(sandbox, "A", snap)
    response = node.client.delete(f"/v1/realms/{sandbox}", headers={"Authorization": "Bearer test-realms"})
    assert response.status_code == 204
    for table in ("applications", "decisions", "permits", "audit_records", "occurrences", "watermarks"):
        assert node.sql(f"SELECT count(*) FROM {table} WHERE realm_id = :r", r=str(sandbox))[0][0] == 0
