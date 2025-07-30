# inventory/forms.py (append this to the existing content)

from django import forms
from .models import PurchaseOrderItem, Supplier, PurchaseOrder, Product, StockAdjustment, Customer # <--- ADD Customer

class SupplierForm(forms.ModelForm):
    class Meta:
        model = Supplier
        fields = ['name', 'contact_person', 'phone_number', 'email', 'address', 'notes']
        widgets = {
            'notes': forms.Textarea(attrs={'rows': 3}),
        }

class PurchaseOrderForm(forms.ModelForm):
    expected_delivery_date = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date'}),
        required=False
    )

    class Meta:
        model = PurchaseOrder
        fields = ['supplier', 'expected_delivery_date', 'status', 'notes']
        widgets = {
            'notes': forms.Textarea(attrs={'rows': 3}),
        }

PurchaseOrderItemFormSet = forms.inlineformset_factory(
    PurchaseOrder,
    PurchaseOrderItem,
    fields=['product', 'quantity', 'unit_cost'],
    extra=1,
    can_delete=True,
    widgets={
        'product': forms.Select(attrs={'class': 'w-full p-2 border rounded-lg'}),
        'quantity': forms.NumberInput(attrs={'class': 'w-full p-2 border rounded-lg'}),
        'unit_cost': forms.NumberInput(attrs={'class': 'w-full p-2 border rounded-lg'}),
    }
)

class StockAdjustmentForm(forms.ModelForm):
    quantity_change = forms.IntegerField(
        label="Quantity Change",
        help_text="Enter a positive number to add stock, or a negative number to remove stock."
    )

    class Meta:
        model = StockAdjustment
        fields = ['product', 'quantity_change', 'adjustment_type', 'notes']
        widgets = {
            'notes': forms.Textarea(attrs={'rows': 3}),
        }

# --- NEW FORM FOR CUSTOMER ---
class CustomerForm(forms.ModelForm):
    class Meta:
        model = Customer
        fields = ['first_name', 'last_name', 'email', 'phone_number', 'address', 'notes']
        widgets = {
            'address': forms.Textarea(attrs={'rows': 3}),
            'notes': forms.Textarea(attrs={'rows': 3}),
        }