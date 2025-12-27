from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login, authenticate, logout
from django.contrib import messages
from django.db.models import Q, Sum
from datetime import date
from .models import Guest, Room, Reservation, Payment, Employee
from .decorators import employee_required, guest_required


def home(request):
    """Strona główna systemu"""
    if request.user.is_authenticated:
        # Superuser nie jest automatycznie przekierowywany - ma dostęp do wszystkiego
        if request.user.is_superuser:
            return render(request, 'core/home.html')
        elif hasattr(request.user, 'employee_profile'):
            return redirect('employee:dashboard')
        elif hasattr(request.user, 'guest_profile'):
            return redirect('guest:dashboard')
    return render(request, 'core/home.html')


def login_view(request):
    """Widok logowania"""
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            if hasattr(user, 'employee_profile'):
                return redirect('employee:dashboard')
            elif hasattr(user, 'guest_profile'):
                return redirect('guest:dashboard')
            return redirect('home')
        else:
            messages.error(request, 'Nieprawidłowa nazwa użytkownika lub hasło.')
    return render(request, 'core/login.html')


def logout_view(request):
    """Widok wylogowania"""
    logout(request)
    messages.success(request, 'Zostałeś pomyślnie wylogowany.')
    return redirect('home')


# ============ WIDOKI DLA GOŚCI ============

@login_required
@guest_required
def guest_dashboard(request):
    """Panel główny gościa"""
    # Dla superusera pokazujemy wszystkie rezerwacje
    if request.user.is_superuser:
        reservations = Reservation.objects.all().order_by('-created_at')[:5]
        upcoming_reservations = Reservation.objects.filter(
            check_in_date__gte=date.today(),
            status__in=['pending', 'confirmed']
        ).order_by('check_in_date')
        guest = None
    else:
        guest = request.user.guest_profile
        reservations = Reservation.objects.filter(guest=guest).order_by('-created_at')[:5]
        upcoming_reservations = Reservation.objects.filter(
            guest=guest,
            check_in_date__gte=date.today(),
            status__in=['pending', 'confirmed']
        ).order_by('check_in_date')
    
    context = {
        'guest': guest,
        'recent_reservations': reservations,
        'upcoming_reservations': upcoming_reservations,
        'is_superuser': request.user.is_superuser,
    }
    return render(request, 'guest/dashboard.html', context)


@login_required
@guest_required
def guest_reservations(request):
    """Lista rezerwacji gościa"""
    # Dla superusera pokazujemy wszystkie rezerwacje
    if request.user.is_superuser:
        reservations = Reservation.objects.all().order_by('-created_at')
        guest = None
    else:
        guest = request.user.guest_profile
        reservations = Reservation.objects.filter(guest=guest).order_by('-created_at')
    
    context = {
        'reservations': reservations,
        'is_superuser': request.user.is_superuser,
    }
    return render(request, 'guest/reservations.html', context)


@login_required
@guest_required
def guest_reservation_detail(request, reservation_id):
    """Szczegóły rezerwacji"""
    # Dla superusera nie sprawdzamy czy rezerwacja należy do gościa
    if request.user.is_superuser:
        reservation = get_object_or_404(Reservation, id=reservation_id)
    else:
        guest = request.user.guest_profile
        reservation = get_object_or_404(Reservation, id=reservation_id, guest=guest)
    payments = Payment.objects.filter(reservation=reservation)
    
    context = {
        'reservation': reservation,
        'payments': payments,
        'is_superuser': request.user.is_superuser,
    }
    return render(request, 'guest/reservation_detail.html', context)


@login_required
@guest_required
def guest_create_reservation(request):
    """Tworzenie nowej rezerwacji"""
    # Dla superusera nie pozwalamy tworzyć rezerwacji bez wyboru gościa
    if request.user.is_superuser:
        messages.info(request, 'Jako administrator użyj panelu pracownika do zarządzania rezerwacjami.')
        return redirect('employee:reservations')
    
    guest = request.user.guest_profile
    
    if request.method == 'POST':
        room_id = request.POST.get('room_id')
        check_in = request.POST.get('check_in_date')
        check_out = request.POST.get('check_out_date')
        notes = request.POST.get('notes', '')
        
        try:
            room = Room.objects.get(id=room_id)
            check_in_date = date.fromisoformat(check_in)
            check_out_date = date.fromisoformat(check_out)
            
            # Sprawdzenie dostępności pokoju
            conflicting_reservations = Reservation.objects.filter(
                room=room,
                status__in=['pending', 'confirmed', 'checked_in'],
                check_in_date__lt=check_out_date,
                check_out_date__gt=check_in_date
            )
            
            if conflicting_reservations.exists():
                messages.error(request, 'Pokój jest już zarezerwowany w wybranym terminie.')
                return redirect('guest:create_reservation')
            
            # Obliczenie ceny
            nights = (check_out_date - check_in_date).days
            price_total = room.price * nights
            
            reservation = Reservation.objects.create(
                guest=guest,
                room=room,
                check_in_date=check_in_date,
                check_out_date=check_out_date,
                price_total=price_total,
                notes=notes,
                status='pending'
            )
            
            messages.success(request, 'Rezerwacja została utworzona. Oczekuje na potwierdzenie.')
            return redirect('guest:reservation_detail', reservation_id=reservation.id)
            
        except Exception as e:
            messages.error(request, f'Błąd podczas tworzenia rezerwacji: {str(e)}')
    
    # Pobranie dostępnych pokoi
    available_rooms = Room.objects.filter(status='available')
    
    context = {
        'available_rooms': available_rooms,
    }
    return render(request, 'guest/create_reservation.html', context)


@login_required
@guest_required
def guest_profile(request):
    """Profil gościa"""
    # Dla superusera przekierowujemy do panelu admin
    if request.user.is_superuser:
        return redirect('/admin/')
    
    guest = request.user.guest_profile
    
    if request.method == 'POST':
        guest.name = request.POST.get('name', guest.name)
        guest.surname = request.POST.get('surname', guest.surname)
        guest.phone = request.POST.get('phone', guest.phone)
        guest.save()
        
        # Aktualizacja danych użytkownika
        request.user.first_name = guest.name
        request.user.last_name = guest.surname
        request.user.email = request.POST.get('email', request.user.email)
        request.user.save()
        
        messages.success(request, 'Profil został zaktualizowany.')
        return redirect('guest:profile')
    
    context = {
        'guest': guest,
    }
    return render(request, 'guest/profile.html', context)


# ============ WIDOKI DLA PRACOWNIKÓW ============

@login_required
@employee_required
def employee_dashboard(request):
    """Panel główny pracownika"""
    # Dla superusera tworzymy pseudo-profil pracownika
    if request.user.is_superuser:
        employee = type('Employee', (), {
            'user': request.user,
            'role': 'admin',
            'get_role_display': lambda: 'Administrator'
        })()
    else:
        employee = request.user.employee_profile
    
    # Statystyki
    today = date.today()
    total_rooms = Room.objects.count()
    available_rooms = Room.objects.filter(status='available').count()
    occupied_rooms = Room.objects.filter(status='occupied').count()
    
    today_check_ins = Reservation.objects.filter(
        check_in_date=today,
        status__in=['confirmed', 'checked_in']
    ).count()
    
    today_check_outs = Reservation.objects.filter(
        check_out_date=today,
        status='checked_in'
    ).count()
    
    pending_reservations = Reservation.objects.filter(status='pending').count()
    
    recent_reservations = Reservation.objects.all().order_by('-created_at')[:10]
    
    context = {
        'employee': employee,
        'total_rooms': total_rooms,
        'available_rooms': available_rooms,
        'occupied_rooms': occupied_rooms,
        'today_check_ins': today_check_ins,
        'today_check_outs': today_check_outs,
        'pending_reservations': pending_reservations,
        'recent_reservations': recent_reservations,
    }
    return render(request, 'employee/dashboard.html', context)


@login_required
@employee_required
def employee_rooms(request):
    """Zarządzanie pokojami"""
    rooms = Room.objects.all().order_by('number')
    
    if request.method == 'POST':
        action = request.POST.get('action')
        room_id = request.POST.get('room_id')
        
        try:
            room = Room.objects.get(id=room_id)
            
            if action == 'update_status':
                room.status = request.POST.get('status')
                room.save()
                messages.success(request, f'Status pokoju {room.number} został zaktualizowany.')
            elif action == 'update':
                room.number = request.POST.get('number', room.number)
                room.room_type = request.POST.get('room_type', room.room_type)
                room.price = request.POST.get('price', room.price)
                room.capacity = request.POST.get('capacity', room.capacity)
                room.notes = request.POST.get('notes', room.notes)
                room.save()
                messages.success(request, f'Pokój {room.number} został zaktualizowany.')
            
        except Exception as e:
            messages.error(request, f'Błąd: {str(e)}')
        
        return redirect('employee:rooms')
    
    context = {
        'rooms': rooms,
    }
    return render(request, 'employee/rooms.html', context)


@login_required
@employee_required
def employee_room_create(request):
    """Tworzenie nowego pokoju"""
    if request.method == 'POST':
        try:
            Room.objects.create(
                number=request.POST.get('number'),
                room_type=request.POST.get('room_type'),
                price=request.POST.get('price'),
                capacity=request.POST.get('capacity'),
                status=request.POST.get('status', 'available'),
                notes=request.POST.get('notes', ''),
            )
            messages.success(request, 'Pokój został utworzony.')
            return redirect('employee:rooms')
        except Exception as e:
            messages.error(request, f'Błąd podczas tworzenia pokoju: {str(e)}')
    
    return render(request, 'employee/room_create.html')


@login_required
@employee_required
def employee_reservations(request):
    """Zarządzanie rezerwacjami"""
    reservations = Reservation.objects.all().order_by('-created_at')
    
    # Filtrowanie
    status_filter = request.GET.get('status')
    if status_filter:
        reservations = reservations.filter(status=status_filter)
    
    if request.method == 'POST':
        action = request.POST.get('action')
        reservation_id = request.POST.get('reservation_id')
        
        try:
            reservation = Reservation.objects.get(id=reservation_id)
            
            if action == 'confirm':
                reservation.status = 'confirmed'
                reservation.room.status = 'reserved'
                reservation.room.save()
                reservation.save()
                messages.success(request, 'Rezerwacja została potwierdzona.')
            elif action == 'cancel':
                reservation.status = 'cancelled'
                # Sprawdź czy pokój jest związany z tą rezerwacją i zwolnij go
                if reservation.room.status in ['reserved', 'occupied']:
                    # Sprawdź czy są inne aktywne rezerwacje dla tego pokoju
                    active_reservations = Reservation.objects.filter(
                        room=reservation.room,
                        status__in=['pending', 'confirmed', 'checked_in']
                    ).exclude(id=reservation.id)
                    
                    if not active_reservations.exists():
                        # Brak innych aktywnych rezerwacji - zwolnij pokój
                        reservation.room.status = 'available'
                        reservation.room.save()
                reservation.save()
                messages.success(request, 'Rezerwacja została anulowana.')
            elif action == 'check_in':
                # Weryfikacja płatności przed zameldowaniem
                payments = Payment.objects.filter(reservation=reservation)
                total_paid = payments.filter(payment_status='completed').aggregate(Sum('amount'))['amount__sum'] or 0
                
                if total_paid < reservation.price_total:
                    remaining = reservation.price_total - total_paid
                    messages.error(
                        request, 
                        f'Rezerwacja nie została w pełni opłacona. Brakuje {remaining:.2f} PLN. '
                        f'Zapłacono: {total_paid:.2f} PLN z {reservation.price_total:.2f} PLN.'
                    )
                    return redirect('employee:reservations')
                
                reservation.status = 'checked_in'
                reservation.room.status = 'occupied'
                reservation.room.save()
                reservation.save()
                messages.success(request, 'Gość został zameldowany.')
            elif action == 'check_out':
                reservation.status = 'checked_out'
                reservation.room.status = 'available'
                reservation.room.save()
                reservation.save()
                messages.success(request, 'Gość został wymeldowany.')
            
        except Exception as e:
            messages.error(request, f'Błąd: {str(e)}')
        
        return redirect('employee:reservations')
    
    # Obliczanie statusu płatności dla każdej rezerwacji
    reservations_with_payment = []
    for reservation in reservations:
        payments = Payment.objects.filter(reservation=reservation)
        total_paid = payments.filter(payment_status='completed').aggregate(Sum('amount'))['amount__sum'] or 0
        remaining = reservation.price_total - total_paid
        reservations_with_payment.append({
            'reservation': reservation,
            'total_paid': total_paid,
            'remaining': remaining,
            'is_fully_paid': remaining <= 0
        })
    
    context = {
        'reservations_data': reservations_with_payment,
        'status_filter': status_filter,
    }
    return render(request, 'employee/reservations.html', context)


@login_required
@employee_required
def employee_reservation_detail(request, reservation_id):
    """Szczegóły rezerwacji dla pracownika"""
    reservation = get_object_or_404(Reservation, id=reservation_id)
    payments = Payment.objects.filter(reservation=reservation)
    total_paid = payments.filter(payment_status='completed').aggregate(Sum('amount'))['amount__sum'] or 0
    
    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'add_payment':
            try:
                Payment.objects.create(
                    reservation=reservation,
                    amount=request.POST.get('amount'),
                    payment_date=request.POST.get('payment_date', date.today()),
                    payment_method=request.POST.get('payment_method'),
                    payment_status=request.POST.get('payment_status', 'completed'),
                    transaction_id=request.POST.get('transaction_id', ''),
                )
                messages.success(request, 'Płatność została dodana.')
                return redirect('employee:reservation_detail', reservation_id=reservation.id)
            except Exception as e:
                messages.error(request, f'Błąd: {str(e)}')
        elif action == 'confirm':
            try:
                reservation.status = 'confirmed'
                reservation.room.status = 'reserved'
                reservation.room.save()
                reservation.save()
                messages.success(request, 'Rezerwacja została potwierdzona.')
                return redirect('employee:reservation_detail', reservation_id=reservation.id)
            except Exception as e:
                messages.error(request, f'Błąd: {str(e)}')
        elif action == 'cancel':
            try:
                reservation.status = 'cancelled'
                # Sprawdź czy pokój jest związany z tą rezerwacją i zwolnij go
                if reservation.room.status in ['reserved', 'occupied']:
                    # Sprawdź czy są inne aktywne rezerwacje dla tego pokoju
                    active_reservations = Reservation.objects.filter(
                        room=reservation.room,
                        status__in=['pending', 'confirmed', 'checked_in']
                    ).exclude(id=reservation.id)
                    
                    if not active_reservations.exists():
                        # Brak innych aktywnych rezerwacji - zwolnij pokój
                        reservation.room.status = 'available'
                        reservation.room.save()
                reservation.save()
                messages.success(request, 'Rezerwacja została anulowana.')
                return redirect('employee:reservation_detail', reservation_id=reservation.id)
            except Exception as e:
                messages.error(request, f'Błąd: {str(e)}')
        elif action == 'check_in':
            try:
                # Weryfikacja płatności przed zameldowaniem
                payments = Payment.objects.filter(reservation=reservation)
                total_paid = payments.filter(payment_status='completed').aggregate(Sum('amount'))['amount__sum'] or 0
                
                if total_paid < reservation.price_total:
                    remaining = reservation.price_total - total_paid
                    messages.error(
                        request, 
                        f'Rezerwacja nie została w pełni opłacona. Brakuje {remaining:.2f} PLN. '
                        f'Zapłacono: {total_paid:.2f} PLN z {reservation.price_total:.2f} PLN. '
                        f'Dodaj płatność przed zameldowaniem.'
                    )
                    return redirect('employee:reservation_detail', reservation_id=reservation.id)
                
                reservation.status = 'checked_in'
                reservation.room.status = 'occupied'
                reservation.room.save()
                reservation.save()
                messages.success(request, 'Gość został zameldowany.')
                return redirect('employee:reservation_detail', reservation_id=reservation.id)
            except Exception as e:
                messages.error(request, f'Błąd: {str(e)}')
        elif action == 'check_out':
            try:
                reservation.status = 'checked_out'
                reservation.room.status = 'available'
                reservation.room.save()
                reservation.save()
                messages.success(request, 'Gość został wymeldowany.')
                return redirect('employee:reservation_detail', reservation_id=reservation.id)
            except Exception as e:
                messages.error(request, f'Błąd: {str(e)}')
    
    context = {
        'reservation': reservation,
        'payments': payments,
        'total_paid': total_paid,
        'remaining': reservation.price_total - total_paid,
    }
    return render(request, 'employee/reservation_detail.html', context)


@login_required
@employee_required
def employee_guests(request):
    """Zarządzanie gośćmi"""
    guests = Guest.objects.all().order_by('-created_at')
    
    # Wyszukiwanie
    search_query = request.GET.get('search')
    if search_query:
        guests = guests.filter(
            Q(name__icontains=search_query) |
            Q(surname__icontains=search_query) |
            Q(email__icontains=search_query)
        )
    
    context = {
        'guests': guests,
        'search_query': search_query,
    }
    return render(request, 'employee/guests.html', context)


@login_required
@employee_required
def employee_guest_detail(request, guest_id):
    """Szczegóły gościa"""
    guest = get_object_or_404(Guest, id=guest_id)
    reservations = Reservation.objects.filter(guest=guest).order_by('-created_at')
    
    context = {
        'guest': guest,
        'reservations': reservations,
    }
    return render(request, 'employee/guest_detail.html', context)
