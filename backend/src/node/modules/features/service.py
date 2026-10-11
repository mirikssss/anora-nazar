"""Расчёт признаков заявки на момент as_of: только факты с received_at ≤ as_of."""

from datetime import datetime
from uuid import UUID

from sqlalchemy.orm import Session

from node.modules.features.domain import FeatureVector, from_group
from node.modules.index import service as index
from node.modules.index.domain import GroupView
from node.modules.policy.domain import Policy
from node.modules.realms.domain import RealmContext


def compute(
    session: Session, realm: RealmContext, application_id: UUID, as_of: datetime, policy: Policy
) -> tuple[FeatureVector, GroupView]:
    view = index.group_view(session, realm, application_id, as_of, policy)
    return from_group(view), view
