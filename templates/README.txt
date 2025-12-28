SwimSync EDU - Django Frontend Setup

STRUCTURE:
- templates/ - All HTML templates
  - base.html - Base template with common structure
  - index.html - Landing page
  - auth/ - Authentication pages (login, signup)
  - dashboards/ - Role-specific dashboards (member, instructor, admin)

- static/ - Static files
  - css/ - Separate CSS files for different sections
    - base.css - Core styles and utilities
    - landing.css - Landing page styles
    - auth.css - Authentication pages styles
    - dashboard.css - Dashboard common styles
    - admin.css - Admin-specific styles
  - js/ - JavaScript files
    - script.js - Common JavaScript functionality

SETUP:
1. Copy templates/ folder to your Django project root
2. Copy static/ folder to your Django project root
3. In settings.py, ensure:
   TEMPLATES = [{
       'DIRS': [BASE_DIR / 'templates'],
       ...
   }]
   STATIC_URL = '/static/'
   STATICFILES_DIRS = [BASE_DIR / 'static']

4. Create views in views.py (sample provided)
5. Configure URLs in urls.py (sample provided)
6. Run migrations and start server

FEATURES:
- Responsive design for mobile and desktop
- Clean aquatic-themed design with CSS variables
- Role-based dashboards (Member, Instructor, Admin)
- Django template syntax with {% extends %}, {% block %}, {% url %}
- Proper CSRF protection with {% csrf_token %}
- Separate, organized CSS files for maintainability
