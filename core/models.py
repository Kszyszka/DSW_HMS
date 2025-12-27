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
        ('reserved', 'Zarezerwowany'),
        ('maintenance', 'W konserwacji'),
        ('to_clean', 'Do sprzątania'),
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
    pin = models.CharField(max_length=8, blank=True)
    room_type = models.CharField(max_length=30, choices=ROOM_TYPE_CHOICES)

    def set_new_pin(self, length=6):
        """Generate and set a new numeric PIN for this room"""
        import secrets
        digits = '0123456789'
        new_pin = ''.join(secrets.choice(digits) for _ in range(length))
        self.pin = new_pin
        self.save(update_fields=['pin'])
        return new_pin
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
    number_of_guests = models.IntegerField(default=1, validators=[MinValueValidator(1)])
    # email rezerwacji może być odczytywany z guest.email
    check_in_date = models.DateField()
    check_out_date = models.DateField()
    price_total = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='pending')
    pin_assigned_at = models.DateTimeField(null=True, blank=True)
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


class RoomIssue(models.Model):
    """Proste zgłoszenie usterki powiązane z pokojem"""
    room = models.ForeignKey(Room, on_delete=models.CASCADE, related_name='issues')
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    reported_by = models.ForeignKey(Guest, on_delete=models.SET_NULL, null=True, blank=True)
    is_resolved = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Zgłoszona Usterka'
        verbose_name_plural = 'Zgłoszone Usterki'
        ordering = ['-created_at']

    def __str__(self):
        return f"Usterka #{self.id} - Pokój {self.room.number} - {self.title}"


class Season(models.Model):
    name = models.CharField(max_length=200)
    identifier = models.CharField(max_length=50, unique=True)
    start_date = models.DateField()
    end_date = models.DateField()
    description = models.TextField(blank=True)
    priority = models.IntegerField(default=0, help_text='Wyższa wartość ma pierwszeństwo przy nakładających się sezonach')
    apply_to_existing = models.BooleanField(default=False, help_text='Jeśli zaznaczone, po zapisie zastosuj ceny do przyszłych rezerwacji (pending/confirmed)')
    created_by = models.ForeignKey('Employee', null=True, blank=True, on_delete=models.SET_NULL, related_name='seasons_created')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Sezon / Cennik'
        verbose_name_plural = 'Sezony / Cenniki'
        ordering = ['-priority', '-start_date']

    def __str__(self):
        return f"{self.name} ({self.start_date} → {self.end_date})"

    def overlaps(self, other):
        return not (self.end_date < other.start_date or self.start_date > other.end_date)

    def apply_to_future_reservations(self):
        """Zastosuj ceny dla rezerwacji w przyszłości (status pending lub confirmed)"""
        from django.utils import timezone
        today = date.today()
        reservations = Reservation.objects.filter(
            status__in=['pending', 'confirmed'],
            check_out_date__gte=today
        )
        for reservation in reservations:
            # check if reservation dates intersect this season
            if reservation.check_in_date <= self.end_date and reservation.check_out_date >= self.start_date:
                # recalculate price_total using season-aware pricing
                reservation.price_total = compute_reservation_price(reservation)
                reservation.save()


class SeasonPrice(models.Model):
    """Cena lub modyfikator przypisany do sezonu (opcjonalnie do konkretnego pokoju)"""
    season = models.ForeignKey(Season, on_delete=models.CASCADE, related_name='prices')
    room = models.ForeignKey(Room, null=True, blank=True, on_delete=models.CASCADE, related_name='season_prices')
    price_override = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    price_modifier_percent = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, help_text='Procentowa zmiana ceny bazowej (może być ujemna)')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Cena w sezonie'
        verbose_name_plural = 'Ceny w sezonach'
        ordering = ['-season__priority', 'room__number']

    def __str__(self):
        target = f'pokój {self.room.number}' if self.room else 'wszystkie pokoje'
        if self.price_override is not None:
            return f"{self.season.name}: {target} -> {self.price_override} PLN"
        if self.price_modifier_percent is not None:
            sign = '+' if self.price_modifier_percent >= 0 else ''
            return f"{self.season.name}: {target} -> {sign}{self.price_modifier_percent}%"
        return f"{self.season.name}: {target} -> bez zmian"


# Helper: compute reservation price by day with season prices override/modify
from datetime import timedelta

def compute_reservation_price(reservation):
    total = 0
    night = reservation.check_in_date
    while night < reservation.check_out_date:
        base = reservation.room.price
        # find season prices applicable
        season_prices = SeasonPrice.objects.filter(
            season__start_date__lte=night,
            season__end_date__gte=night,
        ).filter(models.Q(room=reservation.room) | models.Q(room__isnull=True)).order_by('-season__priority', '-season__created_at')
        if season_prices.exists():
            sp = season_prices.first()
            if sp.price_override is not None:
                nightly = sp.price_override
            elif sp.price_modifier_percent is not None:
                nightly = base * (1 + (sp.price_modifier_percent or 0) / 100)
            else:
                nightly = base
        else:
            nightly = base
        total += nightly
        night += timedelta(days=1)
    return round(total, 2)


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
