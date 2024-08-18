from django.db import models

# Create your models here.

class Game(models.Model):
    name= models.CharField(max_length= 100)
    game_id= models.CharField(max_length= 100, unique= True)

    def __str__(self):
        return self.name
    
class Transaction(models.Model):
    game= models.ForeignKey(Game, on_delete= models.CASCADE)
    transaction_id= models.CharField(max_length= 100, unique= True)
    amount= models.DecimalField(max_digits= 10, decimal_places= 2)
    timestamp= models.DateTimeField(auto_now_add= True)
    status= models.CharField(max_length= 50)
    
    def __str__(self):
        return self.transaction_id
    
    
    