"""
URL configuration for commitrush project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.1/topics/http/urls/
"""
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path('admin/', admin.site.urls),
    # Root auth endpoints (PRD §8.1, Plan M1-T3)
    path('', include('core.urls')),
    # Versioned API auth endpoints (PRD §16)
    path('api/v1/', include('core.urls')),
]
