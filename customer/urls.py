from django.urls import path
from . import views
urlpatterns = [
          path("profile/",views.user_profile_view,name="profile"),
          path("address/save/", views.save_address, name="save_address"),         
          path("address/setdefault/<uuid:address_id>", views.set_default_address, name="set_default"),         
          path("address/delete/<uuid:address_id>", views.delete_address, name="delete_address"),         
          path("product/addcart/<uuid:variant_id>/",views.add_cart,name="add_cart"),
          path("home/cart/",views.view_cart,name="view_cart"),
          path("cart/delete/<uuid:cart_item_id>",views.delete_cart_item,name="delete_cart_item"),
          path("cart/update/",views.update_cart_item,name="update_cart_item"),
          path("wishlist/add/<uuid:variant_id>/",views.add_wishlist, name="add_wishlist_item"),
          path("wishlist/",views.view_wishlist, name="view_wishlist"),
          path("wishlist/add-collection",views.add_collection, name="add_collection"),
          path("wishlist/set-default/<uuid:collection_id>/",views.set_default_collection, name="set_default_collection"),
          path("wishlist/remove/wishlist-item/<uuid:item_id>/",views.remove_wishlist_item, name="remove_wishlist_item"),
          path("wishlist/remove/collection/<uuid:collection_id>/",views.remove_collection, name="remove_wishlist_collection"),


]
