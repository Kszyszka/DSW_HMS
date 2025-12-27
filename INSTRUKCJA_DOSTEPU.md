# Instrukcja dostępu do Hotel Management System

## 1. Uruchomienie serwera deweloperskiego

W terminalu, w katalogu projektu, wykonaj:

```bash
python3 manage.py runserver
```

Serwer uruchomi się na adresie: **http://127.0.0.1:8000/**

## 2. Utworzenie konta administratora (jeśli nie istnieje)

Jeśli nie masz jeszcze konta administratora, utwórz je:

```bash
python3 manage.py createsuperuser
```

Podaj:

-   Username (nazwa użytkownika)
-   Email (opcjonalnie)
-   Password (hasło - minimum 8 znaków)

## 3. Dostęp do aplikacji

### Panel Administracyjny Django

-   URL: **http://127.0.0.1:8000/admin/**
-   Zaloguj się używając konta superużytkownika utworzonego powyżej

### Interfejs Gościa

-   URL: **http://127.0.0.1:8000/**
-   Aby uzyskać dostęp jako gość:
    1. Zaloguj się do panelu admin: http://127.0.0.1:8000/admin/
    2. Utwórz użytkownika (Users → Add user)
    3. Utwórz profil gościa (Core → Guests → Add guest) i powiąż z utworzonym użytkownikiem
    4. Wyloguj się z admina
    5. Zaloguj się na stronie głównej używając danych tego użytkownika

### Interfejs Pracownika

-   URL: **http://127.0.0.1:8000/employee/**
-   Aby uzyskać dostęp jako pracownik:
    1. Zaloguj się do panelu admin: http://127.0.0.1:8000/admin/
    2. Utwórz użytkownika (Users → Add user)
    3. Utwórz profil pracownika (Core → Employees → Add employee) i powiąż z utworzonym użytkownikiem
    4. Wybierz rolę (recepcjonista, menedżer, pokojówka, administrator)
    5. Wyloguj się z admina
    6. Zaloguj się na stronie głównej używając danych tego użytkownika

## 4. Szybki start - Utworzenie testowych kont

Możesz utworzyć testowe konta używając Django shell:

```bash
python3 manage.py shell
```

Następnie wykonaj:

```python
from django.contrib.auth.models import User
from core.models import Guest, Employee

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

print("Utworzono konta:")
print("Gość - login: guest, hasło: guest123")
print("Pracownik - login: employee, hasło: employee123")
```

## 5. Struktura URL

-   **Strona główna**: http://127.0.0.1:8000/
-   **Logowanie**: http://127.0.0.1:8000/login/
-   **Panel gościa**: http://127.0.0.1:8000/guest/
-   **Panel pracownika**: http://127.0.0.1:8000/employee/
-   **Admin Django**: http://127.0.0.1:8000/admin/

## 6. Funkcjonalności

### Dla Gości:

-   Przeglądanie i tworzenie rezerwacji
-   Przeglądanie szczegółów rezerwacji i płatności
-   Edycja profilu

### Dla Pracowników:

-   Zarządzanie pokojami (dodawanie, edycja, zmiana statusu)
-   Zarządzanie rezerwacjami (potwierdzanie, anulowanie, zameldowanie, wymeldowanie)
-   Zarządzanie płatnościami
-   Przeglądanie i wyszukiwanie gości

## Uwaga

System automatycznie przekierowuje użytkowników do odpowiedniego panelu w zależności od ich roli (gość/pracownik) po zalogowaniu.
