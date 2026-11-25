"""
Платёжный провайдер. Сейчас — демо (всегда «Оплачено»).
Для Kaspi / Freedom Pay: реализуйте charge() как создание счёта со статусом
«Ожидает оплаты» и включайте тариф в обработчике вебхука провайдера.
"""
from __future__ import annotations

from dataclasses import dataclass

from ..config import Settings


@dataclass
class ChargeResult:
    provider: str
    status: str
    paid: bool


class DemoProvider:
    name = "Demo"

    def charge(self, business_id: str, plan_id: str, amount: int) -> ChargeResult:
        return ChargeResult(provider=self.name, status="Оплачено", paid=True)


def provider_for(settings: Settings) -> DemoProvider:
    return DemoProvider()
