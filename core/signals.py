from django.db.models.signals import pre_delete
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
