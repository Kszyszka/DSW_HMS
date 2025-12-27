from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login, authenticate, logout
from django.contrib import messages
from django.db.models import Q, Sum
from datetime import date
from django.contrib.auth.models import User
from django.http import JsonResponse
from django.utils import timezone
import datetime
from .models import Guest, Room, Reservation, Payment, Employee, RoomIssue, Season, SeasonPrice
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
    
    # Determine whether to show access PIN
    paid_online = payments.filter(payment_method='online', payment_status='completed').exists()
    show_access_pin = False
    access_pin = None
    precheckin_allowed = False
    try:
        today = timezone.localdate()
        delta = (reservation.check_in_date - today).days
        precheckin_allowed = delta <= 1
        if paid_online and reservation.room.pin and precheckin_allowed:
            show_access_pin = True
            access_pin = reservation.room.pin
    except Exception:
        pass

    context = {
        'reservation': reservation,
        'payments': payments,
        'is_superuser': request.user.is_superuser,
        'show_access_pin': show_access_pin,
        'access_pin': access_pin,
        'precheckin_allowed': precheckin_allowed,
        'paid_online': paid_online,
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
        number_of_guests = int(request.POST.get('number_of_guests') or 1)
        payment_method = request.POST.get('payment_method', 'cash')
        
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
            
            # Sprawdź pojemność
            if number_of_guests > room.capacity:
                messages.error(request, 'Wybrany pokój nie mieści tylu gości.')
                return redirect('guest:create_reservation')

            # Obliczenie ceny
            nights = (check_out_date - check_in_date).days
            price_total = room.price * nights
            
            reservation = Reservation.objects.create(
                guest=guest,
                room=room,
                number_of_guests=number_of_guests,
                check_in_date=check_in_date,
                check_out_date=check_out_date,
                price_total=price_total,
                notes=notes,
                status='pending'
            )

            if payment_method == 'cash':
                Payment.objects.create(
                    reservation=reservation,
                    amount=price_total,
                    payment_date=date.today(),
                    payment_method='cash',
                    payment_status='pending'
                )
                messages.success(request, 'Rezerwacja została utworzona. Oczekuje na potwierdzenie.')
                return redirect('guest:reservation_detail', reservation_id=reservation.id)
            else:
                Payment.objects.create(
                    reservation=reservation,
                    amount=price_total,
                    payment_date=date.today(),
                    payment_method='online',
                    payment_status='pending'
                )
                # Ustaw wstępny PIN dla pokoju przy rezerwacji online
                try:
                    room.set_new_pin()
                    reservation.pin_assigned_at = timezone.now()
                    reservation.save(update_fields=['pin_assigned_at'])
                except Exception:
                    pass
        except Room.DoesNotExist:
            messages.error(request, 'Wybrany pokój nie istnieje.')
        except Exception as e:
            messages.error(request, f'Błąd podczas tworzenia rezerwacji: {str(e)}')

    # Pobranie dostępnych pokoi
    available_rooms = Room.objects.filter(status='available')

    context = {
        'available_rooms': available_rooms,
    }
    return render(request, 'guest/create_reservation.html', context)


def rooms_availability_api(request):
    """API zwraca pokoje dostępne dla zadanego zakresu dat i liczby gości.
    Zwraca dwa zbiory: available_now (pokój wolny teraz) oraz available_later (pokój proponowany - obecnie zajęty ale wolny na żądany termin z dopiskiem do kiedy jest zajęty).
    """
    check_in = request.GET.get('check_in_date')
    check_out = request.GET.get('check_out_date')
    number_of_guests = int(request.GET.get('number_of_guests') or 1)

    if not check_in or not check_out:
        return JsonResponse({'error': 'Brakuje dat'}, status=400)

    try:
        check_in_date = date.fromisoformat(check_in)
        check_out_date = date.fromisoformat(check_out)
    except Exception:
        return JsonResponse({'error': 'Nieprawidłowy format dat'}, status=400)

    # Pobierz wszystkie pokoje (najpierw sprawdzenie dostępności wg dat niezależnie od pojemności)
    rooms_all = Room.objects.all().order_by('number')

    available_by_date = []
    today = timezone.localdate()

    blocked_statuses = ['to_clean', 'maintenance']
    for room in rooms_all:
        # Jeżeli pokój jest oznaczony jako wymagający sprzątania lub w konserwacji - nie oferujemy go w żadnym wariancie
        if room.status in blocked_statuses:
            continue
        conflicts = Reservation.objects.filter(
            room=room,
            status__in=['pending', 'confirmed', 'checked_in'],
            check_in_date__lt=check_out_date,
            check_out_date__gt=check_in_date
        )
        if conflicts.exists():
            continue

        room_data = {
            'id': room.id,
            'number': room.number,
            'room_type': room.get_room_type_display(),
            'price': str(room.price),
            'capacity': room.capacity,
            'status': room.status,
        }

        if room.status == 'available':
            room_data['occupied_until'] = None
        else:
            latest_res = Reservation.objects.filter(
                room=room,
                status__in=['pending', 'confirmed', 'checked_in']
            ).order_by('-check_out_date').first()
            room_data['occupied_until'] = latest_res.check_out_date.isoformat() if latest_res and latest_res.check_out_date >= today else None

        available_by_date.append(room_data)

    # Jeśli brak dostępnych pokoi w żądanym terminie -> znajdź najbliższy dostępny start (do 365 dni)
    nearest_available_start = None
    if not available_by_date:
        duration_days = (check_out_date - check_in_date).days
        for delta in range(1, 366):
            candidate_start = check_in_date + datetime.timedelta(days=delta)
            candidate_end = candidate_start + datetime.timedelta(days=duration_days)
            for room in rooms_all:
                conflicts = Reservation.objects.filter(
                    room=room,
                    status__in=['pending', 'confirmed', 'checked_in'],
                    check_in_date__lt=candidate_end,
                    check_out_date__gt=candidate_start
                )
                if not conflicts.exists():
                    nearest_available_start = candidate_start.isoformat()
                    break
            if nearest_available_start:
                break

    # Teraz filtry pojemności dla pokazania konkretnych pokoi spełniających ilość gości
    rooms_cap = [r for r in available_by_date if r['capacity'] >= number_of_guests]
    available_now = [r for r in rooms_cap if r['status'] == 'available']
    available_later = [r for r in rooms_cap if r['status'] != 'available']

    capacity_issue = bool(available_by_date) and not rooms_cap

    return JsonResponse({
        'available_by_date': available_by_date,
        'available_now': available_now,
        'available_later': available_later,
        'nearest_available_start': nearest_available_start,
        'capacity_issue': capacity_issue,
    })


def public_create_reservation(request):
    """Tworzenie rezerwacji bez logowania - tworzy obiekt Guest (opcjonalnie User)"""
    if request.user.is_authenticated:
        return redirect('guest:create_reservation')

    if request.method == 'POST':
        # Dane gościa
        name = request.POST.get('name')
        surname = request.POST.get('surname')
        email = request.POST.get('email')
        phone = request.POST.get('phone')

        # Rezerwacja
        room_id = request.POST.get('room_id')
        check_in = request.POST.get('check_in_date')
        check_out = request.POST.get('check_out_date')
        number_of_guests = int(request.POST.get('number_of_guests') or 1)
        notes = request.POST.get('notes', '')

        payment_method = request.POST.get('payment_method', 'cash')

        create_account = request.POST.get('create_account') == 'on'
        username = request.POST.get('username')
        password = request.POST.get('password')
        password2 = request.POST.get('password2')

        try:
            # Utwórz lub pobierz Guest po emailu
            guest, created = Guest.objects.get_or_create(
                email=email,
                defaults={'name': name or '', 'surname': surname or '', 'phone': phone or ''}
            )

            # Jeśli zaznaczono tworzenie konta i użytkownik nie istnieje
            if create_account and not guest.user:
                if password != password2:
                    messages.error(request, 'Hasła nie są identyczne.')
                    return redirect('guest:create_reservation_public')

                # Przyjmij username = email jeśli nie podano
                if not username:
                    username = email

                if User.objects.filter(username=username).exists():
                    messages.error(request, 'Nazwa użytkownika jest już zajęta.')
                    return redirect('guest:create_reservation_public')

                user = User.objects.create_user(username=username, password=password)
                user.first_name = name or ''
                user.last_name = surname or ''
                user.email = email or ''
                user.save()
                guest.user = user
                guest.name = name or guest.name
                guest.surname = surname or guest.surname
                guest.phone = phone or guest.phone
                guest.save()

                # Zaloguj użytkownika automatycznie
                login(request, user)

            # Jeśli gość miał konto (user exists) i jest zalogowany, nic więcej

            # Tworzenie rezerwacji
            room = Room.objects.get(id=room_id)
            # Sprawdź pojemność
            if number_of_guests > room.capacity:
                messages.error(request, 'Wybrany pokój nie mieści tylu gości.')
                return redirect('guest:create_reservation_public')
            check_in_date = date.fromisoformat(check_in)
            check_out_date = date.fromisoformat(check_out)

            conflicting_reservations = Reservation.objects.filter(
                room=room,
                status__in=['pending', 'confirmed', 'checked_in'],
                check_in_date__lt=check_out_date,
                check_out_date__gt=check_in_date
            )

            if conflicting_reservations.exists():
                messages.error(request, 'Pokój jest już zarezerwowany w wybranym terminie.')
                return redirect('guest:create_reservation_public')

            nights = (check_out_date - check_in_date).days
            price_total = room.price * nights
            
            reservation = Reservation.objects.create(
                guest=guest,
                room=room,
                number_of_guests=number_of_guests,
                check_in_date=check_in_date,
                check_out_date=check_out_date,
                price_total=price_total,
                notes=notes,
                status='pending'
            )

            # Jeśli wybrano formę płatności - utwórz wpis płatności (dla online -> redirect do bramki testowej)
            if payment_method == 'cash':
                Payment.objects.create(
                    reservation=reservation,
                    amount=price_total,
                    payment_date=date.today(),
                    payment_method='cash',
                    payment_status='pending'
                )
                # Zakończ proces rezerwacji i pokaż stronę z instrukcją
                messages.success(request, 'Rezerwacja została utworzona. Instrukcje zostały wyświetlone poniżej.')
                return redirect('public_reservation_detail', reservation_id=reservation.id)
            else:
                # online
                Payment.objects.create(
                    reservation=reservation,
                    amount=price_total,
                    payment_date=date.today(),
                    payment_method='online',
                    payment_status='pending'
                )
                # Przy rezerwacji z płatnością online ustaw wstępny PIN dla pokoju
                try:
                    room.set_new_pin()
                    reservation.pin_assigned_at = timezone.now()
                    reservation.save(update_fields=['pin_assigned_at'])
                except Exception:
                    pass
                return redirect('online_payment_test', reservation_id=reservation.id)

            messages.success(request, 'Rezerwacja została utworzona. Oczekuje na potwierdzenie.')
            return redirect('guest:reservation_detail', reservation_id=reservation.id)

        except Room.DoesNotExist:
            messages.error(request, 'Wybrany pokój nie istnieje.')
        except Exception as e:
            messages.error(request, f'Błąd podczas tworzenia rezerwacji: {str(e)}')

    # Pobranie dostępnych pokoi
    available_rooms = Room.objects.filter(status='available')

    context = {
        'available_rooms': available_rooms,
    }
    return render(request, 'guest/create_reservation_public.html', context)


def public_reservation_detail(request, reservation_id):
    """Publiczny podgląd rezerwacji dostępny bez logowania"""
    reservation = get_object_or_404(Reservation, id=reservation_id)
    payments = Payment.objects.filter(reservation=reservation)

    # Czy rezerwacja ma opłaconą płatność online?
    paid_online = payments.filter(payment_method='online', payment_status='completed').exists()

    show_access_pin = False
    access_pin = None
    precheckin_allowed = False
    try:
        today = timezone.localdate()
        delta = (reservation.check_in_date - today).days
        # pre-checkin możliwy <=1 dnia przed zameldowaniem
        precheckin_allowed = delta <= 1
        if paid_online and reservation.room.pin and precheckin_allowed:
            show_access_pin = True
            access_pin = reservation.room.pin
    except Exception:
        pass

    context = {
        'reservation': reservation,
        'payments': payments,
        'show_access_pin': show_access_pin,
        'access_pin': access_pin,
        'precheckin_allowed': precheckin_allowed,
        'paid_online': paid_online,
    }
    return render(request, 'public_reservation_detail.html', context) 


def pre_checkin(request, reservation_id):
    """Endpoint inicjujący pre-checkin: regeneruje PIN pokoju jeśli warunki spełnione"""
    reservation = get_object_or_404(Reservation, id=reservation_id)
    payments = Payment.objects.filter(reservation=reservation)

    paid_online = payments.filter(payment_method='online', payment_status='completed').exists()
    if not paid_online:
        messages.error(request, 'Pre-checkin dostępny tylko dla opłaconych rezerwacji online.')
        return redirect('public_reservation_detail', reservation_id=reservation.id)

    today = timezone.localdate()
    delta = (reservation.check_in_date - today).days
    if delta > 1:
        messages.error(request, 'Pre-checkin można wykonać najwcześniej 1 dzień przed zameldowaniem.')
        return redirect('public_reservation_detail', reservation_id=reservation.id)

    # Generate new PIN and save
    try:
        new_pin = reservation.room.set_new_pin()
        reservation.pin_assigned_at = timezone.now()
        reservation.save(update_fields=['pin_assigned_at'])
        messages.success(request, f'Pre-checkin wykonany. Kod PIN do pokoju: {new_pin}')
    except Exception as e:
        messages.error(request, f'Błąd podczas generowania PIN: {str(e)}')

    return redirect('public_reservation_detail', reservation_id=reservation.id)


def online_payment_test(request, reservation_id):
    """Prosta bramka testowa: symulacja płatności online"""
    reservation = get_object_or_404(Reservation, id=reservation_id)
    payment = Payment.objects.filter(reservation=reservation, payment_method='online').first()

    if request.method == 'POST':
        # Oznacz płatność jako zrealizowaną
        if payment:
            payment.payment_status = 'completed'
            payment.transaction_id = 'TEST_TXN_%s' % reservation.id
            payment.save()
        # Ustaw status rezerwacji i pokoju
        reservation.status = 'confirmed'
        reservation.room.status = 'reserved'
        # Jeśli do zameldowania pozostało mniej lub równo 1 dzień -> wygeneruj nowy PIN (pre-checkin)
        try:
            today = timezone.localdate()
            delta = (reservation.check_in_date - today).days
            if delta <= 1:
                # regenerate PIN for room
                reservation.room.set_new_pin()
                reservation.pin_assigned_at = timezone.now()
                reservation.save(update_fields=['pin_assigned_at'])
        except Exception:
            pass

        reservation.room.save()
        reservation.save()
        messages.success(request, 'Płatność została zakończona (symulacja).')
        return redirect('public_reservation_detail', reservation_id=reservation.id)

    context = {
        'reservation': reservation,
        'payment': payment,
    }
    return render(request, 'online_payment_test.html', context)


def guest_register(request):
    """Rejestracja gościa (tworzy User + Guest)"""
    if request.user.is_authenticated:
        return redirect('home')

    if request.method == 'POST':
        name = request.POST.get('name')
        surname = request.POST.get('surname')
        email = request.POST.get('email')
        phone = request.POST.get('phone')
        username = request.POST.get('username') or email
        password = request.POST.get('password')
        password2 = request.POST.get('password2')

        if password != password2:
            messages.error(request, 'Hasła nie są identyczne.')
            return redirect('guest:register')

        if User.objects.filter(username=username).exists():
            messages.error(request, 'Nazwa użytkownika jest już zajęta.')
            return redirect('guest:register')

        if Guest.objects.filter(email=email).exists():
            messages.error(request, 'Gość z podanym adresem e-mail już istnieje. Zaloguj się lub użyj innego adresu.')
            return redirect('guest:register')

        try:
            user = User.objects.create_user(username=username, password=password)
            user.first_name = name or ''
            user.last_name = surname or ''
            user.email = email or ''
            user.save()

            guest = Guest.objects.create(
                user=user,
                name=name or '',
                surname=surname or '',
                email=email or '',
                phone=phone or ''
            )

            login(request, user)
            messages.success(request, 'Konto zostało utworzone i połączone z profilem gościa.')
            return redirect('guest:dashboard')
        except Exception as e:
            messages.error(request, f'Błąd podczas rejestracji: {str(e)}')

    return render(request, 'guest/register.html')


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

    # Jeśli pracownik ma rolę pokojówki — przekieruj bezpośrednio do widoku sprzątania
    try:
        role = getattr(employee, 'role', None)
    except Exception:
        role = None
    if role == 'housekeeping' and not request.user.is_superuser:
        return redirect('employee:housekeeping')

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
                new_status = request.POST.get('status')
                # Check for reservation conflicts when blocking room
                if new_status in ['maintenance', 'to_clean']:
                    from datetime import date as _date
                    conflicts = Reservation.objects.filter(
                        room=room,
                        status__in=['pending', 'confirmed', 'checked_in'],
                        check_out_date__gte=_date.today()
                    ).order_by('check_in_date')
                    # If conflicts exist and user didn't confirm force, show warning with list
                    if conflicts.exists() and request.POST.get('confirm_force') != 'yes':
                        # Re-render page with conflict info
                        rooms = Room.objects.all().order_by('number')
                        context = {
                            'rooms': rooms,
                            'conflict_room': room,
                            'conflict_reservations': conflicts,
                        }
                        messages.warning(request, f'Konflikt rezerwacji: znaleziono {conflicts.count()} rezerwację(je) w blokowanym terminie. Zatwierdź, aby wymusić zmianę statusu i przenieść/anulować rezerwacje.')
                        return render(request, 'employee/rooms.html', context)
                # No conflicts or user confirmed force
                room.status = new_status
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
def employee_pricing(request):
    """Zarządzanie sezonami i cennikami (interface for manager/admin)"""
    # allow only manager or admin
    if not request.user.is_superuser:
        if not hasattr(request.user, 'employee_profile') or request.user.employee_profile.role not in ('manager', 'admin'):
            messages.error(request, 'Brak dostępu do modułu Cenniki i Sezony.')
            return redirect('employee:dashboard')

    seasons = Season.objects.all().order_by('-priority', '-start_date')

    context = {
        'seasons': seasons,
    }
    return render(request, 'employee/pricing.html', context)


@login_required
@employee_required
def employee_room_create(request):
    """Tworzenie nowego pokoju (dla pracowników)"""
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
def employee_create_reservation(request):
    """Tworzenie rezerwacji przez pracownika (możliwość wyboru istniejącego gościa lub utworzenia nowego)"""
    if request.method == 'POST':
        guest_id = request.POST.get('guest_id')
        name = request.POST.get('name')
        surname = request.POST.get('surname')
        email = request.POST.get('email')
        phone = request.POST.get('phone')

        room_id = request.POST.get('room_id')
        check_in = request.POST.get('check_in_date')
        check_out = request.POST.get('check_out_date')
        number_of_guests = int(request.POST.get('number_of_guests') or 1)
        notes = request.POST.get('notes', '')
        payment_method = request.POST.get('payment_method', 'cash')

        try:
            if guest_id:
                guest = Guest.objects.get(id=guest_id)
            else:
                guest, created = Guest.objects.get_or_create(
                    email=email,
                    defaults={'name': name or '', 'surname': surname or '', 'phone': phone or ''}
                )

            room = Room.objects.get(id=room_id)

            # Sprawdź pojemność
            if number_of_guests > room.capacity:
                messages.error(request, 'Wybrany pokój nie mieści tylu gości.')
                return redirect('employee:reservation_create')

            check_in_date = date.fromisoformat(check_in)
            check_out_date = date.fromisoformat(check_out)

            # Sprawdzenie konfliktów
            conflicts = Reservation.objects.filter(
                room=room,
                status__in=['pending', 'confirmed', 'checked_in'],
                check_in_date__lt=check_out_date,
                check_out_date__gt=check_in_date
            )

            if conflicts.exists() and request.POST.get('confirm_force') != 'yes':
                available_rooms = Room.objects.filter(status='available')
                context = {
                    'available_rooms': available_rooms,
                    'conflict_room': room,
                    'conflict_reservations': conflicts,
                    'guests': Guest.objects.all().order_by('-created_at')[:50],
                }
                messages.warning(request, f'Konflikt rezerwacji: znaleziono {conflicts.count()} rezerwację(je) dla wybranego pokoju. Potwierdź wymuszenie, aby przypisać.')
                return render(request, 'employee/create_reservation.html', context)

            nights = (check_out_date - check_in_date).days
            price_total = room.price * nights

            reservation = Reservation.objects.create(
                guest=guest,
                room=room,
                number_of_guests=number_of_guests,
                check_in_date=check_in_date,
                check_out_date=check_out_date,
                price_total=price_total,
                notes=notes,
                status='pending'
            )

            if payment_method == 'cash':
                Payment.objects.create(
                    reservation=reservation,
                    amount=price_total,
                    payment_date=date.today(),
                    payment_method='cash',
                    payment_status='pending'
                )
                messages.success(request, 'Rezerwacja została utworzona.')
                return redirect('employee:reservation_detail', reservation_id=reservation.id)
            else:
                Payment.objects.create(
                    reservation=reservation,
                    amount=price_total,
                    payment_date=date.today(),
                    payment_method='online',
                    payment_status='pending'
                )
                # Wstępny PIN dla rezerwacji online
                try:
                    room.set_new_pin()
                    reservation.pin_assigned_at = timezone.now()
                    reservation.save(update_fields=['pin_assigned_at'])
                except Exception:
                    pass
                return redirect('online_payment_test', reservation_id=reservation.id)

        except Room.DoesNotExist:
            messages.error(request, 'Wybrany pokój nie istnieje.')
        except Guest.DoesNotExist:
            messages.error(request, 'Wybrany gość nie istnieje.')
        except Exception as e:
            messages.error(request, f'Błąd: {str(e)}')

        return redirect('employee:reservation_create')

    available_rooms = Room.objects.filter(status='available')
    guests = Guest.objects.all().order_by('-created_at')[:50]
    context = {
        'available_rooms': available_rooms,
        'guests': guests,
    }
    return render(request, 'employee/create_reservation.html', context)


@login_required
@employee_required
def housekeeping_dashboard(request):
    """Widok dla pokojówek: lista pokoi do posprzątania i zgłoszonych usterek"""
    # tylko pracownicy o odpowiedniej roli
    if not request.user.is_superuser:
        if not hasattr(request.user, 'employee_profile') or request.user.employee_profile.role != 'housekeeping':
            messages.error(request, 'Brak dostępu do tej sekcji.')
            return redirect('employee:dashboard')

    if request.method == 'POST':
        action = request.POST.get('action')
        try:
            if action == 'mark_clean':
                room = Room.objects.get(id=request.POST.get('room_id'))
                room.status = 'available'
                room.save()
                messages.success(request, f'Pokój {room.number} oznaczono jako posprzątany i dostępny.')
            elif action == 'resolve_issue':
                issue = RoomIssue.objects.get(id=request.POST.get('issue_id'))
                issue.is_resolved = True
                issue.save()
                # Sprawdź, czy są jeszcze nie rozwiązane usterki dla tego pokoju
                room = issue.room
                has_unresolved = room.issues.filter(is_resolved=False).exists()
                if not has_unresolved:
                    room.status = 'to_clean'
                    room.save()
                    messages.success(request, 'Usterka została oznaczona jako rozwiązana. Pokój ustawiony jako "Do sprzątania".')
                else:
                    messages.success(request, 'Usterka została oznaczona jako rozwiązana. Pozostałe usterki nadal aktywne, pokój pozostaje w konserwacji.')
            elif action == 'reopen_issue':
                issue = RoomIssue.objects.get(id=request.POST.get('issue_id'))
                issue.is_resolved = False
                issue.save()
                # Jeśli usterka ponownie otwarta ustaw pokój na konserwację
                room = issue.room
                room.status = 'maintenance'
                room.save()
                messages.success(request, 'Usterka została ponownie otwarta. Pokój ustawiony jako "W konserwacji".')
            elif action == 'report_issue':
                # Zgłoszenie nowej usterki (z formularza)
                room = Room.objects.get(id=request.POST.get('room_id'))
                title = request.POST.get('issue_title', 'Usterka zgłoszona')[:200]
                description = request.POST.get('issue_description', '').strip()
                # Spróbuj przypisać zgłaszającego jako Guest jeśli istnieje
                reported_by = None
                if hasattr(request.user, 'guest_profile'):
                    reported_by = request.user.guest_profile
                RoomIssue.objects.create(
                    room=room,
                    title=title,
                    description=description,
                    reported_by=reported_by,
                )
                # Ustaw pokój w tryb konserwacji
                room.status = 'maintenance'
                # Dodaj krótki wpis do notatek pokoju
                note_entry = f"Usterka zgłoszona: {title}"
                if description:
                    note_entry += f" — {description}"
                if room.notes:
                    room.notes = room.notes + "\n" + note_entry
                else:
                    room.notes = note_entry
                room.save()
                messages.success(request, f'Usterka dla pokoju {room.number} została zgłoszona i ustawiona jako "W konserwacji".')
        except Exception as e:
            messages.error(request, f'Błąd: {str(e)}')
        return redirect('employee:housekeeping')

    rooms = Room.objects.filter(status='to_clean').order_by('number')
    rooms_data = []
    for room in rooms:
        unresolved = room.issues.filter(is_resolved=False)
        rooms_data.append({
            'room': room,
            'unresolved_issues': unresolved,
        })

    rooms_with_issues = [r for r in rooms_data if r['unresolved_issues'].exists()]
    rooms_without_issues = [r for r in rooms_data if not r['unresolved_issues'].exists()]

    context = {
        'rooms_with_issues': rooms_with_issues,
        'rooms_without_issues': rooms_without_issues,
    }
    return render(request, 'employee/housekeeping.html', context)

@login_required
@employee_required
def employee_reservations(request):
    """Lista rezerwacji i operacje na nich dla pracowników"""
    status_filter = request.GET.get('status')
    if status_filter:
        reservations = Reservation.objects.filter(status=status_filter).order_by('-created_at')
    else:
        reservations = Reservation.objects.all().order_by('-created_at')

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
                # Po wymeldowaniu pokój wymaga sprzątania, nie ustawiamy go od razu jako dostępny
                reservation.room.status = 'to_clean'
                reservation.room.save()
                reservation.save()
                messages.success(request, 'Gość został wymeldowany. Pokój oznaczono jako "Do sprzątania".')
            
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
    
    # Candidate rooms for reassignment
    candidate_rooms = []
    unavailable_rooms = []
    rooms_qs = Room.objects.filter(capacity__gte=reservation.number_of_guests).exclude(status='maintenance').order_by('number')
    for r in rooms_qs:
        # conflicts excluding current reservation
        conflict_exists = Reservation.objects.filter(
            room=r,
            status__in=['pending', 'confirmed', 'checked_in']
        ).exclude(id=reservation.id).filter(
            check_in_date__lt=reservation.check_out_date,
            check_out_date__gt=reservation.check_in_date
        ).exists()
        if conflict_exists:
            unavailable_rooms.append((r, True))
        else:
            candidate_rooms.append((r, False))

    # Ensure current assigned room is visible in the select even if it doesn't
    # match the candidate/unavailable filters (e.g., in maintenance or capacity mismatch)
    room_ids = {r.id for r, _ in candidate_rooms} | {r.id for r, _ in unavailable_rooms}
    current_room = None
    include_current = False
    if reservation.room:
        if reservation.room.id not in room_ids:
            current_room = reservation.room
            include_current = True
    
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
        elif action == 'edit_payment':
            try:
                payment_id = request.POST.get('payment_id')
                payment = Payment.objects.get(id=payment_id, reservation=reservation)
                payment.amount = request.POST.get('amount')
                payment.payment_date = request.POST.get('payment_date', payment.payment_date)
                payment.payment_method = request.POST.get('payment_method', payment.payment_method)
                payment.payment_status = request.POST.get('payment_status', payment.payment_status)
                payment.transaction_id = request.POST.get('transaction_id', payment.transaction_id)
                payment.save()
                messages.success(request, 'Płatność została zaktualizowana.')
                return redirect('employee:reservation_detail', reservation_id=reservation.id)
            except Exception as e:
                messages.error(request, f'Błąd: {str(e)}')
        elif action == 'delete_payment':
            try:
                payment_id = request.POST.get('payment_id')
                payment = Payment.objects.get(id=payment_id, reservation=reservation)
                payment.delete()
                messages.success(request, 'Płatność została usunięta.')
                return redirect('employee:reservation_detail', reservation_id=reservation.id)
            except Exception as e:
                messages.error(request, f'Błąd: {str(e)}')
        elif action == 'change_room':
            try:
                new_room_id = request.POST.get('new_room_id')
                new_room = Room.objects.get(id=new_room_id)
                # check capacity
                if new_room.capacity < reservation.number_of_guests:
                    messages.error(request, 'Wybrany pokój nie obsługuje tej liczby gości.')
                    return redirect('employee:reservation_detail', reservation_id=reservation.id)
                # check conflicts
                conflicts = Reservation.objects.filter(
                    room=new_room,
                    status__in=['pending', 'confirmed', 'checked_in']
                ).exclude(id=reservation.id).filter(
                    check_in_date__lt=reservation.check_out_date,
                    check_out_date__gt=reservation.check_in_date
                )
                if conflicts.exists() and request.POST.get('confirm_force') != 'yes':
                    # show conflict in template
                    payments = Payment.objects.filter(reservation=reservation)  # refresh
                    total_paid = payments.filter(payment_status='completed').aggregate(Sum('amount'))['amount__sum'] or 0
                    context = {
                        'reservation': reservation,
                        'payments': payments,
                        'total_paid': total_paid,
                        'remaining': reservation.price_total - total_paid,
                        'candidate_rooms': candidate_rooms,
                        'unavailable_rooms': unavailable_rooms,
                        'conflict_room': new_room,
                        'conflict_reservations': conflicts,
                        'current_room': current_room,
                        'include_current': include_current,
                    }
                    messages.warning(request, f'Konflikt rezerwacji: znaleziono {conflicts.count()} rezerwację(je) dla wybranego pokoju. Potwierdź wymuszenie, aby przypisać.')
                    return render(request, 'employee/reservation_detail.html', context)
                # Perform reassignment
                old_room = reservation.room
                reservation.room = new_room
                reservation.save()
                # Update statuses accordingly
                if reservation.status in ['pending', 'confirmed']:
                    new_room.status = 'reserved'
                elif reservation.status == 'checked_in':
                    new_room.status = 'occupied'
                new_room.save()
                # Release old room if no other active reservations
                active_res = Reservation.objects.filter(room=old_room, status__in=['pending', 'confirmed', 'checked_in']).exclude(id=reservation.id)
                if not active_res.exists():
                    old_room.status = 'available'
                    old_room.save()
                messages.success(request, 'Pokój rezerwacji został zmieniony.')
                return redirect('employee:reservation_detail', reservation_id=reservation.id)
            except Exception as e:
                messages.error(request, f'Błąd: {str(e)}')
        # (other existing actions stay below)
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
                # Po wymeldowaniu pokój oznaczamy jako "Do sprzątania"
                reservation.room.status = 'to_clean'
                reservation.room.save()
                reservation.save()
                messages.success(request, 'Gość został wymeldowany. Pokój oznaczono jako "Do sprzątania".')
                return redirect('employee:reservation_detail', reservation_id=reservation.id)
            except Exception as e:
                messages.error(request, f'Błąd: {str(e)}')
    
    # Show PIN for employees as well when applicable
    paid_online = payments.filter(payment_method='online', payment_status='completed').exists()
    show_access_pin = False
    access_pin = None
    precheckin_allowed = False
    try:
        today = timezone.localdate()
        delta = (reservation.check_in_date - today).days
        precheckin_allowed = delta <= 1
        if paid_online and reservation.room.pin and precheckin_allowed:
            show_access_pin = True
            access_pin = reservation.room.pin
    except Exception:
        pass

    context = {
        'reservation': reservation,
        'payments': payments,
        'total_paid': total_paid,
        'remaining': reservation.price_total - total_paid,
        'candidate_rooms': candidate_rooms,
        'unavailable_rooms': unavailable_rooms,
        'current_room': current_room,
        'include_current': include_current,
        'show_access_pin': show_access_pin,
        'access_pin': access_pin,
        'precheckin_allowed': precheckin_allowed,
        'paid_online': paid_online,
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
