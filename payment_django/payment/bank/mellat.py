import logging
import six
import abc
import uuid
from urllib import parse
from json import dumps, loads, load
from time import gmtime, strftime
from zeep import Client, Transport

from django.db.models import Q
from django.shortcuts import redirect
from django.urls import reverse
from django.utils import timezone

from .. import default_settings as settings
from ..exceptions.exceptions import *
from ..models.enums import CurrencyEnum, PaymentStatus
from ..models.banks import Bank, CurrencyEnum, PaymentStatus
from utils import append_querystring


class Mellat(BaseBank):
    _terminal_code= None
    _username= None
    _password= None

    _gateway_currency: str= CurrencyEnum.IRR
    _currency: str= CurrencyEnum.IRR
    _amount: int= 0
    _gateway_amount: int= 0
    _mobile_number: str= None
    _tracking_code: int= None
    _reference_number: str= ""
    _transaction_status_text: str= ""
    _client_callback_url: str= ""
    _bank: Bank= None
    _request= None
        
    
    # initialization
    
    def __init__(self, **kwargs):
        self.default_setting_kwargs= kwargs
        self._set_default_settings()
        self._gateway_currency= CurrencyEnum.IRR
        self._status_codes= self._set_status_codes()
        self._payment_url= "https://bpm.shaparak.ir/pgwchannel/startpay.mellat"

    def _set_default_settings(self):
        for item in ["TERMINAL_CODE", "USERNAME", "PASSWORD"]:
            if item not in self.default_setting_kwargs:
                raise SettingDoesNotExist()
            setattr(self, f"_{item.lower()}", self.default_setting_kwargs[item])
            
    def _set_status_codes(self):
        try:
            with open('status_codes.json', 'r') as f:
                status_codes= json.load(f)
            return status_codes
        
        except Exception as e:
            print(f"Error occurred: {e}")
            
    """
    gateway
    """
    
    @staticmethod
    def _get_client():
        transport= Transport(timeout=5, operation_timeout=5)
        client= Client("https://bpm.shaparak.ir/pgwchannel/services/pgw?wsdl", transport=transport)
        return client

    @staticmethod
    def _get_current_time():
        return strftime("%H%M%S")

    @staticmethod
    def _get_current_date():
        return strftime("%Y%m%d", gmtime())

    @staticmethod
    def get_minimum_amount():
        return 1000

    # Gateway Methods
        
    def _get_gateway_payment_url_parameter(self):
        return self._payment_url

    def _get_gateway_payment_parameter(self):
        params= {
            "RefId": self.get_reference_number(),
            "MobileNo": self.get_mobile_number(),
        }
        return params

    def _get_gateway_payment_method_parameter(self):
        return "GET"
    
    
    # Pay Methods
        
    def _set_tracking_code(self, tracking_code):
        self._tracking_code= tracking_code

    def get_tracking_code(self):
        return self._tracking_code
        
    def prepare_amount(self):
        """prepare amount"""
        if self._currency== self._gateway_currency:
            self._gateway_amount= self._amount
        elif self._currency== CurrencyEnum.IRR and self._gateway_currency== CurrencyEnum.IRT:
            self._gateway_amount= CurrencyEnum.rial_to_toman(self._amount)
        elif self._currency== CurrencyEnum.IRT and self._gateway_currency== CurrencyEnum.IRR:
            self._gateway_amount= CurrencyEnum.toman_to_rial(self._amount)
        else:
            self._gateway_amount= self._amount

        if not self.check_amount():
            raise AmountDoesNotSupport()


    def get_pay_data(self):
        description= "خرید با شماره پیگیری - {}".format(self.get_tracking_code())
        data= {
            "terminalId": int(self._terminal_code),
            "userName": self._username,
            "userPassword": self._password,
            "orderId": int(self.get_tracking_code()),
            "amount": int(self.get_gateway_amount()),
            "localDate": self._get_current_date(),
            "localTime": self._get_current_time(),
            "additionalData": description,
            "callBackUrl": self._get_gateway_callback_url(),
            "payerId": 0,
        }
        return data
    
    
    def ready(self) -> Bank:
        self.pay()
        bank= Bank.objects.create(
            bank_choose_identifier=self.identifier,
            bank_type=self.get_bank_type(),
            amount=self.get_amount(),
            reference_number=self.get_reference_number(),
            response_result=self.get_transaction_status_text(),
            tracking_code=self.get_tracking_code(),
        )
        self._bank= bank
        self._set_payment_status(PaymentStatus.WAITING)
        if self._client_callback_url:
            self._bank.callback_url= self._client_callback_url
        return bank



    def prepare_pay(self):
        logging.debug("Prepare pay method")
        self.prepare_amount()
        tracking_code= int(str(uuid.uuid4().int)[-1 * settings.TRACKING_CODE_LENGTH :])
        self._set_tracking_code(tracking_code)

    def pay(self):
        logging.debug("Pay method")
        self.prepare_pay()
        
        data= self.get_pay_data()
        client= self._get_client()
        response= client.service.bpPayRequest(**data)
        try:
            status, token= response.split(",")
            if status== "0":
                self._set_reference_number(token)
        except ValueError:
            status_text= "Unknown error"
            if response in self.status_codes:
                status_text= self.status_codes[response]

            self._set_transaction_status_text(status_text)
            logging.critical(status_text)
            raise BankGatewayRejectPayment(self.get_transaction_status_text())

    """
    verify from gateway
    """

    def prepare_verify_from_gateway(self):
        post= self.get_request().POST
        token= post.get("RefId", None)
        if not token:
            return
        self._set_reference_number(token)
        self._set_bank_record()
        self._bank.extra_information= dumps(dict(zip(post.keys(), post.values())))
        self._bank.save()

    def _set_payment_status(self, payment_status):
        if payment_status== PaymentStatus.RETURN_FROM_BANK and self._bank.status != PaymentStatus.REDIRECT_TO_BANK:
            logging.debug(
                "Payment status is not status suitable.",
                extra={"status": self._bank.status},
            )
            raise BankGatewayStateInvalid(
                "You change the status bank record before/after this record change status from redirect to bank. "
                "current status is {}".format(self._bank.status)
            )
        self._bank.status= payment_status
        self._bank.save()
        logging.debug("Change bank payment status", extra={"status": payment_status})


    def verify_from_gateway(self, request):
        """زمانی که کاربر از گیت وی بانک باز میگردد این متد فراخوانی می شود."""
        self.set_request(request)
        self.prepare_verify_from_gateway()
        self._set_payment_status(PaymentStatus.RETURN_FROM_BANK)
        self.verify(self.get_tracking_code())

    """
    verify
    """

    def get_verify_data(self):
        super(Mellat, self).get_verify_data()
        data= {
            "terminalId": self._terminal_code,
            "userName": self._username,
            "userPassword": self._password,
            "orderId": self.get_tracking_code(),
            "saleOrderId": self.get_tracking_code(),
            "saleReferenceId": self._get_sale_reference_id(),
        }
        return data

    def prepare_verify(self, tracking_code):
        logging.debug("Prepare verify method")
        self._set_tracking_code(tracking_code)
        self._set_bank_record()
        self.prepare_amount()

    def verify(self, transaction_code):
        logging.debug("Verify method")
        self.prepare_verify(tracking_code)
        
        data= self.get_verify_data()
        client= self._get_client()

        verify_result= client.service.bpVerifyRequest(**data)
        if verify_result== "0":
            self._settle_transaction()
        else:
            verify_result= client.service.bpInquiryRequest(**data)
            if verify_result== "0":
                self._settle_transaction()
            else:
                logging.debug("Not able to verify the transaction, Making reversal request")
                reversal_result= client.service.bpReversalRequest(**data)

                if reversal_result != "0":
                    logging.debug("Reversal request was not successfull")

                self._set_payment_status(PaymentStatus.CANCEL_BY_USER)
                logging.debug("Mellat gateway unapproved the payment")

    def _settle_transaction(self):
        data= self.get_verify_data()
        client= self._get_client()
        settle_result= client.service.bpSettleRequest(**data)
        if settle_result== "0":
            self._set_payment_status(PaymentStatus.COMPLETE)
        else:
            logging.debug("Mellat gateway did not settle the payment")

    
    def _get_sale_reference_id(self):
        extra_information= loads(getattr(self._bank, "extra_information", "{}"))
        return extra_information.get("SaleReferenceId", "1")

    def _verify_payment_expiry(self):
        """برسی میکند درگاه ساخته شده اعتبار دارد یا خیر"""
        if (timezone.now() - self._bank.created_at).seconds > 120:
            self._set_payment_status(PaymentStatus.EXPIRE_GATEWAY_TOKEN)
            logging.debug("Redirect to bank expire!")
            raise BankGatewayTokenExpired()

    def redirect_gateway(self):
        """کاربر را به درگاه بانک هدایت می کند"""
        self._verify_payment_expiry()
        if settings.IS_SAFE_GET_GATEWAY_PAYMENT:
            raise SafeSettingsEnabled()
        logging.debug("Redirect to bank")
        self._set_payment_status(PaymentStatus.REDIRECT_TO_BANK)
        return redirect(self.get_gateway_payment_url())

    def get_gateway(self):
        """اطلاعات درگاه پرداخت را برمیگرداند"""
        self._verify_payment_expiry()
        logging.debug("Redirect to bank")
        self._set_payment_status(PaymentStatus.REDIRECT_TO_BANK)
        return self.safe_get_gateway_payment_url()

    def safe_get_gateway_payment_url(self):
        url= self._get_gateway_payment_url_parameter()
        params= self._get_gateway_payment_parameter()
        method= self._get_gateway_payment_method_parameter()
        context= {"params": params, "url": url, "method": method}
        return context

    def get_gateway_payment_url(self):
        redirect_url= reverse(settings.GO_TO_BANK_GATEWAY_NAMESPACE)
        url= self._get_gateway_payment_url_parameter()
        params= self._get_gateway_payment_parameter()
        method= self._get_gateway_payment_method_parameter()
        params.update(
            {
                "url": url,
                "method": method,
            }
        )
        redirect_url= append_querystring(redirect_url, params)
        if self.get_request():
            redirect_url= self.get_request().build_absolute_uri(redirect_url)
        return redirect_url

    def _get_gateway_callback_url(self):
        url= reverse(settings.CALLBACK_NAMESPACE)
        if self.get_request():
            url_parts= list(parse.urlparse(url))
            if not (url_parts[0] and url_parts[1]):
                url= self.get_request().build_absolute_uri(url)
            query= dict(parse.parse_qsl(self.get_request().GET.urlencode()))
            query.update({"bank_type": self.get_bank_type()})
            query.update({"identifier": self.identifier})
            url= append_querystring(url, query)

        return url
    def _prepare_check_gateway(self, amount=None):
        """ست کردن داده های اولیه"""
        if amount:
            self.set_amount(amount)
        else:
            self.set_amount(10000)
        self.set_client_callback_url("/")

    def check_gateway(self, amount=None):
        """با این متد از صحت و سلامت گیت وی برای اتصال اطمینان حاصل می کنیم."""
        self._prepare_check_gateway(amount)
        self.pay()
        
        

    def verify_from_gateway(self, request):
        """زمانی که کاربر از گیت وی بانک باز میگردد این متد فراخوانی می شود."""
        self.set_request(request)
        self.prepare_verify_from_gateway()
        self._set_payment_status(PaymentStatus.RETURN_FROM_BANK)
        self.verify(self.get_tracking_code())

    def get_client_callback_url(self):
        """این متد پس از وریفای شدن استفاده خواهد شد. لینک برگشت را بر میگرداند.حال چه وریفای موفقیت آمیز باشد چه با
        لغو کاربر مواجه شده باشد"""
        return append_querystring(
            self._bank.callback_url,
            {settings.TRACKING_CODE_QUERY_PARAM: self.get_tracking_code()},
        )

    def redirect_client_callback(self):
        """ "این متد کاربر را به مسیری که نرم افزار میخواهد هدایت خواهد کرد و پس از وریفای شدن استفاده می شود."""
        logging.debug("Redirect to client")
        return redirect(self.get_client_callback_url())

    def set_mobile_number(self, mobile_number):
        """شماره موبایل کاربر را جهت ارسال به درگاه برای فتچ کردن شماره کارت ها و ... ارسال خواهد کرد."""
        self._mobile_number= mobile_number

    def get_mobile_number(self):
        return self._mobile_number

    def set_client_callback_url(self, callback_url):
        """ذخیره کال بک از طریق نرم افزار برای بازگردانی کاربر پس از بازگشت درگاه بانک به پکیج و سپس از پکیج به نرم
        افزار."""
        if not self._bank:
            self._client_callback_url= callback_url
        else:
            logging.critical(
                "You are change the call back url in invalid situation.",
                extra={
                    "bank_id": self._bank.pk,
                    "status": self._bank.status,
                },
            )
            raise BankGatewayStateInvalid(
                "Bank state not equal to waiting. Probably finish "
                f"or redirect to bank gateway. status is {self._bank.status}"
            )

    def _set_reference_number(self, reference_number):
        """reference number get from bank"""
        self._reference_number= reference_number

    def _set_bank_record(self):
        try:
            self._bank= Bank.objects.get(
                Q(Q(reference_number=self.get_reference_number()) | Q(tracking_code=self.get_tracking_code())),
                Q(bank_type=self.get_bank_type()),
            )
            logging.debug("Set reference find bank object.")
        except Bank.DoesNotExist:
            logging.debug("Cant find bank record object.")
            raise BankGatewayStateInvalid(
                "Cant find bank record with reference number reference number is {}".format(
                    self.get_reference_number()
                )
            )
        self._set_tracking_code(self._bank.tracking_code)
        self._set_reference_number(self._bank.reference_number)
        self.set_amount(self._bank.amount)

    def get_reference_number(self):
        return self._reference_number

    """
    ترنزکشن تکست متنی است که از طرف درگاه بانک به عنوان پیام باز میگردد.
    """

    def _set_transaction_status_text(self, txt):
        self._transaction_status_text= txt

    def get_transaction_status_text(self):
        return self._transaction_status_text

    def _set_payment_status(self, payment_status):
        if payment_status== PaymentStatus.RETURN_FROM_BANK and self._bank.status != PaymentStatus.REDIRECT_TO_BANK:
            logging.debug(
                "Payment status is not status suitable.",
                extra={"status": self._bank.status},
            )
            raise BankGatewayStateInvalid(
                "You change the status bank record before/after this record change status from redirect to bank. "
                "current status is {}".format(self._bank.status)
            )
        self._bank.status= payment_status
        self._bank.save()
        logging.debug("Change bank payment status", extra={"status": payment_status})

    def set_gateway_currency(self, currency: CurrencyEnum):
        """واحد پولی درگاه بانک"""
        if currency not in [CurrencyEnum.IRR, CurrencyEnum.IRT]:
            raise CurrencyDoesNotSupport()
        self._gateway_currency= currency

    def get_gateway_currency(self):
        return self._gateway_currency

    def set_currency(self, currency: CurrencyEnum):
        """ "واحد پولی نرم افزار"""
        if currency not in [CurrencyEnum.IRR, CurrencyEnum.IRT]:
            raise CurrencyDoesNotSupport()
        self._currency= currency

    def get_currency(self):
        return self._currency

    def get_gateway_amount(self):
        return self._gateway_amount

    """
    ترکینگ کد توسط برنامه تولید شده و برای استفاده های بعدی کاربرد خواهد داشت.
    """

    def _set_tracking_code(self, tracking_code):
        self._tracking_code= tracking_code

    def get_tracking_code(self):
        return self._tracking_code

    """ًRequest"""

    def set_request(self, request):
        self._request= request

    def get_request(self):
        return self._request

