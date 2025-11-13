from django.contrib import admin
from .models import SwitchRequest

@admin.register(SwitchRequest)
class SwitchRequestAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'requested_role', 'status', 'created_at')
    list_filter = ('status', 'requested_role', 'created_at')
    search_fields = ('user__username', 'user__email', 'requested_role', 'message')
    readonly_fields = ('created_at',)
    ordering = ('-created_at',)
