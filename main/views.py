from django.http.response import HttpResponseRedirect
from django.shortcuts import render
from django.http import HttpResponse
from .source import slash


def home(request):
    return render(request, 'main/home.html')

def dashboard(request):
    context = {}
    context['past_50_uses'] = slash.past_50_uses
    return render(request, 'main/dashboard.html', context)