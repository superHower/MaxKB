# coding=utf-8
from django.urls import path
from .views import Datasets, Runs, RunDetail
from .quality_views import Events, Samples, SampleDetail, Annotation, SampleExport, RuleEvaluate

prefix = "workspace/<str:workspace_id>/application/<str:application_id>/evaluation/"
urlpatterns = [
    path(prefix + "datasets", Datasets.as_view()),
    path(prefix + "runs", Runs.as_view()),
    path(prefix + "runs/<uuid:run_id>", RunDetail.as_view()),
    path(prefix + "events", Events.as_view()),
    path(prefix + "samples", Samples.as_view()),
    path(prefix + "samples/export", SampleExport.as_view()),
    path(prefix + "samples/<uuid:sample_id>", SampleDetail.as_view()),
    path(prefix + "samples/<uuid:sample_id>/annotation", Annotation.as_view()),
    path(prefix + "samples/<uuid:sample_id>/evaluate", RuleEvaluate.as_view()),
]
