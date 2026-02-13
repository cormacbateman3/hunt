from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from .models import UserProfile


class UserProfileInline(admin.StackedInline):
    model = UserProfile
    can_delete = False
    verbose_name_plural = 'Profile'
    fields = ('display_name', 'bio', 'county', 'avatar', 'email_verified', 'stripe_customer_id')
    readonly_fields = ('email_verification_token', 'created_at', 'updated_at')


class UserAdmin(BaseUserAdmin):
    inlines = (UserProfileInline,)
    list_display = ('username', 'email', 'first_name', 'last_name', 'is_staff', 'date_joined')
    list_filter = ('is_staff', 'is_superuser', 'is_active', 'date_joined')
    search_fields = ('username', 'email', 'first_name', 'last_name')


# Re-register UserAdmin
admin.site.unregister(User)
admin.site.register(User, UserAdmin)


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'display_name', 'county', 'email_verified', 'created_at')
    list_filter = ('email_verified', 'county', 'created_at')
    search_fields = ('user__username', 'user__email', 'display_name', 'county')
    readonly_fields = ('email_verification_token', 'created_at', 'updated_at')
    fieldsets = (
        ('User Info', {
            'fields': ('user', 'display_name', 'bio', 'avatar')
        }),
        ('Location', {
            'fields': ('county',)
        }),
        ('Verification', {
            'fields': ('email_verified', 'email_verification_token')
        }),
        ('Payment', {
            'fields': ('stripe_customer_id',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at')
        }),
    )
