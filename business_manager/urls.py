"""
URL configuration for business_manager project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

# business_manager/urls.py

from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

# Assuming your static pages' views are in the inventory app's views.py
from inventory import views as inventory_views 

urlpatterns = [
    # Django Admin Panel
    path('admin/', admin.site.urls),

    # Authentication URLs from the accounts app
    path('accounts/', include('accounts.urls')),
    
    # All inventory-related URLs are handled by the inventory app
    path('', include('inventory.urls')),

    # Static, general pages for the website
    path('about/', inventory_views.about, name='about'),
    path('services/', inventory_views.services, name='services'),
    path('privacy-policy/', inventory_views.privacy_policy, name='privacy_policy'),
    path('terms-of-service/', inventory_views.terms_of_service, name='terms_of_service'),
]

# This block is essential for serving media and static files during local development.
# It should not be used in a production environment.
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
