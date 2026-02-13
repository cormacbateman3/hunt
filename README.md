# KeystoneBid

**Pennsylvania Antique Hunting License Marketplace**

A Django-powered auction marketplace for antique and vintage Pennsylvania hunting licenses.

## Features

- **Auction Listings**: Create, browse, and bid on antique PA hunting licenses
- **User Accounts**: Registration, email verification, and user profiles
- **Live Bidding**: Real-time bid updates with HTMX
- **Payment Processing**: Stripe integration for secure payments
- **Email Notifications**: Automated notifications for bids, auctions, and payments
- **Admin Panel**: Django's built-in admin for content moderation

## Technology Stack

- **Framework**: Django 5.0
- **Database**: SQLite (dev) / PostgreSQL (prod)
- **Frontend**: Django Templates + Tailwind CSS (CDN)
- **Dynamic UI**: HTMX + Alpine.js (via CDN)
- **Payments**: Stripe Checkout
- **Email**: Django email backend / AWS SES (prod)
- **Deployment**: AWS EC2 + Gunicorn + Nginx

## Project Structure

```
keystonebid/
├── manage.py
├── config/                 # Project configuration
│   ├── settings/           # Settings split by environment
│   ├── urls.py
│   ├── wsgi.py
│   └── asgi.py
├── apps/                   # Django apps
│   ├── accounts/           # User authentication & profiles
│   ├── listings/           # Auction listings
│   ├── bids/               # Bidding system
│   ├── payments/           # Stripe integration
│   └── notifications/      # Email notifications
├── templates/              # Global templates
├── static/                 # CSS, JS, images
├── media/                  # User uploads
└── requirements/           # Dependencies
```

## Setup Instructions

### 1. Clone the Repository

```bash
git clone <repository-url>
cd repo
```

### 2. Create Virtual Environment

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 3. Install Dependencies

```bash
pip install -r requirements/development.txt
```

### 4. Environment Variables

Copy `.env.example` to `.env` and configure:

```bash
cp .env.example .env
```

Edit `.env` with your settings (database, Stripe keys, etc.)

### 5. Run Migrations

```bash
python manage.py migrate
```

### 6. Create Superuser

```bash
python manage.py createsuperuser
```

### 7. Run Development Server

```bash
python manage.py runserver
```

Visit `http://localhost:8000`

## Management Commands

### Close Expired Auctions

```bash
python manage.py close_auctions
```

### Send Pending Notifications

```bash
python manage.py send_notifications
```

## Development

- **Settings**: Use `config.settings.development` (default)
- **Database**: SQLite (no setup required)
- **Email**: Console backend (prints to terminal)
- **Static Files**: Served by Django development server

## Production Deployment

1. Update `config/settings/production.py` with production settings
2. Set `DJANGO_SETTINGS_MODULE=config.settings.production`
3. Configure PostgreSQL database
4. Configure AWS SES for email
5. Set up Gunicorn + Nginx
6. Configure SSL with Let's Encrypt
7. Set up cron jobs for management commands

## Django Apps

- **accounts**: User registration, login, profiles, email verification
- **listings**: Auction listings, image uploads, browse/filter
- **bids**: Bidding logic, auction close, winner determination
- **payments**: Stripe checkout, webhooks, transaction tracking
- **notifications**: Email queue and delivery system

## Contributing

See the development plan PDF for detailed implementation guidelines.

## License

Private project - All rights reserved
