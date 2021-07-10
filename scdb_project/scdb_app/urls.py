from django.urls import path
from . import views
from .views import PostListView

urlpatterns = [
    path('', PostListView.as_view(), name='app-home-page'),
    path('about/', views.about_page, name='app-about-page'),
]
