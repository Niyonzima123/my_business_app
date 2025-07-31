# inventory/views.py

from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse, HttpResponse, HttpResponseRedirect
from django.urls import reverse
from django.db import transaction
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.db.models import Sum, F, ExpressionWrapper, DecimalField
from django.db.models.functions import TruncDate
from datetime import datetime, timedelta
import csv

from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.conf import settings

from .models import Product, Category, Sale, SaleItem, Supplier, PurchaseOrder, PurchaseOrderItem, StockAdjustment, Customer
from accounts.models import EmployeeProfile
from accounts.forms import AddStockForm
from .forms import SupplierForm, PurchaseOrderForm, PurchaseOrderItemFormSet, StockAdjustmentForm, CustomerForm


# --- Helper functions for role checking ---
def is_owner(user):
    return user.is_authenticated and hasattr(user, 'employeeprofile') and user.employeeprofile.role == 'Owner'

def is_cashier(user):
    if user.is_authenticated:
        try:
            return user.employeeprofile.role == 'Cashier' or user.employeeprofile.role == 'Owner' or user.is_superuser
        except EmployeeProfile.DoesNotExist:
            return False
    return False

def is_stock_manager(user):
    return user.is_authenticated and hasattr(user, 'employeeprofile') and (user.employeeprofile.role == 'Stock Manager' or user.employeeprofile.role == 'Owner' or user.is_superuser)


# --- Product List View (Homepage) ---
def product_list(request):
    products = Product.objects.filter(is_active=True).select_related('category').order_by('name')
    categories = Category.objects.all().order_by('name')
    context = {
        'products': products,
        'categories': categories,
        'page_title': 'Our Products'
    }
    return render(request, 'inventory/product_list.html', context)


# --- Point of Sale (POS) View ---
@login_required
@user_passes_test(is_cashier, login_url='/accounts/login/')
def pos_view(request):
    if request.method == 'POST':
        try:
            with transaction.atomic():
                customer_id = request.POST.get('customer_id')
                customer = get_object_or_404(Customer, id=customer_id) if customer_id else None

                sale = Sale.objects.create(user=request.user, customer=customer, total_amount=0)

                sale_items_data = request.POST.getlist('items[]')
                total_sale_amount = 0

                for item_data_str in sale_items_data:
                    parts = dict(x.split('=') for x in item_data_str.split('&'))
                    product_id = int(parts.get('product_id'))
                    quantity = int(parts.get('quantity'))

                    product = Product.objects.get(id=product_id)

                    if quantity <= 0:
                        raise ValueError("Quantity must be positive.")
                    if product.stock_quantity < quantity:
                        raise ValueError(f"Not enough stock for {product.name}. Available: {product.stock_quantity}")

                    SaleItem.objects.create(
                        sale=sale,
                        product=product,
                        quantity=quantity,
                        unit_price=product.price,
                        subtotal=quantity * product.price
                    )
                    total_sale_amount += quantity * product.price

                    product.stock_quantity -= quantity
                    product.save()

                sale.total_amount = total_sale_amount
                sale.save()

                if customer:
                    customer.last_purchase = datetime.now()
                    customer.save()

                messages.success(request, f'Sale #{sale.id} recorded successfully! Total: RWF {sale.total_amount:.2f}')
                return JsonResponse({'status': 'success', 'message': 'Sale recorded successfully!', 'sale_id': sale.id})

        except Product.DoesNotExist:
            messages.error(request, 'One or more products not found.')
            return JsonResponse({'status': 'error', 'message': 'One or more products not found.'}, status=400)
        except ValueError as e:
            messages.error(request, str(e))
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
        except Exception as e:
            messages.error(request, 'An error occurred while processing the sale.')
            print(f"Error processing sale: {e}")
            return JsonResponse({'status': 'error', 'message': 'An error occurred while processing the sale.'}, status=500)

    else:
        products = Product.objects.filter(is_active=True, stock_quantity__gt=0).order_by('name')
        customers = Customer.objects.all().order_by('first_name', 'last_name')
        user_role = request.user.employeeprofile.role if hasattr(request.user, 'employeeprofile') else 'N/A'
        context = {
            'products': products,
            'customers': customers,
            'page_title': 'Point of Sale',
            'user_role': user_role,
            'get_product_by_barcode_url': reverse('inventory:get_product_by_barcode'),
        }
        return render(request, 'inventory/pos.html', context)


# --- Get Product by Barcode View (AJAX endpoint) ---
@login_required
@user_passes_test(is_cashier, login_url='/accounts/login/')
def get_product_by_barcode(request):
    if request.method == 'GET':
        barcode = request.GET.get('barcode', None)
        if barcode:
            try:
                product = Product.objects.get(barcode=barcode, is_active=True, stock_quantity__gt=0)
                return JsonResponse({
                    'status': 'success',
                    'product': {
                        'id': product.id,
                        'name': product.name,
                        'price': str(product.price),
                        'stock_quantity': product.stock_quantity,
                        'barcode': product.barcode,
                    }
                })
            except Product.DoesNotExist:
                return JsonResponse({'status': 'error', 'message': 'Product not found or out of stock.'}, status=404)
            except Exception as e:
                print(f"Error fetching product by barcode: {e}")
                return JsonResponse({'status': 'error', 'message': 'An error occurred.'}, status=500)
        return JsonResponse({'status': 'error', 'message': 'Barcode not provided.'}, status=400)
    return JsonResponse({'status': 'error', 'message': 'Invalid request method.'}, status=405)


# --- Add Product Stock View ---
@login_required
@user_passes_test(lambda u: is_owner(u) or is_stock_manager(u), login_url='/accounts/login/')
def add_stock_view(request):
    if request.method == 'POST':
        form = AddStockForm(request.POST)
        if form.is_valid():
            product = form.cleaned_data['product']
            quantity_to_add = form.cleaned_data['quantity_to_add']

            product.stock_quantity += quantity_to_add
            product.save()

            messages.success(request, f'Successfully added {quantity_to_add} to {product.name}. New stock: {product.stock_quantity}.')
            return redirect('inventory:add_stock')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = AddStockForm()

    context = {
        'page_title': 'Add Product Stock',
        'form': form
    }
    return render(request, 'inventory/add_stock.html', context)


# --- My Sales History View for Cashiers ---
@login_required
@user_passes_test(lambda u: is_owner(u) or is_cashier(u), login_url='/accounts/login/')
def my_sales_view(request):
    sales = Sale.objects.filter(user=request.user).order_by('-sale_date')

    context = {
        'page_title': 'My Sales History',
        'sales': sales,
    }
    return render(request, 'inventory/my_sales.html', context)


# --- Sales Report View for Owners (with Chart Data) ---
@login_required
@user_passes_test(is_owner, login_url='/accounts/login/')
def sales_report_view(request):
    days_ago = int(request.GET.get('days', 30))
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days_ago)

    daily_sales = Sale.objects.filter(
        sale_date__range=(start_date, end_date)
    ).annotate(
        date=TruncDate('sale_date')
    ).values('date').annotate(
        total_sales=Sum('total_amount')
    ).order_by('date')

    chart_labels = [sale['date'].strftime('%Y-%m-%d') for sale in daily_sales]
    chart_data = [float(sale['total_sales']) for sale in daily_sales]

    context = {
        'page_title': 'Sales Report',
        'daily_sales': daily_sales,
        'days_ago': days_ago,
        'chart_labels': chart_labels,
        'chart_data': chart_data,
    }
    return render(request, 'inventory/sales_report.html', context)


# --- Export Sales CSV View ---
@login_required
@user_passes_test(is_owner, login_url='/accounts/login/')
def export_sales_csv(request, period):
    response = HttpResponse(content_type='text/csv')
    filename = f"sales_report_{period}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    response['Content-Disposition'] = f'attachment; filename="{filename}"'

    writer = csv.writer(response)

    writer.writerow(['Sale ID', 'Sale Date', 'Total Amount (RWF)', 'Processed By', 'Product Name', 'Quantity', 'Unit Price', 'Subtotal'])

    sales_data = Sale.objects.select_related('user').order_by('sale_date')

    end_date = datetime.now()
    if period == 'daily':
        start_date = end_date - timedelta(days=1)
    elif period == 'weekly':
        start_date = end_date - timedelta(weeks=1)
    elif period == 'monthly':
        start_date = end_date - timedelta(days=30)
    else:
        start_date = datetime.min

    sales_data = sales_data.filter(sale_date__range=(start_date, end_date))

    for sale in sales_data:
        processed_by_username = sale.user.username if sale.user else 'N/A (User Deleted/Missing)'
        
        for item in sale.saleitem_set.all():
            writer.writerow([
                sale.id,
                sale.sale_date.strftime('%Y-%m-%d %H:%M:%S'),
                f"{sale.total_amount:.2f}",
                processed_by_username,
                item.product.name,
                item.quantity,
                f"{item.unit_price:.2f}",
                f"{item.subtotal:.2f}"
            ])
    return response

# --- Low Stock Alerts View ---
@login_required
@user_passes_test(lambda u: is_owner(u) or is_stock_manager(u), login_url='/accounts/login/')
def low_stock_alerts_view(request):
    low_stock_products = Product.objects.filter(
        stock_quantity__lte=F('reorder_level'),
        is_active=True
    ).order_by('name')

    if low_stock_products.exists():
        recipients = []
        for profile in EmployeeProfile.objects.filter(role__in=['Owner', 'Stock Manager'], is_active_employee=True):
            if profile.user.email:
                recipients.append(profile.user.email)
        
        if recipients:
            subject = 'Low Stock Alert from My Business App'
            html_message = render_to_string('inventory/low_stock_email.html', {
                'low_stock_products': low_stock_products,
                'app_name': 'My Business App',
            })
            plain_message = "The following products are running low on stock:\n"
            for product in low_stock_products:
                plain_message += f"- {product.name} (Current Stock: {product.stock_quantity}, Reorder Level: {product.reorder_level})\n"
            
            try:
                send_mail(
                    subject,
                    plain_message,
                    settings.DEFAULT_FROM_EMAIL,
                    recipients,
                    html_message=html_message,
                    fail_silently=False,
                )
                messages.info(request, 'Low stock alert email sent to relevant personnel.')
            except Exception as e:
                messages.error(request, f'Failed to send low stock alert email: {e}')
                print(f"Email sending error: {e}")
        else:
            messages.warning(request, 'No active owners or stock managers with email addresses found to send low stock alerts.')


    context = {
        'page_title': 'Low Stock Alerts',
        'low_stock_products': low_stock_products,
    }
    return render(request, 'inventory/low_stock_alerts.html', context)


# --- Supplier List View ---
@login_required
@user_passes_test(lambda u: is_owner(u) or is_stock_manager(u), login_url='/accounts/login/')
def supplier_list_view(request):
    suppliers = Supplier.objects.all().order_by('name')
    context = {
        'page_title': 'Suppliers',
        'suppliers': suppliers,
    }
    return render(request, 'inventory/supplier_list.html', context)


# --- Create Purchase Order View ---
@login_required
@user_passes_test(lambda u: is_owner(u) or is_stock_manager(u), login_url='/accounts/login/')
def create_purchase_order_view(request):
    if request.method == 'POST':
        po_form = PurchaseOrderForm(request.POST)
        formset = PurchaseOrderItemFormSet(request.POST, instance=PurchaseOrder())
        
        if po_form.is_valid() and formset.is_valid():
            with transaction.atomic():
                purchase_order = po_form.save(commit=False)
                purchase_order.created_by = request.user
                purchase_order.save()

                formset.instance = purchase_order
                formset.save()

                purchase_order.calculate_total_amount()

                messages.success(request, f'Purchase Order #{purchase_order.id} created successfully!')
                return redirect('inventory:supplier_list')

        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        po_form = PurchaseOrderForm()
        formset = PurchaseOrderItemFormSet(instance=PurchaseOrder())

    context = {
        'page_title': 'Create Purchase Order',
        'po_form': po_form,
        'formset': formset,
        'products': Product.objects.filter(is_active=True).order_by('name'),
    }
    return render(request, 'inventory/create_purchase_order.html', context)


# --- Purchase Order List View ---
@login_required
@user_passes_test(lambda u: is_owner(u) or is_stock_manager(u), login_url='/accounts/login/')
def purchase_order_list_view(request):
    purchase_orders = PurchaseOrder.objects.select_related('supplier', 'created_by').order_by('-order_date')
    context = {
        'page_title': 'Purchase Orders',
        'purchase_orders': purchase_orders,
    }
    return render(request, 'inventory/purchase_order_list.html', context)


# --- Purchase Order Detail View ---
@login_required
@user_passes_test(lambda u: is_owner(u) or is_stock_manager(u), login_url='/accounts/login/')
def purchase_order_detail_view(request, pk):
    purchase_order = get_object_or_404(PurchaseOrder.objects.select_related('supplier', 'created_by'), pk=pk)
    purchase_order_items = purchase_order.purchaseorderitem_set.select_related('product').all()

    context = {
        'page_title': f'Purchase Order #{purchase_order.id}',
        'purchase_order': purchase_order,
        'purchase_order_items': purchase_order_items,
    }
    return render(request, 'inventory/purchase_order_detail.html', context)


# --- Receive Purchase Order View (POST only) ---
@login_required
@user_passes_test(lambda u: is_owner(u) or is_stock_manager(u), login_url='/accounts/login/')
def receive_purchase_order(request, pk):
    if request.method == 'POST':
        purchase_order = get_object_or_404(PurchaseOrder, pk=pk)

        if purchase_order.status == 'Received':
            messages.info(request, f'Purchase Order #{purchase_order.id} has already been received.')
            return redirect('inventory:purchase_order_detail', pk=pk)

        try:
            with transaction.atomic():
                for item in purchase_order.purchaseorderitem_set.all():
                    product = item.product
                    product.stock_quantity += item.quantity
                    product.save()
                
                purchase_order.status = 'Received'
                purchase_order.save()
            
            messages.success(request, f'Purchase Order #{purchase_order.id} successfully received and stock updated!')
        except Exception as e:
            messages.error(request, f'Error receiving Purchase Order #{purchase_order.id}: {e}')
            print(f"Error receiving PO {pk}: {e}")

    return redirect('inventory:purchase_order_detail', pk=pk)


# --- Create Stock Adjustment View ---
@login_required
@user_passes_test(lambda u: is_owner(u) or is_stock_manager(u), login_url='/accounts/login/')
def create_stock_adjustment_view(request):
    if request.method == 'POST':
        form = StockAdjustmentForm(request.POST)
        if form.is_valid():
            with transaction.atomic():
                adjustment = form.save(commit=False)
                adjustment.adjusted_by = request.user
                adjustment.save()

                product = adjustment.product
                product.stock_quantity += adjustment.quantity_change
                product.save()

            messages.success(request, f'Stock adjustment for {adjustment.product.name} recorded successfully!')
            return redirect('inventory:create_stock_adjustment')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = StockAdjustmentForm()

    context = {
        'page_title': 'Create Stock Adjustment',
        'form': form,
    }
    return render(request, 'inventory/create_stock_adjustment.html', context)


# --- Product Performance Report View ---
@login_required
@user_passes_test(is_owner, login_url='/accounts/login/')
def product_performance_report_view(request):
    products_by_sales = Product.objects.annotate(
        total_quantity_sold=Sum('saleitem__quantity')
    ).order_by('-total_quantity_sold')
    products_by_sales = products_by_sales.filter(total_quantity_sold__gt=0)

    products_with_revenue = Product.objects.annotate(
        total_revenue=Sum(F('saleitem__quantity') * F('saleitem__unit_price'))
    ).order_by('-total_revenue')
    products_with_revenue = products_with_revenue.filter(total_revenue__gt=0)

    context = {
        'page_title': 'Product Performance Report',
        'products_by_sales': products_by_sales,
        'products_with_revenue': products_with_revenue,
    }
    return render(request, 'inventory/product_performance_report.html', context)


# --- Customer List View ---
@login_required
@user_passes_test(lambda u: is_owner(u) or is_cashier(u), login_url='/accounts/login/')
def customer_list_view(request):
    customers = Customer.objects.all().order_by('first_name', 'last_name')
    context = {
        'page_title': 'Customers',
        'customers': customers,
    }
    return render(request, 'inventory/customer_list.html', context)


# --- Create Customer View ---
@login_required
@user_passes_test(lambda u: is_owner(u) or is_cashier(u), login_url='/accounts/login/')
def create_customer_view(request):
    if request.method == 'POST':
        form = CustomerForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Customer added successfully!')
            return redirect('inventory:customer_list')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = CustomerForm()

    context = {
        'page_title': 'Add New Customer',
        'form': form,
    }
    return render(request, 'inventory/create_customer.html', context)


# --- Customer Detail and Purchase History View ---
@login_required
@user_passes_test(lambda u: is_owner(u) or is_cashier(u), login_url='/accounts/login/')
def customer_detail_view(request, pk):
    customer = get_object_or_404(Customer, pk=pk)
    # Fetch all sales related to this customer, ordered by most recent
    customer_sales = Sale.objects.filter(customer=customer).order_by('-sale_date')

    context = {
        'page_title': f'Customer: {customer.get_full_name()}',
        'customer': customer,
        'customer_sales': customer_sales,
    }
    return render(request, 'inventory/customer_detail.html', context)


# --- Receipt View ---
@login_required
@user_passes_test(is_cashier, login_url='/accounts/login/') # Cashiers and Owners can view receipts
def receipt_view(request, sale_id):
    sale = get_object_or_404(Sale.objects.select_related('user', 'customer'), id=sale_id)
    sale_items = sale.saleitem_set.select_related('product').all()

    context = {
        'page_title': f'Receipt for Sale #{sale.id}',
        'sale': sale,
        'sale_items': sale_items,
    }
    return render(request, 'inventory/receipt.html', context)
