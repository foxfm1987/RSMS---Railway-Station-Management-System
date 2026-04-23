from django.shortcuts import render, redirect
from django.db import IntegrityError
from django.db.models import Sum
from django.utils import timezone
from datetime import datetime, timedelta
import base64
import io
import json
import uuid
try:
    import qrcode
except ModuleNotFoundError:
    qrcode = None

from .models import User, TrainSchedule, PassengerTicket, GoodsShipment, Store, StoreSale, WorkRequest, Product, StoreInventory, StorePurchase
from django.contrib import messages
from django.contrib.auth import authenticate, login as auth_login, logout as auth_logout
from django.contrib.auth.hashers import make_password
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden, JsonResponse

TICKET_PRICES = {
    PassengerTicket.CoachClass.GN: 50,
    PassengerTicket.CoachClass._1A: 2000,
    PassengerTicket.CoachClass._2A: 1500,
    PassengerTicket.CoachClass._3A: 1000,
    PassengerTicket.CoachClass.SL: 400,
    PassengerTicket.CoachClass.CC: 600,
    PassengerTicket.CoachClass._2S: 200,
    PassengerTicket.CoachClass.FC: 1200,
}
PLATFORM_TICKET_PRICE = 10
GOODS_RATE_PER_KG = 25
RESERVED_CLASSES_REQUIRING_DETAILS = {
    PassengerTicket.CoachClass.SL,
    PassengerTicket.CoachClass._3A,
    PassengerTicket.CoachClass._2A,
    PassengerTicket.CoachClass._1A,
}
TICKET_LIMITS_BY_ROLE = {
    User.Role.PASSENGER: 5,
    User.Role.TICKET_STAFF: 10,
}
COACH_CAPACITY = {
    PassengerTicket.CoachClass._1A: 18,
    PassengerTicket.CoachClass._2A: 54,
    PassengerTicket.CoachClass._3A: 64,
    PassengerTicket.CoachClass.SL: 72,
    PassengerTicket.CoachClass.CC: 78,
    PassengerTicket.CoachClass._2S: 100,
}


def _calculate_ticket_amount(ticket_type, coach_class):
    if ticket_type == PassengerTicket.TicketType.PLATFORM:
        return PLATFORM_TICKET_PRICE
    return TICKET_PRICES.get(coach_class, 0)


def _build_qr_base64(payload):
    if qrcode is None:
        return None
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=6,
        border=2,
    )
    qr.add_data(payload)
    qr.make(fit=True)
    image = qr.make_image(fill_color="black", back_color="white")
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode("utf-8")


def _create_tickets_from_booking_request(request, schedules, redirect_name, booking_source):
    ticket_type = request.POST.get("ticket_type")
    coach_class = request.POST.get("coach_class")
    schedule_id = request.POST.get("schedule_id")
    schedule = next((s for s in schedules if str(s.id) == str(schedule_id)), None) if schedule_id else None

    if ticket_type == PassengerTicket.TicketType.TRAIN and not schedule:
        messages.error(request, "Train ticket requires a schedule.")
        return redirect(redirect_name)

    if schedule:
        is_memu = schedule.train.train_type in ["EMU", "MEMU"]
        if is_memu and coach_class != PassengerTicket.CoachClass.GN:
            messages.error(request, "MEMU/EMU trains only allow General (GN) tickets.")
            return redirect(redirect_name)

    role_limit = TICKET_LIMITS_BY_ROLE.get(request.user.role, 1)
    raw_count = request.POST.get("passenger_count", "1")
    try:
        passenger_count = int(raw_count)
    except (TypeError, ValueError):
        messages.error(request, "Passenger count must be a number.")
        return redirect(redirect_name)

    if passenger_count < 1 or passenger_count > role_limit:
        messages.error(request, f"You can book between 1 and {role_limit} tickets at once.")
        return redirect(redirect_name)

    requires_details = (
        ticket_type == PassengerTicket.TicketType.TRAIN
        and coach_class in RESERVED_CLASSES_REQUIRING_DETAILS
    )

    passenger_details = []
    if requires_details:
        names = request.POST.getlist("passenger_name[]")
        ages = request.POST.getlist("passenger_age[]")
        genders = request.POST.getlist("passenger_gender[]")
        if len(names) < passenger_count or len(ages) < passenger_count or len(genders) < passenger_count:
            messages.error(request, "Passenger details are required for all selected passengers.")
            return redirect(redirect_name)

        for idx in range(passenger_count):
            name = (names[idx] or "").strip()
            gender = (genders[idx] or "").strip().upper()
            if not name:
                messages.error(request, f"Passenger {idx + 1}: name is required.")
                return redirect(redirect_name)
            try:
                age = int(ages[idx])
            except (TypeError, ValueError):
                messages.error(request, f"Passenger {idx + 1}: age must be a valid number.")
                return redirect(redirect_name)
            if age < 1 or age > 120:
                messages.error(request, f"Passenger {idx + 1}: age must be between 1 and 120.")
                return redirect(redirect_name)
            if gender not in ["M", "F", "O"]:
                messages.error(request, f"Passenger {idx + 1}: choose a valid gender.")
                return redirect(redirect_name)
            passenger_details.append({
                "name": name,
                "age": age,
                "gender": gender,
            })

    if schedule and coach_class in COACH_CAPACITY:
        already_booked = PassengerTicket.objects.filter(
            schedule=schedule,
            coach_class=coach_class,
            status=PassengerTicket.Status.ACTIVE,
        ).aggregate(total=Sum("passenger_count"))["total"] or 0
        available = max(0, COACH_CAPACITY[coach_class] - already_booked)
        if passenger_count > available:
            messages.error(request, f"Only {available} seat(s) available in {coach_class}.")
            return redirect(redirect_name)

    unit_amount = _calculate_ticket_amount(ticket_type, coach_class)
    total_amount = unit_amount * passenger_count
    pnr = _generate_unique("PNR", PassengerTicket, "pnr")
    PassengerTicket.objects.create(
        user=request.user,
        schedule=schedule,
        ticket_type=ticket_type,
        coach_class=coach_class,
        pnr=pnr,
        amount_inr=total_amount,
        booking_source=booking_source,
        passenger_count=passenger_count,
        passenger_details=passenger_details,
    )
    messages.success(request, f"Ticket booked. PNR: {pnr}")
    return redirect(redirect_name)

# Create your views here.

def home(request):
    return redirect('login')


def login(request):
    if request.method == "POST":
        email = request.POST.get('email')
        password = request.POST.get('password')
        user = authenticate(request, email=email, password=password)
        if user is not None:
            auth_login(request, user)
            if user.role == User.Role.PASSENGER:
                return redirect('passenger')
            return redirect('home')
        else:
            messages.error(request, "Invalid email or password.")
            return render(request, 'login.html')
    return render(request, 'login.html')


def register(request):
    if request.method == "POST":
        fname = request.POST.get('first_name')
        lname = request.POST.get('last_name')
        email = request.POST.get('email')
        password = request.POST.get('password')
        repeat_password = request.POST.get('repeat_password')
        if not email or not password:
            messages.error(request, "Email and password are required.")
            return redirect('register')
        if password != repeat_password:
            messages.error(request, "Passwords do not match.")
            return redirect('register')
        if User.objects.filter(email=email).exists():
            messages.error(request, "An account with this email already exists.")
            return redirect('register')
        try:
            result = User.objects.create(first_name=fname, last_name=lname, email=email, password=make_password(password), role=User.Role.PASSENGER)
            result.save()
        except IntegrityError:
            messages.error(request, "An account with this email already exists.")
            return redirect('register')
        messages.success(request, "Account created successfully. Please log in.")
        return redirect('login')
    return render(request, 'register.html')


def staff_login(request):
    if request.method == "POST":
        email = request.POST.get('email')
        password = request.POST.get('password')
        user = authenticate(request, email=email, password=password)
        if user is not None and user.role != User.Role.PASSENGER:
            auth_login(request, user)
            # Redirect based on role
            if user.role == User.Role.STATION_MASTER:
                return redirect('station_master')
            elif user.role == User.Role.GOODS_MANAGER:
                return redirect('goods_manager')
            elif user.role == User.Role.TICKET_STAFF:
                return redirect('ticket_counter')
            elif user.role == User.Role.STORE_STAFF:
                return redirect('store_dashboard')
            return redirect('home')
        messages.error(request, "Invalid staff credentials.")
        return render(request, 'staff_login.html')
    return render(request, 'staff_login.html')


def staff_register(request):
    if request.method == "POST":
        fname = request.POST.get('first_name')
        lname = request.POST.get('last_name')
        email = request.POST.get('email')
        password = request.POST.get('password')
        repeat_password = request.POST.get('repeat_password')
        role = request.POST.get('role')
        if not email or not password:
            messages.error(request, "Email and password are required.")
            return redirect('staff_register')
        if password != repeat_password:
            messages.error(request, "Passwords do not match.")
            return redirect('staff_register')
        if role not in [User.Role.STATION_MASTER, User.Role.GOODS_MANAGER, User.Role.TICKET_STAFF, User.Role.STORE_STAFF]:
            messages.error(request, "Invalid staff role.")
            return redirect('staff_register')
        if User.objects.filter(email=email).exists():
            messages.error(request, "An account with this email already exists.")
            return redirect('staff_register')
        try:
            result = User.objects.create(first_name=fname, last_name=lname, email=email, password=make_password(password), role=role, is_staff=True)
            result.save()
        except IntegrityError:
            messages.error(request, "An account with this email already exists.")
            return redirect('staff_register')
        messages.success(request, "Staff account created successfully. Please log in.")
        return redirect('staff_login')
    return render(request, 'register.html', {"is_staff_register": True})

def logout(request):
    auth_logout(request)
    return redirect('login')

@login_required
def profile(request):
    if request.method == "POST":
        user = request.user
        user.first_name = request.POST.get('first_name', '')
        user.last_name = request.POST.get('last_name', '')
        user.phone = request.POST.get('phone', '')
        user.address = request.POST.get('address', '')
        user.save()
        messages.success(request, "Profile updated successfully!")
        return redirect('profile')
    return render(request, 'profile.html', {'user': request.user})


def train(request):
    today = timezone.localdate()
    
    # Check if today's schedule exists; if not, create default schedule
    if not TrainSchedule.objects.filter(service_date=today).exists():
        from .management.commands.reset_schedule import Command
        cmd = Command()
        cmd.handle()
    
    # Check if test mode is requested
    test_mode = request.GET.get('test', '0') == '1'
    
    schedules = TrainSchedule.objects.select_related("train").filter(service_date=today).order_by("scheduled_time", "sequence")
    # Only show trains that haven't departed yet
    schedules = _filter_upcoming_trains(schedules)

    schedule_rows = []
    cumulative_delay = 0
    for s in schedules:
        cumulative_delay += s.delay_minutes
        scheduled_dt = timezone.make_aware(datetime.combine(s.service_date, s.scheduled_time))
        effective_dt = scheduled_dt + timedelta(minutes=cumulative_delay)

        direction = 1 if s.direction == "UP" else -1
        
        # Direction-aware track assignment
        # UP direction (left-right): PLATFORM2→1, MAIN/non-stop→2
        # DOWN direction (right-left): PLATFORM1→4, MAIN/non-stop→3
        if s.direction == "UP":
            if s.track_type == "PLATFORM2":
                track_id = 1
            else:  # MAIN or GOODS
                track_id = 2  # Track below PLATFORM2
        else:  # DOWN direction
            if s.track_type == "PLATFORM1":
                track_id = 4
            else:  # MAIN or GOODS
                track_id = 3  # Track above PLATFORM1

        schedule_rows.append({
            "id": s.id,
            "time": effective_dt.time().strftime("%H:%M:%S"),
            "name": s.train.name,
            "number": s.train.number,
            "type": "GOODS" if s.train.train_type == "GDS" else ("LOCAL" if s.train.train_type in ["EMU", "MEMU"] else "NORMAL"),
            "track": track_id,
            "stops": s.stops,
            "dir": direction,
            "status": "PENDING",
        })

    context = {
        "schedule_json": json.dumps(schedule_rows),
        "service_date": today.strftime("%d-%m-%Y"),
        "test_mode": test_mode,
    }
    return render(request, 'train.html', context)


def role_required(*roles):
    def decorator(view_func):
        def _wrapped(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect('login')
            if request.user.role not in roles:
                return HttpResponseForbidden("Access denied.")
            return view_func(request, *args, **kwargs)
        return _wrapped
    return decorator


def _generate_unique(prefix, model_cls, field_name, length=6):
    while True:
        token = uuid.uuid4().hex[:length].upper()
        value = f"{prefix}{token}"
        if not model_cls.objects.filter(**{field_name: value}).exists():
            return value


def _filter_upcoming_trains(schedules):
    """Filter out trains that have already departed based on current time"""
    now = timezone.now()
    upcoming = []
    cumulative_delay = 0
    
    for s in schedules:
        cumulative_delay += s.delay_minutes
        scheduled_dt = timezone.make_aware(datetime.combine(s.service_date, s.scheduled_time))
        effective_dt = scheduled_dt + timedelta(minutes=cumulative_delay)
        
        # Keep trains that haven't departed yet (with 30 min buffer for late bookings)
        if effective_dt > now - timedelta(minutes=30):
            upcoming.append(s)
    
    return upcoming


def _get_today_range():
    now = timezone.localtime(timezone.now())
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    end = start + timedelta(days=1)
    return start, end


def _update_departed_tickets():
    now = timezone.now()
    tickets = PassengerTicket.objects.select_related("schedule").filter(
        status=PassengerTicket.Status.ACTIVE,
        ticket_type=PassengerTicket.TicketType.TRAIN,
        schedule__isnull=False,
    )
    schedule_ids = [t.schedule_id for t in tickets if t.schedule_id]
    if not schedule_ids:
        return

    schedule_dates = TrainSchedule.objects.filter(id__in=schedule_ids).values_list("service_date", flat=True)
    schedules = TrainSchedule.objects.filter(service_date__in=schedule_dates).order_by(
        "service_date", "scheduled_time", "sequence"
    )
    effective_map = {}
    current_date = None
    cumulative_delay = 0
    for s in schedules:
        if current_date != s.service_date:
            current_date = s.service_date
            cumulative_delay = 0
        cumulative_delay += s.delay_minutes
        scheduled_dt = timezone.make_aware(datetime.combine(s.service_date, s.scheduled_time))
        effective_dt = scheduled_dt + timedelta(minutes=cumulative_delay)
        effective_map[s.id] = effective_dt

    departed_ids = []
    for t in tickets:
        effective_dt = effective_map.get(t.schedule_id)
        if effective_dt and effective_dt <= now:
            departed_ids.append(t.id)
    if departed_ids:
        PassengerTicket.objects.filter(id__in=departed_ids).update(
            status=PassengerTicket.Status.DEPARTED
        )


def _get_train_route(train_number):
    routes = {
        "12601": ("Mangaluru Central", "Chennai Central"),
        "12841": ("Chennai Central", "Howrah Junction"),
        "22691": ("Bengaluru City", "Hazrat Nizamuddin"),
        "16001": ("Chennai Central", "Mangaluru Central"),
        "06011": ("Thrissur Junction", "Shoranur Junction"),
        "GDM01": ("Thrissur Goods Yard", "Kochi Goods Yard"),
    }
    return routes.get(train_number, ("Unknown", "Unknown"))


def _get_train_stations(train_number):
    # Station sequence in UP direction for each configured train.
    station_map = {
        "12601": ["Mangaluru Central", "Kasaragod", "Kannur", "Kozhikode", "Thrissur Junction", "Ernakulam Junction", "Alappuzha", "Kottayam", "Chennai Central"],
        "12841": ["Chennai Central", "Nellore", "Vijayawada", "Visakhapatnam", "Bhubaneswar", "Kharagpur", "Howrah Junction"],
        "22691": ["Bengaluru City", "Tumakuru", "Hubballi", "Belagavi", "Pune", "Jhansi", "Agra Cantt", "Hazrat Nizamuddin"],
        "16001": ["Chennai Central", "Katpadi", "Jolarpettai", "Salem", "Erode", "Coimbatore", "Palakkad", "Thrissur Junction", "Mangaluru Central"],
        "06011": ["Thrissur Junction", "Wadakkanchery", "Ottapalam", "Shoranur Junction"],
        "GDM01": ["Thrissur Goods Yard", "Aluva", "Ernakulam Goods Terminal", "Kochi Goods Yard"],
    }
    return station_map.get(train_number, [])


def _get_destination_options_for_schedule(schedule):
    stations = _get_train_stations(schedule.train.number)
    if not stations:
        _, route_destination = _get_train_route(schedule.train.number)
        return [route_destination] if route_destination and route_destination != "Unknown" else []

    if schedule.direction == "DOWN":
        stations = list(reversed(stations))

    # Destination should be a stop ahead, not the current/origin point.
    return stations[1:] if len(stations) > 1 else stations


def _get_store_allowed_categories(store_name):
    rules = {
        "Platform 1 Store": ["SNACKS", "BEVERAGES", "MISC"],
        "Platform 2 Store": ["SNACKS", "BEVERAGES", "MISC"],
        "Main Hall Store": ["SNACKS", "BEVERAGES", "MEALS", "TOILETRIES", "MISC"],
        "Food Court": ["MEALS", "BEVERAGES", "SNACKS"],
        "Book & News Stall": ["NEWSPAPERS", "MISC"],
        "General Store": ["SNACKS", "BEVERAGES", "TOILETRIES", "MISC", "NEWSPAPERS"],
    }
    if store_name in rules:
        return rules[store_name]

    name = (store_name or "").lower()
    if "book" in name or "news" in name:
        return ["NEWSPAPERS", "MISC"]
    if "tea" in name or "coffee" in name:
        return ["BEVERAGES", "SNACKS"]
    if "food" in name or "cafe" in name or "canteen" in name:
        return ["MEALS", "BEVERAGES", "SNACKS"]
    if "general" in name:
        return ["SNACKS", "BEVERAGES", "TOILETRIES", "MISC", "NEWSPAPERS"]

    return ["SNACKS", "BEVERAGES", "MEALS", "NEWSPAPERS", "TOILETRIES", "MISC"]


@login_required
@role_required(User.Role.STATION_MASTER)
def station_master_dashboard(request):
    _update_departed_tickets()
    today = timezone.localdate()
    all_schedules = TrainSchedule.objects.select_related("train").filter(service_date=today).order_by("scheduled_time", "sequence")
    schedules = _filter_upcoming_trains(all_schedules)

    if request.method == "POST":
        action = request.POST.get("action")
        if action == "update_work_request":
            work_id = request.POST.get("work_id")
            new_status = request.POST.get("new_status")
            work = WorkRequest.objects.filter(id=work_id).first()
            if work:
                work.status = new_status
                work.save()
                messages.success(request, "Work request updated.")
            return redirect('station_master')

        schedule_id = request.POST.get("schedule_id")
        delay_minutes = request.POST.get("delay_minutes")
        try:
            delay_val = max(0, int(delay_minutes))
        except (TypeError, ValueError):
            messages.error(request, "Delay must be a valid number.")
            return redirect('station_master')
        schedule = schedules.filter(id=schedule_id).first()
        if not schedule:
            messages.error(request, "Schedule not found.")
            return redirect('station_master')
        schedule.delay_minutes = delay_val
        schedule.save()
        messages.success(request, "Delay updated. Upcoming trains adjusted for today.")
        return redirect('station_master')

    cumulative_delay = 0
    rows = []
    for s in schedules:
        cumulative_delay += s.delay_minutes
        scheduled_dt = timezone.make_aware(datetime.combine(s.service_date, s.scheduled_time))
        effective_dt = scheduled_dt + timedelta(minutes=cumulative_delay)
        origin, destination = _get_train_route(s.train.number)
        direction_label = f"Towards {destination}" if s.direction == "UP" else f"Towards {origin}"
        platform_label = s.get_track_type_display() if s.stops else "Through"
        rows.append({
            "id": s.id,
            "number": s.train.number,
            "name": s.train.name,
            "origin": origin,
            "destination": destination,
            "scheduled": s.scheduled_time.strftime("%H:%M"),
            "effective": effective_dt.time().strftime("%H:%M"),
            "platform": platform_label,
            "direction": direction_label,
            "delay": s.delay_minutes,
        })

    work_requests = WorkRequest.objects.filter(status__in=[WorkRequest.Status.PENDING, WorkRequest.Status.APPROVED])[:20]

    # Daily revenue calculation
    start, end = _get_today_range()
    tickets_today = PassengerTicket.objects.filter(
        booked_at__gte=start,
        booked_at__lt=end,
        status__in=[PassengerTicket.Status.ACTIVE, PassengerTicket.Status.DEPARTED],
    )
    goods_today = GoodsShipment.objects.filter(created_at__gte=start, created_at__lt=end)
    sales_today = StoreSale.objects.filter(sold_at__gte=start, sold_at__lt=end)

    ticket_revenue = sum(t.amount_inr for t in tickets_today)
    goods_revenue = sum(g.amount_inr for g in goods_today)
    store_revenue = sum(s.total_inr for s in sales_today)
    total_revenue = ticket_revenue + goods_revenue + store_revenue

    return render(request, 'station_master.html', {
        "rows": rows,
        "service_date": today.strftime("%d-%m-%Y"),
        "work_requests": work_requests,
        "ticket_revenue": ticket_revenue,
        "goods_revenue": goods_revenue,
        "store_revenue": store_revenue,
        "total_revenue": total_revenue,
    })


@login_required
@role_required(User.Role.TICKET_STAFF)
def ticket_counter_dashboard(request):
    _update_departed_tickets()
    today = timezone.localdate()
    all_schedules = TrainSchedule.objects.select_related("train").filter(service_date=today).order_by("scheduled_time", "sequence")
    # Filter out trains with no stops
    all_schedules = all_schedules.filter(stops=True)
    schedules = _filter_upcoming_trains(all_schedules)

    if request.method == "POST":
        return _create_tickets_from_booking_request(
            request,
            schedules,
            'ticket_counter',
            PassengerTicket.BookingSource.TICKET_COUNTER,
        )

    # Calculate upcoming trains with delays and seat availability
    cumulative_delay = 0
    upcoming_trains = []
    now = timezone.now()
    for s in all_schedules:
        cumulative_delay += s.delay_minutes
        scheduled_dt = timezone.make_aware(datetime.combine(s.service_date, s.scheduled_time))
        effective_dt = scheduled_dt + timedelta(minutes=cumulative_delay)
        is_passed = effective_dt <= now
        is_memu = s.train.train_type in ["EMU", "MEMU"]

        # Calculate seat availability by coach class (GN has no seat-based booking)
        booked_tickets = PassengerTicket.objects.filter(schedule=s, status=PassengerTicket.Status.ACTIVE)
        seat_availability = {
            '1A': 18,
            '2A': 54,
            '3A': 64,
            'SL': 72,
            'CC': 78,
            '2S': 100,
        }
        if not is_memu:
            for ticket in booked_tickets:
                if ticket.coach_class in seat_availability:
                    seat_availability[ticket.coach_class] -= ticket.passenger_count

        upcoming_trains.append({
            "id": s.id,
            "number": s.train.number,
            "name": s.train.name,
            "scheduled": s.scheduled_time.strftime("%H:%M"),
            "effective": effective_dt.time().strftime("%H:%M"),
            "delay": cumulative_delay,
            "track": s.get_track_type_display(),
            "direction": s.get_direction_display(),
            "seats": seat_availability,
            "is_memu": is_memu,
            "is_passed": is_passed,
        })

    cutoff_time = timezone.now() - timedelta(hours=3)
    today_tickets = PassengerTicket.objects.filter(
        booked_at__gte=cutoff_time,
        user=request.user,
        booking_source=PassengerTicket.BookingSource.TICKET_COUNTER,
    ).order_by("-booked_at")
    return render(request, 'ticket_counter.html', {
        "schedules": schedules,
        "tickets": today_tickets,
        "upcoming_trains": upcoming_trains,
        "coach_classes": PassengerTicket.CoachClass.choices,
        "service_date": today.strftime("%d-%m-%Y"),
        "ticket_prices": TICKET_PRICES,
        "platform_price": PLATFORM_TICKET_PRICE,
        "max_tickets_per_booking": TICKET_LIMITS_BY_ROLE[User.Role.TICKET_STAFF],
        "reserved_classes_requiring_details": list(RESERVED_CLASSES_REQUIRING_DETAILS),
    })


@login_required
@role_required(User.Role.GOODS_MANAGER)
def goods_manager_dashboard(request):
    today = timezone.localdate()
    all_schedules = TrainSchedule.objects.select_related("train").filter(service_date=today).order_by("scheduled_time", "sequence")
    # Filter out trains with no stops
    all_schedules = all_schedules.filter(stops=True)
    schedules = _filter_upcoming_trains(all_schedules)

    if request.method == "POST":
        schedule_id = request.POST.get("schedule_id")
        sender_name = (request.POST.get("sender_name") or "").strip()
        sender_email = request.POST.get("sender_email")
        destination = (request.POST.get("destination") or "").strip()
        weight_kg = request.POST.get("weight_kg")

        if not sender_name or not sender_email or not destination:
            messages.error(request, "Sender name, email, and destination are required.")
            return redirect('goods_manager')

        try:
            weight_val = float(weight_kg or 0)
        except (TypeError, ValueError):
            messages.error(request, "Weight must be a valid number.")
            return redirect('goods_manager')

        if weight_val <= 0:
            messages.error(request, "Weight must be greater than 0.")
            return redirect('goods_manager')

        schedule = next((s for s in schedules if str(s.id) == str(schedule_id)), None) if schedule_id else None
        if not schedule:
            messages.error(request, "Train schedule is required.")
            return redirect('goods_manager')

        valid_destinations = _get_destination_options_for_schedule(schedule)
        if destination not in valid_destinations:
            messages.error(request, "Please select a valid destination for the chosen train.")
            return redirect('goods_manager')

        sender = User.objects.filter(email__iexact=sender_email).first()
        label_no = _generate_unique("IRG", GoodsShipment, "label_no")
        amount_inr = weight_val * float(GOODS_RATE_PER_KG)
        GoodsShipment.objects.create(
            sender=sender,
            sender_name=sender_name,
            sender_email=sender_email,
            destination=destination,
            schedule=schedule,
            weight_kg=weight_val,
            rate_per_kg_inr=GOODS_RATE_PER_KG,
            amount_inr=amount_inr,
            label_no=label_no,
        )
        messages.success(request, f"Goods shipment created. Transportation ID: {label_no}")
        return redirect('goods_manager')

    start, end = _get_today_range()
    shipments = GoodsShipment.objects.filter(
        created_at__gte=start,
        created_at__lt=end,
    ).order_by("-created_at")
    destination_options_map = {
        str(s.id): _get_destination_options_for_schedule(s)
        for s in schedules
    }
    return render(request, 'goods_manager.html', {
        "schedules": schedules,
        "shipments": shipments,
        "goods_rate": GOODS_RATE_PER_KG,
        "destination_options_json": json.dumps(destination_options_map),
    })


@login_required
@role_required(User.Role.STORE_STAFF)
def store_dashboard(request):
    # Get user's assigned store
    user_store = request.user.assigned_store
    if not user_store:
        messages.error(request, "You are not assigned to any store.")
        return render(request, 'store_dashboard.html', {'no_store': True})

    allowed_categories = _get_store_allowed_categories(user_store.name)
    
    # Handle form submissions
    if request.method == "POST":
        action = request.POST.get("action")
        
        if action == "sale":
            product_id = request.POST.get("product_id")
            try:
                qty = int(request.POST.get("qty", 1))
            except (TypeError, ValueError):
                messages.error(request, "Quantity must be a valid number.")
                return redirect('store_dashboard')
            if qty <= 0:
                messages.error(request, "Quantity must be at least 1.")
                return redirect('store_dashboard')
            
            try:
                product = Product.objects.get(id=product_id, active=True)
                if product.category not in allowed_categories:
                    messages.error(request, "This item is not allowed for your store.")
                    return redirect('store_dashboard')
                # Check inventory
                try:
                    inventory = StoreInventory.objects.get(store=user_store, product=product)
                    if inventory.quantity <= 0:
                        messages.error(request, f"{product.name} is out of stock.")
                        return redirect('store_dashboard')
                    if inventory.quantity < qty:
                        messages.error(request, f"Insufficient stock! Only {inventory.quantity} available.")
                        return redirect('store_dashboard')
                except StoreInventory.DoesNotExist:
                    messages.error(request, "Product not in inventory.")
                    return redirect('store_dashboard')
                
                # Create sale
                StoreSale.objects.create(
                    store=user_store,
                    cashier=request.user,
                    product=product,
                    item=product.name,
                    qty=qty,
                    unit_price_inr=product.base_price,
                    total_inr=0  # Will be calculated in save()
                )
                messages.success(request, f"Sale recorded: {product.name} x {qty}")
            except Product.DoesNotExist:
                messages.error(request, "Product not found.")
        
        elif action == "purchase":
            product_id = request.POST.get("product_id")
            qty = int(request.POST.get("qty", 1))
            supplier = request.POST.get("supplier", "Railway Stores Depot")
            
            try:
                product = Product.objects.get(id=product_id, active=True)
                if product.category not in allowed_categories:
                    messages.error(request, "This item is not allowed for your store.")
                    return redirect('store_dashboard')
                StorePurchase.objects.create(
                    store=user_store,
                    product=product,
                    quantity=qty,
                    unit_cost=product.base_price,
                    total_cost=0,  # Will be calculated in save()
                    purchased_by=request.user,
                    supplier=supplier
                )
                messages.success(request, f"Purchase recorded: {product.name} x {qty}")
            except Product.DoesNotExist:
                messages.error(request, "Product not found.")
        
        return redirect('store_dashboard')
    
    # Get data for display
    inventory = StoreInventory.objects.filter(
        store=user_store,
        product__category__in=allowed_categories,
    ).select_related('product').order_by('product__name')
    inventory_map = {inv.product_id: inv.quantity for inv in inventory}
    start, end = _get_today_range()
    sales = StoreSale.objects.filter(
        store=user_store,
        sold_at__gte=start,
        sold_at__lt=end,
    ).select_related('product').order_by('-sold_at')[:50]
    purchases = StorePurchase.objects.filter(store=user_store).select_related('product').order_by('-purchased_at')[:50]
    products = Product.objects.filter(active=True, category__in=allowed_categories).order_by('category', 'name')
    products_with_stock = []
    for product in products:
        products_with_stock.append({
            "id": product.id,
            "name": product.name,
            "base_price": product.base_price,
            "category": product.get_category_display(),
            "stock": inventory_map.get(product.id, 0),
        })
    
    # Calculate store revenue today
    today = timezone.localdate()
    today_sales = StoreSale.objects.filter(store=user_store, sold_at__gte=start, sold_at__lt=end)
    today_revenue = sum(s.total_inr for s in today_sales)
    
    return render(request, 'store_dashboard.html', {
        'store': user_store,
        'inventory': inventory,
        'sales': sales,
        'purchases': purchases,
        'products': products,
        'today_revenue': today_revenue,
        'inventory_map': inventory_map,
        'products_with_stock': products_with_stock,
    })


@login_required
@role_required(User.Role.PASSENGER)
def passenger_dashboard(request):
    _update_departed_tickets()
    today = timezone.localdate()
    all_schedules = TrainSchedule.objects.select_related("train").filter(service_date=today).order_by("scheduled_time", "sequence")
    # Filter out trains with no stops
    all_schedules = all_schedules.filter(stops=True)
    schedules = _filter_upcoming_trains(all_schedules)

    if request.method == "POST":
        return _create_tickets_from_booking_request(
            request,
            schedules,
            'passenger',
            PassengerTicket.BookingSource.PASSENGER_PORTAL,
        )

    # Calculate upcoming trains with delays and seat availability
    cumulative_delay = 0
    upcoming_trains = []
    now = timezone.now()
    for s in all_schedules:
        cumulative_delay += s.delay_minutes
        scheduled_dt = timezone.make_aware(datetime.combine(s.service_date, s.scheduled_time))
        effective_dt = scheduled_dt + timedelta(minutes=cumulative_delay)
        is_passed = effective_dt <= now
        
        is_memu = s.train.train_type in ["EMU", "MEMU"]

        # Calculate seat availability by coach class (GN has no seat-based booking)
        booked_tickets = PassengerTicket.objects.filter(schedule=s, status=PassengerTicket.Status.ACTIVE)
        seat_availability = {
            '1A': 18,
            '2A': 54,
            '3A': 64,
            'SL': 72,
            'CC': 78,
            '2S': 100,
        }
        if not is_memu:
            for ticket in booked_tickets:
                if ticket.coach_class in seat_availability:
                    seat_availability[ticket.coach_class] -= ticket.passenger_count
        
        upcoming_trains.append({
            "id": s.id,
            "number": s.train.number,
            "name": s.train.name,
            "scheduled": s.scheduled_time.strftime("%H:%M"),
            "effective": effective_dt.time().strftime("%H:%M"),
            "delay": cumulative_delay,
            "track": s.get_track_type_display(),
            "direction": s.get_direction_display(),
            "seats": seat_availability,
            "is_memu": is_memu,
            "is_passed": is_passed,
        })

    cutoff_time = timezone.now() - timedelta(hours=3)
    my_tickets = PassengerTicket.objects.filter(
        user=request.user,
        booked_at__gte=cutoff_time,
        booking_source=PassengerTicket.BookingSource.PASSENGER_PORTAL,
    ).order_by("-booked_at")
    return render(request, 'passenger_dashboard.html', {
        "schedules": schedules,
        "tickets": my_tickets,
        "upcoming_trains": upcoming_trains,
        "coach_classes": PassengerTicket.CoachClass.choices,
        "service_date": today.strftime("%d-%m-%Y"),
        "ticket_prices": TICKET_PRICES,
        "platform_price": PLATFORM_TICKET_PRICE,
        "max_tickets_per_booking": TICKET_LIMITS_BY_ROLE[User.Role.PASSENGER],
        "reserved_classes_requiring_details": list(RESERVED_CLASSES_REQUIRING_DETAILS),
    })


@login_required
def print_ticket(request, ticket_id):
    ticket = PassengerTicket.objects.select_related("schedule", "schedule__train", "user").filter(id=ticket_id).first()
    if not ticket:
        return HttpResponseForbidden("Ticket not found.")
    if request.user.role not in [User.Role.STATION_MASTER, User.Role.TICKET_STAFF] and ticket.user_id != request.user.id:
        return HttpResponseForbidden("Access denied.")
    train_text = "Platform"
    if ticket.schedule:
        train_text = f"{ticket.schedule.train.number}-{ticket.schedule.train.name}"
    qr_payload = (
        f"PNR:{ticket.pnr}|TYPE:{ticket.ticket_type}|CLASS:{ticket.coach_class}|"
        f"COUNT:{ticket.passenger_count}|AMOUNT:{ticket.amount_inr}|TRAIN:{train_text}|"
        f"BOOKED:{timezone.localtime(ticket.booked_at).strftime('%Y-%m-%d %H:%M:%S')}"
    )
    return render(request, 'ticket_print.html', {
        "ticket": ticket,
        "ticket_qr": _build_qr_base64(qr_payload),
    })


@login_required
def print_goods_label(request, shipment_id):
    shipment = GoodsShipment.objects.select_related("schedule", "schedule__train", "sender").filter(id=shipment_id).first()
    if not shipment:
        return HttpResponseForbidden("Shipment not found.")
    if request.user.role not in [User.Role.STATION_MASTER, User.Role.GOODS_MANAGER]:
        sender_match = shipment.sender_id == request.user.id if shipment.sender_id else False
        email_match = shipment.sender_email.lower() == request.user.email.lower() if shipment.sender_email else False
        if not sender_match and not email_match:
            return HttpResponseForbidden("Access denied.")
    train_text = "NA"
    if shipment.schedule:
        train_text = f"{shipment.schedule.train.number}-{shipment.schedule.train.name}"
    qr_payload = (
        f"TRANS_ID:{shipment.label_no}|SENDER:{shipment.sender_name}|EMAIL:{shipment.sender_email}|"
        f"TRAIN:{train_text}|WEIGHT:{shipment.weight_kg}|DEST:{shipment.destination}|"
        f"AMOUNT:{shipment.amount_inr}|STATUS:{shipment.status}|"
        f"CREATED:{timezone.localtime(shipment.created_at).strftime('%Y-%m-%d %H:%M:%S')}"
    )
    return render(request, 'goods_label_print.html', {
        "shipment": shipment,
        "goods_qr": _build_qr_base64(qr_payload),
    })


@login_required
@role_required(User.Role.STATION_MASTER)
def tickets_report(request):
    days = int(request.GET.get('days', 30))
    start_date = timezone.now() - timedelta(days=days)
    tickets = PassengerTicket.objects.filter(booked_at__gte=start_date).order_by("-booked_at")
    return render(request, 'tickets_report.html', {"tickets": tickets, "days": days})


@login_required
@role_required(User.Role.STATION_MASTER)
def goods_report(request):
    days = int(request.GET.get('days', 30))
    start_date = timezone.now() - timedelta(days=days)
    shipments = GoodsShipment.objects.filter(created_at__gte=start_date).order_by("-created_at")
    return render(request, 'goods_report.html', {"shipments": shipments, "days": days})


@login_required
@role_required(User.Role.STATION_MASTER)
def stores_report(request):
    days = int(request.GET.get('days', 30))
    start_date = timezone.now() - timedelta(days=days)
    sales = StoreSale.objects.filter(sold_at__gte=start_date).order_by("-sold_at")
    return render(request, 'stores_report.html', {"sales": sales, "days": days})


@login_required
@role_required(User.Role.STATION_MASTER)
def full_report(request):
    days = int(request.GET.get('days', 30))
    start_date = timezone.now() - timedelta(days=days)
    tickets = PassengerTicket.objects.filter(booked_at__gte=start_date).order_by("-booked_at")
    shipments = GoodsShipment.objects.filter(created_at__gte=start_date).order_by("-created_at")
    sales = StoreSale.objects.filter(sold_at__gte=start_date).order_by("-sold_at")
    schedules = TrainSchedule.objects.filter(service_date__gte=start_date.date()).order_by("-service_date", "scheduled_time")
    return render(request, 'full_report.html', {
        "tickets": tickets,
        "shipments": shipments,
        "sales": sales,
        "schedules": schedules,
        "days": days,
    })


@login_required
@role_required(User.Role.STATION_MASTER)
def sm_tickets_section(request):
    """Station Master view for ticket counter section"""
    _update_departed_tickets()
    tickets = PassengerTicket.objects.select_related("user", "schedule", "schedule__train").filter(
        user__role=User.Role.TICKET_STAFF
    ).order_by("-booked_at")[:100]
    return render(request, 'sm_tickets_section.html', {"tickets": tickets})


@login_required
@role_required(User.Role.STATION_MASTER)
def sm_passengers_section(request):
    """Station Master view for passengers section"""
    _update_departed_tickets()
    passengers = User.objects.filter(role=User.Role.PASSENGER).order_by("-date_joined")
    passenger_data = []
    for passenger in passengers:
        tickets = PassengerTicket.objects.filter(user=passenger).order_by("-booked_at")[:5]
        passenger_data.append({
            "passenger": passenger,
            "tickets": tickets,
            "total_tickets": PassengerTicket.objects.filter(user=passenger).count(),
        })
    return render(request, 'sm_passengers_section.html', {"passenger_data": passenger_data})


@login_required
@role_required(User.Role.STATION_MASTER)
def sm_goods_section(request):
    """Station Master view for goods section"""
    shipments = GoodsShipment.objects.select_related("sender", "schedule", "schedule__train").order_by("-created_at")[:100]
    return render(request, 'sm_goods_section.html', {"shipments": shipments})


@login_required
@role_required(User.Role.STATION_MASTER)
def sm_stores_section(request):
    """Station Master view for stores section"""
    stores = Store.objects.filter(active=True).order_by("name")
    sales = StoreSale.objects.select_related("store", "cashier").order_by("-sold_at")[:100]
    store_summary = []
    for store in stores:
        store_sales = StoreSale.objects.filter(store=store)
        total_sales = sum(s.total_inr for s in store_sales)
        store_summary.append({
            "store": store,
            "total_sales": total_sales,
            "recent_sales": store_sales.order_by("-sold_at")[:10],
        })
    return render(request, 'sm_stores_section.html', {"store_summary": store_summary, "sales": sales})


@login_required
@role_required(User.Role.STATION_MASTER)
def station_master_revenue(request):
    start, end = _get_today_range()
    tickets_today = PassengerTicket.objects.filter(
        booked_at__gte=start,
        booked_at__lt=end,
        status__in=[PassengerTicket.Status.ACTIVE, PassengerTicket.Status.DEPARTED],
    )
    goods_today = GoodsShipment.objects.filter(created_at__gte=start, created_at__lt=end)
    sales_today = StoreSale.objects.filter(sold_at__gte=start, sold_at__lt=end)

    ticket_revenue = sum(t.amount_inr for t in tickets_today)
    goods_revenue = sum(g.amount_inr for g in goods_today)
    store_revenue = sum(s.total_inr for s in sales_today)
    total_revenue = ticket_revenue + goods_revenue + store_revenue

    return JsonResponse({
        "ticket_revenue": float(ticket_revenue),
        "goods_revenue": float(goods_revenue),
        "store_revenue": float(store_revenue),
        "total_revenue": float(total_revenue),
    })


@login_required
@role_required(User.Role.STORE_STAFF)
def store_revenue(request):
    store = request.user.assigned_store
    if not store:
        return JsonResponse({"error": "No store assigned"}, status=400)
    start, end = _get_today_range()
    today_sales = StoreSale.objects.filter(store=store, sold_at__gte=start, sold_at__lt=end)
    total = sum(s.total_inr for s in today_sales)
    return JsonResponse({"today_revenue": float(total)})


@login_required
@role_required(User.Role.TICKET_STAFF)
def ticket_revenue(request):
    start, end = _get_today_range()
    tickets_today = PassengerTicket.objects.filter(
        booked_at__gte=start,
        booked_at__lt=end,
        status__in=[PassengerTicket.Status.ACTIVE, PassengerTicket.Status.DEPARTED],
        user=request.user,
    )
    total = sum(t.amount_inr for t in tickets_today)
    return JsonResponse({"today_revenue": float(total)})


@login_required
@role_required(User.Role.GOODS_MANAGER)
def goods_revenue(request):
    start, end = _get_today_range()
    shipments_today = GoodsShipment.objects.filter(created_at__gte=start, created_at__lt=end)
    total = sum(s.amount_inr for s in shipments_today)
    return JsonResponse({"today_revenue": float(total)})

