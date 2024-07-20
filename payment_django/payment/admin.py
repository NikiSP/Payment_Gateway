from django.contrib import admin

# Register your models here.
from .models import Game, Transaction

admin.site.register(Game)
admin.site.register(Transaction)
