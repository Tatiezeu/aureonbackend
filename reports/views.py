from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.decorators import action
from .models import Report, Expense
from .serializers import ReportSerializer, ExpenseSerializer
from rest_framework.permissions import AllowAny
from io import BytesIO
from django.http import FileResponse
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.units import cm
from reportlab.lib import colors
from datetime import datetime

class ReportViewSet(viewsets.ModelViewSet):
    """
    Standard CRUD for reports.
    Supports nested 'expenses' create/update in the serializer.
    Also includes:
    - /<id>/expenses/ for listing report's expenses
    - /<id>/print/ for downloading a themed PDF
    """
    serializer_class = ReportSerializer
    permission_classes = [AllowAny]  # change to IsAuthenticated if needed

    def get_queryset(self):
        queryset = Report.objects.all().prefetch_related('expenses').order_by('-created_at')
        date = self.request.query_params.get('date')
        if date:
            queryset = queryset.filter(created_at__date=date)
        return queryset

    def create(self, request, *args, **kwargs):
        """Override POST to properly handle nested expenses."""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        report = serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        """Override PUT to properly handle nested expenses."""
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        report = serializer.save()
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=True, methods=['get'])
    def expenses(self, request, pk=None):
        """Return all expenses for a specific report."""
        report = self.get_object()
        serializer = ExpenseSerializer(report.expenses.all(), many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['get'], url_path='print')
    def print_report(self, request, pk=None):
        """Generate PDF for the report."""
        report = self.get_object()
        buffer = BytesIO()
        p = canvas.Canvas(buffer, pagesize=A4)
        width, height = A4

        def fmt(amount):
            try:
                return f"XAF {int(amount):,}"
            except Exception:
                return f"XAF {amount}"

        left_margin = 2 * cm
        right_margin = width - 2 * cm
        y = height - 2.2 * cm

        # Header
        p.setFillColor(colors.HexColor("#0B3D91"))
        p.rect(0, height - 2.2 * cm, width, 2.2 * cm, stroke=0, fill=1)

        p.setFillColor(colors.white)
        p.setFont("Helvetica-Bold", 18)
        p.drawString(left_margin, height - 1.5 * cm, report.hotel_name.upper())
        p.setFont("Helvetica", 10)
        p.drawRightString(right_margin, height - 1.5 * cm, f"Report Date: {report.created_at.strftime('%Y-%m-%d')}")

        y = height - 3.0 * cm

        # Revenues
        p.setFillColor(colors.HexColor("#D4AF37"))
        p.setFont("Helvetica-Bold", 12)
        p.drawString(left_margin, y, "Revenues")
        y -= 0.7 * cm
        p.setFillColor(colors.black)
        p.setFont("Helvetica", 11)
        p.drawString(left_margin, y, "Hébergement:")
        p.drawRightString(right_margin, y, fmt(report.montant_hebergement))
        y -= 0.6 * cm
        p.drawString(left_margin, y, "Bar:")
        p.drawRightString(right_margin, y, fmt(report.montant_bar))
        y -= 0.6 * cm
        p.drawString(left_margin, y, "Cuisine:")
        p.drawRightString(right_margin, y, fmt(report.montant_cuisine))
        y -= 0.6 * cm

        p.setStrokeColor(colors.HexColor("#BFBFBF"))
        p.setLineWidth(1)
        p.line(left_margin, y, right_margin, y)
        y -= 0.8 * cm

        # Total
        p.setFont("Helvetica-Bold", 12)
        p.setFillColor(colors.HexColor("#D4AF37"))
        p.drawString(left_margin, y, "Total Amount:")
        p.drawRightString(right_margin, y, fmt(report.total_amount))
        y -= 1.0 * cm

        # Expenses
        p.setFillColor(colors.HexColor("#D4AF37"))
        p.setFont("Helvetica-Bold", 12)
        p.drawString(left_margin, y, "Expenses:")
        y -= 0.6 * cm

        p.setFont("Helvetica", 11)
        p.setFillColor(colors.black)
        expenses = report.expenses.all().order_by('created_at')
        if expenses.exists():
            for exp in expenses:
                if y < 3 * cm:
                    p.showPage()
                    width, height = A4
                    left_margin = 2 * cm
                    right_margin = width - 2 * cm
                    y = height - 2.5 * cm
                    p.setFont("Helvetica", 11)
                p.drawString(left_margin, y, f"- {exp.label}")
                p.drawRightString(right_margin, y, fmt(exp.amount))
                y -= 0.6 * cm
        else:
            p.drawString(left_margin, y, "No expenses recorded.")
            y -= 0.6 * cm

        y -= 0.2 * cm
        if y < 3 * cm:
            p.showPage()
            width, height = A4
            left_margin = 2 * cm
            right_margin = width - 2 * cm
            y = height - 2.5 * cm

        p.setStrokeColor(colors.HexColor("#BFBFBF"))
        p.setLineWidth(1)
        p.line(left_margin, y, right_margin, y)
        y -= 0.9 * cm

        p.setFont("Helvetica-Bold", 12)
        p.setFillColor(colors.HexColor("#1F7A1F"))
        p.drawString(left_margin, y, "Reste en Caisse:")
        p.drawRightString(right_margin, y, fmt(report.reste_en_caisse))
        y -= 1.0 * cm

        if y < 2 * cm:
            p.showPage()
            width, height = A4
            left_margin = 2 * cm
            right_margin = width - 2 * cm
            y = height - 2.5 * cm

        p.setFont("Helvetica-Oblique", 9)
        p.setFillColor(colors.grey)
        p.drawString(left_margin, 1.6 * cm, "Generated by Aureon Hotel System")
        p.drawRightString(right_margin, 1.6 * cm, f"Generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

        p.showPage()
        p.save()
        buffer.seek(0)

        filename = f"{report.hotel_name.replace(' ', '_')}_Report_{report.created_at.strftime('%Y-%m-%d')}.pdf"
        return FileResponse(buffer, as_attachment=True, filename=filename)


class ExpenseViewSet(viewsets.ModelViewSet):
    """Direct CRUD for expenses if managed separately."""
    queryset = Expense.objects.select_related('report').all()
    serializer_class = ExpenseSerializer
    permission_classes = [AllowAny]
