"""
Views for SkillSwap.

Auth: landing, register, login, logout
Profile: view, edit, skill CRUD
Marketplace: list, create request, request detail, bid submission, accept bid
Exchanges: detail, confirm, dispute
Ledger: history
AJAX endpoints: bid submit, marketplace filter, send message
"""

import json
from decimal import Decimal

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib import messages
from django.db import transaction
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_POST

from .models import (
    UserProfile, Skill, ServiceRequest, Bid, Exchange, LedgerEntry, Review, Message
)
from .forms import (
    RegistrationForm, LoginForm, UserProfileForm, UserEditForm,
    SkillForm, ServiceRequestForm, BidForm, ReviewForm, MessageForm,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_or_create_profile(user):
    """Return UserProfile for user, creating it with default balance if absent."""
    profile, _ = UserProfile.objects.get_or_create(
        user=user,
        defaults={'time_balance': Decimal('5.00')}
    )
    return profile


def _settle_exchange(exchange):
    """
    Atomically settle an exchange: debit requester, credit provider.
    Creates two LedgerEntry records so Sigma(hours_delta) = 0 (double-entry invariant).
    """
    with transaction.atomic():
        requester_profile = _get_or_create_profile(exchange.requester)
        provider_profile = _get_or_create_profile(exchange.provider)
        hours = exchange.agreed_hours

        requester_profile.time_balance -= hours
        requester_profile.save()

        provider_profile.time_balance += hours
        provider_profile.save()

        LedgerEntry.objects.create(
            exchange=exchange,
            user=exchange.requester,
            hours_delta=-hours,
            entry_type=LedgerEntry.TYPE_SPEND,
            balance_after=requester_profile.time_balance,
        )

        LedgerEntry.objects.create(
            exchange=exchange,
            user=exchange.provider,
            hours_delta=hours,
            entry_type=LedgerEntry.TYPE_EARN,
            balance_after=provider_profile.time_balance,
        )

        exchange.status = Exchange.STATUS_COMPLETED
        exchange.completed_at = timezone.now()
        exchange.service_request.status = ServiceRequest.STATUS_COMPLETED
        exchange.service_request.save()
        exchange.save()


# ---------------------------------------------------------------------------
# Auth views
# ---------------------------------------------------------------------------

def landing(request):
    """Public landing page."""
    if request.user.is_authenticated:
        return redirect('core:dashboard')
    stats = {
        'total_users': User.objects.count(),
        'open_requests': ServiceRequest.objects.filter(status=ServiceRequest.STATUS_OPEN).count(),
        'completed_exchanges': Exchange.objects.filter(status=Exchange.STATUS_COMPLETED).count(),
    }
    return render(request, 'core/landing.html', {'stats': stats})


def register_view(request):
    """User registration."""
    if request.user.is_authenticated:
        return redirect('core:dashboard')

    form = RegistrationForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        user = form.save()
        UserProfile.objects.create(user=user, time_balance=Decimal('5.00'))
        login(request, user)
        messages.success(
            request,
            f'Welcome to SkillSwap, {user.first_name or user.username}! '
            'You start with 5.0 hours of credit.'
        )
        return redirect('core:profile_edit')

    return render(request, 'core/register.html', {'form': form})


def login_view(request):
    """User login."""
    if request.user.is_authenticated:
        return redirect('core:dashboard')

    form = LoginForm(request, data=request.POST or None)
    if request.method == 'POST' and form.is_valid():
        user = form.get_user()
        login(request, user)
        next_url = request.GET.get('next', '')
        return redirect(next_url or 'core:dashboard')

    return render(request, 'core/login.html', {'form': form})


@login_required
def logout_view(request):
    """User logout."""
    logout(request)
    messages.info(request, 'You have been logged out.')
    return redirect('core:landing')


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------

@login_required
def dashboard(request):
    """Main hub: balance, open requests, bids, exchanges, recent ledger."""
    profile = _get_or_create_profile(request.user)
    open_requests = (
        ServiceRequest.objects
        .filter(requester=request.user, status=ServiceRequest.STATUS_OPEN)
        .prefetch_related('bids')[:5]
    )
    my_bids = (
        Bid.objects
        .filter(provider=request.user)
        .select_related('request')[:5]
    )
    as_requester = Exchange.objects.filter(
        service_request__requester=request.user
    ).exclude(status=Exchange.STATUS_COMPLETED).select_related('bid__provider', 'service_request')[:3]
    as_provider = Exchange.objects.filter(
        bid__provider=request.user
    ).exclude(status=Exchange.STATUS_COMPLETED).select_related('service_request__requester')[:3]
    recent_ledger = LedgerEntry.objects.filter(user=request.user).select_related('exchange__service_request')[:5]

    context = {
        'profile': profile,
        'open_requests': open_requests,
        'my_bids': my_bids,
        'as_requester': as_requester,
        'as_provider': as_provider,
        'recent_ledger': recent_ledger,
    }
    return render(request, 'core/dashboard.html', context)


# ---------------------------------------------------------------------------
# Profile views
# ---------------------------------------------------------------------------

def profile_view(request, username):
    """Public user profile."""
    viewed_user = get_object_or_404(User, username=username)
    profile = _get_or_create_profile(viewed_user)
    skills = Skill.objects.filter(user=viewed_user, is_available=True)
    reviews = Review.objects.filter(reviewee=viewed_user).select_related('reviewer')[:10]
    avg_rating = None
    if reviews:
        avg_rating = round(sum(r.rating for r in reviews) / len(reviews), 1)

    context = {
        'viewed_user': viewed_user,
        'profile': profile,
        'skills': skills,
        'reviews': reviews,
        'avg_rating': avg_rating,
        'is_own_profile': request.user.is_authenticated and request.user == viewed_user,
    }
    return render(request, 'core/profile.html', context)


@login_required
def profile_edit(request):
    """Edit own profile."""
    profile = _get_or_create_profile(request.user)
    user_form = UserEditForm(request.POST or None, instance=request.user)
    profile_form = UserProfileForm(request.POST or None, request.FILES or None, instance=profile)

    if request.method == 'POST' and user_form.is_valid() and profile_form.is_valid():
        user_form.save()
        profile_form.save()
        messages.success(request, 'Profile updated.')
        return redirect('core:profile', username=request.user.username)

    context = {'user_form': user_form, 'profile_form': profile_form, 'profile': profile}
    return render(request, 'core/profile_edit.html', context)


# ---------------------------------------------------------------------------
# Skill CRUD
# ---------------------------------------------------------------------------

@login_required
def skill_add(request):
    """Add a skill to the current user's profile."""
    form = SkillForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        skill = form.save(commit=False)
        skill.user = request.user
        skill.save()
        messages.success(request, f'Skill "{skill.title}" added.')
        return redirect('core:profile', username=request.user.username)
    return render(request, 'core/skill_form.html', {'form': form, 'action': 'Add'})


@login_required
def skill_edit(request, pk):
    """Edit an existing skill owned by the current user."""
    skill = get_object_or_404(Skill, pk=pk, user=request.user)
    form = SkillForm(request.POST or None, instance=skill)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, f'Skill "{skill.title}" updated.')
        return redirect('core:profile', username=request.user.username)
    return render(request, 'core/skill_form.html', {'form': form, 'action': 'Edit', 'skill': skill})


@login_required
def skill_delete(request, pk):
    """Delete a skill owned by the current user."""
    skill = get_object_or_404(Skill, pk=pk, user=request.user)
    if request.method == 'POST':
        skill.delete()
        messages.success(request, 'Skill removed.')
        return redirect('core:profile', username=request.user.username)
    return render(request, 'core/skill_confirm_delete.html', {'skill': skill})


# ---------------------------------------------------------------------------
# Marketplace
# ---------------------------------------------------------------------------

def marketplace(request):
    """Browse open service requests; supports AJAX live-filter."""
    queryset = (
        ServiceRequest.objects
        .filter(status=ServiceRequest.STATUS_OPEN)
        .select_related('requester')
        .prefetch_related('bids')
    )

    q = request.GET.get('q', '').strip()
    category = request.GET.get('category', '').strip()
    max_hours = request.GET.get('max_hours', '').strip()

    if q:
        queryset = queryset.filter(title__icontains=q) | ServiceRequest.objects.filter(
            status=ServiceRequest.STATUS_OPEN, description__icontains=q
        ).select_related('requester').prefetch_related('bids')
    if category:
        queryset = queryset.filter(skill_category__icontains=category)
    if max_hours:
        try:
            queryset = queryset.filter(hours_required__lte=Decimal(max_hours))
        except Exception:
            pass

    # Deduplicate when both title and description matched
    queryset = queryset.distinct()

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        results = [
            {
                'id': sr.id,
                'title': sr.title,
                'skill_category': sr.skill_category,
                'hours_required': str(sr.hours_required),
                'bid_count': sr.bids.count(),
                'requester': sr.requester.get_full_name() or sr.requester.username,
                'created_at': sr.created_at.strftime('%d %b %Y'),
                'url': f'/requests/{sr.id}/',
            }
            for sr in queryset
        ]
        return JsonResponse({'results': results, 'count': len(results)})

    categories = (
        ServiceRequest.objects
        .filter(status=ServiceRequest.STATUS_OPEN)
        .values_list('skill_category', flat=True)
        .distinct().order_by('skill_category')
    )
    context = {
        'requests': queryset,
        'q': q,
        'category': category,
        'max_hours': max_hours,
        'categories': categories,
    }
    return render(request, 'core/marketplace.html', context)


@login_required
def request_create(request):
    """Post a new service request."""
    profile = _get_or_create_profile(request.user)
    form = ServiceRequestForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        sr = form.save(commit=False)
        sr.requester = request.user
        sr.save()
        messages.success(request, 'Request posted! Providers can now bid.')
        return redirect('core:request_detail', pk=sr.pk)
    return render(request, 'core/request_form.html', {'form': form, 'profile': profile, 'action': 'Post'})


@login_required
def request_edit(request, pk):
    """Edit an open request owned by the current user."""
    sr = get_object_or_404(ServiceRequest, pk=pk, requester=request.user, status=ServiceRequest.STATUS_OPEN)
    form = ServiceRequestForm(request.POST or None, instance=sr)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Request updated.')
        return redirect('core:request_detail', pk=sr.pk)
    return render(request, 'core/request_form.html', {'form': form, 'action': 'Edit', 'sr': sr})


def request_detail(request, pk):
    """Show request, its bids, message thread. Supports bid submission via AJAX."""
    sr = get_object_or_404(ServiceRequest, pk=pk)
    bids = Bid.objects.filter(request=sr).select_related('provider')
    messages_qs = Message.objects.filter(service_request=sr).select_related('sender')

    existing_bid = None
    if request.user.is_authenticated:
        existing_bid = bids.filter(provider=request.user).first()

    bid_form = BidForm()
    message_form = MessageForm()

    context = {
        'sr': sr,
        'bids': bids,
        'existing_bid': existing_bid,
        'bid_form': bid_form,
        'message_form': message_form,
        'messages_qs': messages_qs,
        'is_requester': request.user.is_authenticated and sr.requester == request.user,
    }
    return render(request, 'core/request_detail.html', context)


@login_required
@require_POST
def bid_submit(request, pk):
    """Submit or update a bid. Returns JSON when called via AJAX."""
    sr = get_object_or_404(ServiceRequest, pk=pk, status=ServiceRequest.STATUS_OPEN)
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'

    if sr.requester == request.user:
        if is_ajax:
            return JsonResponse({'error': 'You cannot bid on your own request.'}, status=400)
        messages.error(request, 'You cannot bid on your own request.')
        return redirect('core:request_detail', pk=pk)

    existing = Bid.objects.filter(request=sr, provider=request.user).first()
    form = BidForm(request.POST, instance=existing)

    if form.is_valid():
        bid = form.save(commit=False)
        bid.request = sr
        bid.provider = request.user
        bid.status = Bid.STATUS_PENDING
        bid.save()

        if is_ajax:
            return JsonResponse({
                'success': True,
                'bid_id': bid.pk,
                'proposed_hours': str(bid.proposed_hours),
                'provider': request.user.get_full_name() or request.user.username,
                'message_text': bid.message,
                'is_update': existing is not None,
            })
        messages.success(request, 'Bid submitted.' if not existing else 'Bid updated.')
        return redirect('core:request_detail', pk=pk)

    if is_ajax:
        return JsonResponse({'errors': form.errors}, status=400)
    messages.error(request, 'Please correct the errors in your bid.')
    return redirect('core:request_detail', pk=pk)


@login_required
@require_POST
def bid_accept(request, pk, bid_id):
    """Accept a bid: creates an Exchange and locks agreed hours."""
    sr = get_object_or_404(ServiceRequest, pk=pk, requester=request.user, status=ServiceRequest.STATUS_OPEN)
    bid = get_object_or_404(Bid, pk=bid_id, request=sr, status=Bid.STATUS_PENDING)
    profile = _get_or_create_profile(request.user)

    if profile.time_balance < bid.proposed_hours:
        messages.error(
            request,
            f'Insufficient balance ({profile.time_balance}h). This bid requires {bid.proposed_hours}h.'
        )
        return redirect('core:request_detail', pk=pk)

    with transaction.atomic():
        Bid.objects.filter(request=sr).exclude(pk=bid_id).update(status=Bid.STATUS_REJECTED)
        bid.status = Bid.STATUS_ACCEPTED
        bid.save()
        sr.status = ServiceRequest.STATUS_ACCEPTED
        sr.save()
        exchange = Exchange.objects.create(
            service_request=sr,
            bid=bid,
            agreed_hours=bid.proposed_hours,
        )

    messages.success(
        request,
        f'Bid accepted! Exchange created for {bid.proposed_hours}h with {bid.provider.username}.'
    )
    return redirect('core:exchange_detail', pk=exchange.pk)


# ---------------------------------------------------------------------------
# Exchange views
# ---------------------------------------------------------------------------

@login_required
def exchange_detail(request, pk):
    """Exchange detail page with confirmation controls."""
    exchange = get_object_or_404(Exchange, pk=pk)

    if request.user not in [exchange.requester, exchange.provider]:
        messages.error(request, 'You do not have access to this exchange.')
        return redirect('core:dashboard')

    reviews = Review.objects.filter(exchange=exchange).select_related('reviewer', 'reviewee')
    user_review = reviews.filter(reviewer=request.user).first()
    can_review = (not user_review) and exchange.status == Exchange.STATUS_COMPLETED
    review_form = ReviewForm() if can_review else None
    ledger_entries = LedgerEntry.objects.filter(exchange=exchange)

    context = {
        'exchange': exchange,
        'reviews': reviews,
        'user_review': user_review,
        'review_form': review_form,
        'ledger_entries': ledger_entries,
        'is_requester': request.user == exchange.requester,
        'is_provider': request.user == exchange.provider,
    }
    return render(request, 'core/exchange_detail.html', context)


@login_required
@require_POST
def exchange_confirm(request, pk):
    """Confirm completion from one party; settle when both confirm."""
    exchange = get_object_or_404(Exchange, pk=pk)

    if exchange.status in [Exchange.STATUS_COMPLETED, Exchange.STATUS_DISPUTED]:
        messages.warning(request, 'This exchange is already finalised.')
        return redirect('core:exchange_detail', pk=pk)

    if request.user == exchange.requester and not exchange.requester_confirmed:
        exchange.requester_confirmed = True
        if exchange.provider_confirmed:
            _settle_exchange(exchange)
            messages.success(request, f'Exchange complete! {exchange.agreed_hours}h transferred.')
            return redirect('core:exchange_detail', pk=pk)
        exchange.status = Exchange.STATUS_REQUESTER_CONFIRMED
        exchange.save()

    elif request.user == exchange.provider and not exchange.provider_confirmed:
        exchange.provider_confirmed = True
        if exchange.requester_confirmed:
            _settle_exchange(exchange)
            messages.success(request, f'Exchange complete! {exchange.agreed_hours}h transferred.')
            return redirect('core:exchange_detail', pk=pk)
        exchange.status = Exchange.STATUS_PROVIDER_CONFIRMED
        exchange.save()

    else:
        messages.warning(request, 'You have already confirmed this exchange.')
        return redirect('core:exchange_detail', pk=pk)

    messages.info(request, 'Confirmation recorded. Waiting for the other party.')
    return redirect('core:exchange_detail', pk=pk)


@login_required
@require_POST
def exchange_dispute(request, pk):
    """Raise a dispute — no credits transferred."""
    exchange = get_object_or_404(Exchange, pk=pk)
    if request.user not in [exchange.requester, exchange.provider]:
        messages.error(request, 'Not authorised.')
        return redirect('core:dashboard')
    if exchange.status in [Exchange.STATUS_COMPLETED, Exchange.STATUS_DISPUTED]:
        messages.warning(request, 'This exchange is already finalised.')
        return redirect('core:exchange_detail', pk=pk)
    exchange.status = Exchange.STATUS_DISPUTED
    exchange.save()
    messages.warning(request, 'Dispute raised. No credits transferred. Please contact support.')
    return redirect('core:exchange_detail', pk=pk)


@login_required
def my_exchanges(request):
    """List all exchanges for current user."""
    as_requester = (
        Exchange.objects
        .filter(service_request__requester=request.user)
        .select_related('service_request', 'bid__provider')
    )
    as_provider = (
        Exchange.objects
        .filter(bid__provider=request.user)
        .select_related('service_request__requester', 'service_request')
    )
    return render(request, 'core/my_exchanges.html', {'as_requester': as_requester, 'as_provider': as_provider})


# ---------------------------------------------------------------------------
# Reviews
# ---------------------------------------------------------------------------

@login_required
@require_POST
def review_submit(request, exchange_pk):
    """Submit a post-exchange review."""
    exchange = get_object_or_404(Exchange, pk=exchange_pk, status=Exchange.STATUS_COMPLETED)
    if request.user not in [exchange.requester, exchange.provider]:
        messages.error(request, 'Not authorised.')
        return redirect('core:dashboard')
    if Review.objects.filter(exchange=exchange, reviewer=request.user).exists():
        messages.warning(request, 'You have already reviewed this exchange.')
        return redirect('core:exchange_detail', pk=exchange_pk)

    reviewee = exchange.provider if request.user == exchange.requester else exchange.requester
    form = ReviewForm(request.POST)
    if form.is_valid():
        review = form.save(commit=False)
        review.exchange = exchange
        review.reviewer = request.user
        review.reviewee = reviewee
        review.save()
        messages.success(request, 'Review submitted.')
    else:
        messages.error(request, 'Review could not be saved.')
    return redirect('core:exchange_detail', pk=exchange_pk)


# ---------------------------------------------------------------------------
# Ledger
# ---------------------------------------------------------------------------

@login_required
def ledger(request):
    """Full transaction history for the current user."""
    profile = _get_or_create_profile(request.user)
    entries = LedgerEntry.objects.filter(user=request.user).select_related('exchange__service_request')
    context = {'profile': profile, 'entries': entries}
    return render(request, 'core/ledger.html', context)


# ---------------------------------------------------------------------------
# Messages (AJAX)
# ---------------------------------------------------------------------------

@login_required
@require_POST
def message_send(request, pk):
    """Send a message on a service request thread."""
    sr = get_object_or_404(ServiceRequest, pk=pk)
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
    form = MessageForm(request.POST)
    if form.is_valid():
        msg = form.save(commit=False)
        msg.service_request = sr
        msg.sender = request.user
        msg.save()
        if is_ajax:
            return JsonResponse({
                'id': msg.pk,
                'sender': request.user.get_full_name() or request.user.username,
                'content': msg.content,
                'created_at': msg.created_at.strftime('%d %b %Y, %H:%M'),
            })
        return redirect('core:request_detail', pk=pk)
    if is_ajax:
        return JsonResponse({'errors': form.errors}, status=400)
    return redirect('core:request_detail', pk=pk)


# ---------------------------------------------------------------------------
# My requests / bids
# ---------------------------------------------------------------------------

@login_required
def my_requests(request):
    """All service requests posted by the current user."""
    requests_qs = ServiceRequest.objects.filter(requester=request.user).prefetch_related('bids')
    return render(request, 'core/my_requests.html', {'requests': requests_qs})


@login_required
def my_bids(request):
    """All bids placed by the current user."""
    bids = Bid.objects.filter(provider=request.user).select_related('request__requester')
    return render(request, 'core/my_bids.html', {'bids': bids})
