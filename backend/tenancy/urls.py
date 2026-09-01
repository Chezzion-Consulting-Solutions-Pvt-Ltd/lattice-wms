from django.urls import path

from tenancy.views import TenantContextView, TenantProbeView
from warehouse.views import (
    ActiveWarehouseContextView,
    BinDetailView,
    BinListCreateView,
    HierarchyTreeView,
    PlantDetailView,
    PlantListCreateView,
    ProductCategoryDetailView,
    ProductCategoryListCreateView,
    StorageSectionDetailView,
    StorageSectionListCreateView,
    StorageTypeDetailView,
    StorageTypeListCreateView,
    TenantDashboardView,
    WarehouseDetailView,
    WarehouseListCreateView,
    ZoneDetailView,
    ZoneListCreateView,
)

urlpatterns = [
    path("context/", TenantContextView.as_view(), name="tenant-context"),
    path("dashboard/", TenantDashboardView.as_view(), name="tenant-dashboard"),
    path("context/warehouse/", ActiveWarehouseContextView.as_view(), name="tenant-active-warehouse"),
    path("hierarchy/", HierarchyTreeView.as_view(), name="tenant-hierarchy"),
    path("plants/", PlantListCreateView.as_view(), name="tenant-plants"),
    path("plants/<uuid:item_id>/", PlantDetailView.as_view(), name="tenant-plant-detail"),
    path("product-categories/", ProductCategoryListCreateView.as_view(), name="tenant-product-categories"),
    path("product-categories/<uuid:item_id>/", ProductCategoryDetailView.as_view(), name="tenant-product-category-detail"),
    path("warehouses/", WarehouseListCreateView.as_view(), name="tenant-warehouses"),
    path("warehouses/<uuid:item_id>/", WarehouseDetailView.as_view(), name="tenant-warehouse-detail"),
    path("zones/", ZoneListCreateView.as_view(), name="tenant-zones"),
    path("zones/<uuid:item_id>/", ZoneDetailView.as_view(), name="tenant-zone-detail"),
    path("storage-types/", StorageTypeListCreateView.as_view(), name="tenant-storage-types"),
    path("storage-types/<uuid:item_id>/", StorageTypeDetailView.as_view(), name="tenant-storage-type-detail"),
    path("storage-sections/", StorageSectionListCreateView.as_view(), name="tenant-storage-sections"),
    path("storage-sections/<uuid:item_id>/", StorageSectionDetailView.as_view(), name="tenant-storage-section-detail"),
    path("bins/", BinListCreateView.as_view(), name="tenant-bins"),
    path("bins/<uuid:item_id>/", BinDetailView.as_view(), name="tenant-bin-detail"),
    path("probe/", TenantProbeView.as_view(), name="tenant-probe"),
]
