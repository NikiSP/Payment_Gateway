from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse

from .models import Game, Transaction
from .forms import TransactionForm 

# Create your views here.