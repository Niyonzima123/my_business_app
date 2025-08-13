# inventory/views.py

from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse, HttpResponse, HttpResponseRedirect
from django.urls import reverse
from django.db import transaction
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.db.models import Sum, F, ExpressionWrapper, DecimalField, Count, Q
from django.db.models.functions import TruncDate
from datetime import datetime, timedelta, date
import csv
from django.utils import timezone
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.conf import settings
# NEW: Import for Class-Based Views
from django.views.generic import ListView
from django.contrib.auth.mixins import UserPassesTestMixin
# NEW: Import for creating a custom decorator
from functools import wraps

from .models import Product, Category, Sale, SaleItem, Supplier, PurchaseOrder, PurchaseOrderItem, StockAdjustment, Customer
from accounts.models import EmployeeProfile
from django.contrib.auth.models import User
from accounts.forms import AddStockForm # Import AddStockForm
from .forms import SupplierForm, PurchaseOrderForm, PurchaseOrderItemFormSet, StockAdjustmentForm, CustomerForm


# --- Helper functions for role checking (moved to top for clarity) ---
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

# --- NEW: Custom decorator for cleaner role checking ---
def role_required(allowed_roles):
    """
    Decorator to check if a user has one of the allowed roles.
    """
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            # The UserPassesTestMixin from Django is generally preferred for CBVs.
            # This is a functional equivalent for FBVs.
            if not request.user.is_authenticated:
                return redirect('accounts:login')
            
            try:
                user_role = request.user.employeeprofile.role
            except EmployeeProfile.DoesNotExist:
                user_role = None

            if user_role in allowed_roles:
                return view_func(request, *args, **kwargs)
            # If the user doesn't have the required role, redirect to login
            return redirect('accounts:login') # Or to a specific forbidden page
        return _wrapped_view
    return decorator


# --- Helper function to build a filtered Sales queryset ---
def get_filtered_sales_query(request):
    """
    Helper function to build a filtered Sales queryset based on GET parameters.
    Returns the queryset and the date/filter parameters for use in context.
    """
    # Default date range: last 30 days
    today = date.today()
    start_date = today - timedelta(days=29)
    end_date = today

    # Get filters from GET parameters
    filter_start_date_str = request.GET.get('start_date')
    filter_end_date_str = request.GET.get('end_date')
    filter_period = request.GET.get('period', 'last_30_days')
    filter_employee_id = request.GET.get('employee_id')

    # Apply period filter first if specified
    if filter_period == 'today':
        start_date = today
        end_date = today
    elif filter_period == 'last_7_days':
        start_date = today - timedelta(days=6)
        end_date = today
    elif filter_period == 'last_30_days':
        start_date = today - timedelta(days=29)
        end_date = today
    elif filter_period == 'this_month':
        start_date = today.replace(day=1)
        end_date = today
    elif filter_period == 'last_month':
        first_day_current_month = today.replace(day=1)
        end_date = first_day_current_month - timedelta(days=1)
        start_date = end_date.replace(day=1)
    elif filter_period == 'this_year':
        start_date = today.replace(month=1, day=1)
        end_date = today
    elif filter_period == 'all_time':
        start_date = datetime.min.date()
        end_date = today

    # Override with custom date range if provided and valid
    if filter_start_date_str:
        try:
            start_date = datetime.strptime(filter_start_date_str, '%Y-%m-%d').date()
        except ValueError:
            messages.error(request, "Invalid start date format. Please use YYYY-MM-DD.")
    if filter_end_date_str:
        try:
            end_date = datetime.strptime(filter_end_date_str, '%Y-%m-%d').date()
        except ValueError:
            messages.error(request, "Invalid end date format. Please use YYYY-MM-DD.")

    # Ensure end_date includes the entire day for filtering
    start_datetime = datetime.combine(start_date, datetime.min.time())
    end_datetime = datetime.combine(end_date, datetime.max.time())

    # Build query for sales
    sales_query = Sale.objects.filter(sale_date__range=(start_datetime, end_datetime))

    if filter_employee_id:
        try:
            employee_user = User.objects.get(id=filter_employee_id)
            sales_query = sales_query.filter(user=employee_user)
        except User.DoesNotExist:
            messages.error(request, "Selected employee not found.")
            # Reset the filter_employee_id if it's invalid
            filter_employee_id = None

    return sales_query, start_date, end_date, filter_period, filter_employee_id


# --- Product List View (Homepage) - CONVERTED TO CLASS-BASED VIEW ---
class ProductListView(ListView):
    model = Product
    template_name = 'inventory/product_list.html'
    context_object_name = 'products'
    paginate_by = 10  # You can adjust this for pagination

    def get_queryset(self):
        # The original view filtered by is_active. We will maintain this behavior.
        queryset = Product.objects.filter(is_active=True).select_related('category').order_by('name')
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Add additional context data from the original function-based view
        context['categories'] = Category.objects.all().order_by('name')
        context['page_title'] = 'Our Products'
        return context


# --- Product Detail View ---
def product_detail(request, pk):
    product = get_object_or_404(Product, pk=pk)
    context = {
        'product': product
    }
    return render(request, 'inventory/product_detail.html', context)


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
                    customer.last_purchase = timezone.now() # <-- CORRECTED LINE
                    customer.save()

                messages.success(request, f'Sale #{sale.id} recorded successfully! Total: RWF {sale.total_amount:.2f}')
                # Pass sale_id back for receipt generation
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


# --- NEW: Receipt View ---
@login_required
def receipt_view(request, sale_id):
    sale = get_object_or_404(Sale.objects.select_related('user', 'customer'), id=sale_id)
    sale_items = sale.saleitem_set.select_related('product').all()

    context = {
        'page_title': f'Receipt for Sale #{sale.id}',
        'sale': sale,
        'sale_items': sale_items,
        'business_name': 'My Business App', # You can make this configurable in settings
        'business_address': '123 Business St, City, Country', # Example
        'business_phone': '+250 7XX XXX XXX', # Example
        'business_email': 'info@mybusinessapp.com', # Example
    }
    return render(request, 'inventory/receipt.html', context)


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
    # Get all active products to populate the dropdown
    products_queryset = Product.objects.filter(is_active=True).order_by('name')

    if request.method == 'POST':
        form = AddStockForm(request.POST, product_queryset=products_queryset) # Pass queryset to form
        if form.is_valid():
            with transaction.atomic():
                product = form.cleaned_data['product']
                quantity_to_add = form.cleaned_data['quantity_to_add']

                product.stock_quantity += quantity_to_add
                product.save()

            messages.success(request, f'Successfully added {quantity_to_add} to {product.name}. New stock: {product.stock_quantity}.')
            return redirect('inventory:add_stock')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = AddStockForm(product_queryset=products_queryset) # Pass queryset to form

    context = {
        'page_title': 'Add Product Stock',
        'form': form,
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


# --- Sales Report View for Owners (with Chart Data, Filters, and Stats) ---
@login_required
@user_passes_test(is_owner, login_url='/accounts/login/')
def sales_report_view(request):
    # Use the new helper function to get the filtered data
    sales_query, start_date, end_date, filter_period, filter_employee_id = get_filtered_sales_query(request)

    # Fetch individual sales for display
    individual_sales = sales_query.select_related('user', 'customer').order_by('-sale_date')

    # Calculate summary statistics
    total_sales_amount = individual_sales.aggregate(total_sum=Sum('total_amount'))['total_sum'] or 0
    total_transactions = individual_sales.count()
    average_sale_value = (total_sales_amount / total_transactions) if total_transactions > 0 else 0

    # Prepare data for daily sales chart
    daily_sales_chart_data = sales_query.annotate(
        date=TruncDate('sale_date')
    ).values('date').annotate(
        total_sales=Sum('total_amount')
    ).order_by('date')

    chart_labels = [entry['date'].strftime('%Y-%m-%d') for entry in daily_sales_chart_data]
    chart_data = [float(entry['total_sales']) for entry in daily_sales_chart_data]

    # Get all employees (users with EmployeeProfile) for the filter dropdown
    employees = User.objects.filter(employeeprofile__isnull=False).order_by('username')

    context = {
        'page_title': 'Sales Report',
        'individual_sales': individual_sales,
        'total_sales_amount': total_sales_amount,
        'total_transactions': total_transactions,
        'average_sale_value': average_sale_value,
        'chart_labels': chart_labels,
        'chart_data': chart_data,
        'employees': employees,
        'selected_start_date': start_date.strftime('%Y-%m-%d'),
        'selected_end_date': end_date.strftime('%Y-%m-%d'),
        'selected_period': filter_period,
        'selected_employee_id': filter_employee_id,
    }
    return render(request, 'inventory/sales_report.html', context)


# --- Export Sales CSV View (Enhanced to use same filters) ---
@login_required
@user_passes_test(is_owner, login_url='/accounts/login/')
def export_sales_csv(request):
    response = HttpResponse(content_type='text/csv')
    filename = f"sales_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    response['Content-Disposition'] = f'attachment; filename="{filename}"'

    writer = csv.writer(response)

    writer.writerow(['Sale ID', 'Sale Date', 'Total Amount (RWF)', 'Processed By', 'Customer Name', 'Product Name', 'Quantity', 'Unit Price', 'Subtotal'])

    # Use the new helper function to get the filtered sales data
    sales_data_query, _, _, _, _ = get_filtered_sales_query(request)
    
    # Fetch all sales items related to the filtered sales
    sales_data = sales_data_query.select_related('user', 'customer').prefetch_related('saleitem_set__product').order_by('sale_date')

    for sale in sales_data:
        processed_by_username = sale.user.username if sale.user else 'N/A'
        customer_name = sale.customer.get_full_name() if sale.customer else 'Walk-in Customer'
        
        if sale.saleitem_set.exists():
            for item in sale.saleitem_set.all():
                writer.writerow([
                    sale.id,
                    sale.sale_date.strftime('%Y-%m-%d %H:%M:%S'),
                    f"{sale.total_amount:.2f}",
                    processed_by_username,
                    customer_name,
                    item.product.name,
                    item.quantity,
                    f"{item.unit_price:.2f}",
                    f"{item.subtotal:.2f}"
                ])
        else:
            writer.writerow([
                sale.id,
                sale.sale_date.strftime('%Y-%m-%d %H:%M:%S'),
                f"{sale.total_amount:.2f}",
                processed_by_username,
                customer_name,
                'No Items', 0, 0.00, 0.00
            ])
    return response


# --- Low Stock Alerts View (UPDATED to send email) ---
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
        formset = PurchaseOrderItemFormSet(request.POST) # <-- THIS LINE WAS MODIFIED
        
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
            # These print statements will show you the exact validation errors
            print("Purchase Order Form Errors:", po_form.errors)
            print("Purchase Order Item Formset Errors:", formset.errors)
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


# --- NEW: Customer Detail View ---
@login_required
@user_passes_test(lambda u: is_owner(u) or is_cashier(u), login_url='/accounts/login/')
def customer_detail_view(request, pk):
    """
    Displays details for a single customer.
    """
    customer = get_object_or_404(Customer, pk=pk)
    context = {
        'page_title': f'Customer: {customer.get_full_name()}',
        'customer': customer,
    }
    return render(request, 'inventory/customer_detail.html', context)


# --- Create Customer View (MODIFIED) ---
@login_required
@user_passes_test(lambda u: is_owner(u) or is_cashier(u), login_url='/accounts/login/')
def create_customer_view(request):
    if request.method == 'POST':
        form = CustomerForm(request.POST)
        if form.is_valid():
            # Save the form and get the new customer instance
            new_customer = form.save()
            messages.success(request, 'Customer added successfully!')
            # Redirect to the customer_detail view using the new customer's ID
            return redirect('inventory:customer_detail', pk=new_customer.pk)
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = CustomerForm()

    context = {
        'page_title': 'Add New Customer',
        'form': form,
    }
    return render(request, 'inventory/create_customer.html', context)


# --- Employee Sales Report View ---
@login_required
@user_passes_test(is_owner, login_url='/accounts/login/')
def employee_sales_report_view(request):
    employee_sales = Sale.objects.filter(
        user__isnull=False
    ).values(
        'user__username',
        'user__employeeprofile__role'
    ).annotate(
        total_sales_amount=Sum('total_amount'),
        total_sales_count=Count('id')
    ).order_by('-total_sales_amount')

    context = {
        'page_title': 'Employee Sales Performance',
        'employee_sales': employee_sales,
    }
    return render(request, 'inventory/employee_sales_report.html', context)


# --- Customer Purchase History View ---
@login_required
@user_passes_test(lambda u: is_owner(u) or is_cashier(u), login_url='/accounts/login/')
def customer_purchase_history_view(request, pk):
    customer = get_object_or_404(Customer, pk=pk)
    
    sales_history = Sale.objects.filter(customer=customer).select_related('user').order_by('-sale_date')

    context = {
        'page_title': f'Purchase History for {customer.get_full_name()}',
        'customer': customer,
        'sales_history': sales_history,
    }
    return render(request, 'inventory/customer_purchase_history.html', context)

# --- NEW: Disable Product View (Soft Delete) ---
@login_required
@user_passes_test(lambda u: is_owner(u) or is_stock_manager(u), login_url='/accounts/login/')
def disable_product_view(request, pk):
    """
    Sets a product's is_active status to False.
    This performs a 'soft delete' to hide it from the POS and other front-end views.
    """
    if request.method == 'POST':
        product = get_object_or_404(Product, pk=pk)
        product.is_active = False
        product.save()
        messages.success(request, f'Successfully disabled product "{product.name}". It is no longer available for sale.')
    else:
        messages.error(request, 'Invalid request method.')
    return redirect('inventory:product_list')


# --- NEW: Enable Product View (Restore) ---
@login_required
@user_passes_test(lambda u: is_owner(u) or is_stock_manager(u), login_url='/accounts/login/')
def enable_product_view(request, pk):
    """
    Sets a product's is_active status back to True.
    This 'restores' a previously disabled product.
    """
    if request.method == 'POST':
        product = get_object_or_404(Product, pk=pk)
        product.is_active = True
        product.save()
        messages.success(request, f'Successfully enabled product "{product.name}". It is now available for sale.')
    else:
        messages.error(request, 'Invalid request method.')
    return redirect('inventory:product_list')


# inventory/views.py

from django.shortcuts import render

def sales_list(request):
    # Fetch your sales data here
    sales_data = [] # Replace with actual data retrieval
    context = {
        'sales': sales_data
    }
    return render(request, 'inventory/sales_list.html', context)
# inventory/views.py

from django.shortcuts import render, redirect
from .forms import ProductForm  # Assuming you have a form

def add_product(request):
    if request.method == 'POST':
        form = ProductForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('inventory:product_list')  # Redirect to product list
    else:
        form = ProductForm()

    context = {'form': form}
    return render(request, 'inventory/add_product.html', context)
# inventory/views.py

from django.shortcuts import render

def generate_report(request):
    # Your logic to generate the report data goes here
    report_data = {
        'title': 'Sales Report',
        'period': 'Last 30 Days',
        # Add more report details
    }

    context = {
        'report': report_data
    }
    return render(request, 'inventory/report.html', context)