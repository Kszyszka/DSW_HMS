from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator

# Create your models here.
class Guest(models.Model):
    # Dla niezarejestrowanych gości
    user = models.OneToOneField(User, on_delete=models.CASCADE, null=True, blank=True, related_name='guest_profile')
    name = models.CharField(max_length=100)
    surname = models.CharField(max_length=100)
    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=15)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Gość"
        verbose_name_plural = "Goście"
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.name} {self.surname} ({self.email})"
class Room(models.Model):
    STATUS_CHOICES = [
        ('available', 'Dostępny'),
        ('occupied', 'Zajęty'),
        ('maintenance', 'W konserwacji'),
        ('reserved', 'Zarezerwowany'),
    ]
    
    ROOM_TYPE_CHOICES = [
        ('single', 'Pojedynczy'),
        ('double', 'Podwójny'),
        ('suite', 'Apartament'),
        ('family', 'Rodzinny'),
    ]
    
    number = models.IntegerField(unique=True) # dodatkowo poza domyślnym id dla rozróżnienia w przypadku aktualizacji lub dodawania pokojów
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='available')
    notes = models.TextField(blank=True)
    pin = models.CharField(max_length=4, blank=True)
    room_type = models.CharField(max_length=30, choices=ROOM_TYPE_CHOICES)
    price = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    capacity = models.IntegerField(default=1, validators=[MinValueValidator(1)])
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Pokój"
        verbose_name_plural = "Pokoje"
        ordering = ['number']
    
    def __str__(self):
        return f"Pokój {self.number} ({self.get_room_type_display()})"

class Reservation(models.Model):
    """Model rezerwacji pokoju"""
    STATUS_CHOICES = [
        ('pending', 'Oczekująca'),
        ('confirmed', 'Potwierdzona'),
        ('checked_in', 'Zameldowana'),
        ('checked_out', 'Wymeldowana'),
        ('cancelled', 'Anulowana'),
    ]
    
    # ID istnieje domyślnie, nie trzeba go definiować
    guest = models.ForeignKey(Guest, on_delete=models.CASCADE, related_name='reservations')
    room = models.ForeignKey(Room, on_delete=models.CASCADE, related_name='reservations')
    # email rezerwacji może być odczytywany z guest.email
    check_in_date = models.DateField()
    check_out_date = models.DateField()
    price_total = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='pending')
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Rezerwacja"
        verbose_name_plural = "Rezerwacje"
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Rezerwacja #{self.id} - {self.guest} ({self.check_in_date} - {self.check_out_date})"
    
    def delete(self, *args, **kwargs):
        """Przy usuwaniu rezerwacji zwolnij pokój jeśli nie ma innych aktywnych rezerwacji"""
        room = self.room
        room_status = room.status
        reservation_id = self.id
        
        # Sprawdź czy są inne aktywne rezerwacje dla tego pokoju PRZED usunięciem
        active_reservations = Reservation.objects.filter(
            room=room,
            status__in=['pending', 'confirmed', 'checked_in']
        ).exclude(id=reservation_id)
        
        # Usuń rezerwację
        super().delete(*args, **kwargs)
        
        # Jeśli pokój był związany z tą rezerwacją i nie ma innych aktywnych rezerwacji, zwolnij go
        if room_status in ['reserved', 'occupied'] and not active_reservations.exists():
            # Odśwież pokój z bazy
            room.refresh_from_db()
            # Sprawdź jeszcze raz po usunięciu czy nie ma innych aktywnych rezerwacji
            remaining_reservations = Reservation.objects.filter(
                room=room,
                status__in=['pending', 'confirmed', 'checked_in']
            )
            if not remaining_reservations.exists() and room.status in ['reserved', 'occupied']:
                room.status = 'available'
                room.save(update_fields=['status'])

class Payment(models.Model):
    PAYMENT_METHOD_CHOICES = [
        ('cash', 'Gotówka'),
        ('card', 'Karta'),
        ('transfer', 'Przelew'),
        ('online', 'Online'),
    ]
    
    PAYMENT_STATUS_CHOICES = [
        ('pending', 'Oczekująca'),
        ('completed', 'Zrealizowana'),
        ('failed', 'Nieudana'),
        ('refunded', 'Zwrócona'),
    ]
    
    reservation = models.ForeignKey(Reservation, on_delete=models.CASCADE, related_name='payments')
    amount = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    payment_date = models.DateField()
    payment_method = models.CharField(max_length=30, choices=PAYMENT_METHOD_CHOICES)
    payment_status = models.CharField(max_length=30, choices=PAYMENT_STATUS_CHOICES, default='pending')
    transaction_id = models.CharField(max_length=100, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Płatność"
        verbose_name_plural = "Płatności"
        ordering = ['-payment_date']
    
    def __str__(self):
        return f"Płatność #{self.id} - {self.amount} PLN ({self.get_payment_status_display()})"


class Employee(models.Model):
    ROLE_CHOICES = [
        ('receptionist', 'Recepcjonista'),
        ('manager', 'Menedżer'),
        ('housekeeping', 'Pokojówka'),
        ('admin', 'Administrator'),
    ]
    
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='employee_profile')
    role = models.CharField(max_length=30, choices=ROLE_CHOICES, default='receptionist')
    phone = models.CharField(max_length=15, blank=True)
    hire_date = models.DateField(auto_now_add=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Pracownik"
        verbose_name_plural = "Pracownicy"
        ordering = ['-hire_date']
    
    def __str__(self):
        return f"{self.user.get_full_name() or self.user.username} ({self.get_role_display()})"
