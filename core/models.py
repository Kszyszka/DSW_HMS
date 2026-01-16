from django.db import models
from django.contrib.auth.models import User
from datetime import timedelta
from django.utils import timezone
from decimal import Decimal

# --- Modele Użytkowników ---

class GuestProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='guest_profile', verbose_name="Użytkownik")
    phone_number = models.CharField(max_length=15, blank=True, null=True, verbose_name="Numer telefonu")

    class Meta:
        verbose_name = "Gość"
        verbose_name_plural = "Goście"

    def __str__(self):
        return f"{self.user.username} (Gość)"

class EmployeeProfile(models.Model):
    ROLE_CHOICES = (
        ('receptionist', 'Recepcjonista'),
        ('manager', 'Kierownik'),
        ('maid', 'Pokojówka'),
        ('technician', 'Pracownik techniczny'),
    )
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='employee_profile', verbose_name="Użytkownik")
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='receptionist', verbose_name="Stanowisko")
    phone_number = models.CharField(max_length=15, blank=True, null=True, verbose_name="Numer telefonu")

    class Meta:
        verbose_name = "Pracownik"
        verbose_name_plural = "Pracownicy"

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
    
    number = models.CharField(max_length=10, unique=True, verbose_name="Numer pokoju")
    capacity = models.IntegerField(default=2, verbose_name="Pojemność")
    price = models.DecimalField(max_digits=10, decimal_places=2, help_text="Cena bazowa za noc", verbose_name="Cena")
    room_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default='double', verbose_name="Typ pokoju")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='available', verbose_name="Status")
    notes = models.TextField(blank=True, default='', verbose_name="Uwagi")
    
    class Meta:
        verbose_name = "Pokój"
        verbose_name_plural = "Pokoje"
    
    def __str__(self):
        return f"Pokój {self.number} ({self.get_room_type_display()})"

class Season(models.Model):
    name = models.CharField(max_length=100, verbose_name="Nazwa sezonu")
    start_date = models.DateField(verbose_name="Data początkowa")
    end_date = models.DateField(verbose_name="Data końcowa")

    class Meta:
        verbose_name = "Sezon"
        verbose_name_plural = "Sezony"

    def __str__(self):
        return f"{self.name} ({self.start_date} - {self.end_date})"

class SeasonPrice(models.Model):
    season = models.ForeignKey(Season, on_delete=models.CASCADE, related_name='prices', verbose_name="Sezon")
    room_type = models.CharField(max_length=20, choices=Room.TYPE_CHOICES, verbose_name="Typ pokoju")
    price_multiplier = models.DecimalField(max_digits=4, decimal_places=2, default=1.0, help_text="Mnożnik ceny bazowej (np. 1.5 dla +50%)", verbose_name="Mnożnik ceny")
    
    class Meta:
        verbose_name = "Cena sezonowa"
        verbose_name_plural = "Ceny sezonowe"
    
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

    guest = models.ForeignKey(GuestProfile, on_delete=models.CASCADE, related_name='reservations', verbose_name="Gość")
    room = models.ForeignKey(Room, on_delete=models.CASCADE, related_name='reservations', verbose_name="Pokój")
    check_in = models.DateField(verbose_name="Data zameldowania")
    check_out = models.DateField(verbose_name="Data wymeldowania")
    number_of_guests = models.IntegerField(default=1, verbose_name="Liczba gości")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', verbose_name="Status")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Utworzono")
    total_price = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True, verbose_name="Cena całkowita")
    reservation_pin = models.CharField(max_length=6, blank=True, null=True, verbose_name="PIN")
    payment_method = models.CharField(max_length=10, choices=PAYMENT_CHOICES, default='cash', verbose_name="Metoda płatności")
    notes = models.TextField(blank=True, null=True, help_text="Notatki do rezerwacji (np. uszkodzenia, dodatkowe opłaty)", verbose_name="Notatki")
    
    class Meta:
        verbose_name = "Rezerwacja"
        verbose_name_plural = "Rezerwacje"
    
    def __str__(self):
        return f"Rezerwacja {self.id} - {self.guest.user.username}"
        
    @property
    def is_paid(self):
        return self.status in ['confirmed', 'checked_in', 'completed']

    @property
    def average_daily_rate(self):
        """Zwraca średnią cenę za noc w tej rezerwacji (uwzględniając sezony)"""
        if self.total_price and self.check_in and self.check_out:
            nights = (self.check_out - self.check_in).days
            if nights > 0:
                return round(self.total_price / nights, 2)
        return self.room.price

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
    reservation = models.ForeignKey(Reservation, on_delete=models.CASCADE, related_name='payments', verbose_name="Rezerwacja")
    amount = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Kwota")
    payment_date = models.DateField(default=timezone.now, verbose_name="Data płatności")
    payment_method = models.CharField(max_length=10, choices=PAYMENT_METHODS, default='cash', verbose_name="Metoda płatności")
    payment_status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='completed', verbose_name="Status płatności")
    transaction_id = models.CharField(max_length=100, blank=True, null=True, verbose_name="ID transakcji")

    class Meta:
        verbose_name = "Płatność"
        verbose_name_plural = "Płatności"

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
    
    total_price = Decimal('0.00')
    current_date = start_date
    
    print(f"DEBUG: Obliczanie ceny dla pokoju {room.number} ({room.get_room_type_display()}) od {start_date} do {end_date}")

    while current_date < end_date:
        day_price = room.price
        # Sprawdzamy sezony dla konkretnego dnia
        active_seasons = Season.objects.filter(start_date__lte=current_date, end_date__gte=current_date)
        
        multiplier = Decimal('1.0')
        for season in active_seasons:
            season_price = SeasonPrice.objects.filter(season=season, room_type=room.room_type).first()
            if season_price:
                if season_price.price_multiplier > multiplier:
                    multiplier = season_price.price_multiplier
                    print(f"DEBUG: Dzień {current_date} wpada w sezon '{season.name}'. Mnożnik: {multiplier}")
            else:
                print(f"DEBUG: Dzień {current_date} jest w sezonie '{season.name}', ale brak zdefiniowanej ceny (SeasonPrice) dla typu {room.room_type}.")
        
        total_price += day_price * multiplier
        current_date += timedelta(days=1)
        
    return round(total_price, 2)