from django.urls import path
from . import views
urlpatterns = [
    path("login/",views.login_view,name="login"),
    path("register/",views.register_view,name="register"),
    path("verify-method/",views.choose_verification,name="choose_verification"),
    path("resend-otp/",views.resend_otp,name="resend_otp"),
    path("verify-email/",views.email_verification,name="email_verification"),
    path("verify-phone/",views.phone_verification,name="phone_verification"),
    path("verify-otp/",views.verify_otp,name="verify_otp"),
    path("",views.home_view,name="home"),
    path("logout/",views.logout_view,name="logout"),
    path("products/", views.all_products, name="all_products"),
    path("products/", views.all_products, name="product_list"),
    path("home/category/subcategory/<str:category_slug>/", views.subcategory_view,name="subcategory"),  
    path("products/subcategory/<str:slug>/", views.product_detail,name="product_details"),  
    path("search-suggestions/", views.search_suggestions, name="search_suggestions"),
    path("new-arrivals/", views.new_arrivals, name="new_arrivals"),
    path("trending/", views.trending_products_page, name="trending"),
    ]