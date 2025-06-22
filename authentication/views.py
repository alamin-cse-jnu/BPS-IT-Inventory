from django.shortcuts import render
from django.http import HttpResponse

def login_view(request):
    return HttpResponse('<h1>🔐 Authentication</h1><p>User login and access control</p>')