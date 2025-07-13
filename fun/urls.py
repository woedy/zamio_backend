from django.urls import path

from fun.views import add_fun, archive_fun, edit_fun, get_all_archived_funs_view, get_all_funs_view, get_fun_details_view, unarchive_fun


app_name = "fun"

urlpatterns = [

    # 🎤 Fun
    path('add/', add_fun, name='add_fun'),
    path('get-all-funs/', get_all_funs_view, name='get_all_funs'),
    path('get-fun-details/', get_fun_details_view, name='get_fun_details'),
    path('edit-fun/', edit_fun, name='edit_fun'),
    path('archive-fun/', archive_fun, name='archive_fun'),
    path('unarchive-fun/', unarchive_fun, name='unarchive_fun'),
    # path('delete/', delete_fun, name='delete_fun'),
    path('get-all-archived-funs/', get_all_archived_funs_view, name='archived_funs'),
]