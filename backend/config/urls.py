from django.urls import path

from planner.views import GeocodeView, HealthView, HeatmapView, PlanView, api_root

urlpatterns = [
    path("", api_root),
    path("api/health/", HealthView.as_view()),
    path("api/geocode/", GeocodeView.as_view()),
    path("api/plan/", PlanView.as_view()),
    path("api/heatmap/", HeatmapView.as_view()),
]
