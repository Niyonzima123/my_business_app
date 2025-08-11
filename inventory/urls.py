# inventory/urls.py

from django.urls import path
from . import views

# NEW: Import for Class-Based Views
from .views import ProductListView

app_name = 'inventory'

urlpatterns = [
    # NEW: The path now uses ProductListView.as_view() to correctly route to the class-based view.
    path('', ProductListView.as_view(), name='product_list'),
    path('products/<int:pk>/', views.product_detail, name='product_detail'),
    path('pos/', views.pos_view, name='pos_view'),
    path('pos/get_product_by_barcode/', views.get_product_by_barcode, name='get_product_by_barcode'),
    # FIX: Changed 'name' from 'receipt' to 'receipt_view' to match the template.
    path('pos/receipt/<int:sale_id>/', views.receipt_view, name='receipt_view'),
    path('add-stock/', views.add_stock_view, name='add_stock'),
    path('my-sales/', views.my_sales_view, name='my_sales'),
    path('reports/sales/', views.sales_report_view, name='sales_report'),
    path('reports/sales/export-csv/', views.export_sales_csv, name='export_sales_csv'),
    path('reports/low-stock/', views.low_stock_alerts_view, name='low_stock_alerts'),
    path('suppliers/', views.supplier_list_view, name='supplier_list'),
    path('purchase-orders/create/', views.create_purchase_order_view, name='create_purchase_order'),
    path('purchase-orders/', views.purchase_order_list_view, name='purchase_order_list'),
    path('purchase-orders/<int:pk>/', views.purchase_order_detail_view, name='purchase_order_detail'),
    path('purchase-orders/<int:pk>/receive/', views.receive_purchase_order, name='receive_purchase_order'),
    path('stock-adjustment/create/', views.create_stock_adjustment_view, name='create_stock_adjustment'),
    path('reports/performance/', views.product_performance_report_view, name='product_performance_report'),
    path('customers/', views.customer_list_view, name='customer_list'),
    path('customers/add/', views.create_customer_view, name='create_customer'),
    # NEW: Added URL pattern for customer detail view, which was missing.
    path('customers/<int:pk>/', views.customer_detail_view, name='customer_detail'),
    path('reports/employee-sales/', views.employee_sales_report_view, name='employee_sales_report'),
    path('customers/<int:pk>/history/', views.customer_purchase_history_view, name='customer_purchase_history'),
    
    # NEW: URL patterns for disabling and enabling products
    path('products/<int:pk>/disable/', views.disable_product_view, name='disable_product'),
    path('products/<int:pk>/enable/', views.enable_product_view, name='enable_product'),
]