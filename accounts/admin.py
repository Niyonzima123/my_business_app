# accounts/admin.py
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from .models import EmployeeProfile, ExpenseCategory, Expense # Import new models

# Define an inline admin descriptor for EmployeeProfile model
# which acts a bit like a singleton
class EmployeeProfileInline(admin.StackedInline):
    model = EmployeeProfile
    can_delete = False
    verbose_name_plural = 'employee profile'

# Define a new User admin
class UserAdmin(BaseUserAdmin):
    inlines = (EmployeeProfileInline,)
    list_display = ('username', 'email', 'first_name', 'last_name', 'is_staff', 'get_role', 'get_phone_number')
    list_filter = ('is_staff', 'is_superuser', 'is_active', 'groups', 'employeeprofile__role') # Add role filter
    search_fields = ('username', 'first_name', 'last_name', 'email', 'employeeprofile__phone_number') # Add phone number search

    def get_role(self, obj):
        return obj.employeeprofile.role if hasattr(obj, 'employeeprofile') else 'N/A'
    get_role.short_description = 'Role'
    get_role.admin_order_field = 'employeeprofile__role' # Allows sorting by role

    def get_phone_number(self, obj):
        return obj.employeeprofile.phone_number if hasattr(obj, 'employeeprofile') else 'N/A'
    get_phone_number.short_description = 'Phone Number'

# Re-register UserAdmin
admin.site.unregister(User)
admin.site.register(User, UserAdmin)


# --- NEW ADMIN CLASSES FOR EXPENSE TRACKING ---

@admin.register(ExpenseCategory)
class ExpenseCategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'description', 'created_at')
    search_fields = ('name',)
    list_filter = ('created_at',)

@admin.register(Expense)
class ExpenseAdmin(admin.ModelAdmin):
    list_display = ('category', 'amount', 'date', 'recorded_by', 'created_at')
    list_filter = ('category', 'date', 'recorded_by')
    search_fields = ('description', 'category__name', 'recorded_by__username')
    raw_id_fields = ('recorded_by',) # Use a raw ID field for recorded_by for better performance with many users
    date_hierarchy = 'date' # Adds a date drill-down navigation
    
    # Automatically set recorded_by to the current user when creating an expense
    def save_model(self, request, obj, form, change):
        if not obj.pk: # Only set on creation
            obj.recorded_by = request.user
        super().save_model(request, obj, form, change)