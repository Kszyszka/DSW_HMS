from django.db import models
from django.contrib.auth.models import User
from datetime import timedelta
from django.utils import timezone

# --- Modele Użytkowników ---

class GuestProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='guest_profile')
    phone_number = models.CharField(max_length=15, blank=True, null=True)

    def __str__(self):
        return f"{self.user.username} (Gość)"

class EmployeeProfile(models.Model):
    ROLE_CHOICES = (
        ('receptionist', 'Recepcjonista'),
        ('manager', 'Kierownik'),
        ('maid', 'Pokojówka'),
        ('technician', 'Pracownik techniczny'),
    )
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='employee_profile')
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='receptionist')
    phone_number = models.CharField(max_length=15, blank=True, null=True)

    def __str__(self):
        return f"{self.user.username} ({self.get_role_display()})"

# --- Pokoje i Sezony ---

class Room(models.Model):
    TYPE_CHOICES = (
        ('single', 'Jednoosobowy'),
        ('double', 'Dwuosobowy'),
        ('suite', 'Apartament'),
    )
    STATUS_CHOICES = (
        ('available', 'Wolny'),
        ('occupied', 'Zajęty'),
        ('dirty', 'Do sprzątania'),
        ('maintenance', 'W naprawie'),
    )
    
    number = models.CharField(max_length=10, unique=True)
    capacity = models.IntegerField(default=2)
    price = models.DecimalField(max_digits=10, decimal_places=2, help_text="Cena bazowa za noc")
    room_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default='double')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='available')
    notes = models.TextField(blank=True, default='')
    
    def __str__(self):
        return f"Pokój {self.number} ({self.get_room_type_display()})"

class Season(models.Model):
    name = models.CharField(max_length=100)
    start_date = models.DateField()
    end_date = models.DateField()

    def __str__(self):
        return f"{self.name} ({self.start_date} - {self.end_date})"

class SeasonPrice(models.Model):
    season = models.ForeignKey(Season, on_delete=models.CASCADE, related_name='prices')
    room_type = models.CharField(max_length=20, choices=Room.TYPE_CHOICES)
    price_multiplier = models.DecimalField(max_digits=4, decimal_places=2, default=1.0, help_text="Mnożnik ceny bazowej (np. 1.5 dla +50%)")
    
    def __str__(self):
        return f"{self.season.name} - {self.get_room_type_display()} (x{self.price_multiplier})"

# --- Rezerwacje ---

class Reservation(models.Model):
    STATUS_CHOICES = (
        ('pending', 'Oczekująca'),
        ('confirmed', 'Potwierdzona'),
        ('checked_in', 'Zameldowany'),
        ('completed', 'Zakończona'),
        ('cancelled', 'Anulowana'),
    )
    PAYMENT_CHOICES = (
        ('cash', 'Gotówka'),
        ('online', 'Online'),
    )

    guest = models.ForeignKey(GuestProfile, on_delete=models.CASCADE, related_name='reservations')
    room = models.ForeignKey(Room, on_delete=models.CASCADE, related_name='reservations')
    check_in = models.DateField()
    check_out = models.DateField()
    number_of_guests = models.IntegerField(default=1)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)
    total_price = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    reservation_pin = models.CharField(max_length=6, blank=True, null=True)
    payment_method = models.CharField(max_length=10, choices=PAYMENT_CHOICES, default='cash')
    notes = models.TextField(blank=True, null=True, help_text="Notatki do rezerwacji (np. uszkodzenia, dodatkowe opłaty)")
    
    def __str__(self):
        return f"Rezerwacja {self.id} - {self.guest.user.username}"
        
    @property
    def is_paid(self):
        return self.status in ['confirmed', 'checked_in', 'completed']

class Payment(models.Model):
    PAYMENT_METHODS = (
        ('cash', 'Gotówka'),
        ('card', 'Karta'),
        ('transfer', 'Przelew'),
        ('online', 'Online'),
    )
    STATUS_CHOICES = (
        ('pending', 'Oczekująca'),
        ('completed', 'Zrealizowana'),
        ('failed', 'Nieudana'),
    )
    reservation = models.ForeignKey(Reservation, on_delete=models.CASCADE, related_name='payments')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    payment_date = models.DateField(default=timezone.now)
    payment_method = models.CharField(max_length=10, choices=PAYMENT_METHODS, default='cash')
    payment_status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='completed')
    transaction_id = models.CharField(max_length=100, blank=True, null=True)

    def __str__(self):
        return f"Płatność {self.id} ({self.amount} PLN)"

# --- Funkcja Obliczająca Cenę (Używana w views.py) ---

def compute_reservation_price(reservation):
    """
    Oblicza cenę rezerwacji, sprawdzając czy data pobytu wpada w zdefiniowane Sezony.
    """
    room = reservation.room
    start_date = reservation.check_in
    end_date = reservation.check_out
    
    total_price = 0
    current_date = start_date
    
    while current_date < end_date:
        day_price = room.price
        # Sprawdzamy sezony dla konkretnego dnia
        active_seasons = Season.objects.filter(start_date__lte=current_date, end_date__gte=current_date)
        
        multiplier = 1.0
        for season in active_seasons:
            season_price = SeasonPrice.objects.filter(season=season, room_type=room.room_type).first()
            if season_price:
                multiplier = max(multiplier, float(season_price.price_multiplier))
        
        total_price += float(day_price) * multiplier
        current_date += timedelta(days=1)
        
    return round(total_price, 2)