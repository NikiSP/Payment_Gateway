from django.contrib import admin

# Register your models here.
from payment.models import Game, Transaction
from payment.models.banks import Bank

admin.site.register(Game)
admin.site.register(Transaction)
admin.site.register(Bank)