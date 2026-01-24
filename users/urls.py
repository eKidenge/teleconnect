from django.urls import path
# FIX: Import from quickconnect.views instead of users.views
from quickconnect.views import api_register, api_login, user_profile

urlpatterns = [
    # Use actual functions from quickconnect.views
    path('register/', api_register, name='user-register'),  # ✅ Uses api_register from quickconnect.views
    path('login/', api_login, name='user-login'),  # ✅ Uses api_login from quickconnect.views
    path('profile/', user_profile, name='user-profile'),  # ✅ Uses user_profile from quickconnect.views
    
    # COMMENTED OUT: These functions don't exist in quickconnect.views yet
    #path('profile/update/', views.update_profile, name='update-profile'),  # ⚠️ Function doesn't exist yet
    #path('logout/', views.user_logout, name='user-logout'),  # ⚠️ Function doesn't exist yet
    
    # Add other user-related routes here when you create the functions
]
