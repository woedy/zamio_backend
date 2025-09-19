from django.urls import path

from . import views

urlpatterns = [
    # Partners
    path("partners/", views.list_partners),
    path("partners/create/", views.create_partner),
    path("partners/<int:partner_id>/", views.get_partner),
    path("partners/<int:partner_id>/agreements/", views.list_agreements),
    path("partners/<int:partner_id>/agreements/create/", views.create_agreement),
    path("partners/<int:partner_id>/ingest-repertoire/", views.ingest_repertoire),  # path-based import
    path("partners/<int:partner_id>/repertoire/upload/", views.ingest_repertoire_upload),  # file upload

    # Cycles
    path("cycles/", views.list_cycles),
    path("cycles/create/", views.create_cycle),
    path("cycles/<int:cycle_id>/close/", views.close_cycle),
    path("cycles/<int:cycle_id>/line-items/", views.list_cycle_line_items),
    path("cycles/<int:cycle_id>/exports/", views.list_cycle_exports),

    # Exports & Remittance
    path("cycles/<int:cycle_id>/partners/<int:partner_id>/export/", views.export_partner_csv),
    path("cycles/<int:cycle_id>/partners/<int:partner_id>/remit/", views.create_remittance),
    path("remittances/<int:remittance_id>/", views.get_remittance),
    path("cycles/<int:cycle_id>/remittances/", views.list_cycle_remittances),

    # QA
    path("usage/unmatched/", views.list_unmatched_usage),
    
    # Enhanced Royalty Calculator
    path("calculate/", views.calculate_play_log_royalties),
    path("rates/", views.get_royalty_rates),
    path("rates/<int:rate_id>/update/", views.update_royalty_rate),
    path("exchange-rates/", views.get_exchange_rates),
    path("audit/", views.get_calculation_audit),
    
    # PRO Integration and Reciprocal Agreements
    path("cycles/<int:cycle_id>/process-reciprocal/", views.process_reciprocal_cycle),
    path("generate-pro-report/", views.generate_pro_report),
    path("cycles/<int:cycle_id>/reciprocal-summary/", views.get_reciprocal_payments_summary),
]
