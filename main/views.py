from django.http.response import HttpResponseRedirect
from django.shortcuts import render
from django.http import HttpResponse
from .source import slash


def home(request):
    return render(request, 'main/home.html')

def dashboard(request):
    context = {}
    context["uses_per_day_x"] = list(slash.uses_per_day.keys())
    context["uses_per_day_y"] = list(slash.uses_per_day.values())
    context['num_unique_users_x'] = list(slash.unique_users_per_day.keys())#len(slash.df.index)
    context['num_unique_users_y'] = list(slash.unique_users_per_day.values())
    context['num_unique_codes_x'] = list(slash.unique_codes_per_day.keys())#len(slash.used.columns) - 1
    context['num_unique_codes_y'] = list(slash.unique_codes_per_day.values())
    context['points_in_circulation_x'] = list(slash.points_in_circulation.keys())#slash.df['Points'].sum()
    context['points_in_circulation_y'] = list(slash.points_in_circulation.values())
    return render(request, 'main/dashboard.html', context)


def redemptions(request):
    context = {}
    context['seven_day_redeems'] = slash.seven_day_redeems
    return render(request, 'main/redemptions.html', context=context)

def purchases(request):
    context = {}
    context['thirty_day_purchases'] = slash.thirty_day_purchase
    return render(request, 'main/purchases.html', context=context)