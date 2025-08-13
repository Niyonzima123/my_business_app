# accounts/views.py
from django.contrib.auth.views import LoginView, LogoutView
from django.urls import reverse_lazy
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.db.models import Sum # For aggregation in reports
from django.db.models.functions import TruncMonth, TruncDate # For date-based aggregation
from datetime import datetime, timedelta, date # For date calculations
from django.db import transaction # To ensure both user and profile are saved together

# Import the helper functions from inventory.views (ensure they are defined there)
from inventory.views import is_owner, is_cashier, is_stock_manager
from django.contrib.auth.decorators import login_required, user_passes_test

# Import Expense models and forms
from .models import ExpenseCategory, Expense
from .forms import ExpenseCategoryForm, ExpenseForm, EmployeeProfileForm # Added EmployeeProfileForm
from inventory.models import Product # Needed for AddStockForm queryset if it's in accounts.forms

# Added for user management
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import get_user_model
User = get_user_model()


class CustomLoginView(LoginView):
    template_name = 'accounts/login.html'
    fields = '__all__'
    redirect_authenticated_user = True

    def get_success_url(self):
        if is_owner(self.request.user):
            return reverse_lazy('accounts:owner_dashboard')
        elif is_stock_manager(self.request.user):
            return reverse_lazy('accounts:stock_manager_dashboard')
        elif is_cashier(self.request.user):
            return reverse_lazy('inventory:pos_view')
        return reverse_lazy('inventory:product_list') # Fallback


class CustomLogoutView(LogoutView):
    next_page = reverse_lazy('accounts:login')


# Owner Dashboard View
@login_required
@user_passes_test(is_owner, login_url='/accounts/login/')
def owner_dashboard(request):
    context = {
        'page_title': 'Owner Dashboard',
        'username': request.user.username,
        'user_role': request.user.employeeprofile.role if hasattr(request.user, 'employeeprofile') else 'N/A'
    }
    return render(request, 'accounts/owner_dashboard.html', context)


# Stock Manager Dashboard View
@login_required
@user_passes_test(is_stock_manager, login_url='/accounts/login/')
def stock_manager_dashboard(request):
    context = {
        'page_title': 'Stock Manager Dashboard',
        'username': request.user.username,
        'user_role': request.user.employeeprofile.role if hasattr(request.user, 'employeeprofile') else 'N/A'
    }
    return render(request, 'accounts/stock_manager_dashboard.html', context)


# --- NEW USER MANAGEMENT VIEWS ---

@login_required
@user_passes_test(is_owner, login_url='/accounts/login/')
def create_user(request):
    """
    Allows an owner to create a new user and assign a role.
    """
    if request.method == 'POST':
        user_form = UserCreationForm(request.POST)
        profile_form = EmployeeProfileForm(request.POST)

        if user_form.is_valid() and profile_form.is_valid():
            try:
                with transaction.atomic():
                    user = user_form.save()
                    profile = profile_form.save(commit=False)
                    profile.user = user
                    profile.save()
                    messages.success(request, f'User {user.username} created successfully!')
                    return redirect('accounts:user_list')
            except Exception as e:
                messages.error(request, f'An error occurred: {e}')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        user_form = UserCreationForm()
        profile_form = EmployeeProfileForm()
        
    context = {
        'page_title': 'Create New User',
        'user_form': user_form,
        'profile_form': profile_form,
    }
    return render(request, 'accounts/create_user.html', context)


@login_required
@user_passes_test(is_owner, login_url='/accounts/login/')
def user_list(request):
    """
    Displays a list of all users.
    """
    users = User.objects.all().select_related('employeeprofile')
    context = {
        'page_title': 'User Management',
        'users': users,
    }
    return render(request, 'accounts/user_list.html', context)

# --- EXPENSE TRACKING VIEWS ---
# (The rest of the expense tracking views remain unchanged)
# The provided code for these views is correct and can be used as is.

@login_required
@user_passes_test(is_owner, login_url='/accounts/login/')
def create_expense_category(request):
    """
    View to create a new expense category.
    """
    if request.method == 'POST':
        form = ExpenseCategoryForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Expense category added successfully!')
            return redirect('accounts:expense_category_list')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = ExpenseCategoryForm()

    context = {
        'page_title': 'Add Expense Category',
        'form': form,
    }
    return render(request, 'accounts/create_expense_category.html', context)


@login_required
@user_passes_test(is_owner, login_url='/accounts/login/')
def expense_category_list(request):
    """
    View to list all expense categories.
    """
    categories = ExpenseCategory.objects.all().order_by('name')
    context = {
        'page_title': 'Expense Categories',
        'categories': categories,
    }
    return render(request, 'accounts/expense_category_list.html', context)


@login_required
@user_passes_test(is_owner, login_url='/accounts/login/') # Only owners can record expenses for now
def create_expense(request):
    """
    View to record a new expense.
    """
    if request.method == 'POST':
        form = ExpenseForm(request.POST)
        if form.is_valid():
            expense = form.save(commit=False)
            expense.recorded_by = request.user # Set the user who recorded the expense
            expense.save()
            messages.success(request, 'Expense recorded successfully!')
            return redirect('accounts:expense_list')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = ExpenseForm()

    context = {
        'page_title': 'Record New Expense',
        'form': form,
    }
    return render(request, 'accounts/create_expense.html', context)


@login_required
@user_passes_test(is_owner, login_url='/accounts/login/')
def expense_list(request):
    """
    View to list all recorded expenses with filtering.
    """
    expenses = Expense.objects.all().select_related('category', 'recorded_by')

    # Filtering logic
    category_id = request.GET.get('category')
    start_date_str = request.GET.get('start_date')
    end_date_str = request.GET.get('end_date')

    if category_id:
        expenses = expenses.filter(category_id=category_id)
    
    if start_date_str:
        try:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
            expenses = expenses.filter(date__gte=start_date)
        except ValueError:
            messages.error(request, "Invalid start date format.")
    
    if end_date_str:
        try:
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
            expenses = expenses.filter(date__lte=end_date)
        except ValueError:
            messages.error(request, "Invalid end date format.")

    expenses = expenses.order_by('-date', '-created_at') # Order by most recent

    categories = ExpenseCategory.objects.all().order_by('name') # For filter dropdown

    context = {
        'page_title': 'All Expenses',
        'expenses': expenses,
        'categories': categories,
        'selected_category': category_id,
        'selected_start_date': start_date_str,
        'selected_end_date': end_date_str,
    }
    return render(request, 'accounts/expense_list.html', context)


@login_required
@user_passes_test(is_owner, login_url='/accounts/login/')
def expense_report(request):
    """
    View to display a summary expense report.
    """
    today = date.today()
    start_date = today.replace(day=1) # Default to start of current month
    end_date = today

    filter_period = request.GET.get('period', 'this_month') # 'this_month', 'last_month', 'this_year', 'custom'
    filter_start_date_str = request.GET.get('start_date')
    filter_end_date_str = request.GET.get('end_date')

    if filter_period == 'last_month':
        first_day_current_month = today.replace(day=1)
        end_date = first_day_current_month - timedelta(days=1)
        start_date = end_date.replace(day=1)
    elif filter_period == 'this_year':
        start_date = today.replace(month=1, day=1)
        end_date = today
    elif filter_period == 'custom':
        if filter_start_date_str:
            try:
                start_date = datetime.strptime(filter_start_date_str, '%Y-%m-%d').date()
            except ValueError:
                messages.error(request, "Invalid start date format for custom range.")
        if filter_end_date_str:
            try:
                end_date = datetime.strptime(filter_end_date_str, '%Y-%m-%d').date()
            except ValueError:
                messages.error(request, "Invalid end date format for custom range.")

    # Ensure date range is correct for query
    expenses_query = Expense.objects.filter(date__range=(start_date, end_date))

    # Aggregate expenses by category
    expenses_by_category = expenses_query.values('category__name').annotate(
        total_amount=Sum('amount')
    ).order_by('-total_amount')

    # Aggregate expenses by month (for charting)
    monthly_expenses = expenses_query.annotate(
        month=TruncMonth('date')
    ).values('month').annotate(
        total_amount=Sum('amount')
    ).order_by('month')

    chart_labels = [m['month'].strftime('%Y-%m') for m in monthly_expenses]
    chart_data = [float(m['total_amount']) for m in monthly_expenses]

    total_expenses_for_period = expenses_query.aggregate(total_sum=Sum('amount'))['total_sum'] or 0

    context = {
        'page_title': 'Expense Report',
        'expenses_by_category': expenses_by_category,
        'monthly_expenses': monthly_expenses,
        'total_expenses_for_period': total_expenses_for_period,
        'chart_labels': chart_labels,
        'chart_data': chart_data,
        'selected_period': filter_period,
        'selected_start_date': start_date.strftime('%Y-%m-%d'),
        'selected_end_date': end_date.strftime('%Y-%m-%d'),
    }
    return render(request, 'accounts/expense_report.html', context)