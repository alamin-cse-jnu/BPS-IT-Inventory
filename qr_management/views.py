from django.shortcuts import render
from django.http import HttpResponse

def qr_index(request):
    return HttpResponse('<h1>📱 QR Code Management</h1><p>QR code generation and scanning</p>')