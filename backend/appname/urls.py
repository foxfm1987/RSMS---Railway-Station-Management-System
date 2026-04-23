from django.urls import path
from . import views
from django.conf import settings
from django.conf.urls.static import static
urlpatterns = [
    path('', views.home, name='home'),
    path('login/', views.login, name='login'),
    path('register/', views.register, name='register'),
    path('staff/login/', views.staff_login, name='staff_login'),
    path('staff/register/', views.staff_register, name='staff_register'),
    path('logout/', views.logout, name='logout'),
    path('profile/', views.profile, name='profile'),
    path('train/', views.train, name='train'),
    path('station-master/', views.station_master_dashboard, name='station_master'),
    path('ticket-counter/', views.ticket_counter_dashboard, name='ticket_counter'),
    path('goods-manager/', views.goods_manager_dashboard, name='goods_manager'),
    path('store/', views.store_dashboard, name='store_dashboard'),
    path('passenger/', views.passenger_dashboard, name='passenger'),
    path('tickets/<int:ticket_id>/print/', views.print_ticket, name='print_ticket'),
    path('goods/<int:shipment_id>/label/', views.print_goods_label, name='print_goods_label'),
    path('station-master/reports/tickets/', views.tickets_report, name='tickets_report'),
    path('station-master/reports/goods/', views.goods_report, name='goods_report'),
    path('station-master/reports/stores/', views.stores_report, name='stores_report'),
    path('station-master/reports/full/', views.full_report, name='full_report'),
    path('station-master/section/tickets/', views.sm_tickets_section, name='sm_tickets_section'),
    path('station-master/section/passengers/', views.sm_passengers_section, name='sm_passengers_section'),
    path('station-master/section/goods/', views.sm_goods_section, name='sm_goods_section'),
    path('station-master/section/stores/', views.sm_stores_section, name='sm_stores_section'),
    path('station-master/revenue/', views.station_master_revenue, name='station_master_revenue'),
    path('store/revenue/', views.store_revenue, name='store_revenue'),
    path('ticket-counter/revenue/', views.ticket_revenue, name='ticket_revenue'),
    path('goods-manager/revenue/', views.goods_revenue, name='goods_revenue'),
]+ static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

