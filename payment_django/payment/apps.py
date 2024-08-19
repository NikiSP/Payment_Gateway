from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _

class AZIranianBankGatewaysConfig(AppConfig):
    name = "payment"
    verbose_name = _("payment gatway")
    verbose_name_plural = _("payment gateways")
    # compatible with django >= 3.2
    default_auto_field = "django.db.models.AutoField"
