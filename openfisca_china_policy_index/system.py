from __future__ import annotations

from openfisca_core.taxbenefitsystems import TaxBenefitSystem

from .entities import SupportUnit
from .variables import VARIABLES


class CountryTaxBenefitSystem(TaxBenefitSystem):
    def __init__(self) -> None:
        super().__init__([SupportUnit])
        for variable in VARIABLES:
            self.add_variable(variable)
