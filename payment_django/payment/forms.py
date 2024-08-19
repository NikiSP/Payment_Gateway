from django import forms


class PaymentSampleForm(forms.Form):
    amount = forms.IntegerField(label="Amount", initial=100000)
    mobile_number = forms.CharField(label="Mobile", max_length=13, initial="+989112223344")
    game_id = forms.CharField(label="Game ID", max_length=20, initial="abcd")
