from django.shortcuts import render,redirect,get_object_or_404
from django.contrib import messages
from core.decorator import admin_required
from core.models import *
from seller.models import *
from .models import *

# Create your views here.
@admin_required
def admin_dashboard(request):
    return render(request,"bnadmin/dashboard.html")
@admin_required
def seller_verification(request):
    return render(request,"bnadmin/sellerverification.html")
@admin_required
def product_verification(request):
    return render(request,"bnadmin/productverification.html")
@admin_required
def catalogue_management(request):
    categories= Category.objects.prefetch_related("subcategories__attributes__options").all()
    return render(request,"bnadmin/cataloguemanagement.html",{"categories": categories})
@admin_required
def add_category(request):
    if request.method == "POST":
        name = request.POST.get("name")
        description = request.POST.get("description")
        display_order = request.POST.get("order") or 0
        is_active = request.POST.get("is_active") == "on"
        image = request.FILES.get("image")
        if Category.objects.filter(name=name).exists():
            messages.error(request, "Category with this name already exists.")
            return redirect("add_category")
        if Category.objects.filter(display_order=display_order).exists():
            messages.error(request, f"Display order {display_order} is already taken.")
            return redirect("add_category")

        Category.objects.create(
            name=name,
            description=description,
            display_order=display_order,
            is_active=is_active,
            image=image
        )
        messages.success(request, "Category created successfully.")
        return redirect("catalogue_management")
    return render(request,"bnadmin/addcategory.html")
@admin_required
def edit_category(request, category_id):

    category = get_object_or_404(Category, id=category_id)

    if request.method == "POST":

        category.name = request.POST.get("name")
        category.description = request.POST.get("description")
        category.display_order = request.POST.get("order") or 0
        category.is_active = request.POST.get("is_active") == "on"

        if request.FILES.get("image"):
            if category.image:
                category.image.delete(save=False)
            category.image = request.FILES.get("image")

        category.save()

        messages.success(request, "Category updated successfully.")
        return redirect("catalogue_management")

    return render(request, "bnadmin/edit_category.html", {"category": category})
@admin_required
def delete_category(request, category_id):
    category = get_object_or_404(Category, id=category_id)
    if category.image:
        category.image.delete(save=False)
    category.delete()
    messages.success(request, "Category deleted successfully.")

    return redirect("catalogue_management")
@admin_required
def add_subcategory(request,category_id):
    category = get_object_or_404(Category, id=category_id)
    if request.method == "POST":

        category_id = request.POST.get("category")
        name = request.POST.get("name")
        description = request.POST.get("description")
        display_order = request.POST.get("order") or 0
        is_active = request.POST.get("is_active") == "on"
        image = request.FILES.get("image")
        if not category_id:
            messages.error(request, "Please select a category.")
            return redirect("add_subcategory")
        category = Category.objects.get(id=category_id)
        if SubCategory.objects.filter(category=category, name=name).exists():
            messages.error(request, "SubCategory already exists in this category.")
            return redirect("add_subcategory",category_id=category.id)
        if SubCategory.objects.filter(category=category,display_order=display_order).exists():
            messages.error(request, f"Display order {display_order} is already taken.")
            return redirect("add_subcategory",category.id)
        SubCategory.objects.create(
            category=category,
            name=name,
            description=description,
            image=image,
            display_order=display_order,
            is_active=is_active
        )
        messages.success(request, "SubCategory created successfully.")
        return redirect("catalogue_management")
    return render(request,"bnadmin/addsubcategory.html", {"category": category})
@admin_required
def edit_subcategory(request,subcategory_id):
   subcategory = get_object_or_404(SubCategory, id=subcategory_id)
   category = subcategory.category
   if request.method == "POST":
       subcategory.name = request.POST.get("name")
       subcategory.description = request.POST.get("description")
       subcategory.display_order = request.POST.get("order") or 0
       subcategory.is_active = request.POST.get("is_active") == "on"
       if request.FILES.get("image"):
            if subcategory.image:
                subcategory.image.delete(save=False)
            subcategory.image = request.FILES.get("image")
       subcategory.save() 
       messages.success(request, "SubCategory updated successfully.")
       return redirect("catalogue_management")

   return render(request,"bnadmin/edit_subcategory.html",{"subcategory": subcategory,"category": category})
@admin_required
def delete_subcategory(request,subcategory_id):
    subcategory = get_object_or_404(SubCategory, id=subcategory_id)
    if subcategory.image:
        subcategory.image.delete(save=False)
    subcategory.delete()
    messages.success(request, "SubCategory deleted successfully.")
    return redirect("catalogue_management")

@admin_required
def add_attribute(request):
    subcategories = SubCategory.objects.filter(is_active=True).order_by("display_order")
    if request.method == "POST":
        name = request.POST.get("name")
        display_order = request.POST.get("order") or 0
        subcategory_ids = request.POST.getlist("subcategories")
        if Attribute.objects.filter(name__iexact=name).exists():
            messages.error(request, "Attribute with this name already exists.")
            return redirect("add_attribute")
        attribute = Attribute.objects.create(name=name, display_order=display_order)
        if subcategory_ids:
            attribute.subcategories.set(subcategory_ids)
        messages.success(request, "Attribute created successfully.")
        return redirect("catalogue_management")
    return render(request,"bnadmin/addattribute.html",{"subcategories": subcategories})
@admin_required
def edit_attribute(request,attribute_id):

    attribute = get_object_or_404(Attribute, id=attribute_id)
    subcategories = SubCategory.objects.all().order_by("name")

    if request.method == "POST":

        name = request.POST.get("name")
        subcategory_ids = request.POST.getlist("subcategories")

        if Attribute.objects.filter(name__iexact=name).exclude(id=attribute.id).exists():
            messages.error(request, "Attribute with this name already exists.")
            return redirect("edit_attribute", attribute_id=attribute.id)
        
        attribute.name = name
        attribute.save()
        attribute.subcategories.set(subcategory_ids)
        messages.success(request, "Attribute updated successfully.")
        return redirect("catalogue_management")
    return render(request,"bnadmin/edit_attribute.html",{"attribute": attribute,"subcategories": subcategories})
@admin_required
def delete_attribute(request, attribute_id):
    attribute = get_object_or_404(Attribute, id=attribute_id)
    attribute.delete()
    messages.success(request, "Attribute deleted successfully.")
    return redirect("catalogue_management")
@admin_required
def add_attributeoptions(request):

    attributes = Attribute.objects.all().order_by("name")

    if request.method == "POST":

        attribute_id = request.POST.get("attribute")
        value = request.POST.get("value")
        display_order = request.POST.get("order") or 0

        if not attribute_id:
            messages.error(request, "Please select an attribute.")
            return redirect("add_attributeoptions")

        attribute = get_object_or_404(Attribute, id=attribute_id)
        if AttributeOption.objects.filter(attribute=attribute, value=value).exists():
            messages.error(request, "This option already exists for the selected attribute.")
            return redirect("add_attributeoptions")
        AttributeOption.objects.create(
            attribute=attribute,
            value=value,
            display_order=display_order)
        messages.success(request, "Attribute option added successfully.")
        return redirect("catalogue_management")
    return render(request,"bnadmin/addattributeoptions.html", {"attributes": attributes})
@admin_required
def delete_attribute_option(request, option_id):
    option = get_object_or_404(AttributeOption, id=option_id)
    option.delete()
    messages.success(request, "Attribute option deleted successfully.")
    return redirect("catalogue_management")