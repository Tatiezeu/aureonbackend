from decimal import Decimal
from django.db import models
from django.core.validators import MinValueValidator


class Report(models.Model):
    """
    Hotel report summary.
    - montant_hebergement, montant_bar, montant_cuisine: main revenue sources.
    - total_amount: computed sum of the three revenue sources (stored for convenience).
    - total_expenses: computed sum of all related Expense.amount (stored).
    - reste_en_caisse: total_amount - total_expenses (stored).
    """
    hotel_name = models.CharField(max_length=255)
    montant_hebergement = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))]
    )
    montant_bar = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))]
    )
    montant_cuisine = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))]
    )

    total_amount = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0.00'),
        help_text="Sum of hebergement, bar and cuisine (computed)"
    )
    total_expenses = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0.00'),
        help_text="Sum of related expenses (computed)"
    )
    reste_en_caisse = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0.00'),
        help_text="total_amount - total_expenses (computed)"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = "Report"
        verbose_name_plural = "Reports"

    def recalc_totals(self):
        # compute totals without saving
        total_amount = (
            (self.montant_hebergement or Decimal('0.00')) +
            (self.montant_bar or Decimal('0.00')) +
            (self.montant_cuisine or Decimal('0.00'))
        )
        # sum related expenses if instance already saved (has pk)
        total_expenses = Decimal('0.00')
        if self.pk:
            total_expenses = self.expenses.aggregate(
                total=models.Sum('amount')
            )['total'] or Decimal('0.00')
        # If no pk yet, expenses should be provided on serializer create and computed there.
        reste = total_amount - total_expenses
        return total_amount, total_expenses, reste

    def save(self, *args, **kwargs):
        # Ensure total_amount at least from self fields
        total_amount = (
            (self.montant_hebergement or Decimal('0.00')) +
            (self.montant_bar or Decimal('0.00')) +
            (self.montant_cuisine or Decimal('0.00'))
        )
        # If pk exists, compute expenses from DB; otherwise, keep default zeros (serializer will handle)
        if self.pk:
            total_expenses = self.expenses.aggregate(
                total=models.Sum('amount')
            )['total'] or Decimal('0.00')
        else:
            total_expenses = getattr(self, 'total_expenses', Decimal('0.00')) or Decimal('0.00')

        self.total_amount = total_amount
        self.total_expenses = total_expenses
        self.reste_en_caisse = self.total_amount - self.total_expenses
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.hotel_name} — {self.created_at.date()}"


class Expense(models.Model):
    """
    An expense entry belonging to a Report.
    """
    report = models.ForeignKey(
        Report, related_name='expenses', on_delete=models.CASCADE
    )
    label = models.CharField(max_length=255)
    amount = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))]
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = "Expense"
        verbose_name_plural = "Expenses"

    def save(self, *args, **kwargs):
        # Standard save; Report.save() will recompute totals when needed.
        super().save(*args, **kwargs)
        # After saving an expense, update parent totals.
        self.report.save()

    def delete(self, *args, **kwargs):
        # On delete update report totals
        parent = self.report
        super().delete(*args, **kwargs)
        parent.save()

    def __str__(self):
        return f"{self.label}: {self.amount}"
