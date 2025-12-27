#!/usr/bin/env python
"""
Skrypt do tworzenia testowych kont użytkowników
Uruchom: python3 manage.py shell < create_test_users.py
lub: python3 create_test_users.py
"""

import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.contrib.auth.models import User
from core.models import Guest, Employee

def create_test_users():
    # Sprawdź czy użytkownicy już istnieją
    if User.objects.filter(username='guest').exists():
        print("Użytkownik 'guest' już istnieje. Pomijam...")
    else:
        # Utworzenie użytkownika gościa
        guest_user = User.objects.create_user('guest', 'guest@example.com', 'guest123')
        guest_user.first_name = 'Jan'
        guest_user.last_name = 'Kowalski'
        guest_user.save()
        guest = Guest.objects.create(
            user=guest_user,
            name='Jan',
            surname='Kowalski',
            email='guest@example.com',
            phone='123456789'
        )
        print("✓ Utworzono konto gościa:")
        print("  Login: guest")
        print("  Hasło: guest123")
        print("  Email: guest@example.com")
    
    if User.objects.filter(username='employee').exists():
        print("\nUżytkownik 'employee' już istnieje. Pomijam...")
    else:
        # Utworzenie użytkownika pracownika
        employee_user = User.objects.create_user('employee', 'employee@example.com', 'employee123')
        employee_user.first_name = 'Anna'
        employee_user.last_name = 'Nowak'
        employee_user.save()
        employee = Employee.objects.create(
            user=employee_user,
            role='receptionist',
            phone='987654321'
        )
        print("\n✓ Utworzono konto pracownika:")
        print("  Login: employee")
        print("  Hasło: employee123")
        print("  Email: employee@example.com")
        print("  Rola: Recepcjonista")
    
    if User.objects.filter(username='manager').exists():
        print("\nUżytkownik 'manager' już istnieje. Pomijam...")
    else:
        # Utworzenie użytkownika menedżera
        manager_user = User.objects.create_user('manager', 'manager@example.com', 'manager123')
        manager_user.first_name = 'Piotr'
        manager_user.last_name = 'Wiśniewski'
        manager_user.save()
        manager = Employee.objects.create(
            user=manager_user,
            role='manager',
            phone='555666777'
        )
        print("\n✓ Utworzono konto menedżera:")
        print("  Login: manager")
        print("  Hasło: manager123")
        print("  Email: manager@example.com")
        print("  Rola: Menedżer")
    
    print("\n" + "="*50)
    print("Konta testowe zostały utworzone!")
    print("="*50)
    print("\nMożesz teraz zalogować się na:")
    print("  http://127.0.0.1:8000/login/")
    print("\nLub użyć panelu admin:")
    print("  http://127.0.0.1:8000/admin/")

if __name__ == '__main__':
    create_test_users()

