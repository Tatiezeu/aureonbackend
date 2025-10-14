from decimal import Decimal
from rest_framework import serializers
from django.db.models import Sum
from .models import Report, Expense


class ExpenseSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(required=False)

    class Meta:
        model = Expense
        fields = ['id', 'label', 'amount', 'created_at']
        read_only_fields = ['created_at']


class ReportSerializer(serializers.ModelSerializer):
    # Writable fields mapping to model
    hebergement = serializers.DecimalField(source='montant_hebergement', max_digits=12, decimal_places=2)
    bar = serializers.DecimalField(source='montant_bar', max_digits=12, decimal_places=2)
    cuisine = serializers.DecimalField(source='montant_cuisine', max_digits=12, decimal_places=2)

    # Nested expenses
    expenses = ExpenseSerializer(many=True, required=False)

    # Computed fields
    total_amount = serializers.SerializerMethodField()
    total_expenses = serializers.SerializerMethodField()
    reste_en_caisse = serializers.SerializerMethodField()

    class Meta:
        model = Report
        fields = [
            'id', 'hotel_name',
            'hebergement', 'bar', 'cuisine',
            'total_amount', 'total_expenses', 'reste_en_caisse',
            'expenses', 'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at', 'total_amount', 'total_expenses', 'reste_en_caisse']

    # -----------------------------
    # Computed field getters
    # -----------------------------
    def get_total_amount(self, obj):
        return (obj.montant_hebergement or 0) + (obj.montant_bar or 0) + (obj.montant_cuisine or 0)

    def get_total_expenses(self, obj):
        return obj.expenses.aggregate(total=Sum('amount'))['total'] or 0

    def get_reste_en_caisse(self, obj):
        return self.get_total_amount(obj) - self.get_total_expenses(obj)

    # -----------------------------
    # Create / Update with nested expenses
    # -----------------------------
    def create(self, validated_data):
        expenses_data = validated_data.pop('expenses', [])
        report = Report.objects.create(**validated_data)
        for exp in expenses_data:
            Expense.objects.create(report=report, **exp)
        return report

    def update(self, instance, validated_data):
        expenses_data = validated_data.pop('expenses', None)

        # Update scalar fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        if expenses_data is not None:
            incoming_ids = []
            for exp in expenses_data:
                exp_id = exp.get('id')
                if exp_id:
                    try:
                        obj = Expense.objects.get(pk=exp_id, report=instance)
                        obj.label = exp.get('label', obj.label)
                        obj.amount = exp.get('amount', obj.amount)
                        obj.save()
                        incoming_ids.append(obj.id)
                    except Expense.DoesNotExist:
                        new_obj = Expense.objects.create(report=instance, **{k: v for k, v in exp.items() if k != 'id'})
                        incoming_ids.append(new_obj.id)
                else:
                    new_obj = Expense.objects.create(report=instance, label=exp['label'], amount=exp.get('amount', 0))
                    incoming_ids.append(new_obj.id)

            # Delete removed expenses
            instance.expenses.exclude(id__in=incoming_ids).delete()

        return instance
