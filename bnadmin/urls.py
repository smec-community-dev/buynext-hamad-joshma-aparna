from django.urls import path

from . import views


urlpatterns = [
    path("dashboard/", views.admin_dashboard, name="admin_dashboard"),
    path("customers/", views.user_management, name="usermanagement"),
    path("customers/edit/<int:user_id>/", views.edit_user, name="edit_user"),
    path("customers/delete/<int:user_id>/", views.delete_user, name="delete_user"),
    path(
        "customers/<int:user_id>/orders/",
        views.customer_orders,
        name="customer_orders",
    ),
    path("seller-management/", views.seller_management, name="seller_management"),
    path("sellers/verify/<uuid:seller_id>/", views.verify_seller, name="verify_seller"),
    path("sellers/reject/<uuid:seller_id>/", views.reject_seller, name="reject_seller"),
    path("sellers/edit/<uuid:seller_id>/", views.edit_seller, name="edit_seller"),
    path("sellers/delete/<uuid:seller_id>/", views.delete_seller, name="delete_seller"),
    path(
        "sellers/<uuid:seller_id>/report/",
        views.seller_product_report,
        name="seller_product_report",
    ),
    path("orders/", views.order_management, name="order_management"),
    path("orders/<uuid:order_id>/", views.order_detail, name="order_detail"),
    path("product-verification/", views.product_verification, name="product_verification"),
    path(
        "products/<uuid:product_id>/view/",
        views.admin_product_preview,
        name="admin_product_preview",
    ),
    path(
        "products/edit/<uuid:product_id>/",
        views.edit_product_admin,
        name="edit_product_admin",
    ),
    path(
        "products/delete/<uuid:product_id>/",
        views.delete_product_admin,
        name="delete_product_admin",
    ),
    path(
        "products/approve/<uuid:product_id>/",
        views.approve_product,
        name="approve_product",
    ),
    path(
        "products/reject/<uuid:product_id>/",
        views.reject_product,
        name="reject_product",
    ),
    path("search/", views.admin_search, name="admin_search"),
    path("catalogue-management/", views.catalogue_management, name="catalogue_management"),
    path("category/add/", views.add_category, name="add_category"),
    path(
        "category/delete/<uuid:category_id>/",
        views.delete_category,
        name="delete_category",
    ),
    path("category/edit/<uuid:category_id>/", views.edit_category, name="edit_category"),
    path(
        "category/subcategory/add/<uuid:category_id>/",
        views.add_subcategory,
        name="add_subcategory",
    ),
    path(
        "category/subcategory/edit/<uuid:subcategory_id>/",
        views.edit_subcategory,
        name="edit_subcategory",
    ),
    path(
        "category/subcategory/delete/<uuid:subcategory_id>/",
        views.delete_subcategory,
        name="delete_subcategory",
    ),
    path(
        "category/subcategory/attribute/add/",
        views.add_attribute,
        name="add_attribute",
    ),
    path(
        "category/subcategory/attribute/edit/<uuid:attribute_id>/",
        views.edit_attribute,
        name="edit_attribute",
    ),
    path(
        "category/subcategory/attribute/delete/<uuid:attribute_id>/",
        views.delete_attribute,
        name="delete_attribute",
    ),
    path(
        "category/subcategory/attribute/options/add/",
        views.add_attributeoptions,
        name="add_attributeoptions",
    ),
    path(
        "category/subcategory/attribute/options/delete/<uuid:option_id>/",
        views.delete_attribute_option,
        name="delete_attribute_option",
    ),
]
