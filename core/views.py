from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.contrib.auth.models import User
from .models import Room, Reservation, GuestProfile, EmployeeProfile, Payment, compute_reservation_price, Season, SeasonPrice
from .decorators import employee_required, guest_required, manager_required
from django.utils import timezone
from django.db.models import Sum
from datetime import datetime
from django.db import transaction
import random
import string
import re
import json
import logging
from decimal import Decimal
from django.http import FileResponse
import io
try:
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import A4
except ImportError:
    canvas = None

# Authentication Views

def login_view(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            messages.success(request, f"Witaj, {user.first_name or user.username}! Zalogowano pomyślnie.")
            if user.is_superuser or hasattr(user, 'employee_profile'):
                return redirect('employee:dashboard')
            else:
                return redirect('guest:dashboard')
        else:
            messages.error(request, "Nieprawidłowy email lub hasło.")
    return render(request, 'core/login.html')

def logout_view(request):
    logout(request)
    messages.info(request, "Zostałeś wylogowany.")
    return redirect('home')

def home_view(request):
    return render(request, 'core/home.html')

def generate_pin():
    return ''.join(random.choices(string.digits, k=4))

def clean_text(text):
    """Usuwa polskie znaki dla prostego PDF."""
    replacements = {
        'ą': 'a', 'ć': 'c', 'ę': 'e', 'ł': 'l', 'ń': 'n', 'ó': 'o', 'ś': 's', 'ź': 'z', 'ż': 'z',
        'Ą': 'A', 'Ć': 'C', 'Ę': 'E', 'Ł': 'L', 'Ń': 'N', 'Ó': 'O', 'Ś': 'S', 'Ź': 'Z', 'Ż': 'Z'
    }
    if not text: return ""
    text = str(text)
    for k, v in replacements.items():
        text = text.replace(k, v)
    return text

# Employee Views

@login_required
@employee_required
def employee_dashboard(request):
    today = timezone.now().date()
    pending_reservations = Reservation.objects.filter(status='pending').count()
    checkins_today = Reservation.objects.filter(check_in=today, status='confirmed').count()
    checkouts_today = Reservation.objects.filter(check_out=today, status='checked_in').count()

    total_rooms = Room.objects.count()
    available_rooms = Room.objects.filter(status='available').count()

    recent_reservations = Reservation.objects.all().order_by('-created_at')[:5]

    employee = None
    if hasattr(request.user, 'employee_profile'):
        employee = request.user.employee_profile
        if employee.role == 'technician':
            return redirect('employee:maintenance')
        if employee.role == 'maid':
            return redirect('employee:housekeeping')
    elif request.user.is_superuser:
        class AdminProxy:
            user = request.user
            role = 'manager'
            def get_role_display(self):
                return "Administrator"
        employee = AdminProxy()

    calendar_events = []
    active_reservations = Reservation.objects.filter(
        status__in=['confirmed', 'checked_in', 'pending']
    ).values('id', 'status', 'check_in', 'check_out', 'room__number', 'guest__user__last_name')

    for res in active_reservations:
        color = '#28a745' if res['status'] == 'checked_in' else ('#0d6efd' if res['status'] == 'confirmed' else '#ffc107')
        calendar_events.append({
            'title': f"{res['room__number']} - {res['guest__user__last_name']}",
            'start': res['check_in'].isoformat(),
            'end': res['check_out'].isoformat(),
            'color': color,
            'url': f"/employee/reservations/{res['id']}/"
        })

    context = {
        'pending_reservations': pending_reservations,
        'checkins_today': checkins_today,
        'checkouts_today': checkouts_today,
        'total_rooms': total_rooms,
        'available_rooms': available_rooms,
        'recent_reservations': recent_reservations,
        'employee': employee,
        'calendar_events_json': json.dumps(calendar_events),
    }
    return render(request, 'employee/dashboard.html', context)

@login_required
@employee_required
def employee_rooms(request):
    if not request.user.is_superuser and request.user.employee_profile.role in ['technician', 'maid']:
        messages.error(request, "Brak uprawnień do zarządzania pokojami.")
        return redirect('employee:dashboard')

    if request.method == 'POST':
        room_id = request.POST.get('room_id')
        new_status = request.POST.get('status')
        
        if room_id and new_status:
            room = get_object_or_404(Room, pk=room_id)

            if new_status == 'maintenance':
                description = request.POST.get('maintenance_description')
                if not description:
                    messages.error(request, "Wymagany jest opis usterki przy zmianie statusu na 'W naprawie'.")
                    return redirect('employee:rooms')
                timestamp = timezone.now().strftime('%Y-%m-%d %H:%M')
                room.notes = f"{room.notes}\n[RECEPCJA {timestamp}]: {description}".strip()
            
            room.status = new_status
            room.save()
            messages.success(request, f"Status pokoju {room.number} zmieniony na {room.get_status_display()}.")
            return redirect('employee:rooms')

    today = timezone.now().date()
    rooms = Room.objects.all()

    for room in rooms:
        active_reservation = Reservation.objects.filter(
            room=room,
            check_in__lte=today,
            check_out__gte=today,
            status__in=['confirmed', 'checked_in']
        ).first()
        room.active_reservation = active_reservation
        
    return render(request, 'employee/rooms.html', {'rooms': rooms})

@login_required
@employee_required
def employee_reservations(request):
    if not request.user.is_superuser and request.user.employee_profile.role in ['technician', 'maid']:
        messages.error(request, "Brak uprawnień do modułu rezerwacji.")
        return redirect('employee:dashboard')

    reservations = Reservation.objects.all().order_by('-created_at')
    return render(request, 'employee/reservations.html', {'reservations': reservations})

@login_required
@employee_required
def employee_reservation_detail(request, pk):
    if not request.user.is_superuser and request.user.employee_profile.role in ['technician', 'maid']:
        messages.error(request, "Brak uprawnień do szczegółów rezerwacji.")
        return redirect('employee:dashboard')

    reservation = get_object_or_404(Reservation, pk=pk)

    if not reservation.total_price:
        reservation.total_price = compute_reservation_price(reservation)
        reservation.save()

    payments = reservation.payments.all().order_by('-payment_date')
    total_paid = sum(p.amount for p in payments if p.payment_status == 'completed')
    remaining = (reservation.total_price or 0) - total_paid

    candidate_rooms = []
    unavailable_rooms = []
    if request.method == 'GET':
        all_rooms = Room.objects.all().order_by('number')
        for r in all_rooms:
            if r.id == reservation.room.id:
                continue
            collision = Reservation.objects.filter(
                room=r,
                check_in__lt=reservation.check_out,
                check_out__gt=reservation.check_in,
                status__in=['pending', 'confirmed', 'checked_in']
            ).exists()
            if not collision and r.status != 'maintenance':
                candidate_rooms.append((r, 'Dostępny'))
            else:
                unavailable_rooms.append((r, 'Zajęty'))

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'confirm':
            reservation.status = 'confirmed'
            reservation.save()
            messages.success(request, "Rezerwacja została potwierdzona.")

        elif action == 'cancel':
            reservation.status = 'cancelled'
            reservation.save()
            if reservation.room.status == 'occupied':
                reservation.room.status = 'available'
                reservation.room.save()
            messages.success(request, "Rezerwacja została anulowana.")

        elif action == 'check_in':
            reservation.status = 'checked_in'
            reservation.save()
            room = reservation.room
            room.status = 'occupied'
            room.save()
            messages.success(request, f"Gość zameldowany. Pokój {room.number} oznaczony jako ZAJĘTY.")

        elif action == 'check_out':
            if remaining > 0:
                messages.error(request, f"Nie można wymeldować gościa. Nieopłacone saldo: {remaining} PLN.")
                return redirect('employee:reservation_detail', pk=pk)

            reservation.status = 'completed'
            reservation.save()
            room = reservation.room
            room.status = 'dirty'
            room.save()
            messages.success(request, f"Gość wymeldowany. Pokój {room.number} oznaczony jako DO SPRZĄTANIA.")

        elif action == 'change_room':
            new_room_id = request.POST.get('new_room_id')
            confirm_force = request.POST.get('confirm_force') == 'yes'

            if new_room_id:
                new_room = get_object_or_404(Room, pk=new_room_id)

                if new_room.status == 'maintenance':
                    messages.error(request, f"Pokój {new_room.number} jest w naprawie. Nie można go przypisać.")
                    return redirect('employee:reservation_detail', pk=pk)

                if not confirm_force:
                    if new_room.status == 'occupied':
                        messages.error(request, f"Pokój {new_room.number} jest oznaczony jako ZAJĘTY. Użyj przycisku 'Wymuś', aby zignorować.")
                        return redirect('employee:reservation_detail', pk=pk)
                    
                    if new_room.status == 'dirty':
                        messages.warning(request, f"Pokój {new_room.number} jest DO SPRZĄTANIA. Użyj przycisku 'Wymuś', aby zignorować.")
                        return redirect('employee:reservation_detail', pk=pk)

                    collision = Reservation.objects.filter(
                        room=new_room,
                        check_in__lt=reservation.check_out,
                        check_out__gt=reservation.check_in,
                        status__in=['pending', 'confirmed', 'checked_in']
                    ).exclude(id=reservation.id).exists()
                    
                    if collision:
                        messages.error(request, f"Pokój {new_room.number} ma kolizję terminów. Użyj przycisku 'Wymuś'.")
                        return redirect('employee:reservation_detail', pk=pk)

                reservation.room = new_room
                reservation.save()
                messages.success(request, f"Pokój zmieniony na {new_room.number}.")

        elif action == 'add_payment':
            try:
                amount_str = request.POST.get('amount', '').strip().replace(' ', '').replace('\xa0', '').replace(',', '.')
                amount = Decimal(amount_str)
                
                method = request.POST.get('payment_method')
                status = request.POST.get('payment_status')
                date = request.POST.get('payment_date')
                Payment.objects.create(
                    reservation=reservation,
                    amount=amount,
                    payment_method=method,
                    payment_status=status,
                    payment_date=date
                )
                messages.success(request, "Płatność dodana.")
            except Exception as e:
                messages.error(request, f"Błąd kwoty: {e}")

        elif action == 'delete_payment':
            payment_id = request.POST.get('payment_id')
            payment = get_object_or_404(Payment, pk=payment_id, reservation=reservation)
            payment.delete()
            messages.success(request, "Płatność została usunięta.")

        elif action == 'edit_payment':
            payment_id = request.POST.get('payment_id')
            payment = get_object_or_404(Payment, pk=payment_id, reservation=reservation)
            try:
                amount_str = request.POST.get('amount', '').strip().replace(' ', '').replace('\xa0', '').replace(',', '.')
                payment.amount = Decimal(amount_str)
                payment.payment_date = request.POST.get('payment_date')
                payment.payment_method = request.POST.get('payment_method')
                payment.payment_status = request.POST.get('payment_status')
                payment.transaction_id = request.POST.get('transaction_id')
                payment.save()
                messages.success(request, "Płatność zaktualizowana.")
            except Exception as e:
                messages.error(request, f"Błąd edycji płatności: {e}")

        elif action == 'add_charge':
            try:
                amount_str = request.POST.get('charge_amount', '').strip().replace(' ', '').replace('\xa0', '')
                charge_amount = Decimal(amount_str.replace(',', '.'))
                
                charge_description = request.POST.get('charge_description')

                if charge_amount > 0:
                    reservation.total_price = Decimal(reservation.total_price or 0) + charge_amount

                    note_entry = f"Dnia {timezone.now().date()} doliczono {charge_amount} PLN: {charge_description}"
                    if reservation.notes:
                        reservation.notes += f"\n{note_entry}"
                    else:
                        reservation.notes = note_entry

                    reservation.save()
                    messages.success(request, f"Doliczono opłatę {charge_amount} PLN.")
                else:
                    messages.error(request, "Kwota musi być dodatnia.")
            except Exception as e:
                print(f"Błąd add_charge: {e}")
                messages.error(request, f"Wystąpił błąd: {e}")

        return redirect('employee:reservation_detail', pk=pk)

    context = {
        'reservation': reservation,
        'payments': payments,
        'total_paid': total_paid,
        'remaining': remaining,
        'candidate_rooms': candidate_rooms,
        'unavailable_rooms': unavailable_rooms,
        'current_room': reservation.room
    }
    return render(request, 'employee/reservation_detail.html', context)

@login_required
@employee_required
def employee_guests(request):
    if not request.user.is_superuser and request.user.employee_profile.role in ['technician', 'maid']:
        messages.error(request, "Brak uprawnień do listy gości.")
        return redirect('employee:dashboard')

    guests = GuestProfile.objects.all()
    return render(request, 'employee/guests.html', {'guests': guests})

@login_required
@employee_required
def employee_guest_detail(request, pk):
    if not request.user.is_superuser and request.user.employee_profile.role in ['technician', 'maid']:
        messages.error(request, "Brak uprawnień do szczegółów gościa.")
        return redirect('employee:dashboard')

    guest = get_object_or_404(GuestProfile, pk=pk)
    return render(request, 'employee/guest_detail.html', {'guest': guest})

@login_required
@employee_required
def employee_create_reservation(request):
    if not request.user.is_superuser and request.user.employee_profile.role in ['technician', 'maid']:
        messages.error(request, "Brak uprawnień do tworzenia rezerwacji.")
        return redirect('employee:dashboard')

    if request.method == 'POST':
        guest_id = request.POST.get('guest_id')
        room_id = request.POST.get('room_id')
        if not room_id:
            messages.error(request, "Nie wybrano pokoju.")
            return redirect('employee:reservation_create')

        check_in_str = request.POST.get('check_in_date')
        check_out_str = request.POST.get('check_out_date')

        try:
            check_in = datetime.strptime(check_in_str, '%Y-%m-%d').date()
            check_out = datetime.strptime(check_out_str, '%Y-%m-%d').date()

            if check_in >= check_out:
                messages.error(request, "Data zameldowania musi być wcześniejsza niż data wymeldowania.")
                return redirect('employee:reservation_create')

            with transaction.atomic():
                room = get_object_or_404(Room, pk=room_id)
                
                if room.status == 'maintenance':
                    messages.error(request, "Ten pokój jest wyłączony z użytku (konserwacja).")
                    return redirect('employee:reservation_create')

                if guest_id:
                    guest = get_object_or_404(GuestProfile, pk=guest_id)
                else:
                    name = request.POST.get('name')
                    surname = request.POST.get('surname')
                    email = request.POST.get('email')
                    phone = request.POST.get('phone')

                    if not name or not surname:
                        messages.error(request, "Imię i nazwisko są wymagane dla nowego gościa.")
                        return redirect('employee:reservation_create')

                    base_username = email.split('@')[0] if email else f"{name}.{surname}".lower()
                    clean_username = re.sub(r'[^a-zA-Z0-9@.+-_]', '', base_username) or 'guest'

                    username = clean_username
                    counter = 1
                    while User.objects.filter(username=username).exists():
                        username = f"{clean_username}{counter}"
                        counter += 1
                    
                    user = User.objects.create_user(username=username, email=email, password=phone or 'hotel123')
                    user.first_name = name
                    user.last_name = surname
                    user.save()
                    guest = GuestProfile.objects.create(user=user, phone_number=phone)

                conflicting_reservations = Reservation.objects.filter(
                    room=room,
                    check_in__lt=check_out,
                    check_out__gt=check_in,
                    status__in=['pending', 'confirmed', 'checked_in']
                ).exists()

                if conflicting_reservations:
                    messages.error(request, "Ten pokój jest już zajęty w wybranym terminie.")
                else:
                    reservation = Reservation(
                        guest=guest,
                        room=room,
                        check_in=check_in,
                        check_out=check_out,
                        number_of_guests=room.capacity,
                        status='confirmed',
                        reservation_pin=generate_pin()
                    )
                    total_price = compute_reservation_price(reservation)
                    reservation.total_price = total_price
                    reservation.save()

                    messages.success(request, f"Rezerwacja utworzona pomyślnie. Cena: {total_price} PLN")
                    return redirect('employee:reservations')

        except ValueError:
            messages.error(request, "Nieprawidłowy format daty.")
        except Exception as e:
            messages.error(request, f"Wystąpił błąd: {e}")

    guests = GuestProfile.objects.all()
    rooms = Room.objects.all()
    return render(request, 'employee/create_reservation.html', {'guests': guests, 'available_rooms': rooms})


# Guest Views

@login_required
@guest_required
def guest_dashboard(request):
    guest_profile, created = GuestProfile.objects.get_or_create(user=request.user)
    active_reservations = Reservation.objects.filter(
        guest=guest_profile,
        status__in=['pending', 'confirmed', 'checked_in']
    ).order_by('check_in')
    return render(request, 'guest/dashboard.html', {'reservations': active_reservations})

@login_required
@guest_required
def guest_reservations(request):
    guest_profile, created = GuestProfile.objects.get_or_create(user=request.user)
    reservations = Reservation.objects.filter(guest=guest_profile).order_by('-created_at')
    return render(request, 'guest/reservations.html', {'reservations': reservations})

@login_required
@guest_required
def guest_reservation_detail(request, pk):
    guest_profile, created = GuestProfile.objects.get_or_create(user=request.user)
    reservation = get_object_or_404(Reservation, pk=pk, guest=guest_profile)

    if not reservation.reservation_pin:
        reservation.reservation_pin = generate_pin()
        reservation.save()

    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'pay_online':
            try:
                with transaction.atomic():
                    Payment.objects.create(
                        reservation=reservation,
                        amount=reservation.total_price,
                        payment_method='online',
                        payment_status='completed'
                    )
                    reservation.status = 'confirmed'
                    reservation.save()
                messages.success(request, "Płatność przyjęta pomyślnie. Rezerwacja potwierdzona.")
            except Exception as e:
                messages.error(request, "Wystąpił błąd podczas przetwarzania płatności online. Spróbuj ponownie lub skontaktuj się z obsługą.")
                logger = logging.getLogger(__name__)
                logger.error(f"Błąd płatności online dla rezerwacji {reservation.id}: {str(e)}", exc_info=True)
            return redirect('guest:reservation_detail', pk=pk)

    return render(request, 'guest/reservation_detail.html', {'reservation': reservation})

@login_required
@guest_required
def guest_create_reservation(request):
    if request.method == 'POST':
        room_id = request.POST.get('room_id')
        if not room_id:
            messages.error(request, "Nie wybrano pokoju.")
            return redirect('guest:create_reservation')

        check_in_str = request.POST.get('check_in_date')
        check_out_str = request.POST.get('check_out_date')
        payment_method = request.POST.get('payment_method', 'cash')

        try:
            check_in = datetime.strptime(check_in_str, '%Y-%m-%d').date()
            check_out = datetime.strptime(check_out_str, '%Y-%m-%d').date()

            if check_in < timezone.now().date():
                messages.error(request, "Nie można rezerwować dat w przeszłości.")
                return redirect('guest:create_reservation')

            if check_in >= check_out:
                messages.error(request, "Data zameldowania musi być wcześniejsza niż data wymeldowania.")
                return redirect('guest:create_reservation')

            with transaction.atomic():
                room = get_object_or_404(Room, pk=room_id)
                
                if room.status == 'maintenance':
                    messages.error(request, "Ten pokój jest wyłączony z użytku (konserwacja).")
                    return redirect('guest:create_reservation')
                
                conflicting_reservations = Reservation.objects.filter(
                    room=room,
                    check_in__lt=check_out,
                    check_out__gt=check_in,
                    status__in=['pending', 'confirmed', 'checked_in']
                ).exists()

                if conflicting_reservations:
                    messages.error(request, "Ten pokój jest niestety zajęty w wybranym terminie.")
                else:
                    guest_profile, created = GuestProfile.objects.get_or_create(user=request.user)

                    reservation = Reservation(
                        guest=guest_profile,
                        room=room,
                        check_in=check_in,
                        check_out=check_out,
                        number_of_guests=room.capacity,
                        status='pending',
                        reservation_pin=generate_pin()
                    )
                    reservation.payment_method = payment_method
                    total_price = compute_reservation_price(reservation)
                    reservation.total_price = total_price
                    reservation.save()

                    payment_msg = "Opłacono online" if payment_method == 'online' else "Płatność gotówką na miejscu"
                    messages.success(request, f"Rezerwacja złożona! Kwota: {total_price} PLN. ({payment_msg})")

                    return redirect('guest:reservation_detail', pk=reservation.pk)

        except ValueError:
            messages.error(request, "Błąd formatu daty.")

    rooms = Room.objects.filter(status='available')
    return render(request, 'guest/create_reservation.html', {'available_rooms': rooms})


@login_required
@guest_required
def guest_profile(request):
    guest, created = GuestProfile.objects.get_or_create(user=request.user)
    if request.method == 'POST':
        guest.phone_number = request.POST.get('phone_number')
        request.user.first_name = request.POST.get('first_name')
        request.user.last_name = request.POST.get('last_name')
        request.user.save()
        guest.save()
        messages.success(request, "Profil zaktualizowany.")
    return render(request, 'guest/profile.html', {'guest': guest})


@login_required
@guest_required
def guest_cancel_reservation(request, pk):
    guest_profile, created = GuestProfile.objects.get_or_create(user=request.user)
    reservation = get_object_or_404(Reservation, pk=pk, guest=guest_profile)

    if request.method == 'POST':
        if reservation.status in ['pending', 'confirmed'] and reservation.check_in > timezone.now().date():
            reservation.status = 'cancelled'
            reservation.save()
            messages.success(request, "Rezerwacja została anulowana.")
        else:
            messages.error(request, "Nie można anulować tej rezerwacji (zbyt późno lub zły status).")

    return redirect('guest:reservation_detail', pk=pk)


# Public Views

def register_view(request):
    if request.method == 'POST':
        email = request.POST.get('email')
        password = request.POST.get('password')
        first_name = request.POST.get('name')
        last_name = request.POST.get('surname')
        phone = request.POST.get('phone')
        username_input = request.POST.get('username')

        username = username_input if username_input else email

        if User.objects.filter(username=username).exists():
            messages.error(request, "Użytkownik o takiej nazwie już istnieje.")
            return redirect('register')
        if User.objects.filter(email=email).exists():
            messages.error(request, "Użytkownik o takim emailu już istnieje.")
            return redirect('register')
            
        user = User.objects.create_user(username=username, email=email, password=password)
        user.first_name = first_name
        user.last_name = last_name
        user.save()
        
        GuestProfile.objects.create(user=user, phone_number=phone)
        
        messages.success(request, "Konto utworzone! Zaloguj się.")
        return redirect('login')

    return render(request, 'guest/register.html')

def public_create_reservation(request):
    """Umożliwia rezerwację bez logowania."""
    if request.method == 'POST':
        room_id = request.POST.get('room_id')
        check_in_str = request.POST.get('check_in_date')
        check_out_str = request.POST.get('check_out_date')

        email = request.POST.get('email')
        first_name = request.POST.get('name')
        last_name = request.POST.get('surname')
        phone = request.POST.get('phone')
        
        create_account_flag = request.POST.get('create_account')
        password_input = request.POST.get('password')
        username_input = request.POST.get('username')

        try:
            check_in = datetime.strptime(check_in_str, '%Y-%m-%d').date()
            check_out = datetime.strptime(check_out_str, '%Y-%m-%d').date()

            if check_in >= check_out:
                messages.error(request, "Data zameldowania musi być wcześniejsza niż data wymeldowania.")
                return redirect('public_create_reservation')

            with transaction.atomic():
                if request.user.is_authenticated:
                    user = request.user
                    guest_profile = user.guest_profile
                else:
                    if User.objects.filter(email=email).exists():
                        messages.error(request, "Konto z tym adresem email już istnieje. Zaloguj się.")
                        return redirect('login')

                    if create_account_flag == 'on':
                        final_password = password_input if password_input else phone
                        final_username = username_input if username_input else email
                    else:
                        final_password = phone
                        final_username = email

                    user = User.objects.create_user(username=final_username, email=email, password=final_password)
                    user.first_name = first_name
                    user.last_name = last_name
                    user.save()
                    guest_profile = GuestProfile.objects.create(user=user, phone_number=phone)

                    login(request, user)

                    if create_account_flag != 'on':
                        messages.info(request, f"Utworzono konto tymczasowe dla tej rezerwacji. Twój login: {email}, hasło: {phone}")

                room = get_object_or_404(Room, pk=room_id)

                reservation = Reservation(
                    guest=guest_profile,
                    room=room,
                    check_in=check_in,
                    check_out=check_out,
                    number_of_guests=room.capacity,
                    status='pending',
                    reservation_pin=generate_pin()
                )
                reservation.payment_method = 'online' if request.POST.get('payment_method') == 'online' else 'cash'
                reservation.total_price = compute_reservation_price(reservation)
                reservation.save()

                messages.success(request, f"Rezerwacja przyjęta! Witaj {user.first_name}.")
                return redirect('guest:reservation_detail', pk=reservation.pk)

        except ValueError:
            messages.error(request, "Błąd danych.")
        except Exception as e:
            messages.error(request, f"Wystąpił błąd: {e}")

    rooms = Room.objects.filter(status='available')
    return render(request, 'guest/create_reservation_public.html', {'available_rooms': rooms})


@login_required
@employee_required
def employee_housekeeping(request):
    if request.method == 'POST':
        action = request.POST.get('action')
        room_id = request.POST.get('room_id')
        room = get_object_or_404(Room, pk=room_id)
        
        if action == 'mark_clean':
            room.status = 'available'
            room.save()
            messages.success(request, f"Pokój {room.number} oznaczony jako POSPRZĄTANY (Wolny).")
        elif action == 'report_issue':
            title = request.POST.get('issue_title')
            desc = request.POST.get('issue_description')
            if not title or not desc:
                messages.error(request, "Tytuł i opis usterki są wymagane.")
                return redirect('employee:housekeeping')
            room.status = 'maintenance'
            timestamp = timezone.now().strftime('%Y-%m-%d %H:%M')
            room.notes = f"{room.notes}\n[HK {timestamp}] {title}: {desc}".strip()
            room.save()
            messages.warning(request, f"Zgłoszono usterkę w pokoju {room.number}. Status: W NAPRAWIE.")

        return redirect('employee:housekeeping')

    rooms = Room.objects.all().order_by('number')
    return render(request, 'employee/housekeeping.html', {'rooms': rooms})

@login_required
@employee_required
def employee_maintenance(request):
    if request.method == 'POST':
        action = request.POST.get('action')
        room_id = request.POST.get('room_id')
        room = get_object_or_404(Room, pk=room_id)
        
        if action == 'repair_done':
            room.status = 'dirty'
            room.notes = ""
            room.save()
            messages.success(request, f"Usterka w pokoju {room.number} usunięta. Pokój przekazany do sprzątania.")
        elif action == 'clean_done':
            room.status = 'available'
            room.save()
            messages.success(request, f"Pokój {room.number} oznaczony jako POSPRZĄTANY (Wolny).")

        elif action == 'report_issue':
            title = request.POST.get('issue_title')
            desc = request.POST.get('issue_description')
            if not title or not desc:
                messages.error(request, "Tytuł i opis usterki są wymagane.")
                return redirect('employee:maintenance')
            room.status = 'maintenance'
            timestamp = timezone.now().strftime('%Y-%m-%d %H:%M')
            room.notes = f"{room.notes}\n[TECH {timestamp}] {title}: {desc}".strip()
            room.save()
            messages.warning(request, f"Zgłoszono usterkę w pokoju {room.number}. Status: W NAPRAWIE.")

        return redirect('employee:maintenance')

    maintenance_rooms = Room.objects.filter(status='maintenance').order_by('number')
    dirty_rooms = Room.objects.filter(status='dirty').order_by('number')
    return render(request, 'employee/maintenance.html', {'maintenance_rooms': maintenance_rooms, 'dirty_rooms': dirty_rooms})


# Manager Views

@login_required

@login_required
@employee_required
def manager_employees(request):
    if not request.user.is_superuser and (not hasattr(request.user, 'employee_profile') or request.user.employee_profile.role != 'manager'):
        messages.error(request, "Brak uprawnień menadżerskich.")
        return redirect('employee:dashboard')

    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'add_employee':
            first_name = request.POST.get('first_name')
            last_name = request.POST.get('last_name')
            email = request.POST.get('email')
            role = request.POST.get('role')
            password = request.POST.get('password')

            username = email.split('@')[0]
            if User.objects.filter(username=username).exists():
                 username = f"{username}_{random.randint(100,999)}"

            if User.objects.filter(email=email).exists():
                 messages.error(request, "Użytkownik o takim emailu już istnieje.")
            else:
                try:
                    with transaction.atomic():
                        user = User.objects.create_user(username=username, email=email, password=password)
                        user.first_name = first_name
                        user.last_name = last_name
                        user.save()
                        EmployeeProfile.objects.create(user=user, role=role)
                        messages.success(request, f"Pracownik {first_name} {last_name} dodany pomyślnie.")
                except Exception as e:
                    messages.error(request, f"Błąd podczas dodawania: {e}")
        
        elif action == 'toggle_active':
            user_id = request.POST.get('user_id')
            user = get_object_or_404(User, pk=user_id)
            if user.is_superuser:
                 messages.error(request, "Nie można dezaktywować administratora.")
            else:
                user.is_active = not user.is_active
                user.save()
                status = "aktywowany" if user.is_active else "dezaktywowany"
                messages.success(request, f"Pracownik {user.get_full_name()} został {status}.")

        return redirect('employee:manager_employees')

    employees = EmployeeProfile.objects.all().select_related('user').order_by('role')
    return render(request, 'employee/manager_employees.html', {'employees': employees})

@login_required
@employee_required
def manager_reports(request):
    if not request.user.is_superuser and (not hasattr(request.user, 'employee_profile') or request.user.employee_profile.role != 'manager'):
        messages.error(request, "Brak uprawnień menadżerskich.")
        return redirect('employee:dashboard')

    today = timezone.now().date()
    current_month = today.month
    current_year = today.year

    revenue_data = Payment.objects.filter(
        payment_date__month=current_month, 
        payment_date__year=current_year, 
        payment_status='completed'
    ).aggregate(Sum('amount'))
    monthly_revenue = revenue_data['amount__sum'] or 0

    total_rooms = Room.objects.count()
    occupied_rooms = Room.objects.filter(status='occupied').count()
    occupancy_rate = 0
    if total_rooms > 0:
        occupancy_rate = round((occupied_rooms / total_rooms) * 100, 1)

    cancelled_reservations = Reservation.objects.filter(status='cancelled').order_by('-created_at')[:20]

    context = {
        'monthly_revenue': monthly_revenue,
        'occupancy_rate': occupancy_rate,
        'cancelled_reservations': cancelled_reservations,
        'total_rooms': total_rooms,
        'occupied_rooms': occupied_rooms,
        'current_date': today
    }
    return render(request, 'employee/manager_reports.html', context)

@login_required
@employee_required
def manager_report_pdf(request):
    if not canvas:
        messages.error(request, "Brak biblioteki reportlab. Zainstaluj: pip install reportlab")
        return redirect('employee:manager_reports')
        
    if not request.user.is_superuser and (not hasattr(request.user, 'employee_profile') or request.user.employee_profile.role != 'manager'):
        messages.error(request, "Brak uprawnień.")
        return redirect('employee:dashboard')

    today = timezone.now().date()
    current_month = today.month
    current_year = today.year

    revenue_data = Payment.objects.filter(
        payment_date__month=current_month, 
        payment_date__year=current_year, 
        payment_status='completed'
    ).aggregate(Sum('amount'))
    monthly_revenue = revenue_data['amount__sum'] or 0
    
    total_rooms = Room.objects.count()
    occupied_rooms = Room.objects.filter(status='occupied').count()
    occupancy_rate = 0
    if total_rooms > 0:
        occupancy_rate = round((occupied_rooms / total_rooms) * 100, 1)

    buffer = io.BytesIO()
    p = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4

    p.setFont("Helvetica-Bold", 18)
    p.drawString(50, height - 50, clean_text(f"Raport Managerski - {today.strftime('%m/%Y')}"))
    
    p.setFont("Helvetica", 12)
    p.drawString(50, height - 80, clean_text(f"Wygenerowano: {today.strftime('%Y-%m-%d')}"))
    
    p.drawString(50, height - 120, clean_text(f"Przychod (miesiac): {monthly_revenue} PLN"))
    p.drawString(50, height - 140, clean_text(f"Oblozenie (teraz): {occupancy_rate}%"))
    p.drawString(50, height - 160, clean_text(f"Zajete pokoje: {occupied_rooms} / {total_rooms}"))
    
    p.showPage()
    p.save()
    
    buffer.seek(0)
    return FileResponse(buffer, as_attachment=True, filename=f"raport_{current_month}_{current_year}.pdf")

@login_required
def reservation_invoice_pdf(request, pk):
    if not canvas:
        messages.error(request, "Brak biblioteki reportlab. Zainstaluj: pip install reportlab")
        return redirect('home')

    reservation = get_object_or_404(Reservation, pk=pk)

    is_owner = hasattr(request.user, 'guest_profile') and reservation.guest == request.user.guest_profile
    is_staff = hasattr(request.user, 'employee_profile') or request.user.is_superuser
    
    if not (is_owner or is_staff):
        messages.error(request, "Brak uprawnień.")
        return redirect('home')

    buffer = io.BytesIO()
    p = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4

    p.setFont("Helvetica-Bold", 16)
    p.drawString(50, height - 50, clean_text(f"Faktura / Rachunek #{reservation.id}"))
    
    p.setFont("Helvetica", 12)
    p.drawString(50, height - 80, clean_text(f"Data: {timezone.now().strftime('%Y-%m-%d')}"))
    p.drawString(50, height - 100, "Hotel XYZ")

    p.drawString(50, height - 140, "Nabywca:")
    p.drawString(50, height - 155, clean_text(f"{reservation.guest.user.first_name} {reservation.guest.user.last_name}"))
    p.drawString(50, height - 170, clean_text(f"{reservation.guest.user.email}"))

    p.drawString(50, height - 210, "Szczegoly rezerwacji:")
    p.drawString(50, height - 230, clean_text(f"Pokoj: {reservation.room.number} ({reservation.room.get_room_type_display()})"))
    p.drawString(50, height - 250, clean_text(f"Termin: {reservation.check_in} - {reservation.check_out}"))
    p.drawString(50, height - 270, clean_text(f"Liczba gosci: {reservation.number_of_guests}"))

    p.drawString(50, height - 310, clean_text(f"Status: {reservation.get_status_display()}"))
    p.drawString(50, height - 330, clean_text(f"Metoda platnosci: {reservation.get_payment_method_display()}"))

    p.setFont("Helvetica-Bold", 14)
    p.drawString(50, height - 370, clean_text(f"Razem: {reservation.total_price} PLN"))
    
    p.showPage()
    p.save()
    
    buffer.seek(0)
    return FileResponse(buffer, as_attachment=True, filename=f"faktura_{reservation.id}.pdf")

@login_required
@employee_required
def employee_pricing(request):
    if not request.user.is_superuser and request.user.employee_profile.role in ['technician', 'maid']:
        messages.error(request, "Brak uprawnień do cennika.")
        return redirect('employee:dashboard')

    seasons = Season.objects.all().order_by('start_date')
    season_prices = SeasonPrice.objects.all().select_related('season')

    context = {
        'seasons': seasons,
        'season_prices': season_prices
    }
    return render(request, 'employee/pricing.html', context)

@login_required
@employee_required
def employee_room_create(request):
    if not request.user.is_superuser and request.user.employee_profile.role in ['technician', 'maid']:
        messages.error(request, "Brak uprawnień do dodawania pokoi.")
        return redirect('employee:dashboard')

    if request.method == 'POST':
        number = request.POST.get('number')
        capacity = request.POST.get('capacity')
        price = request.POST.get('price')
        room_type = request.POST.get('room_type') or request.POST.get('type')

        if number and capacity and price and room_type:
            try:
                Room.objects.create(
                    number=number,
                    capacity=capacity,
                    price=price,
                    room_type=room_type,
                    status='available'
                )
                messages.success(request, "Pokój dodany.")
                return redirect('employee:rooms')
            except Exception as e:
                messages.error(request, f"Błąd: {e}")
        else:
            messages.error(request, "Wszystkie pola są wymagane.")
    return render(request, 'employee/room_create.html')


# API Views

def room_availability_api(request):
    """API zwracające dostępne pokoje w zadanym terminie (JSON)."""
    check_in_str = request.GET.get('check_in_date')
    check_out_str = request.GET.get('check_out_date')
    guests_str = request.GET.get('number_of_guests', '1')

    if not check_in_str or not check_out_str:
        return JsonResponse({'error': 'Brak dat'}, status=400)

    try:
        check_in = datetime.strptime(check_in_str, '%Y-%m-%d').date()
        check_out = datetime.strptime(check_out_str, '%Y-%m-%d').date()
        guests = int(guests_str)
    except ValueError:
        return JsonResponse({'error': 'Błędny format danych'}, status=400)

    rooms = Room.objects.exclude(status='maintenance').filter(capacity__gte=guests)

    available_now = []

    for room in rooms:
        collision = Reservation.objects.filter(
            room=room,
            check_in__lt=check_out,
            check_out__gt=check_in,
            status__in=['pending', 'confirmed', 'checked_in']
        ).exists()

        if not collision:
            dummy_res = Reservation(room=room, check_in=check_in, check_out=check_out)
            total_price = compute_reservation_price(dummy_res)

            days = (check_out - check_in).days
            avg_price = total_price / days if days > 0 else total_price

            available_now.append({
                'id': room.id,
                'number': room.number,
                'price': str(round(avg_price, 2)),
                'total_price': str(total_price),
                'average_price': str(round(avg_price, 2)),
                'capacity': room.capacity,
                'room_type': room.get_room_type_display()
            })

    return JsonResponse({
        'available_now': available_now,
        'available_later': [],
        'capacity_issue': len(available_now) == 0 and not rooms.exists()
    })