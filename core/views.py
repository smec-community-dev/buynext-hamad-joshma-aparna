from django.shortcuts import render,redirect
from .models import User
from django.contrib.auth import authenticate,login,logout
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from .decorator import _dashboard_for_user
# Create your views here.

def login_view(request):
    if request.method=="POST":
        username_or_email=request.POST.get("username_or_email")
        password=request.POST.get("password")
        try:
            user_obj=User.objects.get(email=username_or_email)
            username=user_obj.username
        except User.DoesNotExist:
            username=username_or_email
        user = authenticate(request,username=username,password=password)
        if user is not None:
            login(request,user)
            return redirect(_dashboard_for_user(request.user))
        else:
            messages.error(request, "Invalid username or password")
    return render(request,"core/login.html")
def register_view(request):
    if request.method=="POST":
        username=request.POST.get("username")
        email = request.POST.get("email")
        phone_no = request.POST.get("full_phone")
        password = request.POST.get("password")
        confirm_password = request.POST.get("confirm_password")
        if password != confirm_password:
            messages.error(request, "Passwords do not match")
            return render(request, "core/register.html")
        if User.objects.filter(username=username).exists():
            messages.error(request, "Username already taken")
            return render(request, "core/register.html")
        if User.objects.filter(email=email).exists():
            messages.error(request, "Email already registered")
            return render(request, "core/register.html")
        if User.objects.filter( phone_number=phone_no).exists():
            messages.error(request, "phone number already registered")
            return render(request, "core/register.html")
        user=User.objects.create_user(
            username=username,
            email=email,
             phone_number=phone_no,
            password=password
        )
        user.is_active=True
        user.save()
        login(request, user)
        messages.success(request, "Registration successful! please login.")
        return redirect("login")
        
    return render(request,"core/register.html")
def home_view(request):
    return render(request,"core/home.html")
@login_required
def logout_view(request):
    logout(request)
    return redirect("/")



