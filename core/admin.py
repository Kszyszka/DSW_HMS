from django.contrib import admin
from .models import GuestProfile, Room, Reservation, EmployeeProfile, Season, SeasonPrice, Payment

@admin.register(GuestProfile)
class GuestProfileAdmin(admin.ModelAdmin):
    list_display = ('get_full_name', 'get_email', 'phone_number')
    search_fields = ('user__first_name', 'user__last_name', 'user__email', 'phone_number')

    def get_full_name(self, obj):
        return f"{obj.user.first_name} {obj.user.last_name}"
    get_full_name.short_description = 'Imię i Nazwisko'

    def get_email(self, obj):
        return obj.user.email
    get_email.short_description = 'Email'

@admin.register(Room)
class RoomAdmin(admin.ModelAdmin):
    list_display = ('number', 'room_type', 'status', 'price', 'capacity')
    list_filter = ('status', 'room_type')
    list_editable = ('status',)
    search_fields = ('number',)
    fieldsets = (
        ('Informacje podstawowe', {
            'fields': ('number', 'room_type', 'capacity', 'price')
        }),
        ('Status', {
            'fields': ('status', 'notes') 
        }),
    )

@admin.register(Reservation)
class ReservationAdmin(admin.ModelAdmin):
    list_display = ('id', 'guest', 'room', 'check_in', 'check_out', 'status', 'total_price', 'created_at')
    list_filter = ('status', 'check_in', 'check_out', 'created_at')
    search_fields = ('guest__user__last_name', 'guest__user__email', 'room__number')
    readonly_fields = ('created_at',)
    date_hierarchy = 'check_in'
    fieldsets = (
        ('Rezerwacja', {
            'fields': ('guest', 'room', 'check_in', 'check_out', 'status', 'notes')
        }),
        ('Płatność', {
            'fields': ('total_price',)
        }),
        ('Daty', {
            'fields': ('created_at',)
        }),
    )
    
    def delete_queryset(self, request, queryset):
        """Przy masowym usuwaniu rezerwacji - logika zwalniania pokoi"""
        rooms_to_release = {}

        for reservation in queryset:
            room = reservation.room
            if room.status in ['occupied']:
                active = Reservation.objects.filter(
                     room=room,
                     status__in=['pending', 'confirmed', 'checked_in']
                ).exclude(id=reservation.id)

                if not active.exists():
                    rooms_to_release[room.id] = room

        queryset.delete()

        for room_id, room in rooms_to_release.items():
            remaining = Reservation.objects.filter(
                room_id=room_id,
                status__in=['pending', 'confirmed', 'checked_in']
            )
            if not remaining.exists():
                Room.objects.filter(id=room_id).update(status='available')

@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ('reservation', 'amount', 'payment_date', 'payment_method', 'payment_status')
    list_filter = ('payment_date', 'payment_method', 'payment_status')


class SeasonPriceInline(admin.TabularInline):
    model = SeasonPrice
    extra = 1

@admin.register(Season)
class SeasonAdmin(admin.ModelAdmin):
    list_display = ('name', 'start_date', 'end_date')
    list_filter = ('start_date', 'end_date')
    search_fields = ('name',)
    inlines = (SeasonPriceInline,)

@admin.register(SeasonPrice)
class SeasonPriceAdmin(admin.ModelAdmin):
    list_display = ('season', 'room_type', 'price_multiplier')
    list_filter = ('season', 'room_type')

@admin.register(EmployeeProfile)
class EmployeeProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'role', 'phone_number')
    list_filter = ('role',)
    search_fields = ('user__username', 'user__last_name')

admin.site.site_header = "Panel Administracyjny Hotelu XYZ"
admin.site.site_title = "Hotel XYZ Admin"
admin.site.index_title = "Witamy w panelu zarządzania"