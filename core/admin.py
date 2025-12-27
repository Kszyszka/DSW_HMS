from django.contrib import admin
from .models import Guest, Room, Reservation, Payment, Employee


@admin.register(Guest)
class GuestAdmin(admin.ModelAdmin):
    list_display = ('name', 'surname', 'email', 'phone', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('name', 'surname', 'email', 'phone')
    readonly_fields = ('created_at', 'updated_at')
    fieldsets = (
        ('Informacje podstawowe', {
            'fields': ('user', 'name', 'surname', 'email', 'phone')
        }),
        ('Daty', {
            'fields': ('created_at', 'updated_at')
        }),
    )


@admin.register(Room)
class RoomAdmin(admin.ModelAdmin):
    list_display = ('number', 'room_type', 'status', 'price', 'capacity', 'created_at')
    list_filter = ('status', 'room_type', 'created_at')
    search_fields = ('number', 'notes')
    readonly_fields = ('created_at', 'updated_at')
    fieldsets = (
        ('Informacje podstawowe', {
            'fields': ('number', 'room_type', 'capacity', 'price')
        }),
        ('Status', {
            'fields': ('status', 'pin', 'notes')
        }),
        ('Daty', {
            'fields': ('created_at', 'updated_at')
        }),
    )


@admin.register(Reservation)
class ReservationAdmin(admin.ModelAdmin):
    list_display = ('id', 'guest', 'room', 'check_in_date', 'check_out_date', 'status', 'price_total', 'created_at')
    list_filter = ('status', 'check_in_date', 'check_out_date', 'created_at')
    search_fields = ('guest__name', 'guest__surname', 'guest__email', 'room__number')
    readonly_fields = ('created_at', 'updated_at')
    date_hierarchy = 'check_in_date'
    fieldsets = (
        ('Rezerwacja', {
            'fields': ('guest', 'room', 'check_in_date', 'check_out_date', 'status')
        }),
        ('Płatność', {
            'fields': ('price_total',)
        }),
        ('Dodatkowe', {
            'fields': ('notes',)
        }),
        ('Daty', {
            'fields': ('created_at', 'updated_at')
        }),
    )
    
    def delete_model(self, request, obj):
        """Przy usuwaniu rezerwacji z admina - sygnał pre_delete automatycznie zwolni pokój"""
        # Sygnał pre_delete automatycznie obsłuży zwolnienie pokoju
        super().delete_model(request, obj)
    
    def delete_queryset(self, request, queryset):
        """Przy masowym usuwaniu rezerwacji - zwolnij pokoje przed usunięciem"""
        # Przed usunięciem zwolnij pokoje dla każdej rezerwacji
        rooms_to_release = {}
        
        for reservation in queryset:
            room = reservation.room
            room_id = room.id
            
            # Jeśli pokój jest związany z rezerwacją
            if room.status in ['reserved', 'occupied']:
                # Sprawdź czy są inne aktywne rezerwacje dla tego pokoju
                active_reservations = Reservation.objects.filter(
                    room=room,
                    status__in=['pending', 'confirmed', 'checked_in']
                ).exclude(id=reservation.id)
                
                # Jeśli nie ma innych aktywnych rezerwacji, oznacz pokój do zwolnienia
                if not active_reservations.exists():
                    rooms_to_release[room_id] = room
        
        # Usuń rezerwacje (sygnał pre_delete również zadziała)
        for obj in queryset:
            obj.delete()
        
        # Zwolnij pokoje po usunięciu (backup)
        for room_id, room in rooms_to_release.items():
            # Sprawdź jeszcze raz czy nie ma aktywnych rezerwacji
            remaining_reservations = Reservation.objects.filter(
                room_id=room_id,
                status__in=['pending', 'confirmed', 'checked_in']
            )
            if not remaining_reservations.exists():
                Room.objects.filter(id=room_id).update(status='available')


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ('id', 'reservation', 'amount', 'payment_date', 'payment_method', 'payment_status', 'created_at')
    list_filter = ('payment_status', 'payment_method', 'payment_date', 'created_at')
    search_fields = ('reservation__guest__name', 'reservation__guest__surname', 'transaction_id')
    readonly_fields = ('created_at', 'updated_at')
    date_hierarchy = 'payment_date'
    fieldsets = (
        ('Płatność', {
            'fields': ('reservation', 'amount', 'payment_date', 'payment_method', 'payment_status')
        }),
        ('Transakcja', {
            'fields': ('transaction_id',)
        }),
        ('Daty', {
            'fields': ('created_at', 'updated_at')
        }),
    )


@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):
    list_display = ('user', 'role', 'phone', 'is_active', 'hire_date')
    list_filter = ('role', 'is_active', 'hire_date')
    search_fields = ('user__username', 'user__first_name', 'user__last_name', 'user__email', 'phone')
    readonly_fields = ('created_at', 'updated_at', 'hire_date')
    fieldsets = (
        ('Użytkownik', {
            'fields': ('user',)
        }),
        ('Informacje pracownika', {
            'fields': ('role', 'phone', 'is_active')
        }),
        ('Daty', {
            'fields': ('hire_date', 'created_at', 'updated_at')
        }),
    )
