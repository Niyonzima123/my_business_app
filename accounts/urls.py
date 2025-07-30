# accounts/urls.py
from django.urls import path
from . import views
from inventory import views as inventory_views # Import inventory views for the sales report

app_name = 'accounts'

urlpatterns = [
    path('login/', views.CustomLoginView.as_view(), name='login'),
    path('logout/', views.CustomLogoutView.as_view(), name='logout'),
    path('dashboard/', views.owner_dashboard, name='owner_dashboard'),
    path('stock-dashboard/', views.stock_manager_dashboard, name='stock_manager_dashboard'),
    path('sales-report/', inventory_views.sales_report_view, name='sales_report'),

    # --- NEW EXPENSE TRACKING URLs ---
    path('expenses/categories/create/', views.create_expense_category, name='create_expense_category'),
    path('expenses/categories/', views.expense_category_list, name='expense_category_list'),
    path('expenses/create/', views.create_expense, name='create_expense'),
    path('expenses/', views.expense_list, name='expense_list'),
    path('expenses/report/', views.expense_report, name='expense_report'),
]