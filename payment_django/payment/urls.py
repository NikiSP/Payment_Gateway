from django.urls import path

from payment import default_settings as settings
from payment.apps import AZIranianBankGatewaysConfig
from payment.views import(
    callback_view,
    go_to_bank_gateway,
    sample_payment_view,
    sample_result_view,
)
 

app_name = AZIranianBankGatewaysConfig.name

urlpatterns = [
    path("callback/", callback_view, name="callback"),
]

if not settings.IS_SAFE_GET_GATEWAY_PAYMENT:
    urlpatterns += [
        path("go-to-bank-gateway/", go_to_bank_gateway, name="go-to-bank-gateway"),
    ]

if settings.IS_SAMPLE_FORM_ENABLE:
    urlpatterns += [
        path("sample-payment/", sample_payment_view, name="sample-payment"),
        path("sample-result/", sample_result_view, name="sample-result"),
    ]


def az_bank_gateways_urls():
    return urlpatterns, app_name, app_name

