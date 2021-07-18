from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='app-home-page'),
    path('about/', views.about_page, name='app-about-page'),
    path('single-upload/', views.single_upload, name='single-upload-page'),
    path('about/', views.about_page, name='app-about-page'),
    path('file-upload/', views.file_upload, name='file-upload-page'),
    path('my_contributions/', views.my_contributions, name='my-contributions-page')
]
