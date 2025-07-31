# inventory/urls.py
from django.urls import path
from . import views
from django.db.models import Count

app_name = 'inventory'

urlpatterns = [
    path('', views.product_list, name='product_list'),
    path('pos/', views.pos_view, name='pos_view'),
    path('add-stock/', views.add_stock_view, name='add_stock'),
    path('my-sales/', views.my_sales_view, name='my_sales'),
    path('low-stock-alerts/', views.low_stock_alerts_view, name='low_stock_alerts'),

    # Supplier Management URLs
    path('suppliers/', views.supplier_list_view, name='supplier_list'),
    path('purchase-orders/create/', views.create_purchase_order_view, name='create_purchase_order'),
    path('purchase-orders/', views.purchase_order_list_view, name='purchase_order_list'),
    path('purchase-orders/<int:pk>/', views.purchase_order_detail_view, name='purchase_order_detail'),
    path('purchase-orders/<int:pk>/receive/', views.receive_purchase_order, name='receive_purchase_order'),

    # Stock Adjustment URL
    path('stock-adjustments/create/', views.create_stock_adjustment_view, name='create_stock_adjustment'),

    # Advanced Reporting URLs
    path('reports/product-performance/', views.product_performance_report_view, name='product_performance_report'),
    path('reports/employee-sales/', views.employee_sales_report_view, name='employee_sales_report'),
    path('reports/sales/export/csv/', views.export_sales_csv, name='export_sales_csv'),

    # Customer Management URLs
    path('customers/', views.customer_list_view, name='customer_list'),
    path('customers/create/', views.create_customer_view, name='create_customer'),
    path('customers/<int:pk>/history/', views.customer_purchase_history_view, name='customer_purchase_history'),

    # Barcode Integration URL
    path('api/get-product-by-barcode/', views.get_product_by_barcode, name='get_product_by_barcode'),

    # NEW: Receipt URL
    path('receipt/<int:sale_id>/', views.receipt_view, name='receipt_view'),
]