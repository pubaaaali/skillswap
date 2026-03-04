from django.contrib import admin
from .models import UserProfile, Skill, ServiceRequest, Bid, Exchange, LedgerEntry, Review, Message


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'time_balance')
    search_fields = ('user__username',)


@admin.register(Skill)
class SkillAdmin(admin.ModelAdmin):
    list_display = ('title', 'user', 'level', 'duration_hours', 'is_available')
    list_filter = ('level', 'is_available')
    search_fields = ('title', 'user__username')


@admin.register(ServiceRequest)
class ServiceRequestAdmin(admin.ModelAdmin):
    list_display = ('title', 'requester', 'skill_category', 'hours_required', 'status', 'created_at')
    list_filter = ('status',)
    search_fields = ('title', 'requester__username')


@admin.register(Bid)
class BidAdmin(admin.ModelAdmin):
    list_display = ('request', 'provider', 'proposed_hours', 'status', 'created_at')
    list_filter = ('status',)


@admin.register(Exchange)
class ExchangeAdmin(admin.ModelAdmin):
    list_display = ('service_request', 'agreed_hours', 'status', 'created_at')
    list_filter = ('status',)


@admin.register(LedgerEntry)
class LedgerEntryAdmin(admin.ModelAdmin):
    list_display = ('user', 'exchange', 'hours_delta', 'entry_type', 'balance_after', 'created_at')
    list_filter = ('entry_type',)


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ('reviewer', 'reviewee', 'rating', 'created_at')


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ('sender', 'service_request', 'created_at')
