from django.forms import ModelForm
from .models import Game, Transaction

class TransactionForm(ModelForm):
    class Meta:
        model= Transaction
        fields= ['game', 'transaction_id', 'amount', 'status']
        
# class GameForm(ModelForm):
#     class Meta:
#         model= Game
#         fields= ['name', 'game_id']