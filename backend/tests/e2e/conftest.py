"""E2E: сценарии через HTTP против поднятого стека (docker compose). Адреса — из окружения."""

import os
from collections.abc import Iterator
from typing import Any

import httpx
import pytest

BANK_URL = os.environ.get("E2E_BANK_SIM_URL")
NODE_URL = os.environ.get("E2E_NODE_URL")

pytestmark = pytest.mark.skipif(not BANK_URL or not NODE_URL, reason="E2E: задайте E2E_BANK_SIM_URL и E2E_NODE_URL")


class Sandbox:
    """Песочница посетителя: всё, что делает проверяющий, — через API имитатора банка и узла."""

    def __init__(self, bank: httpx.Client, node: httpx.Client) -> None:
        self.bank, self.node = bank, node
        self.realm = bank.post("/v1/sandboxes").raise_for_status().json()["realm_id"]
        self.headers = {"X-Realm-Id": self.realm}

    def apply(self, draft: dict[str, Any]) -> dict[str, Any]:
        response = self.bank.post("/v1/conveyor/applications", json=draft, headers=self.headers)
        assert response.status_code == 201, response.text
        return response.json()

    def reassess(self, app_id: str) -> dict[str, Any]:
        return (
            self.bank.post(f"/v1/conveyor/applications/{app_id}/assessments", headers=self.headers)
            .raise_for_status()
            .json()
        )

    def execute(self, app_id: str, operation_type: str = "disbursement") -> dict[str, Any]:
        response = self.bank.post(
            "/v1/core-banking/operations",
            headers=self.headers,
            json={"application_id": app_id, "operation_type": operation_type},
        )
        assert response.status_code == 201, response.text
        return response.json()

    def staff_token(self, user_code: str) -> str:
        return (
            self.node.post("/v1/auth/demo-login", json={"user_code": user_code}, headers=self.headers)
            .raise_for_status()
            .json()["token"]
        )

    def as_staff(self, user_code: str) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.staff_token(user_code)}"}

    def close(self) -> None:
        self.bank.delete("/v1/sandboxes/current", headers=self.headers)


@pytest.fixture
def sandbox() -> Iterator[Sandbox]:
    with (
        httpx.Client(base_url=BANK_URL or "", timeout=30) as bank,
        httpx.Client(base_url=NODE_URL or "", timeout=30) as node,
    ):
        box = Sandbox(bank, node)
        yield box
        box.close()


def online_draft(
    pinfl: str,
    phone: str,
    *,
    branch: str = "BR-01",
    employee: str = "EMP-01-1",
    device: str | None = None,
    address: str | None = None,
    employer: str | None = None,
    amount: int = 30_000_000,
) -> dict[str, Any]:
    applicant: dict[str, Any] = {"pinfl": pinfl, "phone": phone}
    if device:
        applicant["device_id"] = device
    if address:
        applicant["address"] = address
    if employer:
        applicant["employer_inn"] = employer
    return {
        "channel": "online",
        "branch_id": branch,
        "employee_id": employee,
        "applicant": applicant,
        "loan": {"amount": amount, "term_months": 12},
        "disbursement_account": f"8600{pinfl[-8:]}",
        "checks": {"biometry": "passed", "phone_owner_match": True},
    }
