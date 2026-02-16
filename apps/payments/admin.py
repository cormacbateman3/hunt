from django.contrib import admin
from .models import Transaction, PaymentTransaction


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ('id', 'listing', 'buyer', 'seller', 'sale_amount', 'status', 'created_at')
    list_filter = ('status', 'created_at')
    search_fields = ('listing__title', 'buyer__username', 'seller__username', 'stripe_payment_id')
    readonly_fields = ('created_at', 'updated_at', 'stripe_payment_id', 'stripe_session_id')
    date_hierarchy = 'created_at'

    fieldsets = (
        ('Transaction Information', {
            'fields': ('listing', 'buyer', 'seller', 'sale_amount')
        }),
        ('Payment Details', {
            'fields': ('status', 'stripe_payment_id', 'stripe_session_id')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def has_add_permission(self, request):
        return False


@admin.register(PaymentTransaction)
class PaymentTransactionAdmin(admin.ModelAdmin):
    list_display = ('id', 'order', 'status', 'stripe_payment_intent_id', 'created_at')
    list_filter = ('status', 'created_at')
    search_fields = ('order__listing__title', 'stripe_payment_intent_id', 'stripe_checkout_session_id')
    readonly_fields = ('created_at', 'updated_at')
    date_hierarchy = 'created_at'
