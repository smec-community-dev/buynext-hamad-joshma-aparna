from django.shortcuts import render
from core.models import User

# Create your views here.
def user_seller_bridge(request):
    return render(request,"seller/user_seller_bridge.html")
def seller_registration(request):
    

    return render(request,"seller/seller_registration.html")