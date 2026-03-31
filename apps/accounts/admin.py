from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from .models import UserProfile, Address


class UserProfileInline(admin.StackedInline):
    model = UserProfile
    can_delete = False
    verbose_name_plural = 'Profile'
    fields = ('display_name', 'bio', 'county', 'avatar', 'email_verified', 'phone_verified', 'stripe_customer_id', 'shipping_address', 'messaging_disabled', 'messaging_disabled_reason', 'messaging_disabled_at')
    readonly_fields = ('email_verification_token', 'created_at', 'updated_at')


class UserAdmin(BaseUserAdmin):
    inlines = (UserProfileInline,)
    list_display = ('username', 'email', 'first_name', 'last_name', 'is_staff', 'date_joined')
    list_filter = ('is_staff', 'is_superuser', 'is_active', 'date_joined')
    search_fields = ('username', 'email', 'first_name', 'last_name')


# Re-register UserAdmin
admin.site.unregister(User)
admin.site.register(User, UserAdmin)


@admin.action(description='Disable messaging for selected profiles')
def disable_messaging(modeladmin, request, queryset):
    from django.utils import timezone
    queryset.update(messaging_disabled=True, messaging_disabled_at=timezone.now())
    modeladmin.message_user(request, f'{queryset.count()} profile(s) messaging disabled.')


@admin.action(description='Enable messaging for selected profiles')
def enable_messaging(modeladmin, request, queryset):
    queryset.update(messaging_disabled=False, messaging_disabled_at=None)
    modeladmin.message_user(request, f'{queryset.count()} profile(s) messaging enabled.')


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'display_name', 'county', 'email_verified', 'phone_verified', 'messaging_disabled', 'created_at')
    list_filter = ('email_verified', 'phone_verified', 'messaging_disabled', 'county', 'created_at')
    search_fields = ('user__username', 'user__email', 'display_name', 'county')
    readonly_fields = ('email_verification_token', 'created_at', 'updated_at')
    actions = [disable_messaging, enable_messaging]
    fieldsets = (
        ('User Info', {
            'fields': ('user', 'display_name', 'bio', 'avatar')
        }),
        ('Location', {
            'fields': ('county', 'shipping_address')
        }),
        ('Verification', {
            'fields': ('email_verified', 'email_verification_token', 'phone_verified')
        }),
        ('Payment', {
            'fields': ('stripe_customer_id',)
        }),
        ('Messaging', {
            'fields': ('messaging_disabled', 'messaging_disabled_reason', 'messaging_disabled_at'),
            'classes': ('collapse',),
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at')
        }),
    )


@admin.register(Address)
class AddressAdmin(admin.ModelAdmin):
    list_display = ('user', 'full_name', 'city', 'state', 'postal_code', 'is_default')
    list_filter = ('state', 'is_default')
    search_fields = ('user__username', 'full_name', 'city', 'postal_code')
    readonly_fields = ('created_at', 'updated_at')
