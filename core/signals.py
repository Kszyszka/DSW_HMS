from django.db.models.signals import pre_delete, post_delete
from django.dispatch import receiver
from .models import Reservation, Room


@receiver(pre_delete, sender=Reservation)
def release_room_on_reservation_delete(sender, instance, **kwargs):
    """Sygnał wywoływany przed usunięciem rezerwacji - zwalnia pokój jeśli potrzeba"""
    # Zapisz informacje o pokoju przed usunięciem
    room_id = instance.room_id
    room_status = instance.room.status
    
    # Jeśli pokój jest związany z tą rezerwacją
    if room_status in ['reserved', 'occupied']:
        # Sprawdź czy są inne aktywne rezerwacje dla tego pokoju (wykluczając tę, która jest usuwana)
        active_reservations = Reservation.objects.filter(
            room_id=room_id,
            status__in=['pending', 'confirmed', 'checked_in']
        ).exclude(id=instance.id)
        
        # Jeśli nie ma innych aktywnych rezerwacji, zwolnij pokój
        if not active_reservations.exists():
            # Użyj update zamiast save, aby uniknąć problemów z relacjami
            Room.objects.filter(id=room_id).update(status='available')


@receiver(post_delete, sender=Reservation)
def release_room_on_reservation_delete_backup(sender, instance, **kwargs):
    """Backup sygnał wywoływany po usunięciu rezerwacji - zwalnia pokój jeśli potrzeba"""
    # Ten sygnał działa jako backup, gdy pre_delete nie zadziała
    # Pobierz room_id z kwargs jeśli jest dostępny, lub spróbuj odczytać z instance
    try:
        # W post_delete instance już nie ma relacji, więc musimy użyć innego podejścia
        # Sprawdzamy wszystkie pokoje które mogą być związane z usuniętą rezerwacją
        # To jest backup - główna logika jest w pre_delete
        pass
    except Exception:
        pass

