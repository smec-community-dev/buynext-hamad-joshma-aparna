from django.urls import path
from . import views
urlpatterns = [
    path("dashboard/",views.admin_dashboard,name="admin_dashboard"),
    path("seller-verification/",views.seller_verification,name="seller_verification"),
    path("product-verification/",views.product_verification,name="product_verification"),
    path("catalogue-management/",views.catalogue_management,name="catalogue_management"),
    path("category/add/",views.add_category,name="add_category"),
    path("category/delete/<uuid:category_id>/",views.delete_category,name="delete_category"),
    path("category/edit/<uuid:category_id>/",views.edit_category,name="edit_category"),
    path("category/subcategory/add/<uuid:category_id>/",views.add_subcategory,name="add_subcategory"),
    path("category/subcategory/edit/<uuid:subcategory_id>/",views.edit_subcategory,name="edit_subcategory"),
    path("category/subcategory/delete/<uuid:subcategory_id>/",views.delete_subcategory,name="delete_subcategory"),
    path("category/subcategory/attribute/add/",views.add_attribute,name="add_attribute"),
    path("category/subcategory/attribute/edit/<uuid:attribute_id>/",views.edit_attribute,name="edit_attribute"),
    path("category/subcategory/attribute/delete/<uuid:attribute_id>/",views.delete_attribute,name="delete_attribute"),
    path("category/subcategory/attribute/options/add",views.add_attributeoptions,name="add_attributeoptions"),
    path("category/subcategory/attribute/options/delete/<uuid:option_id>/",views.delete_attribute_option,name="delete_attribute_option"),
 
 
 
    ]