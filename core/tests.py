from django.test import TestCase
from django.contrib.auth.models import User
from datetime import date, timedelta
from decimal import Decimal
from .models import (
    GuestProfile, Room, Season, SeasonPrice,
    Reservation, Payment, compute_reservation_price
)


class ReservationTestCase(TestCase):
    """Test 1: Tworzenie rezerwacji - główny model biznesowy"""
    def setUp(self):
        self.user = User.objects.create_user(
            username='reservationguest',
            email='reservation@test.com'
        )
        self.guest = GuestProfile.objects.create(user=self.user)
        self.room = Room.objects.create(
            number='101',
            price=Decimal('150.00'),
            capacity=2
        )
        self.check_in = date.today() + timedelta(days=7)
        self.check_out = date.today() + timedelta(days=10)
    
    def test_reservation_creation(self):
        """Test tworzenia rezerwacji z wszystkimi polami"""
        reservation = Reservation.objects.create(
            guest=self.guest,
            room=self.room,
            check_in=self.check_in,
            check_out=self.check_out,
            number_of_guests=2,
            status='pending',
            total_price=Decimal('450.00'),
            payment_method='online'
        )
        self.assertIsNotNone(reservation.id)
        self.assertEqual(reservation.guest, self.guest)
        self.assertEqual(reservation.room, self.room)
        self.assertEqual(reservation.status, 'pending')
        self.assertEqual(reservation.total_price, Decimal('450.00'))
        self.assertIn('Rezerwacja', str(reservation))
        self.assertIn(self.user.username, str(reservation))


class ReservationIsPaidTestCase(TestCase):
    """Test 2: Właściwość is_paid dla różnych statusów rezerwacji"""
    def setUp(self):
        self.user = User.objects.create_user(
            username='paidguest',
            email='paid@test.com'
        )
        self.guest = GuestProfile.objects.create(user=self.user)
        self.room = Room.objects.create(
            number='201',
            price=Decimal('200.00')
        )
        self.check_in = date.today() + timedelta(days=5)
        self.check_out = date.today() + timedelta(days=8)
    
    def test_is_paid_property(self):
        """Test właściwości is_paid dla różnych statusów"""
        paid_statuses = ['confirmed', 'checked_in', 'completed']
        for status in paid_statuses:
            reservation = Reservation.objects.create(
                guest=self.guest,
                room=self.room,
                check_in=self.check_in,
                check_out=self.check_out,
                status=status
            )
            self.assertTrue(reservation.is_paid, 
                          f"Status {status} powinien oznaczać opłaconą rezerwację")

        unpaid_statuses = ['pending', 'cancelled']
        for status in unpaid_statuses:
            reservation = Reservation.objects.create(
                guest=self.guest,
                room=self.room,
                check_in=self.check_in + timedelta(days=10),
                check_out=self.check_out + timedelta(days=10),
                status=status
            )
            self.assertFalse(reservation.is_paid,
                           f"Status {status} nie powinien oznaczać opłaconej rezerwacji")


class PaymentTestCase(TestCase):
    """Test 3: Tworzenie płatności i relacje z rezerwacją"""
    def setUp(self):
        self.user = User.objects.create_user(
            username='paymentguest',
            email='payment@test.com'
        )
        self.guest = GuestProfile.objects.create(user=self.user)
        self.room = Room.objects.create(
            number='201',
            price=Decimal('200.00')
        )
        self.reservation = Reservation.objects.create(
            guest=self.guest,
            room=self.room,
            check_in=date.today() + timedelta(days=5),
            check_out=date.today() + timedelta(days=8),
            total_price=Decimal('600.00')
        )
    
    def test_payment_creation_and_relationship(self):
        """Test tworzenia płatności i relacji z rezerwacją"""
        payment1 = Payment.objects.create(
            reservation=self.reservation,
            amount=Decimal('300.00'),
            payment_method='cash',
            payment_status='completed'
        )
        payment2 = Payment.objects.create(
            reservation=self.reservation,
            amount=Decimal('300.00'),
            payment_method='online',
            payment_status='completed'
        )
        
        self.assertIsNotNone(payment1.id)
        self.assertEqual(payment1.amount, Decimal('300.00'))
        
        # Test relacji z rezerwacją
        payments = self.reservation.payments.all()
        self.assertEqual(payments.count(), 2)
        self.assertIn(payment1, payments)
        self.assertIn(payment2, payments)
        
        self.assertIn('Płatność', str(payment1))
        self.assertIn('300.00', str(payment1))


class ComputeReservationPriceWithSeasonTestCase(TestCase):
    """Test 4: Obliczanie ceny rezerwacji z sezonem"""
    def setUp(self):
        self.user = User.objects.create_user(
            username='seasonguest',
            email='season@test.com'
        )
        self.guest = GuestProfile.objects.create(user=self.user)
        self.room = Room.objects.create(
            number='401',
            price=Decimal('100.00'),
            room_type='double',
            capacity=2
        )

    def test_compute_price_with_season(self):
        """Test obliczania ceny z sezonem (mnożnik 1.5)"""
        season = Season.objects.create(
            name='Sezon letni',
            start_date=date(2024, 6, 1),
            end_date=date(2024, 6, 30)
        )
        
        # Test ceny sezonowej dla pokoju z mnożnikiem 1.5
        SeasonPrice.objects.create(
            season=season,
            room_type='double',
            price_multiplier=Decimal('1.5')
        )

        # Rezerwacja w sezonie
        check_in = date(2024, 6, 10)
        check_out = date(2024, 6, 13)
        
        reservation = Reservation(
            guest=self.guest,
            room=self.room,
            check_in=check_in,
            check_out=check_out
        )
        
        price = compute_reservation_price(reservation)
        expected_price = 3 * 100.00 * 1.5
        self.assertEqual(price, expected_price)
