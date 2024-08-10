import json
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


from payment import default_settings as settings
from payment.exceptions.exceptions import *
from payment.models.enum import CurrencyEnum, PaymentStatus
from payment.bank.utils import append_querystring
from payment.models.banks import Bank

class Mellat():
    _terminal_code= 7164489
    _username= 'ebcom41'
    _password= 26952397
    
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
        
    
    """
    initialization
    """
    
    def __init__(self, **kwargs):
        self.default_setting_kwargs= kwargs
        self._set_default_settings()
        self._status_codes= self._set_status_codes()
        self._payment_url= "https://bpm.shaparak.ir/pgwchannel/startpay.mellat"

    def _set_default_settings(self):
        # for item in ["TERMINAL_CODE", "USERNAME", "PASSWORD"]:
        #     if item not in self.default_setting_kwargs:
        #         raise SettingDoesNotExist()
        #     setattr(self, f"_{item.lower()}", self.default_setting_kwargs[item])
        pass 
    
    def _set_status_codes(self):
        try:
            with open('payment/bank/status_codes.json', 'r') as f:
                status_codes= json.load(f)
            
            return status_codes
        
        except Exception as e:
            print(f"Error occurred: {e}")
            
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

    """
    Basic Methods
    """
    
    def set_mobile_number(self, mobile_number):
        self._mobile_number= mobile_number

    def get_mobile_number(self):
        return self._mobile_number
        
    def _set_tracking_code(self, tracking_code):
        self._tracking_code= tracking_code

    def get_tracking_code(self):
        return self._tracking_code    
    
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
    
    def set_gateway_currency(self, currency: CurrencyEnum):
        if currency not in [CurrencyEnum.IRR, CurrencyEnum.IRT]:
            raise CurrencyDoesNotSupport()
        self._gateway_currency= currency

    def get_gateway_currency(self):
        return self._gateway_currency

    def set_currency(self, currency: CurrencyEnum):
        if currency not in [CurrencyEnum.IRR, CurrencyEnum.IRT]:
            raise CurrencyDoesNotSupport()
        self._currency= currency

    def get_currency(self):
        return self._currency

    def get_gateway_amount(self):
        return self._gateway_amount

    def set_request(self, request):
        self._request= request

    def get_request(self):
        return self._request
    
    def _set_reference_number(self, reference_number):
        self._reference_number= reference_number

    def get_amount(self):
        return self._amount
    
    def set_amount(self, amount):
        self._amount= amount

    """
    Pay
    """
        
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
            bank_choose_identifier= self.identifier,
            amount= self.get_amount(),
            reference_number= self.get_reference_number(),
            response_result= self.get_transaction_status_text(),
            tracking_code= self.get_tracking_code(),
        )
        self._bank= bank
        self._set_payment_status(PaymentStatus.WAITING)
        if self._client_callback_url:
            self._bank.callback_url= self._client_callback_url
        return bank

    
    def check_amount(self):
        return self.get_gateway_amount() >= self.get_minimum_amount()


    def prepare_amount(self):
        if self._currency==CurrencyEnum.IRR and self._gateway_currency==CurrencyEnum.IRT:
            self._gateway_amount= CurrencyEnum.rial2toman_converter(self._amount)
        elif self._currency==CurrencyEnum.IRT and self._gateway_currency==CurrencyEnum.IRR:
            self._gateway_amount=CurrencyEnum.toman2rial_coverter(self._amount)
        else:
            self._gateway_amount= self._amount

        if not self.check_amount():
            raise AmountDoesNotSupport()


    def prepare_pay(self):
        logging.debug("Prepare pay method")
        self.prepare_amount()
        tracking_code= int(str(uuid.uuid4().int)[-1*settings.TRACKING_CODE_LENGTH:])
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
            if response in self._status_codes:
                status_text= self._status_codes[response]

            self._set_transaction_status_text(status_text)
            logging.critical(status_text)
            raise BankGatewayRejectPayment(self.get_transaction_status_text())


    """
    Verificaiton
    """

    # Verify basic methods
    
    def get_reference_number(self):
        # reference number the bank returned
        return self._reference_number

    def _set_transaction_status_text(self, txt):
        # text that the bank itself returns
        self._transaction_status_text= txt

    def get_transaction_status_text(self):
        # text that the bank itself returns
        return self._transaction_status_text

    def _get_sale_reference_id(self):
        extra_information= loads(getattr(self._bank, "extra_information", "{}"))
        return extra_information.get("SaleReferenceId", "1")
        
            
    def _verify_payment_expiry(self):
        if (timezone.now()-self._bank.created_at).seconds>120:
            self._set_payment_status(PaymentStatus.EXPIRE_GATEWAY_TOKEN)
            logging.debug("Redirect to bank expire!")
            raise BankGatewayTokenExpired()

    def get_gateway(self):
        # gateway info
        self._verify_payment_expiry()
        logging.debug("Redirect to bank")
        self._set_payment_status(PaymentStatus.REDIRECT_TO_BANK)
        return self.safe_get_gateway_payment_url()
    


    # Get_URL methods
        

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


    # Callback URL 
    
    def get_client_callback_url(self):
        # Get callback URL after verification
        return append_querystring(
            self._bank.callback_url,
            {settings.TRACKING_CODE_QUERY_PARAM: self.get_tracking_code()},
        )


    def _get_gateway_callback_url(self):
        url= reverse(settings.CALLBACK_NAMESPACE)
        if self.get_request():
            url_parts= list(parse.urlparse(url))
            if not (url_parts[0] and url_parts[1]):
                url= self.get_request().build_absolute_uri(url)
            query= dict(parse.parse_qsl(self.get_request().GET.urlencode()))
            # query.update({"bank_type": self.get_bank_type()})
            # query.update({"identifier": self.identifier})
            url= append_querystring(url, query)

        return url
    
    def set_client_callback_url(self, callback_url):
        # Stores callback through to return the user after redirecting from the bank gateway
        if not self._bank:
            self._client_callback_url= callback_url
        else:
            logging.critical(
                "The URL is getting change in an invalid state",
                extra={
                    "bank_id": self._bank.pk,
                    "status": self._bank.status,
                },
            )
            raise BankGatewayStateInvalid(
                "Bank state not equal to waiting. Probably finish"
                f"or redirect to bank gateway. status:{self._bank.status}"
            )
    
    
    # Redirect Methods
    def redirect_gateway(self):
        self._verify_payment_expiry()
        if settings.IS_SAFE_GET_GATEWAY_PAYMENT:
            raise SafeSettingsEnabled()
        logging.debug("Redirect to bank")
        self._set_payment_status(PaymentStatus.REDIRECT_TO_BANK)
        return redirect(self.get_gateway_payment_url())
    
    def redirect_client_callback(self):
        # Used after verification
        logging.debug("Redirect to client")
        return redirect(self.get_client_callback_url())

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

    
    def _settle_transaction(self):
        data= self.get_verify_data()
        client= self._get_client()
        settle_result= client.service.bpSettleRequest(**data)
        
        if settle_result== "0":
            self._set_payment_status(PaymentStatus.COMPLETE)
        else:
            logging.debug("Mellat gateway did not settle the payment")


    def _prepare_check_gateway(self, amount=None):
        # Set preliminary data
        if amount:
            self.set_amount(amount)
        else:
            self.set_amount(10000)
        self.set_client_callback_url("/")

    def check_gateway(self, amount=None):
        self._prepare_check_gateway(amount)
        self.pay()
        

    def get_verify_data(self):
        data= {
            "terminalId": self._terminal_code,
            "userName": self._username,
            "userPassword": self._password,
            "orderId": self.get_tracking_code(),
            "saleOrderId": self.get_tracking_code(),
            "saleReferenceId": self._get_sale_reference_id(),
        }
        return data
    
        
    def prepare_verify_from_gateway(self):
        post= self.get_request().POST
        token= post.get("RefId", None)
        if not token:
            return
        self._set_reference_number(token)
        self._set_bank_record()
        self._bank.extra_information= dumps(dict(zip(post.keys(), post.values())))
        self._bank.save()
        
    def verify_from_gateway(self, request):
        # When returned client is returned by the bank
        self.set_request(request)
        self.prepare_verify_from_gateway()
        self._set_payment_status(PaymentStatus.RETURN_FROM_BANK)
        self.verify(self.get_tracking_code())

    def prepare_verify(self, tracking_code):
        logging.debug("Prepare verify method")
        self._set_tracking_code(tracking_code)
        self._set_bank_record()
        self.prepare_amount()

    def verify(self, tracking_code):
        logging.debug("Verify method")
        self.prepare_verify(tracking_code)
        
        data= self.get_verify_data()
        client= self._get_client()
        verify_result= client.service.bpVerifyRequest(**data)
        
        if verify_result=="0":
            self._settle_transaction()
        else:
            verify_result= client.service.bpInquiryRequest(**data)
            if verify_result=="0":
                self._settle_transaction()
            else:
                logging.debug("Transaction not verified. Making reversal request.")
                reversal_result= client.service.bpReversalRequest(**data)

                if reversal_result!="0":
                    logging.debug("Reversal request was not successfull")

                self._set_payment_status(PaymentStatus.CANCEL_BY_USER)
                logging.debug("Mellat gateway unapproved the payment")

        
    # WHATS?
    def _set_payment_status(self, payment_status):
        if payment_status==PaymentStatus.RETURN_FROM_BANK and self._bank.status!=PaymentStatus.REDIRECT_TO_BANK:
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

    

    
    
