from django.db import models
from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.core.exceptions import ValidationError
from django.utils import timezone

# Create your models here.

class CustomUserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("The Email field must be set")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)

        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")

        return self.create_user(email, password, **extra_fields)


# Custom user model
class User(AbstractUser):
    email = models.EmailField(max_length=100, unique=True)  
    phone = models.CharField(max_length=15, null=True, blank=True)
    fullname = models.CharField(max_length=100, null=True, blank=True)
    address = models.TextField(null=True, blank=True)
    profile = models.ImageField(upload_to="profile/", null=True, blank=True)
    username = None

    class Role(models.TextChoices):
        PASSENGER = "PASSENGER", "Passenger"
        STATION_MASTER = "STATION_MASTER", "Station Master"
        GOODS_MANAGER = "GOODS_MANAGER", "Goods Manager"
        TICKET_STAFF = "TICKET_STAFF", "Ticket Counter Staff"
        STORE_STAFF = "STORE_STAFF", "Store Staff"

    role = models.CharField(max_length=20, choices=Role.choices, default=Role.PASSENGER)
    assigned_store = models.ForeignKey('Store', on_delete=models.SET_NULL, null=True, blank=True, related_name="staff_members")

    objects = CustomUserManager()

    class Meta:
        db_table = 'user'

    def __str__(self):
        return self.fullname

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    ROLE_LIMITS = {
        Role.STATION_MASTER: 1,
        Role.GOODS_MANAGER: 1,
        Role.TICKET_STAFF: 3,
        Role.STORE_STAFF: 6,
    }

    def clean(self):
        super().clean()
        limit = self.ROLE_LIMITS.get(self.role)
        if limit:
            qs = User.objects.filter(role=self.role)
            if self.pk:
                qs = qs.exclude(pk=self.pk)
            if qs.count() >= limit:
                raise ValidationError({"role": f"Only {limit} user(s) allowed for role {self.get_role_display()}."})

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)


class Train(models.Model):
    class TrainType(models.TextChoices):
        EXPRESS = "EXP", "Express"
        SUPERFAST = "SF", "Superfast"
        PASSENGER = "PASS", "Passenger"
        MEMU = "MEMU", "MEMU"
        EMU = "EMU", "EMU"
        GOODS = "GDS", "Goods"

    class BogieType(models.TextChoices):
        LHB = "LHB", "LHB"
        ICF = "ICF", "ICF"
        BOXN = "BOXN", "BOXN"
        BCN = "BCN", "BCN"
        BOBRN = "BOBRN", "BOBRN"
        BTPN = "BTPN", "BTPN"

    number = models.CharField(max_length=10, unique=True)
    name = models.CharField(max_length=100)
    train_type = models.CharField(max_length=6, choices=TrainType.choices)
    bogie_type = models.CharField(max_length=10, choices=BogieType.choices)

    def __str__(self):
        return f"{self.number} {self.name}"


class TrainSchedule(models.Model):
    class Direction(models.TextChoices):
        UP = "UP", "Up"
        DOWN = "DOWN", "Down"

    class TrackType(models.TextChoices):
        MAIN = "MAIN", "Main"
        PLATFORM1 = "PLATFORM1", "Platform 1"
        PLATFORM2 = "PLATFORM2", "Platform 2"
        GOODS = "GOODS", "Goods"

    train = models.ForeignKey(Train, on_delete=models.CASCADE, related_name="schedules")
    service_date = models.DateField()
    scheduled_time = models.TimeField()
    sequence = models.PositiveIntegerField(default=0)
    direction = models.CharField(max_length=6, choices=Direction.choices, default=Direction.UP)
    track_type = models.CharField(max_length=12, choices=TrackType.choices, default=TrackType.MAIN)
    stops = models.BooleanField(default=True)
    delay_minutes = models.PositiveIntegerField(default=0)

    class Meta:
        unique_together = ("train", "service_date", "direction", "scheduled_time")
        ordering = ["service_date", "scheduled_time", "sequence"]

    def __str__(self):
        return f"{self.train.number} {self.service_date} {self.scheduled_time}"


class PassengerTicket(models.Model):
    class TicketType(models.TextChoices):
        TRAIN = "TRAIN", "Train"
        PLATFORM = "PLATFORM", "Platform"

    class Status(models.TextChoices):
        ACTIVE = "ACTIVE", "Active"
        DEPARTED = "DEPARTED", "Departed"
        CANCELLED = "CANCELLED", "Cancelled"

    class CoachClass(models.TextChoices):
        GN = "GN", "General"
        _1A = "1A", "1A"
        _2A = "2A", "2A"
        _3A = "3A", "3A"
        SL = "SL", "SL"
        CC = "CC", "CC"
        _2S = "2S", "2S"
        FC = "FC", "FC"

    class BookingSource(models.TextChoices):
        PASSENGER_PORTAL = "PASSENGER_PORTAL", "Passenger Portal"
        TICKET_COUNTER = "TICKET_COUNTER", "Ticket Counter"
        UNKNOWN = "UNKNOWN", "Unknown"

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="tickets")
    schedule = models.ForeignKey(TrainSchedule, on_delete=models.SET_NULL, null=True, blank=True)
    ticket_type = models.CharField(max_length=10, choices=TicketType.choices, default=TicketType.TRAIN)
    coach_class = models.CharField(max_length=3, choices=CoachClass.choices, default=CoachClass.SL)
    pnr = models.CharField(max_length=10, unique=True)
    amount_inr = models.DecimalField(max_digits=10, decimal_places=2)
    booking_source = models.CharField(max_length=20, choices=BookingSource.choices, default=BookingSource.UNKNOWN)
    passenger_count = models.PositiveIntegerField(default=1)
    passenger_details = models.JSONField(default=list, blank=True)
    booked_at = models.DateTimeField(default=timezone.now)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.ACTIVE)

    def __str__(self):
        return f"{self.pnr} ({self.ticket_type})"


class GoodsShipment(models.Model):
    class Status(models.TextChoices):
        BOOKED = "BOOKED", "Booked"
        IN_TRANSIT = "IN_TRANSIT", "In Transit"
        DELIVERED = "DELIVERED", "Delivered"

    sender = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="goods_shipments")
    sender_name = models.CharField(max_length=100)
    sender_email = models.EmailField(max_length=100)
    destination = models.CharField(max_length=100)
    schedule = models.ForeignKey(TrainSchedule, on_delete=models.SET_NULL, null=True, blank=True)
    weight_kg = models.DecimalField(max_digits=8, decimal_places=2)
    rate_per_kg_inr = models.DecimalField(max_digits=8, decimal_places=2)
    amount_inr = models.DecimalField(max_digits=10, decimal_places=2)
    label_no = models.CharField(max_length=20, unique=True)
    status = models.CharField(max_length=15, choices=Status.choices, default=Status.BOOKED)
    created_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"{self.label_no} ({self.status})"


class Store(models.Model):
    name = models.CharField(max_length=100, unique=True)
    manager = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="stores")
    active = models.BooleanField(default=True)

    STORE_LIMIT = 6

    def clean(self):
        super().clean()
        if not self.pk and Store.objects.count() >= self.STORE_LIMIT:
            raise ValidationError(f"Only {self.STORE_LIMIT} stores allowed.")

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class Product(models.Model):
    class Category(models.TextChoices):
        SNACKS = "SNACKS", "Snacks"
        BEVERAGES = "BEVERAGES", "Beverages"
        MEALS = "MEALS", "Meals"
        NEWSPAPERS = "NEWSPAPERS", "Newspapers & Magazines"
        TOILETRIES = "TOILETRIES", "Toiletries"
        MISC = "MISC", "Miscellaneous"

    name = models.CharField(max_length=100)
    category = models.CharField(max_length=20, choices=Category.choices)
    base_price = models.DecimalField(max_digits=10, decimal_places=2)
    active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.name} - ₹{self.base_price}"


class StoreInventory(models.Model):
    store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name="inventory")
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.IntegerField(default=0)
    reorder_level = models.IntegerField(default=10)

    class Meta:
        unique_together = ['store', 'product']
        verbose_name_plural = "Store Inventories"

    def __str__(self):
        return f"{self.store.name} - {self.product.name} ({self.quantity})"


class StorePurchase(models.Model):
    store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name="purchases")
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField()
    unit_cost = models.DecimalField(max_digits=10, decimal_places=2)
    total_cost = models.DecimalField(max_digits=10, decimal_places=2)
    purchased_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    purchased_at = models.DateTimeField(default=timezone.now)
    supplier = models.CharField(max_length=100, default="Railway Stores Depot")

    def save(self, *args, **kwargs):
        if not self.total_cost:
            self.total_cost = self.quantity * self.unit_cost
        super().save(*args, **kwargs)
        # Update inventory
        inv, created = StoreInventory.objects.get_or_create(
            store=self.store, 
            product=self.product,
            defaults={'quantity': 0}
        )
        inv.quantity += self.quantity
        inv.save()

    def __str__(self):
        return f"{self.store.name} - {self.product.name} x{self.quantity}"


class StoreSale(models.Model):
    store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name="sales")
    cashier = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    product = models.ForeignKey(Product, on_delete=models.SET_NULL, null=True, blank=True)
    item = models.CharField(max_length=100)
    qty = models.PositiveIntegerField(default=1)
    unit_price_inr = models.DecimalField(max_digits=10, decimal_places=2)
    total_inr = models.DecimalField(max_digits=10, decimal_places=2)
    sold_at = models.DateTimeField(default=timezone.now)

    def save(self, *args, **kwargs):
        if not self.total_inr:
            self.total_inr = self.qty * self.unit_price_inr
        super().save(*args, **kwargs)
        # Update inventory if product is linked
        if self.product:
            try:
                inv = StoreInventory.objects.get(store=self.store, product=self.product)
                inv.quantity = max(0, inv.quantity - self.qty)
                inv.save()
            except StoreInventory.DoesNotExist:
                pass

    def __str__(self):
        return f"{self.store.name} - {self.item}"


class WorkRequest(models.Model):
    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        APPROVED = "APPROVED", "Approved"
        REJECTED = "REJECTED", "Rejected"
        COMPLETED = "COMPLETED", "Completed"

    title = models.CharField(max_length=200)
    description = models.TextField()
    requested_by = models.CharField(max_length=100, default="Railway Division HQ")
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.PENDING)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.title} ({self.status})"

