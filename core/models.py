from django.db import models

# Create your models here.
class Guest(models.Model):
    # Dla niezarejestrowanych gości
    name = models.CharField(max_length=100)
    surname = models.CharField(max_length=100)
    email = models.EmailField()
    phone = models.CharField(max_length=15)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
class Room(models.Model):
    number = models.IntegerField() # dodatkowo poza domyślnym id dla rozróżnienia w przypadku aktualizacji lub dodawania pokojów
    status = models.CharField(max_length=30)
    notes = models.TextField()
    pin = models.CharField(max_length=4)
    room_type = models.CharField(max_length=30)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

class Reservation(models.Model):
    # ID istnieje domyślnie, nie trzeba go definiować
    guest = models.ForeignKey(Guest, on_delete=models.CASCADE)
    room = models.ForeignKey(Room, on_delete=models.CASCADE)
    # email rezerwacji może być odczytywany z guest.email
    check_in_date = models.DateField()
    check_out_date = models.DateField()
    price_total = models.DecimalField(max_digits=10, decimal_places=2)
    notes = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

class Payment(models.Model):
    reservation = models.ForeignKey(Reservation, on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    payment_date = models.DateField()
    payment_method = models.CharField(max_length=30)
    payment_status = models.CharField(max_length=30)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
