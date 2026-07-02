import random
from django.conf import settings
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.utils import timezone

from issues.models import Issue


# Generic, country-neutral demo issues. Coordinates are generated as small
# random offsets from settings.DEFAULT_MAP_LAT/LNG (configurable via .env),
# so seeded data lands near wherever *you've* configured the app for,
# rather than being hardcoded to any specific city.
DEMO_ISSUES = [
    ("Deep pothole on Main Street", "infrastructure", "Vehicles swerving to avoid it, worse after recent rain."),
    ("Overflowing garbage bin near the market", "sanitation", "Not collected in over a week, attracting pests."),
    ("Exposed live wire near the bus stop", "hazard", "Wire hanging low after last storm, safety risk to commuters."),
    ("Streetlight out on Elm Avenue", "infrastructure", "Entire block dark since last week, safety concern at night."),
    ("Open utility cover outside the school gate", "hazard", "Cover missing for several days, right where children cross."),
    ("Drain overflow flooding the sidewalk", "sanitation", "Backed-up drain, water has been standing for days."),
    ("Faded pedestrian crossing markings", "other", "Barely visible at night, vehicles aren't slowing down."),
    ("Broken pavement tiles near the park entrance", "infrastructure", "Pedestrians tripping regularly, needs repair."),
]


class Command(BaseCommand):
    help = "Populate the database with demo users and issues for local testing / screenshots."

    def handle(self, *args, **options):
        demo_user, created = User.objects.get_or_create(
            username="demo_citizen", defaults={"email": "demo@civicfix.local"}
        )
        if created:
            demo_user.set_password("demopass123")
            demo_user.save()
            self.stdout.write("Created user demo_citizen / demopass123")

        center_lat = settings.DEFAULT_MAP_LAT
        center_lng = settings.DEFAULT_MAP_LNG

        if center_lat == 20.0 and center_lng == 0.0:
            self.stdout.write(self.style.WARNING(
                "DEFAULT_MAP_LAT/LNG aren't set — seeding near the generic "
                "world-view default (20, 0). Set them in .env to seed demo "
                "issues near your own city instead, e.g.:\n"
                "  DEFAULT_MAP_LAT=40.7128\n  DEFAULT_MAP_LNG=-74.0060  # New York\n"
            ))

        created_count = 0
        for title, category, desc in DEMO_ISSUES:
            if Issue.objects.filter(title=title).exists():
                continue
            # Small random offset so issues don't all stack on one point.
            lat = center_lat + random.uniform(-0.05, 0.05)
            lng = center_lng + random.uniform(-0.05, 0.05)

            issue = Issue.objects.create(
                title=title, category=category, description=desc,
                latitude=lat, longitude=lng, reported_by=demo_user,
                address="Demo location — set DEFAULT_MAP_LAT/LNG in .env to seed near your own city",
            )
            # Randomly backdate some issues and add upvotes so the
            # priority scoring / overdue logic has something to show.
            backdate_hours = random.choice([2, 30, 80, 150, 200])
            issue.created_at = timezone.now() - timezone.timedelta(hours=backdate_hours)
            issue.save(update_fields=["created_at"])
            created_count += 1

        self.stdout.write(self.style.SUCCESS(f"Seeded {created_count} demo issue(s)."))
