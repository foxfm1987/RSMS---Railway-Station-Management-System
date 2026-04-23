from django.contrib import admin
from .models import User, Train, TrainSchedule, PassengerTicket, GoodsShipment, Store, StoreSale, WorkRequest


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
	list_display = ("email", "fullname", "role", "is_active", "is_staff")
	search_fields = ("email", "fullname")
	list_filter = ("role", "is_active", "is_staff")


@admin.register(Train)
class TrainAdmin(admin.ModelAdmin):
	list_display = ("number", "name", "train_type", "bogie_type")
	search_fields = ("number", "name")
	list_filter = ("train_type", "bogie_type")


@admin.register(TrainSchedule)
class TrainScheduleAdmin(admin.ModelAdmin):
	list_display = ("train", "service_date", "scheduled_time", "track_type", "direction", "delay_minutes")
	list_filter = ("service_date", "track_type", "direction")
	search_fields = ("train__number", "train__name")


@admin.register(PassengerTicket)
class PassengerTicketAdmin(admin.ModelAdmin):
	list_display = ("pnr", "ticket_type", "coach_class", "amount_inr", "booked_at")
	search_fields = ("pnr", "user__email")
	list_filter = ("ticket_type", "coach_class")


@admin.register(GoodsShipment)
class GoodsShipmentAdmin(admin.ModelAdmin):
	list_display = ("label_no", "status", "weight_kg", "amount_inr", "created_at")
	search_fields = ("label_no", "sender__email")
	list_filter = ("status",)


@admin.register(Store)
class StoreAdmin(admin.ModelAdmin):
	list_display = ("name", "manager", "active")
	list_filter = ("active",)
	search_fields = ("name",)


@admin.register(StoreSale)
class StoreSaleAdmin(admin.ModelAdmin):
	list_display = ("store", "item", "qty", "total_inr", "sold_at")
	list_filter = ("store",)
	search_fields = ("item", "store__name")

@admin.register(WorkRequest)
class WorkRequestAdmin(admin.ModelAdmin):
    list_display = ("title", "requested_by", "status", "created_at")
    list_filter = ("status",)
    search_fields = ("title", "description")