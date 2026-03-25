# SwimSyncEDU Viva Prep

## 1. One-line project explanation
SwimSyncEDU is a Django-based swimming management system where users can discover pools, book group or private classes, pay online, view attendance and certificates, and review trainers, while admins manage pools, trainers, schedules, attendance, and quality records.

## 2. Core architecture
- Framework: Django
- Database: MySQL
- Frontend: Django templates + static CSS/JS
- Main project config: `swimsyncedu/settings.py`, `swimsyncedu/urls.py`
- Apps:
  - `accounts`: login, signup, roles, dashboards, member/trainer management
  - `pool`: pools, images, pool quality, trainer-pool assignment, nearby search
  - `classes`: class types, group sessions, private classes, bookings, certificates
  - `attendance`: trainer attendance, student attendance, substitute trainer flow
  - `payments`: eSewa/Khalti payment flow, payment reports
  - `reviews`: trainer reviews and certificate viewing

## 3. How request flow works
1. Browser sends request to Django URL.
2. `swimsyncedu/urls.py` routes the request to the correct app.
3. App `urls.py` maps the route to a view function.
4. View reads/writes models.
5. View returns an HTML template or redirects to another route.
6. Templates render the data for the user.

Example:
- `/pool/nearby/` -> `pool/urls.py` -> `nearby_pools()` in `pool/views.py`
- That view queries `Pool` and returns `templates/pools/nearby_pools.html`

## 4. Main models and what connects to what

### Accounts
- `User` in `accounts/models.py`
- Custom auth model with roles: `user`, `trainer`, `admin`
- This is the central model used by almost every app

### Pools
- `Pool`: pool info like name, address, capacity, coordinates
- `PoolImage`: multiple images for one pool
- `PoolQuality`: daily quality record for one pool
- `TrainerPoolAssignment`: connects one trainer to one pool for a date range

### Classes
- `ClassType`: type of class with cost and duration
- `ClassSession`: actual group class at a pool with trainer, class type, schedule
- `ClassBooking`: user booking for one group class session
- `PrivateClassDetails`: global admin pricing for private classes
- `PrivateClass`: one user with one trainer at one pool for a date range
- `CompletionCertificate`: generated after finishing a class/private class

### Attendance
- `TrainerAttendanceRecord`: whether trainer is present/absent on a date
- `ClassSessionAttendance`: student attendance for group class on a date
- `PrivateClassAttendance`: student attendance for private class on a date

### Payments
- `Payment`: records group/private payments, gateway status, payload, links to booking/private class

### Reviews
- `Review`: one review per completion certificate

## 5. Relationship summary
- One `User` can be a member, trainer, or admin.
- One `Pool` can have many `ClassSession`, `PoolImage`, `PoolQuality`, and `TrainerPoolAssignment`.
- One trainer can be assigned to many pools over time, but code tries to prevent overlapping active assignments.
- One `ClassType` can be used in many `ClassSession`.
- One `ClassSession` belongs to one trainer, one pool, one class type.
- One user can make many `ClassBooking`.
- One `Payment` can create one `ClassBooking` or one `PrivateClass`.
- One `CompletionCertificate` belongs to either one `ClassBooking` or one `PrivateClass`.
- One `Review` is tied to one certificate, so duplicate review for same certificate is blocked.

## 6. Important code entry points
- Root routing: `swimsyncedu/urls.py`
- Auth entry: `accounts/views.py`
- Pool discovery and admin pool management: `pool/views.py`
- Group/private class logic: `classes/views.py`
- Attendance and substitute logic: `attendance/views.py`
- Payment verification and booking creation: `payments/views.py`
- Reviews and certificate export: `reviews/views.py`

## 7. End-to-end feature flows

### A. Login flow
- Route: `/accounts/login/`
- View: `login_view()` in `accounts/views.py`
- Uses Django `authenticate()` and `login()`
- After login it checks `user.role`
- Admin -> admin dashboard
- Trainer -> trainer dashboard
- User -> user dashboard

### B. Group class booking flow
1. User opens nearby pools.
2. User chooses pool and class type.
3. User sees available class sessions.
4. Clicking book goes to `book_class()` in `classes/views.py`.
5. That redirects to `group_class_payment_checkout()` in `payments/views.py`.
6. A `Payment` row is created with `Pending`.
7. User pays with eSewa or Khalti.
8. Success callback verifies amount, transaction id, and status.
9. `complete_group_payment()` creates `ClassBooking`.
10. `ClassSession.total_bookings` increases by 1.

### C. Private class booking flow
1. User chooses pool.
2. User chooses trainer assigned to that pool.
3. `book_private_class()` validates dates, time, overlap, assignment, and weekdays.
4. Checkout info is stored in session as `private_class_checkout`.
5. `private_class_payment_checkout()` creates `Payment`.
6. On success, `complete_private_payment()` creates `PrivateClass`.

### D. Attendance flow
1. Admin marks trainer present/absent.
2. If trainer is absent, admin can:
   - assign substitute trainer
   - cancel class for today
3. Trainer marks student attendance for group/private classes.
4. User dashboard `todays_classes()` combines bookings and attendance records to show status like upcoming, ongoing, completed, cancelled.

### E. Certificate and review flow
1. After class/private class ends, trainer issues `CompletionCertificate`.
2. User opens certificate page.
3. User creates review.
4. Review is linked to certificate, so only one review per certificate.
5. Certificate can also be printed from the certificate page.

## 8. Business rules worth saying in viva
- Only assigned trainers should teach in a pool.
- Group class overlap in same pool is blocked.
- Private class overlap for same trainer/pool/time is blocked.
- Class times are limited between 06:00 and 19:00.
- Class duration cannot exceed 3 hours.
- Private class price is based on weekday count only.
- Attendance can only be marked for today.
- Weekend attendance marking is blocked.
- Certificates are only issued after class end date.
- Payment is verified before booking/private class is finalized.

## 9. What connects to what

### Auth to everything
- `AUTH_USER_MODEL = 'accounts.User'` in `swimsyncedu/settings.py`
- All foreign keys to users point to this custom user model

### Pool to classes
- `ClassSession.pool -> Pool`
- `PrivateClass.pool -> Pool`

### Trainer assignment to scheduling
- `TrainerPoolAssignment` is checked before creating group/private classes
- If assignment ends before class end date, creation is rejected

### Classes to payments
- `book_class()` redirects to payment checkout
- `Payment` stores purpose and links to class/private data
- Successful payment creates final booking/private class

### Classes to attendance
- `ClassSessionAttendance.class_session -> ClassSession`
- `PrivateClassAttendance.private_class -> PrivateClass`
- `todays_classes()` reads attendance rows to decide UI status

### Classes to certificates to reviews
- `CompletionCertificate` is created from completed class/private class
- `Review.certificate -> CompletionCertificate`
- This prevents random users from reviewing trainers without completing training

## 10. Likely viva questions and short answers

### Why did you use separate apps?
Because each domain has a clear responsibility. `accounts` handles identity, `pool` handles infrastructure, `classes` handles scheduling, `attendance` handles daily operations, `payments` handles transactions, and `reviews` handles feedback. This keeps code modular and easier to maintain.

### Why use a custom user model?
Because the system needs role-based behavior and trainer-specific fields like specialization and experience. A custom user model avoids creating separate profile tables later.

### Why keep payment separate from booking?
Because payment is a transaction with its own lifecycle: pending, completed, failed, cancelled. Only after verification does the system create a booking or private class.

### Why use certificates before reviews?
To guarantee only users who actually completed a training session can review the trainer.

### Why store private class checkout in session?
Because the system collects booking details before payment succeeds. Session temporarily holds the booking info until the payment callback finalizes it.

## 11. "If we change this, what happens?" questions

### If we remove `AUTH_USER_MODEL`
- Django auth will try to use default `auth.User`
- Existing foreign keys and login logic will break
- Migrations and authentication will become inconsistent

### If we change `user.role`
- Dashboard routing changes
- Permission checks across views change
- A trainer changed to user may lose access to attendance and certificate pages

### If we remove `TrainerPoolAssignment` check before scheduling
- A trainer could be scheduled in any pool
- Pool-trainer consistency breaks
- Viva answer: assignment is used as a business constraint

### If we remove overlap checks in class/private booking
- Two classes may run in the same pool at the same time
- One trainer may be double-booked
- Attendance and substitute logic become unreliable

### If we create booking before payment verification
- Users could get classes without successful payment
- Duplicate unpaid reservations become possible

### If we remove payment amount verification
- A tampered callback could mark wrong payments as successful
- This is a security and accounting issue

### If we remove `OneToOneField` from review/certificate
- Same certificate could have multiple reviews
- That would change business logic and review counting

### If we remove `total_bookings` update
- Seat tracking becomes incorrect
- Class may appear available when full, or full when not

## 12. Common errors and how to fix them

### Migration error after changing models
Problem:
- You changed model fields and app crashes or queries fail

Fix:
1. Run `python manage.py makemigrations`
2. Run `python manage.py migrate`
3. If field names changed, check old migrations and dependent code

### Login not working
Check:
- username/password correct
- `AUTH_USER_MODEL` is set
- user exists in DB
- password was created with `set_password()`

Fix:
- Make sure users are created via `create_user()`, not raw password insert

### Images not showing
Check:
- `MEDIA_URL` and `MEDIA_ROOT`
- `urlpatterns += static(...)` under `DEBUG`
- template is using `{{ image.url }}`

### Payment success page not creating booking
Check:
- gateway callback data exists
- transaction UUID matches stored payment UID
- amount matches `payment.total_amount`
- payment status became `Completed`

### Nearby pool distance not working
Check:
- coordinates format must be `lat,lng`
- user location query params exist
- `geopy` may be missing, but fallback Haversine is implemented

### Attendance not marking
Check:
- date must be today
- trainer must have permission
- for group class, trainer must be marked present first
- weekends are blocked

### Certificate not issuing
Check:
- class/private class end date must already pass
- certificate must not already exist
- trainer must own the class or be substitute trainer

## 13. Real code weaknesses you should know before viva

### Inconsistent admin permission style
- Some places check `request.user.role == 'admin'`
- Some places check `request.user.is_superuser == False`
- Better design: use one consistent permission rule

### Debug prints in landing page
- `index()` prints auth info to console
- Fine for development, not for production

### Hardcoded development security values
- `SECRET_KEY` is hardcoded
- `DEBUG = True`
- Database credentials are local development style
- Good viva answer: acceptable for prototype, should move fully to environment variables in production

### Duplicate helper logic
- `_parse_busy_range()` and `_build_trainer_unavailability()` appear in both `pool/views.py` and `classes/views.py`
- Better design: move them to shared utility module

### Group/private attendance consistency
- Group and private attendance both require the trainer to be marked present before student attendance can be marked
- Viva answer: this is an area for improvement to make rules consistent

## 14. Strong viva explanation for design choices
- Django was chosen because it provides rapid development, authentication, ORM, admin support, URL routing, template rendering, and clean separation of apps.
- MySQL was used as relational data is central here: users, pools, bookings, payments, attendance, certificates, and reviews all have strong relationships.
- Business rules are enforced in view logic before writing to the database to prevent invalid schedules and invalid payments.
- Role-based access is implemented using the custom `User` model and checks in views.

## 15. Fast revision cheat sheet
- `accounts`: who the user is
- `pool`: where the class happens
- `classes`: what is scheduled/booked
- `attendance`: whether class actually happened and who attended
- `payments`: whether payment succeeded before finalizing
- `reviews`: feedback after completion

## 16. Best way to answer diagram-style viva questions
Say this:
"The project starts from URL routing. The request hits a Django view, the view validates role and business rules, reads or writes MySQL through models, then returns a template or redirects to the next step. Payments are separated from bookings so a booking is only finalized after verified payment. Certificates are generated after class completion, and reviews are tied to certificates so only completed students can review."

## 17. Commands to remember
```powershell
python manage.py runserver
python manage.py makemigrations
python manage.py migrate
python manage.py createsuperuser
python manage.py test
```

## 18. Final viva advice
- Always answer in flow form: route -> view -> model -> template
- Mention business rule checks before database save
- If asked about improvements, mention:
  - move duplicate helpers to utilities
  - unify permission checks
  - move secrets fully to env vars
  - add more tests
  - strengthen production security
