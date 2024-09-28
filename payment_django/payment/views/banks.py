import logging
from urllib.parse import unquote
from django.urls import reverse

from django.http import Http404
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt

from payment.bankfactories import BankFactory
from payment.exceptions.exceptions import AZBankGatewaysException
from rest_framework.decorators import api_view


@csrf_exempt
@api_view()
def callback_view(request):
    factory = BankFactory()
    bank= factory.create()
    try:
        bank.verify_from_gateway(request)
    except AZBankGatewaysException:
        logging.exception("Verify from gateway failed.", stack_info=True)
    return bank.redirect_client_callback()


@csrf_exempt
@api_view()
def go_to_bank_gateway(request):
    context = {"params": {}}
    for key, value in request.GET.items():
        if key == "url" or key == "method":
            context[key] = unquote(value)
        else:
            context["params"][key] = unquote(value)

    return render(request, "azbankgateways/redirect_to_bank.html", context=context)


# def go_to_gateway_view(request):
    # # خواندن مبلغ از هر جایی که مد نظر است
    # amount = 100000
    # # تنظیم شماره موبایل کاربر از هر جایی که مد نظر است
    # user_mobile_number = "+989396551765"  # اختیاری

    # factory= BankFactory()
    # try:
    #     bank= (
    #         factory.create()
    #     )  # or factory.create(bank_models.BankType.BMI) or set identifier
    #     bank.set_request(request)
    #     bank.set_amount(amount)
    #     # یو آر ال بازگشت به نرم افزار برای ادامه فرآیند
    #     # bank.set_client_callback_url(reverse("callback-gateway"))
    #     bank.set_mobile_number(user_mobile_number)  # اختیاری

    #     # در صورت تمایل اتصال این رکورد به رکورد فاکتور یا هر چیزی که بعدا بتوانید ارتباط بین محصول یا خدمات را با این
    #     # پرداخت برقرار کنید.
    #     bank_record = bank.ready()

    #     # هدایت کاربر به درگاه بانک
    #     return bank.redirect_gateway()
    # except AZBankGatewaysException as e:
    #     logging.critical(e)
    #     # TODO: redirect to failed page.
    #     raise e