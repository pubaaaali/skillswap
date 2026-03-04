"""
Unit tests for SkillSwap.

Coverage:
- UserProfile creation and default balance
- Double-entry ledger invariant (_settle_exchange)
- ServiceRequest validation (hours > 0)
- Bid uniqueness constraint
- Exchange confirm/settle flow
- View: marketplace accessible without login
- View: dashboard requires login
- View: bid submission (AJAX)
- View: bid_accept creates Exchange and rejects other bids

Run with: python manage.py test core
"""

from decimal import Decimal
from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse

from .models import UserProfile, Skill, ServiceRequest, Bid, Exchange, LedgerEntry
from .views import _settle_exchange, _get_or_create_profile


# ─── Helpers ────────────────────────────────────────────────────────────────

def make_user(username, balance=Decimal('5.00')):
    """Create a user with a UserProfile."""
    user = User.objects.create_user(username=username, password='testpass123')
    profile = UserProfile.objects.create(user=user, time_balance=balance)
    return user, profile


def make_request(requester, hours=Decimal('1.0'), status='open'):
    return ServiceRequest.objects.create(
        requester=requester,
        title='Test request',
        skill_category='Testing',
        description='A test request',
        hours_required=hours,
        status=status,
    )


def make_bid(provider, sr, hours=Decimal('1.0')):
    return Bid.objects.create(
        request=sr,
        provider=provider,
        proposed_hours=hours,
        message='I can help!',
        status=Bid.STATUS_PENDING,
    )


# ─── Model tests ────────────────────────────────────────────────────────────

class UserProfileTest(TestCase):

    def test_profile_created_with_default_balance(self):
        user = User.objects.create_user(username='alice', password='pass')
        profile = UserProfile.objects.create(user=user, time_balance=Decimal('5.00'))
        self.assertEqual(profile.time_balance, Decimal('5.00'))

    def test_get_or_create_profile_creates_missing_profile(self):
        user = User.objects.create_user(username='bob', password='pass')
        # No profile yet
        profile = _get_or_create_profile(user)
        self.assertEqual(profile.time_balance, Decimal('5.00'))
        self.assertEqual(profile.user, user)

    def test_profile_str(self):
        user, profile = make_user('carol')
        self.assertIn('carol', str(profile))


class ServiceRequestTest(TestCase):

    def test_request_defaults_to_open(self):
        user, _ = make_user('dave')
        sr = make_request(user)
        self.assertEqual(sr.status, ServiceRequest.STATUS_OPEN)

    def test_bid_count_property(self):
        user, _ = make_user('eve')
        provider, _ = make_user('frank')
        sr = make_request(user)
        make_bid(provider, sr)
        self.assertEqual(sr.bid_count, 1)

    def test_request_str(self):
        user, _ = make_user('george')
        sr = make_request(user)
        self.assertIn('Test request', str(sr))


class BidUniquenessTest(TestCase):

    def test_duplicate_bid_raises_error(self):
        from django.db import IntegrityError
        user, _ = make_user('helen')
        provider, _ = make_user('ivan')
        sr = make_request(user)
        make_bid(provider, sr)
        with self.assertRaises(IntegrityError):
            make_bid(provider, sr)  # duplicate: same provider + same request


# ─── Double-entry ledger tests ───────────────────────────────────────────────

class LedgerSettlementTest(TestCase):

    def setUp(self):
        self.requester, self.req_profile = make_user('requester', Decimal('10.00'))
        self.provider, self.prov_profile = make_user('provider', Decimal('2.00'))
        self.sr = make_request(self.requester, hours=Decimal('2.0'), status='accepted')
        self.bid = make_bid(self.provider, self.sr, hours=Decimal('2.0'))
        self.bid.status = Bid.STATUS_ACCEPTED
        self.bid.save()
        self.exchange = Exchange.objects.create(
            service_request=self.sr,
            bid=self.bid,
            agreed_hours=Decimal('2.0'),
        )

    def test_settle_transfers_credits(self):
        _settle_exchange(self.exchange)
        self.req_profile.refresh_from_db()
        self.prov_profile.refresh_from_db()
        self.assertEqual(self.req_profile.time_balance, Decimal('8.00'))
        self.assertEqual(self.prov_profile.time_balance, Decimal('4.00'))

    def test_settle_creates_two_ledger_entries(self):
        _settle_exchange(self.exchange)
        entries = LedgerEntry.objects.filter(exchange=self.exchange)
        self.assertEqual(entries.count(), 2)

    def test_double_entry_invariant(self):
        """Sum of hours_delta across both entries must equal zero."""
        _settle_exchange(self.exchange)
        entries = LedgerEntry.objects.filter(exchange=self.exchange)
        total = sum(e.hours_delta for e in entries)
        self.assertEqual(total, Decimal('0.00'))

    def test_settle_marks_exchange_completed(self):
        _settle_exchange(self.exchange)
        self.exchange.refresh_from_db()
        self.assertEqual(self.exchange.status, Exchange.STATUS_COMPLETED)

    def test_settle_marks_request_completed(self):
        _settle_exchange(self.exchange)
        self.sr.refresh_from_db()
        self.assertEqual(self.sr.status, ServiceRequest.STATUS_COMPLETED)

    def test_earn_entry_is_positive(self):
        _settle_exchange(self.exchange)
        earn = LedgerEntry.objects.get(exchange=self.exchange, entry_type=LedgerEntry.TYPE_EARN)
        self.assertGreater(earn.hours_delta, 0)

    def test_spend_entry_is_negative(self):
        _settle_exchange(self.exchange)
        spend = LedgerEntry.objects.get(exchange=self.exchange, entry_type=LedgerEntry.TYPE_SPEND)
        self.assertLess(spend.hours_delta, 0)


# ─── View tests ──────────────────────────────────────────────────────────────

class MarketplaceViewTest(TestCase):

    def test_marketplace_accessible_without_login(self):
        response = self.client.get(reverse('core:marketplace'))
        self.assertEqual(response.status_code, 200)

    def test_marketplace_shows_open_requests(self):
        user, _ = make_user('seller')
        make_request(user)
        response = self.client.get(reverse('core:marketplace'))
        self.assertContains(response, 'Test request')

    def test_marketplace_ajax_returns_json(self):
        response = self.client.get(
            reverse('core:marketplace'),
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn('results', data)
        self.assertIn('count', data)


class DashboardViewTest(TestCase):

    def setUp(self):
        self.user, self.profile = make_user('dashuser')
        self.client.login(username='dashuser', password='testpass123')

    def test_dashboard_requires_login(self):
        self.client.logout()
        response = self.client.get(reverse('core:dashboard'))
        self.assertRedirects(response, reverse('core:login') + '?next=' + reverse('core:dashboard'))

    def test_dashboard_loads_for_authenticated_user(self):
        response = self.client.get(reverse('core:dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Dashboard')


class BidSubmitViewTest(TestCase):

    def setUp(self):
        self.requester, _ = make_user('req1', Decimal('5.00'))
        self.provider, _ = make_user('prov1', Decimal('5.00'))
        self.sr = make_request(self.requester)
        self.client.login(username='prov1', password='testpass123')

    def test_submit_bid_via_ajax(self):
        url = reverse('core:bid_submit', kwargs={'pk': self.sr.pk})
        response = self.client.post(
            url,
            {'proposed_hours': '1.0', 'message': 'I can help'},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
        self.assertEqual(Bid.objects.filter(request=self.sr, provider=self.provider).count(), 1)

    def test_requester_cannot_bid_on_own_request(self):
        self.client.login(username='req1', password='testpass123')
        url = reverse('core:bid_submit', kwargs={'pk': self.sr.pk})
        response = self.client.post(
            url,
            {'proposed_hours': '1.0', 'message': 'Self-bid'},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        self.assertEqual(response.status_code, 400)

    def test_bid_submit_invalid_hours(self):
        url = reverse('core:bid_submit', kwargs={'pk': self.sr.pk})
        response = self.client.post(
            url,
            {'proposed_hours': '-1', 'message': 'Bad hours'},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        self.assertEqual(response.status_code, 400)


class BidAcceptViewTest(TestCase):

    def setUp(self):
        self.requester, self.req_profile = make_user('reqacc', Decimal('5.00'))
        self.provider, _ = make_user('provacc', Decimal('3.00'))
        self.sr = make_request(self.requester)
        self.bid = make_bid(self.provider, self.sr)
        self.client.login(username='reqacc', password='testpass123')

    def test_accept_bid_creates_exchange(self):
        url = reverse('core:bid_accept', kwargs={'pk': self.sr.pk, 'bid_id': self.bid.pk})
        self.client.post(url)
        self.bid.refresh_from_db()
        self.sr.refresh_from_db()
        self.assertEqual(self.bid.status, Bid.STATUS_ACCEPTED)
        self.assertEqual(self.sr.status, ServiceRequest.STATUS_ACCEPTED)
        self.assertTrue(Exchange.objects.filter(service_request=self.sr).exists())

    def test_accept_bid_rejects_other_bids(self):
        other_provider, _ = make_user('otherprov', Decimal('3.00'))
        other_bid = make_bid(other_provider, self.sr, hours=Decimal('1.5'))
        url = reverse('core:bid_accept', kwargs={'pk': self.sr.pk, 'bid_id': self.bid.pk})
        self.client.post(url)
        other_bid.refresh_from_db()
        self.assertEqual(other_bid.status, Bid.STATUS_REJECTED)

    def test_accept_bid_fails_if_insufficient_balance(self):
        self.req_profile.time_balance = Decimal('0.50')
        self.req_profile.save()
        url = reverse('core:bid_accept', kwargs={'pk': self.sr.pk, 'bid_id': self.bid.pk})
        response = self.client.post(url)
        # Should redirect back to request detail (not create exchange)
        self.assertFalse(Exchange.objects.filter(service_request=self.sr).exists())


class ExchangeConfirmViewTest(TestCase):

    def setUp(self):
        self.requester, self.req_profile = make_user('confr', Decimal('5.00'))
        self.provider, self.prov_profile = make_user('confp', Decimal('2.00'))
        self.sr = make_request(self.requester, status='accepted')
        self.bid = make_bid(self.provider, self.sr)
        self.bid.status = Bid.STATUS_ACCEPTED
        self.bid.save()
        self.exchange = Exchange.objects.create(
            service_request=self.sr, bid=self.bid, agreed_hours=Decimal('1.0')
        )

    def test_both_confirm_settles_exchange(self):
        # Requester confirms
        self.client.login(username='confr', password='testpass123')
        self.client.post(reverse('core:exchange_confirm', kwargs={'pk': self.exchange.pk}))
        # Provider confirms
        self.client.login(username='confp', password='testpass123')
        self.client.post(reverse('core:exchange_confirm', kwargs={'pk': self.exchange.pk}))

        self.exchange.refresh_from_db()
        self.assertEqual(self.exchange.status, Exchange.STATUS_COMPLETED)

    def test_single_confirm_does_not_settle(self):
        self.client.login(username='confr', password='testpass123')
        self.client.post(reverse('core:exchange_confirm', kwargs={'pk': self.exchange.pk}))
        self.exchange.refresh_from_db()
        self.assertNotEqual(self.exchange.status, Exchange.STATUS_COMPLETED)


class RegistrationViewTest(TestCase):

    def test_register_creates_user_and_profile(self):
        response = self.client.post(reverse('core:register'), {
            'username': 'newuser',
            'email': 'new@example.com',
            'first_name': 'New',
            'last_name': 'User',
            'password1': 'securepwd99',
            'password2': 'securepwd99',
        })
        self.assertTrue(User.objects.filter(username='newuser').exists())
        user = User.objects.get(username='newuser')
        self.assertTrue(UserProfile.objects.filter(user=user).exists())
        profile = UserProfile.objects.get(user=user)
        self.assertEqual(profile.time_balance, Decimal('5.00'))

    def test_register_mismatched_passwords(self):
        response = self.client.post(reverse('core:register'), {
            'username': 'testuser2',
            'email': 'test2@example.com',
            'password1': 'securepwd99',
            'password2': 'different99',
        })
        self.assertFalse(User.objects.filter(username='testuser2').exists())
        self.assertEqual(response.status_code, 200)
