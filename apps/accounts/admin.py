from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from .models import UserProfile, Address


# `county` is the pre-Pass-6 free-text field, now editable=False. Listing it
# as an ordinary field made every User and UserProfile change page a 500, so
# it is shown read-only next to the home_state / home_county FKs that replaced
# it.
class UserProfileInline(admin.StackedInline):
    model = UserProfile
    can_delete = False
    verbose_name_plural = 'Profile'
    fields = ('display_name', 'bio', 'home_state', 'home_county', 'county', 'avatar',
              'email_verified', 'phone_verified', 'stripe_customer_id', 'shipping_address',
              'messaging_disabled', 'messaging_disabled_reason', 'messaging_disabled_at')
    readonly_fields = ('county', 'email_verification_token', 'created_at', 'updated_at')
    autocomplete_fields = ('home_state', 'home_county')


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
    list_display = ('user', 'display_name', 'home_state', 'home_county', 'email_verified', 'phone_verified', 'messaging_disabled', 'created_at')
    list_filter = ('email_verified', 'phone_verified', 'messaging_disabled', 'home_state', 'created_at')
    search_fields = ('user__username', 'user__email', 'display_name', 'home_county__name')
    readonly_fields = ('county', 'email_verification_token', 'created_at', 'updated_at')
    autocomplete_fields = ('home_state', 'home_county')
    actions = [disable_messaging, enable_messaging]
    fieldsets = (
        ('User Info', {
            'fields': ('user', 'display_name', 'bio', 'avatar')
        }),
        ('Location', {
            'fields': ('home_state', 'home_county', 'county', 'shipping_address')
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
