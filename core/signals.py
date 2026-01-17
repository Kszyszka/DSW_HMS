from django.db.models.signals import pre_delete
from django.dispatch import receiver
from .models import Reservation, Room


@receiver(pre_delete, sender=Reservation)
def release_room_on_reservation_delete(sender, instance, **kwargs):
    """Sygnał wywoływany przed usunięciem rezerwacji - zwalnia pokój jeśli potrzeba"""
    room_id = instance.room_id
    room_status = instance.room.status

    if room_status in ['reserved', 'occupied']:
        active_reservations = Reservation.objects.filter(
            room_id=room_id,
            status__in=['pending', 'confirmed', 'checked_in']
        ).exclude(id=instance.id)

        if not active_reservations.exists():
            Room.objects.filter(id=room_id).update(status='available')
