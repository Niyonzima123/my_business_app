# inventory/models.py
from django.db import models
from django.contrib.auth.models import User # Import Django's built-in User model
from cloudinary.models import CloudinaryField # Import Cloudinary's image field

# Model for Product Categories (e.g., "Electronics", "Clothing", "Food")
class Category(models.Model):
    name = models.CharField(max_length=100, unique=True, help_text="Name of the product category")
    description = models.TextField(blank=True, null=True, help_text="Optional description for the category")

    class Meta:
        verbose_name_plural = "Categories" # Correct plural name for the admin interface
        ordering = ['name'] # Order categories by name by default

    def __str__(self):
        return self.name # How the object is displayed in the admin

# Model for Products
class Product(models.Model):
    name = models.CharField(max_length=200, help_text="Name of the product")
    description = models.TextField(blank=True, null=True, help_text="Detailed description of the product")
    price = models.DecimalField(max_digits=10, decimal_places=2, help_text="Selling price of the product")
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, blank=True, help_text="Category the product belongs to")
    stock_quantity = models.IntegerField(default=0, help_text="Current quantity of product in stock")
    reorder_level = models.IntegerField(default=10, help_text="Minimum stock quantity to trigger a reorder alert")
    is_active = models.BooleanField(default=True, help_text="Is the product currently available for sale?")
    image = CloudinaryField('image', blank=True, null=True, help_text="Optional image for the product") # <--- UPDATED
    barcode = models.CharField(max_length=100, unique=True, blank=True, null=True, help_text="Unique barcode for the product")
    created_at = models.DateTimeField(auto_now_add=True, help_text="Date and time when the product was added")
    updated_at = models.DateTimeField(auto_now=True, help_text="Last date and time when the product details were updated")

    class Meta:
        ordering = ['name'] # Order products by name by default

    def __str__(self):
        return self.name # How the object is displayed in the admin

    # You can add custom methods to your models for business logic
    def get_stock_status(self):
        if self.stock_quantity <= 0:
            return "Out of Stock"
        elif self.stock_quantity <= self.reorder_level:
            return "Low Stock - Reorder Soon!"
        else:
            return "In Stock"


# --- NEW MODEL FOR CUSTOMER MANAGEMENT ---
class Customer(models.Model):
    first_name = models.CharField(max_length=100, help_text="Customer's first name")
    last_name = models.CharField(max_length=100, blank=True, null=True, help_text="Customer's last name")
    email = models.EmailField(max_length=254, unique=True, blank=True, null=True, help_text="Customer's email address (optional, but recommended)")
    phone_number = models.CharField(max_length=20, blank=True, null=True, help_text="Customer's phone number")
    address = models.TextField(blank=True, null=True, help_text="Customer's physical address")
    date_joined = models.DateTimeField(auto_now_add=True, help_text="Date when the customer was added")
    last_purchase = models.DateTimeField(blank=True, null=True, help_text="Date of customer's last purchase")
    notes = models.TextField(blank=True, null=True, help_text="Any additional notes about the customer")

    class Meta:
        ordering = ['last_name', 'first_name']

    def __str__(self):
        full_name = f"{self.first_name} {self.last_name or ''}".strip()
        return full_name if full_name else (self.email or self.phone_number or f"Customer #{self.id}")

    def get_full_name(self):
        return f"{self.first_name} {self.last_name or ''}".strip()


# Model for a Sale Transaction (UPDATED to link to Customer)
class Sale(models.Model):
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, help_text="User who processed the sale")
    customer = models.ForeignKey(Customer, on_delete=models.SET_NULL, null=True, blank=True, help_text="The customer for this sale (optional)")
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, help_text="Total amount of the sale")
    sale_date = models.DateTimeField(auto_now_add=True, help_text="Date and time when the sale occurred")

    class Meta:
        ordering = ['-sale_date'] # Order sales by most recent first

    def __str__(self):
        customer_info = f" ({self.customer.get_full_name()})" if self.customer else ""
        return f"Sale #{self.id} on {self.sale_date.strftime('%Y-%m-%d %H:%M')}{customer_info}"

    def calculate_total_amount(self):
        total = sum(item.subtotal for item in self.saleitem_set.all())
        self.total_amount = total
        self.save()

# Model for individual items within a Sale
class SaleItem(models.Model):
    sale = models.ForeignKey(Sale, on_delete=models.CASCADE, help_text="The sale this item belongs to")
    product = models.ForeignKey('Product', on_delete=models.PROTECT, help_text="The product sold")
    quantity = models.IntegerField(help_text="Quantity of the product sold")
    unit_price = models.DecimalField(max_digits=10, decimal_places=2, help_text="Price of the product at the time of sale")
    subtotal = models.DecimalField(max_digits=10, decimal_places=2, help_text="Subtotal for this item (quantity * unit_price)")

    class Meta:
        unique_together = ('sale', 'product') # A product can only appear once per sale

    def __str__(self):
        return f"{self.quantity} x {self.product.name} in Sale #{self.sale.id}"

    def save(self, *args, **kwargs):
        if not self.unit_price:
            self.unit_price = self.product.price

        self.subtotal = self.quantity * self.unit_price

        if self.pk:
            original_sale_item = SaleItem.objects.get(pk=self.pk)
            stock_change = self.quantity - original_sale_item.quantity
            self.product.stock_quantity -= stock_change
        else:
            self.product.stock_quantity -= self.quantity

        self.product.save()
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        self.product.stock_quantity += self.quantity
        self.product.save()
        super().delete(*args, **kwargs)

# --- Models for Supplier Management ---
class Supplier(models.Model):
    name = models.CharField(max_length=200, unique=True, help_text="Name of the supplier company")
    contact_person = models.CharField(max_length=100, blank=True, null=True, help_text="Main contact person at the supplier")
    phone_number = models.CharField(max_length=20, blank=True, null=True, help_text="Supplier's phone number")
    email = models.EmailField(max_length=254, blank=True, null=True, help_text="Supplier's email address")
    address = models.TextField(blank=True, null=True, help_text="Supplier's physical address")
    notes = models.TextField(blank=True, null=True, help_text="Any additional notes about the supplier")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name

class PurchaseOrder(models.Model):
    supplier = models.ForeignKey(Supplier, on_delete=models.PROTECT, help_text="The supplier for this purchase order")
    order_date = models.DateField(auto_now_add=True, help_text="Date the purchase order was created")
    expected_delivery_date = models.DateField(blank=True, null=True, help_text="Expected date of delivery")
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, help_text="Total amount of the purchase order")
    STATUS_CHOICES = [
        ('Pending', 'Pending'),
        ('Ordered', 'Ordered'),
        ('Received', 'Received'),
        ('Canceled', 'Canceled'),
    ]
    status = models.CharField(max_length=50, choices=STATUS_CHOICES, default='Pending', help_text="Current status of the purchase order")
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, help_text="User who created the purchase order")
    notes = models.TextField(blank=True, null=True, help_text="Internal notes about the purchase order")

    class Meta:
        ordering = ['-order_date']

    def __str__(self):
        return f"PO #{self.id} - {self.supplier.name} ({self.status})"

    def calculate_total_amount(self):
        total = sum(item.subtotal for item in self.purchaseorderitem_set.all())
        self.total_amount = total
        self.save()

class PurchaseOrderItem(models.Model):
    purchase_order = models.ForeignKey(PurchaseOrder, on_delete=models.CASCADE, help_text="The purchase order this item belongs to")
    product = models.ForeignKey('Product', on_delete=models.PROTECT, help_text="The product being ordered")
    quantity = models.IntegerField(help_text="Quantity of the product ordered")
    unit_cost = models.DecimalField(max_digits=10, decimal_places=2, help_text="Cost per unit from the supplier")
    subtotal = models.DecimalField(max_digits=10, decimal_places=2, help_text="Subtotal for this item (quantity * unit_cost)")

    class Meta:
        unique_together = ('purchase_order', 'product')

    def __str__(self):
        return f"{self.quantity} x {self.product.name} for PO #{self.purchase_order.id}"

    def save(self, *args, **kwargs):
        self.subtotal = self.quantity * self.unit_cost
        super().save(*args, **kwargs)

# --- Model for Inventory Adjustments ---
class StockAdjustment(models.Model):
    product = models.ForeignKey(Product, on_delete=models.PROTECT, help_text="The product whose stock is being adjusted")
    quantity_change = models.IntegerField(help_text="The amount by which stock changed (positive for increase, negative for decrease)")
    adjustment_date = models.DateTimeField(auto_now_add=True, help_text="Date and time of the adjustment")
    adjusted_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, help_text="User who made the adjustment")

    ADJUSTMENT_TYPE_CHOICES = [
        ('Add', 'Addition (e.g., found inventory)'),
        ('Remove', 'Removal (e.g., damaged, lost, spoilage)'),
        ('Return', 'Customer Return'),
        ('Physical Count', 'Adjustment after physical count'),
        ('Other', 'Other (specify in notes)'),
    ]
    adjustment_type = models.CharField(
        max_length=50,
        choices=ADJUSTMENT_TYPE_CHOICES,
        default='Other',
        help_text="Type of stock adjustment"
    )
    notes = models.TextField(blank=True, null=True, help_text="Reason or additional details for the adjustment")

    class Meta:
        ordering = ['-adjustment_date']
        verbose_name_plural = "Stock Adjustments"

    def __str__(self):
        action = "added" if self.quantity_change > 0 else "removed"
        return f"{abs(self.quantity_change)} of {self.product.name} {action} ({self.adjustment_type})"