# accounts/models.py
from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save # Import signal
from django.dispatch import receiver # Import receiver
from datetime import date # Import date for default value

# Define choices for employee roles
ROLE_CHOICES = [
    ('Owner', 'Owner'),
    ('Cashier', 'Cashier'),
    ('Stock Manager', 'Stock Manager'),
    # Add more roles as needed
]

class EmployeeProfile(models.Model):
    """
    Extends Django's built-in User model to store additional employee-specific information.
    """
    user = models.OneToOneField(User, on_delete=models.CASCADE, help_text="The associated Django user account.")
    phone_number = models.CharField(max_length=20, blank=True, null=True, help_text="Employee's phone number.")
    role = models.CharField(max_length=50, choices=ROLE_CHOICES, default='Cashier', help_text="The role of the employee.")
    date_joined = models.DateField(auto_now_add=True, help_text="Date when the employee joined.")
    is_active_employee = models.BooleanField(default=True, help_text="Is this employee currently active?")

    class Meta:
        verbose_name = "Employee Profile"
        verbose_name_plural = "Employee Profiles"
        ordering = ['user__username'] # Order by associated username

    def __str__(self):
        return f"{self.user.username}'s Profile ({self.role})"

# --- Signal to automatically create/update EmployeeProfile when a User is created/saved ---
@receiver(post_save, sender=User)
def create_or_update_user_profile(sender, instance, created, **kwargs):
    """
    Ensures that every User instance has an associated EmployeeProfile.
    This signal runs whenever a User object is saved.
    """
    if created:
        # If a new User instance was just created, create its EmployeeProfile.
        EmployeeProfile.objects.create(user=instance)
    else:
        # If the User instance already existed (e.g., being updated in admin),
        # ensure its existing EmployeeProfile is saved.
        # get_or_create is used defensively in case a profile doesn't exist for an old user.
        profile, _ = EmployeeProfile.objects.get_or_create(user=instance)
        profile.save() # Explicitly save the profile to ensure any changes from the inline are persisted.


# --- NEW MODELS FOR EXPENSE TRACKING ---

class ExpenseCategory(models.Model):
    """
    Represents a category for expenses (e.g., Rent, Utilities, Salaries).
    """
    name = models.CharField(max_length=100, unique=True, help_text="Name of the expense category (e.g., Rent, Utilities)")
    description = models.TextField(blank=True, null=True, help_text="Optional description for the category")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "Expense Categories"
        ordering = ['name']

    def __str__(self):
        return self.name

class Expense(models.Model):
    """
    Represents an individual expense record.
    """
    category = models.ForeignKey(ExpenseCategory, on_delete=models.PROTECT, help_text="The category this expense belongs to")
    amount = models.DecimalField(max_digits=10, decimal_places=2, help_text="Amount of the expense")
    # CORRECTED LINE: Removed auto_now_add=True and added default=date.today
    date = models.DateField(default=date.today, help_text="Date the expense occurred")
    description = models.TextField(blank=True, null=True, help_text="Detailed description or notes about the expense")
    recorded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, help_text="User who recorded this expense")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-date', '-created_at'] # Order by most recent date, then creation time

    def __str__(self):
        return f"Expense of RWF {self.amount:.2f} for {self.category.name} on {self.date}"