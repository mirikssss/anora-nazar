"""F1 — воздействие на заёмщика, только онлайн.

Жертва чаще «чистый клиент с долгой историей»: без текущих долгов и с картой в банке. Сессия с аномалиями —
восстановление доступа, новое устройство, звонок, ночь, быстрая форма, сумма сильно больше трат.
Ловушка: часть жертв проходит без аномалий — по признакам не отличить от честных.

Серия по ПИНФЛ (межбанковая схема): от имени части жертв в окне вокруг заявки у кредитора узла подают заявки
ещё у других кредиторов — тот же ПИНФЛ, телефон, устройство и сумма. Серия идёт до выдачи: после выдачи бюро
закрывает ПИНФЛ для остальных (№ 3759 п. 19–20), поэтому их заявки бюро отклоняет (см. lenders).
"""

from dataclasses import replace
from datetime import timedelta

from world.plans import ApplicationPlan, PlanFactory, draw_signals
from world.sampling import between, chance, pick, portion


def plan_coercion(factory: PlanFactory, online_total: int) -> list[ApplicationPlan]:
    spec = factory.params.fraud.f1
    rng, population, calendar = factory.rng, factory.population, factory.calendar
    if online_total == 0 or spec.share_of_online == 0:
        return []
    plans: list[ApplicationPlan] = []
    for number in range(1, max(1, round(online_total * spec.share_of_online)) + 1):
        clean = chance(rng, spec.clean_history_share)
        if clean and population.card_holders:
            person = population.people[pick(rng, population.card_holders)]
        else:
            person = population.random(rng)
        if chance(rng, spec.victims_without_anomalies):
            signals = factory.honest_signals()
        else:
            signals = draw_signals(rng, spec, factory.params.session)
        signals = replace(signals, clean_history=clean, income_jump=None)
        moment = calendar.moment(rng, calendar.start, calendar.days, night=signals.night)
        plan = factory.online(person, moment, signals)
        plans.append(replace(plan, typology="F1", scheme_key=f"F1-{number:04d}"))
    return _with_series(factory, plans)


def _with_series(factory: PlanFactory, victims: list[ApplicationPlan]) -> list[ApplicationPlan]:
    cross = factory.params.fraud.cross_lender
    if cross is None:
        return victims
    rng, calendar = factory.rng, factory.calendar
    window = timedelta(minutes=cross.f1_series_minutes)
    chosen = set(rng.sample(range(len(victims)), portion(len(victims), cross.f1_series)))
    plans: list[ApplicationPlan] = []
    for index, victim in enumerate(victims):
        series: list[ApplicationPlan] = []
        if index in chosen:
            for lender in factory.other_lenders(between(rng, cross.f1_series_lenders)):
                moment = calendar.around(rng, victim.submitted_at, timedelta(), window)
                if moment is not None:
                    series.append(replace(victim, lender=lender, submitted_at=moment, cross_lender=True))
        plans.append(replace(victim, cross_lender=bool(series)))
        plans += series
    return plans
