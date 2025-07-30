# inventory/admin.py
from django.contrib import admin
from .models import Category, Product, Sale, SaleItem, Supplier, PurchaseOrder, PurchaseOrderItem, StockAdjustment, Customer

# Register Category directly
admin.site.register(Category)

# Custom Admin for the Product model (UPDATED for barcode)
@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'price', 'stock_quantity', 'reorder_level', 'barcode', 'is_active') # <--- ADD 'barcode'
    list_filter = ('category', 'is_active')
    search_fields = ('name', 'description', 'barcode') # <--- ADD 'barcode'
    # Add 'barcode' to fields if you want it editable in the main form, it's already there by default.

# Inline for SaleItem to be displayed within the Sale admin form
class SaleItemInline(admin.TabularInline):
    model = SaleItem
    extra = 1
    fields = ('product', 'quantity', 'unit_price', 'subtotal')
    readonly_fields = ('unit_price', 'subtotal')

@admin.register(Sale)
class SaleAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'customer', 'total_amount', 'sale_date')
    list_filter = ('sale_date', 'user', 'customer')
    search_fields = ('id', 'user__username', 'customer__first_name', 'customer__last_name', 'customer__email')
    inlines = [SaleItemInline]
    raw_id_fields = ('customer',)

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        obj.calculate_total_amount()

    def save_formset(self, request, form, formset, change):
        instances = formset.save(commit=False)
        for instance in instances:
            if instance.pk:
                original_sale_item = SaleItem.objects.get(pk=instance.pk)
                stock_change = instance.quantity - original_sale_item.quantity
                instance.product.stock_quantity -= stock_change
            else:
                instance.product.stock_quantity -= instance.quantity
            instance.product.save()
            instance.save()

        for obj in formset.deleted_objects:
            obj.delete()

        formset.save_m2m()
        form.instance.calculate_total_amount()

# Admin for Supplier model
@admin.register(Supplier)
class SupplierAdmin(admin.ModelAdmin):
    list_display = ('name', 'contact_person', 'phone_number', 'email', 'created_at')
    search_fields = ('name', 'contact_person', 'email')
    list_filter = ('created_at',)

# Inline for PurchaseOrderItem to be displayed within the PurchaseOrder admin form
class PurchaseOrderItemInline(admin.TabularInline):
    model = PurchaseOrderItem
    extra = 1
    fields = ('product', 'quantity', 'unit_cost', 'subtotal')
    readonly_fields = ('subtotal',)

# Admin for the PurchaseOrder model
@admin.register(PurchaseOrder)
class PurchaseOrderAdmin(admin.ModelAdmin):
    list_display = ('id', 'supplier', 'order_date', 'expected_delivery_date', 'total_amount', 'status', 'created_by')
    list_filter = ('status', 'order_date', 'supplier')
    search_fields = ('id', 'supplier__name', 'notes')
    inlines = [PurchaseOrderItemInline]
    raw_id_fields = ('created_by',)

    def save_model(self, request, obj, form, change):
        if not obj.pk and not obj.created_by:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)
        obj.calculate_total_amount()

    def save_formset(self, request, form, formset, change):
        super().save_formset(request, form, formset, change)
        form.instance.calculate_total_amount()

# Admin for StockAdjustment model
@admin.register(StockAdjustment)
class StockAdjustmentAdmin(admin.ModelAdmin):
    list_display = ('product', 'quantity_change', 'adjustment_type', 'adjustment_date', 'adjusted_by')
    list_filter = ('adjustment_type', 'adjustment_date', 'adjusted_by', 'product__name')
    search_fields = ('product__name', 'notes')
    readonly_fields = ('adjustment_date',)

    def save_model(self, request, obj, form, change):
        if not obj.pk and not obj.adjusted_by:
            obj.adjusted_by = request.user
        
        product = obj.product
        product.stock_quantity += obj.quantity_change
        product.save()
        
        super().save_model(request, obj, form, change)

# Admin for Customer model
@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ('first_name', 'last_name', 'email', 'phone_number', 'date_joined', 'last_purchase')
    list_filter = ('date_joined',)
    search_fields = ('first_name', 'last_name', 'email', 'phone_number')
    readonly_fields = ('date_joined', 'last_purchase')