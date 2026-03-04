"""
populate.py — Populate SkillSwap with demo data.

Usage:
    python manage.py shell < populate.py
  OR
    python populate.py  (if run with the right DJANGO_SETTINGS_MODULE)
"""

import os
import django
from decimal import Decimal

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'skillswap.settings')
django.setup()

from django.contrib.auth.models import User
from core.models import UserProfile, Skill, ServiceRequest, Bid, Exchange, LedgerEntry

print("Clearing existing data…")
LedgerEntry.objects.all().delete()
Exchange.objects.all().delete()
Bid.objects.all().delete()
ServiceRequest.objects.all().delete()
Skill.objects.all().delete()
UserProfile.objects.all().delete()
User.objects.filter(is_superuser=False).delete()

print("Creating users…")

def make_user(username, first, last, email, balance):
    u = User.objects.create_user(username=username, password='skillswap', email=email,
                                  first_name=first, last_name=last)
    UserProfile.objects.create(user=u, time_balance=Decimal(str(balance)),
                                bio=f"{first} is passionate about sharing skills.")
    return u

alice  = make_user('alice',  'Alice',  'Chen',    'alice@example.com',  8.0)
bob    = make_user('bob',    'Bob',    'Patel',   'bob@example.com',    5.0)
carol  = make_user('carol',  'Carol',  'Smith',   'carol@example.com',  6.5)
dave   = make_user('dave',   'Dave',   'Kim',     'dave@example.com',   3.0)

# Admin superuser
if not User.objects.filter(username='admin').exists():
    User.objects.create_superuser('admin', 'admin@skillswap.com', 'admin123')
    print("Superuser: admin / admin123")

print("Creating skills…")
Skill.objects.create(user=alice,  title='Linear Algebra',    description='Eigenvectors, matrices, dot products.', level='advanced',     duration_hours=1.0)
Skill.objects.create(user=alice,  title='Python Programming', description='Beginner to intermediate Python.',      level='intermediate', duration_hours=1.5)
Skill.objects.create(user=bob,    title='Guitar',             description='Acoustic guitar — chords and theory.',  level='intermediate', duration_hours=1.0)
Skill.objects.create(user=carol,  title='UX Design',          description='Wireframes, user testing, Figma.',      level='expert',       duration_hours=2.0)
Skill.objects.create(user=dave,   title='Spanish',            description='Conversational Spanish at A2–B1 level.',level='intermediate', duration_hours=1.0)

print("Creating service requests…")
r1 = ServiceRequest.objects.create(requester=bob,   title='Help with Eigenvalues',    skill_category='Mathematics',      description='Need help understanding eigenvalues for my ML course.', hours_required=Decimal('1.0'), preferred_schedule='Evenings or weekends')
r2 = ServiceRequest.objects.create(requester=carol, title='Learn Python basics',      skill_category='Programming',     description='Total beginner — want to learn loops and functions.',   hours_required=Decimal('1.5'), preferred_schedule='Saturday mornings')
r3 = ServiceRequest.objects.create(requester=alice, title='Guitar lesson swap',       skill_category='Music',           description='Looking for acoustic guitar intro session.',            hours_required=Decimal('1.0'), preferred_schedule='Any afternoon')
r4 = ServiceRequest.objects.create(requester=dave,  title='UX feedback on my app',    skill_category='Design',          description='Quick UX review of a student project prototype.',       hours_required=Decimal('1.0'), preferred_schedule='Flexible')

print("Creating bids…")
b1 = Bid.objects.create(request=r1, provider=alice, proposed_hours=Decimal('1.0'), message='I teach linear algebra at uni level — happy to help!', status='accepted')
b2 = Bid.objects.create(request=r2, provider=alice, proposed_hours=Decimal('1.5'), message='I run Python workshops — this is perfect for me.', status='accepted')
b3 = Bid.objects.create(request=r3, provider=bob,   proposed_hours=Decimal('1.0'), message='Acoustic is my main instrument — let\'s do it!', status='accepted')
Bid.objects.create(request=r4, provider=carol, proposed_hours=Decimal('1.0'), message='UX is my speciality — I can give you actionable feedback.', status='pending')

print("Creating exchanges and settling r1, r2…")

def create_exchange(sr, bid):
    sr.status = 'accepted'
    sr.save()
    bid.status = 'accepted'
    bid.save()
    return Exchange.objects.create(service_request=sr, bid=bid, agreed_hours=bid.proposed_hours)

ex1 = create_exchange(r1, b1)
ex2 = create_exchange(r2, b2)
ex3 = create_exchange(r3, b3)

from core.views import _settle_exchange
_settle_exchange(ex1)
_settle_exchange(ex2)

print("Done! Demo credentials:")
print("  alice / skillswap")
print("  bob   / skillswap")
print("  carol / skillswap")
print("  dave  / skillswap")
print("  admin / admin123")
print("\nRun the server: python manage.py runserver")
