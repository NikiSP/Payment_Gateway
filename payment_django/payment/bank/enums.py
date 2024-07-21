from django.db import models
from django.utils.translation import gettext_lazy as _

class CurrencyEnum(models.TextChoices):
    IRR= "IRR", _("Rial")
    IRT= "IRT", _("Toman")

    @classmethod
    def rial_to_toman(cls, amount):
        return amount / 10

    @classmethod
    def toman_to_rial(cls, amount):
        return amount * 10


class PaymentStatus(models.TextChoices):
    WAITING = "WAITING", _("Waiting")
    ERROR= "ERROR", _("Unknown error occured")
    COMPLETE= "COMPLETE", _("Complete")
    CANCEL_BY_USER= "CANCEL_BY_USER", _("Cancel by user")
    REDIRECT_TO_BANK = "REDIRECT_TO_BANK", _("Redirect to bank")
    RETURN_FROM_BANK = "RETURN_FROM_BANK", _("Return from bank")
    EXPIRE_GATEWAY_TOKEN= "EXPIRE_GATEWAY_TOKEN", _("Expired gateway token")
    EXPIRE_VERIFY_PAYMENT= "EXPIRE_VERIFY_PAYMENT", _("Expired verify payment")
    
