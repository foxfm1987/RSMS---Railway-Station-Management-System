from django.core.management.base import BaseCommand
from django.utils import timezone
from appname.models import Train, TrainSchedule
from datetime import time

class Command(BaseCommand):
    help = 'Reset train schedule for today with default schedule from Railway HQ'

    def handle(self, *args, **options):
        today = timezone.localdate()
        
        # Delete existing schedules for today
        deleted_count, _ = TrainSchedule.objects.filter(service_date=today).delete()
        self.stdout.write(self.style.WARNING(f'Deleted {deleted_count} existing schedules for {today}'))
        
        # Default schedule configuration from Railway Division HQ
        # Format: (train_number, scheduled_time, direction, track_type, stops, delay_minutes)
        default_schedules = [
            # UP direction (left-right) - PLATFORM2 for stops, track 2 for non-stops
            # Mangaluru Express UP - with stops
            ('12601', time(6, 15), 'UP', 'PLATFORM2', True, 0),
            # Coromandel Express UP - with stops
            ('12841', time(7, 30), 'UP', 'PLATFORM2', True, 0),
            # Rajdhani Express UP - no stops
            ('22691', time(9, 0), 'UP', 'MAIN', False, 0),
            # Chennai Mail UP - with stops
            ('16001', time(11, 45), 'UP', 'PLATFORM2', True, 0),
            # MEMU Special UP - with stops
            ('06011', time(6, 0), 'UP', 'PLATFORM2', True, 0),
            ('06011', time(8, 30), 'UP', 'PLATFORM2', True, 0),
            # Goods Rake UP - no stops
            ('GDM01', time(12, 0), 'UP', 'MAIN', False, 0),
            
            # DOWN direction (right-left) - PLATFORM1 for stops, track 3 for non-stops
            # Mangaluru Express DN - with stops
            ('12601', time(18, 45), 'DOWN', 'PLATFORM1', True, 0),
            # Coromandel Express DN - with stops
            ('12841', time(20, 15), 'DOWN', 'PLATFORM1', True, 0),
            # Rajdhani Express DN - no stops
            ('22691', time(22, 30), 'DOWN', 'MAIN', False, 0),
            # Chennai Mail DN - with stops
            ('16001', time(11, 0), 'DOWN', 'PLATFORM1', True, 0),
            # MEMU Special DN - with stops
            ('06011', time(16, 0), 'DOWN', 'PLATFORM1', True, 0),
            ('06011', time(19, 30), 'DOWN', 'PLATFORM1', True, 0),
            # Goods Rake DN - no stops
            ('GDM01', time(2, 0), 'DOWN', 'MAIN', False, 0),
        ]
        
        created_count = 0
        for train_num, sched_time, direction, track_type, stops, delay in default_schedules:
            try:
                train = Train.objects.get(number=train_num)
                schedule = TrainSchedule.objects.create(
                    train=train,
                    service_date=today,
                    scheduled_time=sched_time,
                    sequence=0,
                    direction=direction,
                    track_type=track_type,
                    stops=stops,
                    delay_minutes=delay
                )
                created_count += 1
                self.stdout.write(
                    self.style.SUCCESS(
                        f'Created: {train_num} @ {sched_time} ({direction})'
                    )
                )
            except Train.DoesNotExist:
                self.stdout.write(
                    self.style.ERROR(f'Train {train_num} not found')
                )
        
        self.stdout.write(
            self.style.SUCCESS(f'\n✓ Schedule reset complete! Created {created_count} schedules for {today}')
        )
