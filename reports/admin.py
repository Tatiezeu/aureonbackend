from django.contrib import admin
from .models import Report, Expense


class ExpenseInline(admin.TabularInline):
    model = Expense
    extra = 1
    readonly_fields = ['created_at']


@admin.register(Report)
class ReportAdmin(admin.ModelAdmin):
    list_display = ('hotel_name', 'created_at', 'total_amount', 'total_expenses', 'reste_en_caisse')
    search_fields = ('hotel_name',)
    inlines = [ExpenseInline]
    readonly_fields = ('total_amount', 'total_expenses', 'reste_en_caisse', 'created_at', 'updated_at')


@admin.register(Expense)
class ExpenseAdmin(admin.ModelAdmin):
    list_display = ('label', 'amount', 'report', 'created_at')
    list_filter = ('report',)
    search_fields = ('label',)
