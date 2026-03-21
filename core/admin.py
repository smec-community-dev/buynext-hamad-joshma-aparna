from django.contrib import admin
from .models import (
    User,
    Address,
    Notification,
    Category,
    SubCategory,
    Banner,
)


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    search_fields = ("username", "email", "first_name", "last_name", "phone_number")
    list_display = ("username", "email", "role", "is_active", "is_verified")
    list_filter = ("role", "is_active", "is_verified")


admin.site.register(Address)
admin.site.register(Notification)
admin.site.register(Category)
admin.site.register(SubCategory)
admin.site.register(Banner)
