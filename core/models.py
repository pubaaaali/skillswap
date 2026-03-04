"""
SkillSwap models: UserProfile, Skill, ServiceRequest, Bid, Exchange, LedgerEntry, Review, Message.

Double-entry invariant: when an exchange is settled, two LedgerEntries are created atomically
such that the sum of hours_delta across all entries remains zero.
"""

from django.db import models
from django.contrib.auth.models import User
from django.conf import settings


class UserProfile(models.Model):
    """Extended profile linked one-to-one to Django's built-in User."""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    time_balance = models.DecimalField(
        max_digits=8, decimal_places=2, default=5.00,
        help_text="Available time credits (hours)"
    )
    bio = models.TextField(blank=True, max_length=500)
    avatar = models.ImageField(upload_to='avatars/', blank=True, null=True)

    def __str__(self):
        return f"{self.user.username} ({self.time_balance}h)"


class Skill(models.Model):
    """A skill that a user offers to teach or provide."""
    LEVEL_CHOICES = [
        ('beginner', 'Beginner'),
        ('intermediate', 'Intermediate'),
        ('advanced', 'Advanced'),
        ('expert', 'Expert'),
    ]
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='skills')
    title = models.CharField(max_length=100)
    description = models.TextField(max_length=500)
    level = models.CharField(max_length=20, choices=LEVEL_CHOICES, default='intermediate')
    duration_hours = models.DecimalField(
        max_digits=4, decimal_places=1, default=1.0,
        help_text="Typical session duration in hours"
    )
    is_available = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.title} ({self.user.username})"


class ServiceRequest(models.Model):
    """A request posted by a user seeking a particular skill."""
    STATUS_OPEN = 'open'
    STATUS_ACCEPTED = 'accepted'
    STATUS_COMPLETED = 'completed'
    STATUS_CANCELLED = 'cancelled'
    STATUS_CHOICES = [
        (STATUS_OPEN, 'Open'),
        (STATUS_ACCEPTED, 'Accepted'),
        (STATUS_COMPLETED, 'Completed'),
        (STATUS_CANCELLED, 'Cancelled'),
    ]

    requester = models.ForeignKey(User, on_delete=models.CASCADE, related_name='requests_posted')
    title = models.CharField(max_length=150)
    skill_category = models.CharField(max_length=100)
    description = models.TextField(max_length=1000)
    hours_required = models.DecimalField(
        max_digits=4, decimal_places=1,
        help_text="Estimated hours needed (must be > 0)"
    )
    preferred_schedule = models.CharField(max_length=200, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_OPEN)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.title} — {self.requester.username} ({self.status})"

    @property
    def bid_count(self):
        return self.bids.count()


class Bid(models.Model):
    """A provider's bid on an open ServiceRequest."""
    STATUS_PENDING = 'pending'
    STATUS_ACCEPTED = 'accepted'
    STATUS_REJECTED = 'rejected'
    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pending'),
        (STATUS_ACCEPTED, 'Accepted'),
        (STATUS_REJECTED, 'Rejected'),
    ]

    request = models.ForeignKey(ServiceRequest, on_delete=models.CASCADE, related_name='bids')
    provider = models.ForeignKey(User, on_delete=models.CASCADE, related_name='bids_made')
    proposed_hours = models.DecimalField(max_digits=4, decimal_places=1)
    message = models.TextField(max_length=500)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        # A user can only bid once per request
        unique_together = ('request', 'provider')
        ordering = ['created_at']

    def __str__(self):
        return f"Bid by {self.provider.username} on '{self.request.title}' ({self.proposed_hours}h)"


class Exchange(models.Model):
    """
    An active session created when a requester accepts a bid.
    Tracks dual-confirmation before ledger settlement.
    """
    STATUS_PENDING = 'pending'
    STATUS_REQUESTER_CONFIRMED = 'requester_confirmed'
    STATUS_PROVIDER_CONFIRMED = 'provider_confirmed'
    STATUS_COMPLETED = 'completed'
    STATUS_DISPUTED = 'disputed'
    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pending'),
        (STATUS_REQUESTER_CONFIRMED, 'Requester Confirmed'),
        (STATUS_PROVIDER_CONFIRMED, 'Provider Confirmed'),
        (STATUS_COMPLETED, 'Completed'),
        (STATUS_DISPUTED, 'Disputed'),
    ]

    service_request = models.OneToOneField(ServiceRequest, on_delete=models.CASCADE, related_name='exchange')
    bid = models.OneToOneField(Bid, on_delete=models.CASCADE, related_name='exchange')
    agreed_hours = models.DecimalField(max_digits=4, decimal_places=1)
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default=STATUS_PENDING)
    requester_confirmed = models.BooleanField(default=False)
    provider_confirmed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Exchange: {self.service_request.title} ({self.status})"

    @property
    def requester(self):
        return self.service_request.requester

    @property
    def provider(self):
        return self.bid.provider


class LedgerEntry(models.Model):
    """
    Double-entry ledger: each settlement creates two entries summing to zero.
    type='earn' → provider receives hours; type='spend' → requester pays hours.
    """
    TYPE_EARN = 'earn'
    TYPE_SPEND = 'spend'
    TYPE_CHOICES = [
        (TYPE_EARN, 'Earn'),
        (TYPE_SPEND, 'Spend'),
    ]

    exchange = models.ForeignKey(Exchange, on_delete=models.CASCADE, related_name='ledger_entries')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='ledger_entries')
    hours_delta = models.DecimalField(max_digits=6, decimal_places=2)  # positive=earn, negative=spend
    entry_type = models.CharField(max_length=10, choices=TYPE_CHOICES)
    balance_after = models.DecimalField(max_digits=8, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        sign = '+' if self.hours_delta > 0 else ''
        return f"{self.user.username}: {sign}{self.hours_delta}h (bal: {self.balance_after}h)"


class Review(models.Model):
    """Post-exchange review from one party about the other."""
    exchange = models.ForeignKey(Exchange, on_delete=models.CASCADE, related_name='reviews')
    reviewer = models.ForeignKey(User, on_delete=models.CASCADE, related_name='reviews_given')
    reviewee = models.ForeignKey(User, on_delete=models.CASCADE, related_name='reviews_received')
    rating = models.PositiveSmallIntegerField(choices=[(i, i) for i in range(1, 6)])
    comment = models.TextField(max_length=500, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('exchange', 'reviewer')

    def __str__(self):
        return f"Review by {self.reviewer.username} for {self.reviewee.username}: {self.rating}/5"


class Message(models.Model):
    """Simple message thread attached to a ServiceRequest."""
    service_request = models.ForeignKey(ServiceRequest, on_delete=models.CASCADE, related_name='messages')
    sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name='messages_sent')
    content = models.TextField(max_length=1000)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f"Message from {self.sender.username} on '{self.service_request.title}'"
