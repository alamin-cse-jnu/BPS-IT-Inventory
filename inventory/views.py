from django.shortcuts import render
from django.http import HttpResponse

def index(request):
    return HttpResponse('<h1>📦 Inventory Management</h1><p>Device tracking and management system</p>')