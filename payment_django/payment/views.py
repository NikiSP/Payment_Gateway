from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse

from .models import Game, Transaction
from .forms import TransactionForm 

# Create your views here.
def process_payment(request):
    if request.method == 'POST':
        
        game_id= request.POST.get('game_id')
        amount= request.POST.get('amount')
        
        game= get_object_or_404(Game, game_id= game_id)
        form= TransactionForm(request.POST, initial={'game': game, 'transaction_id': '', 'status': ''})
        
        if form.is_valid():
            transaction= form.save(commit= False)
            
            #TODO
            transaction.transaction_id= ''
            transaction.status= '' 
            
            transaction.save()
            
            return JsonResponse({'status': transaction.status, 'transaction_id': transaction.transaction_id})
        else:
            return JsonResponse({'errors': form.errors}, status=400)
        
        
        return JsonResponse({'status': status, 'transaction_id': transaction_id})