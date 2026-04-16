from django.urls import path
from . import views
urlpatterns = [
          path("usersellerbridge/",views.user_seller_bridge,name="user_seller"),
          path("sellerregistration/",views.seller_registration,name="seller_registration"),
          path("sellerdashboard/",views.seller_dashboard,name="seller_dashboard"),
          path("sellerproducts/",views.seller_products,name="seller_product"),
          path("product/<uuid:id>/deactivate/", views.deactivate_product, name="deactivate_product"),
          path("product/<uuid:id>/activate/", views.activate_product, name="activate_product"),
          path('sellerproducts/<uuid:product_id>/view/', views.seller_product_preview, name='seller_product_preview'),
          path("variant/<uuid:id>/deactivate/", views.deactivate_variant, name="deactivate_variant"),
          path("variant/<uuid:id>/activate/", views.activate_variant, name="activate_variant"),
          path("addproduct/",views.add_products,name="add_product"),
          path("addproduct/<uuid:product_id>/",views.edit_product,name="edit_product"),
          path("addvariant/<uuid:product_id>",views.add_variant,name="add_variant"),
          path("productstatus/",views.product_status,name="product_status"),
          path("inventory/",views.seller_inventory,name="seller_inventory"),
          path("sellerorder/",views.seller_order,name="seller_orders"),
          path("sellerearnings/", views.earnings_view, name="seller_earnings"),
          path("offerdiscount/",views.offer_discount,name="offer_discount"),
          path("sellerreviews/",views.seller_reviews,name="seller_reviews"),
          path("review-reply/<uuid:review_id>/", views.reply_review, name="reply_review"),
          path("sellerprofile/",views.seller_profile,name="seller_profile"),
          path("sellersettings/",views.seller_settings,name="seller_settings"),
          path("inventory/", views.inventory_dashboard, name="seller_inventory"),
          path("inventory/adjust/", views.adjust_inventory, name="adjust_inventory"),
          path("update-order-status/<int:item_id>/",views.update_order_item_status, name="update_order_status"),
          


]