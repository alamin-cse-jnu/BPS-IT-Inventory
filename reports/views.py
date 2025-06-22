from django.shortcuts import render
from django.http import HttpResponse

def reports_index(request):
    return HttpResponse('<h1>📊 Reports</h1><p>System reports and analytics</p>')