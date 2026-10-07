# coding=utf-8
from django.urls import path
from .views import Datasets, Runs, RunDetail

prefix = "workspace/<str:workspace_id>/application/<str:application_id>/evaluation/"
urlpatterns = [
    path(prefix + "datasets", Datasets.as_view()),
    path(prefix + "runs", Runs.as_view()),
    path(prefix + "runs/<uuid:run_id>", RunDetail.as_view()),
]
