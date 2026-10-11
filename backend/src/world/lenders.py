"""Три условных кредитора. Историю получает только кредитор узла; заявки остальных — заготовка для сети (И4).

Объём кредитора — по его доле рынка относительно доли кредитора узла.
"""

from world.plans import ApplicationPlan, PlanFactory
from world.records import ApplicationTruth, OtherLenderApplication
from world.sampling import chance


def _draft(factory: PlanFactory, online_share: float) -> ApplicationPlan:
    rng, calendar = factory.rng, factory.calendar
    person = factory.population.random(rng)
    signals = factory.honest_signals()
    if chance(rng, online_share):
        return factory.online(person, calendar.moment(rng, calendar.start, calendar.days, night=signals.night), signals)
    moment = calendar.moment(rng, calendar.start, calendar.days, night=False)
    return factory.program(person, moment, signals, factory.usual_roles(person))


def other_lender_applications(
    factory: PlanFactory, node_total: int, online_share: float
) -> tuple[list[OtherLenderApplication], dict[str, ApplicationTruth]]:
    params = factory.params
    node = params.applications.lender
    node_share = params.lender_share(node)
    applications: list[OtherLenderApplication] = []
    truth: dict[str, ApplicationTruth] = {}
    for lender in params.lenders:
        if lender.code == node:
            continue
        drafts = [_draft(factory, online_share) for _ in range(round(node_total * lender.share / node_share))]
        drafts.sort(key=lambda plan: plan.submitted_at)
        for number, plan in enumerate(drafts, start=1):
            record = OtherLenderApplication(
                id=f"W{lender.code}-{number:06d}",
                lender=lender.code,
                channel=plan.channel,
                pinfl=plan.person.pinfl,
                phone=plan.phone,
                device_id=plan.device_id,
                amount=plan.amount,
                occurred_at=plan.submitted_at,
            )
            applications.append(record)
            truth[record.id] = ApplicationTruth(lender=lender.code)
    return applications, truth
