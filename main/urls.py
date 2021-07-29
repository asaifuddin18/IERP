from django.conf.urls import url
from django.urls import path
from . import views
from django.views.generic import TemplateView
urlpatterns = [
    path('', views.home, name='search-home'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('dashboard/redemptions/', views.redemptions, name='redemptions'),
    path('dashboard/purchases/', views.purchases, name='purchases')
]