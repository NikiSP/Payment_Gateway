from django.contrib import admin

# Register your models here.
from payment.models import Game, Transaction

admin.site.register(Game)
admin.site.register(Transaction)
