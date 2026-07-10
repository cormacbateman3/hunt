KEYSTONEBID
Pennsylvania Antique Hunting License Marketplace
Django Development Plan - MVP to Scale
Cost-Conscious Development • Modular • Scalable • Production-Ready
 
Table of Contents
1. Executive Summary, Brand, & Django Rationale
2. MVP vs Post-MVP Features
3. Django Technology Stack
4. Modular Django App Architecture
5. Database Schema (Django Models)
6. Design & UX Direction
7. MVP Core Features
8. ALPHA Phase 1
9. ALPHA Phase 2
10. ALPHA Phase 3
11. BETA
12. Launch
13. Post-MVP Features
14. Development Plan: Phase by Phase
15. AWS Deployment & Cost Strategy
16. Scaling Path
17. Security & Legal
 
1. Executive Summary & Django Rationale
1.1 Mission
KeystoneBid is a dedicated online auction marketplace for antique and vintage Pennsylvania hunting licenses. It is not a general hunting marketplace, not a social network, and not a gaming app. Its primary function is connecting collectors who want to buy, sell, and trade authentic pieces of Pennsylvania hunting history in a trustworthy, curated environment.
The secondary function is cultural stewardship — the platform celebrates the deep tradition of hunting in Pennsylvania, educates visitors about the history of the license system, the people behind it, and the communities it shaped. Every non-transactional feature serves this mission.
1.1.2 Target Audience
The primary audience is the existing Pennsylvania antique hunting license collector community, which is active, passionate, and well-networked. These collectors attend shows, maintain physical collections, and are highly knowledgeable about scarcity, provenance, and value. Many are older and value authenticity over trendiness, but a meaningful younger generation also participates.
Secondary audiences include Pennsylvania hunting heritage enthusiasts who may not yet collect, antique dealers who occasionally handle licenses, and history researchers or educators.
1.1.3 Name & Brand Direction
Suggested working name: KeystoneBid — referencing Pennsylvania's "Keystone State" identity, which resonates deeply with PA residents. The brand should feel like a well-worn field journal: earthy, honest, quietly proud. Not polished corporate, not rustic kitsch. Think the aesthetic of a carefully preserved license book from 1942 — aged paper tones, deep forest greens, warm browns, clean serif typography. Modern in its functionality, classical in its soul.
Gamification on KeystoneBid is purely about personal joy, discovery, and community recognition — not competition. There are no leaderboards, no rankings, no points for buying more. Every mechanic is designed to make an individual collector's experience richer, more organized, and more fun. The historical and community spirit comes first.
Design Directive: The website must feel like it belongs to Pennsylvania hunters. A collector from Lycoming County should open it and feel immediately at home. Avoid anything that feels generic, Silicon Valley, or gamified in an aggressive way. The platform honors a living tradition.
1.2 Why Django Architecture
•	I know python
•	Batteries-included framework: Built-in admin panel, authentication system, ORM with migrations, form handling, security features (CSRF, XSS protection) all out of the box
•	Less code to write: Django's conventions mean you build features faster than Flask's 'assemble your own stack' approach
•	Modular by design: Django apps are self-contained modules. Each feature (listings, bids, payments, collector tools) is an independent app
•	Production-ready from day one: Django is built for scaling. Instagram, Pinterest, and Spotify use Django at massive scale
•	Admin panel included: You get a full content management system for free. No need to build admin views for listings, users, transactions

1.3 Cost Philosophy
•	Development phase: $0 (AWS free tier + SQLite)
•	First 12 months: $0.50–$5/month (EC2 free tier + Route 53)
•	After free tier: $20–$35/month (EC2, RDS, S3 combined)
•	Scale only when revenue justifies it: Start small, upgrade infrastructure as paying users grow 
2. MVP vs Post-MVP Features
2.1 What is MVP?
MVP = The smallest feature set needed to facilitate buying and selling antique PA hunting licenses. If a feature doesn't directly enable a transaction, it's post-MVP.
Feature	Why MVP
User registration & login	Django's built-in auth system. Users need accounts to list and bid.
Email verification	Prevents spam accounts. Django email backend + token verification.
Create listing	Core functionality. Sellers upload photos, set price, choose duration.
Browse & filter listings	Buyers need to find items. Filter by county and year via Django QuerySets.
Place bid	Core auction mechanic. Server-side validation, outbid detection.
Auto-close auctions	Django management command via cron. No manual intervention required.
Payment (Stripe)	Stripe Checkout for buyer payment. Without this, no marketplace.
Email notifications	Outbid alerts and auction-won emails expected by users.
User dashboard	Buyers/sellers see active bids/listings. Django class-based views.
Django admin	Moderate listings and manage users. Free with Django.

2.2 Post-MVP Features (Add Later)
•	Proxy bidding & Buy It Now - Nice to have but manual bidding proves concept
•	Watchlist & saved searches - Convenience features, not core to transactions
•	Reviews & ratings - Important at scale but not needed for first 20 sales
•	Education hub (articles, timeline, county spotlights) - Great for SEO and community but not needed to sell licenses
•	Collector features (county tracker, badges, collection showcase) - Engagement tools that prove value only after users are active
•	User stories/blog posts - Community content, additive not essential
•	Price history charts - Requires data. Can't build without completed sales 
3. Django Technology Stack
3.1 Complete Stack Overview
Layer	Technology	Why This Choice
Backend Framework	Django 5.0	Python web framework with admin panel, auth system, ORM, and form handling built-in. Less code to write than Flask.
Database (Dev)	SQLite	Zero configuration. Included with Python. Switches to PostgreSQL with one settings change.
Database (Prod)	PostgreSQL	Industry-standard relational database. Start on EC2 (free), move to RDS when scaling.
Frontend - HTML	Django Templates	Server-side rendering. Django generates complete HTML pages. SEO-friendly, fast initial load.
Frontend - CSS	Custom CSS	Write your own styles. Organize in modular files. Use CSS custom properties for theming.
Frontend - JavaScript	Vanilla JavaScript (ES6+)	Your existing JS skills apply directly. No framework needed for this app's complexity level.
Background Jobs (MVP)	Django Management Commands + Cron	Python scripts that run on schedule. Close auctions, send emails. Simple and reliable.
Background Jobs (Scale)	Celery + Redis	When you need complex task queuing or need to process hundreds of jobs concurrently. Not needed initially.
Authentication	Django built-in (django.contrib.auth)	User accounts, login/logout, password hashing, permissions - all included. Zero setup.
Payments	Stripe Checkout	Hosted payment page. Stripe handles PCI compliance, you handle none of the card data.
Image Storage (Dev)	Local filesystem via Django's ImageField	Images save to media/ directory. Django serves them during development.
Image Storage (Prod)	AWS S3 via django-storages	Move images off EC2 instance to S3. Scales infinitely, serves via CloudFront CDN.
Email	Django's email backend + AWS SES	Django sends emails natively. SES provides 62,000 emails/month free.
Hosting	AWS EC2 t3.micro	Single server runs Django + PostgreSQL together. Free tier covers 750 hours/month for 12 months.
Web Server	Gunicorn + Nginx	Gunicorn runs Django (WSGI). Nginx sits in front as reverse proxy, handles static files and SSL.
SSL	Let's Encrypt (Certbot)	Free SSL certificates. Auto-renewal via cron. Industry standard.
3.2 Why JavaScript Is Essential
An auction site requires several real-time features that JavaScript handles best:
What JavaScript Does:
Countdown timers - Show auction ending in "2h 15m 32s" and update every second without page reload
Live bid updates - Poll server every 10 seconds to show new bids without manual refresh
Image gallery/zoom - Click thumbnail to view full image, next/prev navigation, zoom capability
Form validation - Check bid amount is valid before submission, provide instant feedback
Dynamic filtering - Update listing results when user changes filters without full page reload (optional enhancement)
What Django Does:
Renders the initial HTML page with all data
Provides JSON API endpoints that JavaScript calls (e.g., /listings/123/bid-status/ returns current bid)
Handles all form submissions, database updates, business logic
Manages authentication, security, payments
3.3 Frontend Architecture: Django + JavaScript Pattern
How They Work Together:
User visits listing page → Django renders complete HTML with listing data
Page loads → Your JavaScript initializes: 
Reads auction end time from data-auction-end attribute Django put in HTML
Starts countdown timer using setInterval()
Starts polling Django's API for bid updates using fetch()
User places bid → Form submits to Django (traditional POST)
Django processes bid → Updates database, returns success/error
JavaScript detects change → Next poll shows updated bid without page reload
3.4 Required Python Packages
Core (MVP):
Django==5.0
Pillow==10.2.0              # Image processing for ImageField
psycopg2-binary==2.9.9      # PostgreSQL database adapter
gunicorn==21.2.0            # Production WSGI server
stripe==8.0.0               # Payment processing
python-dotenv==1.0.0        # Environment variable management
Production (when scaling):
django-storages==1.14       # S3 integration
boto3==1.34.0               # AWS SDK (for S3)
celery==5.3.6               # Background task queue
redis==5.0.1                # Celery broker/backend
Development:
django-extensions==3.2.3    # shell_plus, runserver_plus
ipython==8.12.0             # Better Python shell
3.5 CSS Approach
static/css/
├── reset.css          # Normalize browser defaults
├── variables.css      # CSS custom properties (colors, spacing)
├── base.css           # Typography, defaults
├── layout.css         # Grid, page structure
├── components.css     # Cards, buttons, badges
└── pages/
    ├── listing.css    # Listing page specific
    └── browse.css     # Browse page specific
3.6 What You DON'T Need
React/Vue/Angular - Overkill for this app's complexity
TypeScript - Adds compilation step, not needed for Python developers
Sass/SCSS - CSS custom properties handle theming, no preprocessor needed
Webpack/Vite - No build step = faster development
jQuery - Modern vanilla JS is cleaner and faster
Bootstrap - Write your own styles for unique Pennsylvania aesthetic
4. Modular Django App Architecture
4.1 Django Apps = Modularity
Each feature is a Django app. Apps are self-contained with their own models, views, templates, and URLs. Enable/disable by adding/removing from INSTALLED_APPS. Zero coupling between apps except through model relationships.

4.2 MVP Apps
Django App	Responsibility
accounts	User registration, login, email verification, profiles. Extends Django's User model.
listings	Create/edit/view auction listings. Browse, filter, image uploads. Core marketplace.
bids	Place bids, bid history, auction close logic, winner determination.
payments	Stripe checkout, payment confirmation, transaction records, webhooks.
notifications	Email queue, outbid alerts, auction won notifications.

4.4 Project Structure
keystonebid/
├── manage.py                           # Django CLI
├── config/
│   ├── settings/
│   │   ├── base.py                     # Shared settings
│   │   ├── development.py              # Dev: DEBUG=True, SQLite
│   │   └── production.py               # Prod: DEBUG=False, PostgreSQL
│   ├── urls.py                         # Root URL configuration
│   ├── wsgi.py                         # WSGI config
│   └── asgi.py                         # Optional (future real-time)
│
├── apps/
│   ├── accounts/                       # Auth, profiles, verification, addresses
│   │   ├── models.py                   # UserProfile, Address (and verification fields)
│   │   ├── views.py
│   │   ├── forms.py
│   │   ├── urls.py
│   │   └── templates/accounts/
│   │
│   ├── core/                           # Shared primitives + reference data (lean)
│   │   ├── models.py                   # County, LicenseType (+ any shared enums/constants)
│   │   ├── management/commands/        # Seed counties/types
│   │   └── admin.py
│   │
│   ├── collections/                    # User collections + wanted list (trade inventory)
│   │   ├── models.py                   # CollectionItem, CollectionItemImage, WantedItem
│   │   ├── views.py
│   │   ├── forms.py
│   │   ├── urls.py
│   │   └── templates/collections/
│   │
│   ├── listings/                       # Unified listings (auction/buy_now/trade)
│   │   ├── models.py                   # Listing, ListingImage (listing_type, reserve, etc.)
│   │   ├── views.py
│   │   ├── forms.py
│   │   ├── services.py                 # Listing create helpers (prefill from collection)
│   │   ├── urls.py
│   │   └── templates/listings/
│   │
│   ├── bids/                           # Auction-only bidding logic
│   │   ├── models.py                   # Bid
│   │   ├── services.py                 # place_bid(), winner resolution
│   │   ├── views.py
│   │   ├── urls.py
│   │   └── templates/bids/
│   │
│   ├── orders/                         # Orders + lifecycle (auction + buy-now)
│   │   ├── models.py                   # Order, AddressSnapshot
│   │   ├── services.py                 # state transitions, deadlines, completion
│   │   ├── views.py                    # order detail, confirm receipt, cancel rules
│   │   ├── urls.py
│   │   └── templates/orders/
│   │
│   ├── payments/                       # Stripe Checkout + webhooks
│   │   ├── models.py                   # PaymentTransaction (and optional TradeFeeTransaction)
│   │   ├── stripe_helpers.py
│   │   ├── webhooks.py                 # Idempotent webhook handlers
│   │   ├── views.py
│   │   └── urls.py
│   │
│   ├── shipping/                       # Labels + tracking (Shippo/EasyPost)
│   │   ├── models.py                   # Shipment, ShipmentEvent, TradeShipment
│   │   ├── providers/                  # shippo.py / easypost.py wrapper
│   │   ├── services.py                 # buy label, update status, polling fallback
│   │   ├── webhooks.py                 # tracking webhooks (provider -> Shipment updates)
│   │   ├── urls.py
│   │   └── templates/shipping/
│   │
│   ├── trades/                         # Trading Block negotiation + agreement + lifecycle
│   │   ├── models.py                   # TradeOffer, TradeOfferItem, Trade
│   │   ├── services.py                 # counter/accept/expire, deadlines, state transitions
│   │   ├── views.py                    # propose/counter UI, trade detail
│   │   ├── urls.py
│   │   └── templates/trades/
│   │
│   ├── favorites/                      # Favorites/watch (user saves)
│   │   ├── models.py                   # Favorite (listing or collection_item)
│   │   ├── views.py
│   │   └── urls.py
│   │
│   ├── enforcement/                    # Strikes, excuses, restrictions (low-maintenance trust)
│   │   ├── models.py                   # Strike (with excused fields), AccountRestriction
│   │   ├── services.py                 # apply_strike(), excuse_flow(), gating checks
│   │   └── admin.py
│   │
│   └── notifications/                  # In-app + email notifications
│       ├── models.py                   # Notification (is_read, sent_email, link_url)
│       ├── services.py                 # enqueue/send
│       ├── management/commands/        # send_notifications, retry failed
│       └── templates/emails/
│
├── templates/
│   ├── base.html                       # Master template
│   └── components/                     # Shared partials (nav, cards, alerts)
│
├── static/
│   ├── css/
│   └── js/
│
├── media/                              # User uploads (dev only)
│
├── requirements/
│   ├── base.txt
│   ├── development.txt
│   └── production.txt
│
├── .env.example
└── README.md 
5. Database Schema (Django Models)
5.1 MVP Models Only
Django ORM handles database abstraction. These models create all necessary tables automatically via migrations.
Core Principles
•	Use Django FK relationships to preserve historical accuracy (snapshot addresses, pricing, and shipping details at time of transaction).
•	Separate Listing (market-facing) from CollectionItem (user-owned inventory) so trades can safely reference inventory without relying on listings.
•	Use explicit status fields to support automation (cron jobs / background tasks) and reduce manual admin work.

5.2 Users & Verification
User (Django built-in)
Use Django’s User for authentication and security. Django provides User model with username, email, password.
UserProfile (extends User via OneToOneField)
•	user — OneToOneField(User)
•	display_name — CharField(100)
•	bio — TextField(blank=True)
•	home_county — ForeignKey(County, null=True, blank=True) (prefer FK over free text)
•	avatar — ImageField(blank=True)
•	email_verified — BooleanField(default=False)
•	phone_verified — BooleanField(default=False) (Alpha: trading gate)
•	shipping_address — ForeignKey(Address, null=True, blank=True) (default ship-from; snapshot later)
•	stripe_customer_id — CharField(100, blank=True)
•	created_at — DateTimeField(auto_now_add=True)
Relationships
•	UserProfile ↔ Address: many users can point to one address record, but in practice create per-user.
•	UserProfile is the canonical source for “allowed to trade” checks (verification flags + strikes).

5.3 Reference Data
County
•	name — CharField(50, unique=True)
•	state — CharField(2, default="PA")
•	fips_code — CharField(5, blank=True) (optional, enables future mapping)
•	slug — SlugField(unique=True)
LicenseType (light taxonomy, Alpha)
•	name — CharField(60, unique=True)
•	slug — SlugField(unique=True)
(Optional but recommended for “wanted lists” and filter consistency.)

5.4 Addresses & Shipping Snapshots
Address
Stores user-entered addresses (not tied to a transaction snapshot).
•	user — ForeignKey(User, related_name="addresses")
•	full_name — CharField(120)
•	line1 — CharField(120)
•	line2 — CharField(120, blank=True)
•	city — CharField(80)
•	state — CharField(2)
•	postal_code — CharField(20)
•	country — CharField(2, default="US")
•	phone — CharField(30, blank=True)
•	is_default — BooleanField(default=False)
•	created_at — DateTimeField(auto_now_add=True)
AddressSnapshot
Immutable copy used on Orders/Shipments/Trades so profile edits don’t rewrite history.
•	full_name, line1, line2, city, state, postal_code, country, phone (same fields as Address)
•	created_at — DateTimeField(auto_now_add=True)

5.5 Collections (Trade Inventory Backbone)
CollectionItem
User-owned license record (may or may not ever be listed).
•	owner — ForeignKey(User, related_name="collection_items")
•	title — CharField(200)
•	description — TextField(blank=True)
•	license_year — IntegerField(null=True, blank=True)
•	county — ForeignKey(County, null=True, blank=True)
•	license_type — ForeignKey(LicenseType, null=True, blank=True)
•	resident_status — CharField(20, blank=True) (e.g., resident/non-resident; optional Alpha field)
•	condition_grade — CharField(20, blank=True)
•	is_public — BooleanField(default=True)
•	trade_eligible — BooleanField(default=True)
•	created_at — DateTimeField(auto_now_add=True)
•	updated_at — DateTimeField(auto_now=True)
CollectionItemImage
•	collection_item — ForeignKey(CollectionItem, related_name="images")
•	image — ImageField
•	sort_order — IntegerField(default=0)
•	uploaded_at — DateTimeField(auto_now_add=True)
WantedItem (“Looking For”)
Keep it structured and lightweight.
•	user — ForeignKey(User, related_name="wanted_items")
•	county — ForeignKey(County, null=True, blank=True)
•	year_min — IntegerField(null=True, blank=True)
•	year_max — IntegerField(null=True, blank=True)
•	license_type — ForeignKey(LicenseType, null=True, blank=True)
•	notes — CharField(250, blank=True)
•	created_at — DateTimeField(auto_now_add=True)

5.6 Listings (Auction / Buy-Now / Trade)
Listing
Marketplace-facing listing. Supports multiple listing types.
•	seller — ForeignKey(User, related_name="listings")
•	listing_type — CharField(20) (auction / buy_now / trade)
•	source_collection_item — ForeignKey(CollectionItem, null=True, blank=True)
(Alpha: enables “list from collection” and trade inventory linkage)
•	title — CharField(200)
•	description — TextField
•	license_year — IntegerField(null=True, blank=True)
•	county — ForeignKey(County, null=True, blank=True)
•	license_type — ForeignKey(LicenseType, null=True, blank=True)
•	resident_status — CharField(20, blank=True)
•	condition_grade — CharField(20, blank=True)
Auction fields (only used when listing_type=auction)
•	starting_price — DecimalField(10,2, null=True, blank=True)
•	reserve_price — DecimalField(10,2, null=True, blank=True) (Alpha)
•	current_bid — DecimalField(10,2, null=True, blank=True)
•	auction_end — DateTimeField(null=True, blank=True)
Buy-now fields (only used when listing_type=buy_now)
•	buy_now_price — DecimalField(10,2, null=True, blank=True)
Trade fields (only used when listing_type=trade)
•	trade_notes — TextField(blank=True) (what they want / preferences in freeform, minimal Alpha)
•	(Optional) allow_cash — BooleanField(default=False)
Status
•	status — CharField(20) (active / pending / closed / sold / expired / cancelled)
•	created_at — DateTimeField(auto_now_add=True)
•	updated_at — DateTimeField(auto_now=True)
ListingImage
•	listing — ForeignKey(Listing, related_name="images")
•	image — ImageField
•	sort_order — IntegerField(default=0)
•	uploaded_at — DateTimeField(auto_now_add=True)

5.7 Bidding (Auctions Only)
Bid
•	listing — ForeignKey(Listing, related_name="bids")
•	bidder — ForeignKey(User, related_name="bids")
•	amount — DecimalField(10,2)
•	is_winning — BooleanField(default=False)
•	placed_at — DateTimeField(auto_now_add=True)
Constraints
•	Add DB-level ordering/index on (listing, amount desc, placed_at asc) for winner resolution.
•	Enforce “auction-only” in app logic (listing_type must be auction).

5.8 Orders, Payments, and Shipping (Auctions + Buy-Now)
Key change from MVP: replace generic Transaction with an Order-centric model, and let “Transaction” be the payment record.
Order
Represents a purchased listing (auction win or buy-now purchase).
•	listing — OneToOneField(Listing, related_name="order") (prevents double-sell for buy-now)
•	buyer — ForeignKey(User, related_name="orders_bought")
•	seller — ForeignKey(User, related_name="orders_sold")
•	order_type — CharField(20) (auction / buy_now)
•	item_amount — DecimalField(10,2)
•	shipping_amount — DecimalField(10,2, default=0)
•	platform_fee_amount — DecimalField(10,2, default=0)
•	total_amount — DecimalField(10,2)
•	status — CharField(25)
(pending_payment / paid / label_created / in_transit / delivered / completed / cancelled / refunded)
•	ship_from_snapshot — ForeignKey(AddressSnapshot, null=True, blank=True, related_name="+")
•	ship_to_snapshot — ForeignKey(AddressSnapshot, null=True, blank=True, related_name="+")
•	created_at — DateTimeField(auto_now_add=True)
•	updated_at — DateTimeField(auto_now=True)
PaymentTransaction
Stripe-specific payment record (separate from Order state machine).
•	order — OneToOneField(Order, related_name="payment")
•	stripe_payment_intent_id — CharField(200, blank=True)
•	stripe_checkout_session_id — CharField(200, blank=True)
•	status — CharField(20) (pending / paid / failed / refunded)
•	created_at — DateTimeField(auto_now_add=True)
Shipment
Represents shipment tracking/label for an Order. (Trades handled separately.)
•	order — OneToOneField(Order, related_name="shipment")
•	provider — CharField(30) (shippo / easypost / manual)
•	carrier — CharField(40, blank=True)
•	service_level — CharField(60, blank=True)
•	tracking_number — CharField(80, blank=True)
•	label_url — URLField(blank=True)
•	rate_id — CharField(120, blank=True) (provider reference)
•	status — CharField(20) (label_created / in_transit / delivered / exception / unknown)
•	last_event_at — DateTimeField(null=True, blank=True)
•	created_at — DateTimeField(auto_now_add=True)
ShipmentEvent (optional but useful for disputes)
•	shipment — ForeignKey(Shipment, related_name="events")
•	status — CharField(30)
•	description — CharField(200, blank=True)
•	event_time — DateTimeField(null=True, blank=True)
•	raw_payload — JSONField(null=True, blank=True)

5.9 Trades (Offers, Agreement, Dual Shipping)
Trade
Represents an accepted trade agreement.
•	listing — OneToOneField(Listing, related_name="trade") (listing_type must be trade)
•	initiator — ForeignKey(User, related_name="trades_started")
•	counterparty — ForeignKey(User, related_name="trades_received")
•	status — CharField(30)
(accepted / awaiting_shipments / shipped_one / shipped_both / delivered_one / delivered_both / completed / cancelled / expired)
•	expires_at — DateTimeField(null=True, blank=True) (for accepted-window rules if needed)
•	ship_by_deadline — DateTimeField(null=True, blank=True)
•	created_at — DateTimeField(auto_now_add=True)
TradeOffer
Stores offers and counteroffers (versioned negotiation).
•	trade_listing — ForeignKey(Listing, related_name="trade_offers")
•	from_user — ForeignKey(User, related_name="trade_offers_sent")
•	to_user — ForeignKey(User, related_name="trade_offers_received")
•	status — CharField(20) (pending / accepted / declined / countered / expired / withdrawn)
•	expires_at — DateTimeField()
•	message — TextField(blank=True)
•	cash_amount — DecimalField(10,2, null=True, blank=True)
•	created_at — DateTimeField(auto_now_add=True)
TradeOfferItem
Links collection items to offers (many-to-many with quantity=1 typical).
•	offer — ForeignKey(TradeOffer, related_name="items")
•	collection_item — ForeignKey(CollectionItem)
•	direction — CharField(10) (give / receive)
(or infer by ownership; explicit is clearer and safer)
TradeShipment
Two shipments per trade (one from each party).
•	trade — ForeignKey(Trade, related_name="shipments")
•	sender — ForeignKey(User, related_name="trade_shipments_sent")
•	recipient — ForeignKey(User, related_name="trade_shipments_received")
•	provider — CharField(30) (shippo / easypost / manual)
•	tracking_number — CharField(80, blank=True)
•	label_url — URLField(blank=True)
•	status — CharField(20) (label_created / in_transit / delivered / exception / unknown)
•	ship_from_snapshot — ForeignKey(AddressSnapshot, null=True, blank=True, related_name="+")
•	ship_to_snapshot — ForeignKey(AddressSnapshot, null=True, blank=True, related_name="+")
•	created_at — DateTimeField(auto_now_add=True)
TradeFeeTransaction (Alpha if charging $1 label fee)
•	trade — ForeignKey(Trade, related_name="fees")
•	user — ForeignKey(User)
•	amount — DecimalField(10,2)
•	stripe_payment_intent_id — CharField(200, blank=True)
•	status — CharField(20) (pending / paid / failed)
•	created_at — DateTimeField(auto_now_add=True)
5.10 Favorites (Alpha)
Favorite
Single table supports favoriting listings and collection items.
•	user — ForeignKey(User, related_name="favorites")
•	listing — ForeignKey(Listing, null=True, blank=True)
•	collection_item — ForeignKey(CollectionItem, null=True, blank=True)
•	created_at — DateTimeField(auto_now_add=True)
Constraint
•	Exactly one of (listing, collection_item) must be set (enforce in app + DB constraint).

5.11 Notifications (Alpha)
Notification
•	user — ForeignKey(User, related_name="notifications")
•	notification_type — CharField(50)
•	message — TextField
•	link_url — CharField(255, blank=True) (deep link target)
•	is_read — BooleanField(default=False)
•	sent_email — BooleanField(default=False)
•	created_at — DateTimeField(auto_now_add=True)
(Replaces MVP “sent” with read/unread + email tracking.)

5.12 Strikes & Enforcement (Alpha)
Strike
•	user — ForeignKey(User, related_name="strikes")
•	reason — CharField(50) (non_shipment / non_payment / cancellation_abuse / etc.)
•	related_order — ForeignKey(Order, null=True, blank=True)
•	related_trade — ForeignKey(Trade, null=True, blank=True)
•	notes — TextField(blank=True)
•	created_at — DateTimeField(auto_now_add=True)
•	expires_at — DateTimeField(null=True, blank=True) (12-month strike window)
Exception / Mutual Resolution fields (Alpha)
•	is_excused — BooleanField(default=False)
•	excuse_reason — CharField(50, blank=True) (local_pickup / agreed_delay / combined_shipment / alternative_delivery / other)
•	excuse_note — CharField(250, blank=True) (short note; keep low-maintenance)
•	excuse_initiated_by — ForeignKey(User, null=True, blank=True, related_name="excuses_initiated")
•	excuse_confirmed_by — ForeignKey(User, null=True, blank=True, related_name="excuses_confirmed")
•	excuse_confirmed_at — DateTimeField(null=True, blank=True)
Behavior
•	A strike is only counted toward enforcement if is_excused = False.
•	Excuses require confirmation by the other party; otherwise the strike remains active.

AccountRestriction (optional, but helpful for automation)
•	user — OneToOneField(User, related_name="restriction")
•	can_bid — BooleanField(default=True)
•	can_sell — BooleanField(default=True)
•	can_trade — BooleanField(default=True)
•	suspended_until — DateTimeField(null=True, blank=True)
•	updated_at — DateTimeField(auto_now=True)

5.13 Notes on Primary/Foreign Keys & Relationships
•	Listing <---> Order: OneToOne prevents double-sell for buy-now and guarantees a single “fulfillment record.”
•	Listing <---> Trade: OneToOne ensures each trade listing results in at most one accepted agreement.
•	TradeOffer <---> Trade: Offers can exist before a Trade exists; a Trade is created when an offer is accepted.
•	AddressSnapshot: always used on Orders/Shipments/TradeShipments to preserve history.
•	CollectionItem is the source of truth for trade inventory; listings can optionally reference it for convenience/prefill.

Replacement Note for Existing MVP “Transaction”
You can either:
•	replace Transaction with Order + PaymentTransaction (recommended), or
•	keep Transaction but rename it to PaymentTransaction and add Order.
For Alpha’s shipping + lifecycle requirements, having an Order model is the cleanest way to avoid a tangled “Transaction tries to do everything” design.

 
6. Design & UX Direction
6.1 Visual Concept: The Old Commonwealth
Modern utility meets Pennsylvania heritage. Forest greens, aged ambers, parchment tones. Clean serif typography (Georgia) for headings, sans-serif for body. Warm, trustworthy, distinctly Pennsylvania.

6.2 Color Palette
•	Forest Green (#2C4A1E) - Primary brand, navigation, buttons
•	Aged Amber (#8B5E0A) - Links, secondary headings
•	Hunting Rust (#A0391A) - Alerts, urgency indicators
•	Parchment (#F5ECD7) - Card backgrounds
•	Cream White (#FAFAF5) - Page background

6.3 Typography
•	Headings: Georgia serif
•	Body: System UI sans-serif stack (Tailwind default)
•	Labels: Uppercase with letter-spacing for county badges

6.4 Key Pages (MVP)
•	Homepage - Grid of active auctions ending soon
•	Listing Detail - Large image, bid box, description, related listings
•	Browse - Filter sidebar (county, year), listing grid, pagination
•	Dashboard - My Bids and My Listings tabs
•	Create Listing - Form with image upload 
6.5 Key Pages (Alpha)

Alpha introduces new site sections and new lifecycle pages. These are required to make buy-now and trades real, not just “feature flags.”

Primary Navigation (Alpha)
•	The Auction House (auction browse + filters + listing detail)
•	The General Store (buy-now browse + filters + listing detail)
•	The Trading Block (trade browse + filters + trade detail)

*Note: Join the community/sign-in remains on mains.

Account + Profile (Alpha)
•	My Profile (public view): Shows public collection, % positive (if reviews later), trade eligibility, “Looking For” summary.
•	Edit Profile / Verification: Address required for shipping; optional phone verification; trade eligibility indicators.
•	My Collection (private management view): Add/edit collection items, set visibility and trade eligibility, manage “Looking For.”
•	Collector Profile (Public): Public-facing “collector card,” public collection grid, “Looking For” (optional public), and “Message / Propose Trade” entry points (messaging can be minimal or deferred).

Transaction Lifecycles (Alpha)
•	Order Detail Page (Auction + Buy-Now): Payment status, shipment purchase/entry, tracking, delivery, confirm receipt. Integration from Shippo for tracking.
•	Trade Detail Page: Offer terms, counter history, dual tracking numbers, both shipment deadlines, confirm receipt (both sides).
•	Create Listing (expanded): One entry point with listing type selection (auction / buy-now / trade).
•	Propose Trade (ESPN-style fantasy football screen): Left: you give. Right: you receive. Counter/accept/decline + expiration.

Operations / Trust (Alpha)
•	Notifications Center (in-app list): Not just a badge—must show actionable items (payment due, ship by deadline, etc.).

7. MVP Core Features - Django Implementation
7.1 User Authentication (Django Built-in)
•	Registration: Django UserCreationForm + email verification
•	Login: Django's LoginView
•	Password reset: Django's PasswordResetView
•	UserProfile extends User via OneToOneField
•	Email verification: Generate UUID token, send email, verify via link

7.2 Create Listing (Django ModelForm)
•	ListingForm auto-generated from Listing model
•	ImageFormSet for up to 4 additional images
•	Calculate auction_end = timezone.now() + timedelta(days=duration)
•	Images saved to media/ in dev, S3 in production

7.3 Browse & Filter (Django QuerySets)
•	ListView displays Listing.objects.filter(status='active')
•	Filter by GET params: ?county=Adams&year_min=1920
•	Django QuerySet chaining for dynamic filters
•	Pagination: Django's Paginator class, 24 per page

7.4 Bidding (Custom Business Logic)
•	Bid form validates: amount >= current_bid + 1, user != seller, email verified
•	Create Bid, update Listing.current_bid, set is_winning flags
•	Create Notification for outbid user
•	HTMX polls /listings/<id>/bid-status/ every 10s for live updates

7.5 Auction Close (Django Management Command)
•	Command: python manage.py close_auctions
•	Find expired auctions, identify winner, create Transaction
•	Update Listing.status='sold'
•	Create Notification with Stripe checkout link
•	Run via cron every 5 minutes

7.6 Payments (Stripe)
•	Stripe Checkout Session created for winner
•	Webhook handles payment_intent.succeeded
•	Updates Transaction.status='paid'
•	Notifies seller

7.7 Notifications (Django Email)
•	Management command: python manage.py send_notifications
•	Send queued emails via Django's send_mail()
•	AWS SES backend in production
•	HTML templates for each notification type

8. ALPHA Phase 1 – Building out Core Features
Alpha is where KeystoneBid becomes a complete marketplace, not an auction prototype. It introduces two new transaction types (buy-now, trades) and the operational systems required to complete transactions with low admin overhead.

8.0 Alpha Outcomes
By end of Alpha, KeystoneBid supports three transaction paths end-to-end:
•	Auction House: bid → win → pay → ship → receive
•	General Store: buy now → pay → ship → receive
•	Trading Block: propose → accept → both ship → both receive
Alpha also adds the operational spine:
•	shipping + tracking capture
•	order/trade states
•	deadlines + strikes
•	in-app notifications
•	verification gating (minimum controls to avoid “one burn and the feature dies”)

8.1 Listing Types (Auction / Buy-Now / Trade) (Extended Core)
The listing model supports listing_type with three modes:
•	Auction House (auction)
•	General Store (buy_now)
•	Trading Block (trade)
UI + Validation by listing_type
•	Auction
o	starting price (required)
o	duration (required)
o	reserve price (optional, Alpha)
•	Buy-now
o	fixed price (required)
o	quantity fixed to 1
o	cannot accept bids
•	Trade
o	no price
o	“trade preferences” (what they want)
o	links to a collection item (trade inventory is sourced from collections)
Browse separation
•	Each section (Auction House / General Store / Trading Block) is a separate browse experience, even if it reuses templates. Could probably have an all browse feed too

8.2 Fulfillment & Confirmation (Orders + Trades) (Extended Core)
Alpha introduces unified lifecycle state tracking so you can enforce shipping behavior and complete transactions without manual intervention.
Orders (Auction + Buy-Now)
•	paid
•	label_created (or tracking_provided)
•	in_transit
•	delivered
•	completed (after buyer confirms receipt or auto-complete after grace window)
Trades (two-sided lifecycle)
•	accepted
•	awaiting_shipments
•	shipped_one_side
•	shipped_both_sides
•	delivered_one_side
•	delivered_both_sides
•	completed
Critical rule
•	You only enforce what you can observe. In Alpha, observability = tracking number + delivery status + confirm receipt actions.

8.3 Shipping Integration (Aggregator + Tracking)
Approach
•	Integrate a shipping aggregator (Shippo) to support USPS/UPS/FedEx via one API.
•	KeystoneBid provides label purchase + tracking capture; it does not operate as a shipping business.
•	Shimment tracking is integrated in the website and viewable by the user.
8.3.1 Sales Shipping (Auction House + General Store)
Who pays
•	Buyer pays shipping at checkout.
How rates are calculated
•	Based on:
o	seller ship-from address
o	buyer ship-to address
o	package weight + dimensions (entered by seller)
When shipping is locked
•	On label purchase (or tracking entry), create a Shipment snapshot:
o	both addresses at time of transaction
o	package specs
o	chosen carrier/service
o	label URL + tracking number
How tracking updates happen
•	Prefer carrier tracking webhooks via aggregator.
•	Fallback: scheduled polling job if webhook delivery fails.
8.3.2 Trade Shipping (Trading Block)
Trades are not ecommerce, but they still require enforced shipping to maintain trust.
Trade shipping rules
•	Both parties must ship within 5 business days.
•	Both parties must provide tracking numbers (mandatory) built in app by Shippo tracking.
•	Completion requires:
o	delivery events for both shipments
o	confirm receipt from both parties (or auto-complete after grace window)
Optional trade labels (Alpha)
•	Offer in-app label purchase to standardize tracking.
•	Fee model:
o	$1 per trader only when using platform label purchase
o	no percentage commission on trades
o	Traders can meet in person for no charge – can mark in app handled offline
8.3.3 Failure to Ship (Orders + Trades)
Alpha enforcement is accountability-based (no escrow).
Order non-shipment
•	After payment, seller must ship by deadline (policy-defined – 5 business days).
•	If missed:
o	reminders
o	buyer can cancel after deadline
o	seller gets a strike
Trade non-shipment
•	If one party doesn’t ship by deadline:
o	other party can cancel
o	non-shipper gets a strike
8.4 Collections (Inventory Backbone for Trades)
Collections are not just a “nice-to-have” in Alpha; they are the inventory system for the Trading Block.
Collection capabilities
•	Add/edit collection item with images + metadata
•	Set:
o	is_public (default true)
o	trade_eligible (default true)
•	Collection items can be:
o	shown on profile (public)
o	eligible to be offered in trades
o	used to pre-fill a listing form
Post-transaction
•	After an order is completed:
o	buyer can add the purchased license to their collection from the order page (one-click + editable metadata)
Looking For (Wanted List)
•	On profile, users maintain a “Looking For” list:
o	county/year/type/era
•	Used in Trading Block:
o	as filtering/search hints
o	to display “matches your wants” (lightweight, no heavy matching engine in Alpha)
List-from-collection
•	Create listing supports selecting a collection item to prefill:
o	title/description/year/county/type/images
o	price fields are always listing-type specific (never copied from collection)
Adding to collection
•	Adding to a user collection is primarily done through the user profile through an upload module. User collection entry does not require as much metadata as a listing.
Viewing collection
•	Collection is visible in user profile page and the trade module


8.5 Buy-Now (The General Store)
Behavior
•	Fixed price purchase.
•	First buyer to complete Stripe payment wins.
•	Then it follows standard order fulfillment:
o	pay → ship → deliver → confirm receipt
Commission
•	Same commission structure as auctions.
Inventory locking
•	Buy-now listings must lock immediately upon successful payment to prevent double-sell.

8.6 Trading Block (Structured Negotiation Engine)
The Trading Block is a structured negotiation system, not classifieds.
ESPN Fantasy Football trading feel.
8.6.1 Trade Listing
•	Users can browse through collections by user or a full list like county/year/etc and offer trades
•	Lists an item available for trade (a user collection item).
•	Users can also add their ‘want list’
•	Includes:
o	Trader makes offer (many for one, one for many)
o	whether cash is allowed as part of trade (“boot”)
8.6.2 Offers + Counteroffers
•	Offer contains:
o	one or more items from proposer’s collection
o	optional cash add-on
o	expiration window (default 4 days)
•	Recipient can:
o	accept
o	decline
o	counter (creates a new offer version)
8.6.3 Trust Gating
Minimum gate for trading:
•	verified email
•	saved shipping address
•	phone verification (recommended)

8.7 Auction House Enhancements
•	Reserve price option
•	Improved image upload: drag/drop, multi-upload, reorder
•	Resident/non-resident classification
•	Q&A section

8.8 Favorites
Users can favorite:
•	listings (auction/buy-now/trade)
•	public collection items
Favorites appear in dashboard.

8.10 In-App Notifications
Alpha adds operational states; users must see them in-app.
•	Nav icon with unread count
•	Notification list page
•	Deep links to order/trade/listing context

8.11 Maintenance Minimization Rules
Final sales
•	All sales final; no returns processing.
Strikes
•	Apply strikes for:
o	non-shipment
o	repeated cancellations after acceptance (trade)
o	repeated non-payment (auction winner)
Enforcement ladder (Alpha baseline)
•	1 strike: warning + temporary restriction (buy-now only 14-days)
•	2 strikes: suspension window (30 days)
•	3 strikes within 12 months: ban
Gating
•	No selling without address on file.
•	No trading without verification gate.
Exceptions (Mutual Resolution / “Excused” Events)
•	Some late-ship or non-ship scenarios are legitimate (local pickup, agreed delay, combined shipments, etc.). KeystoneBid supports a lightweight “mutual resolution” flow so enforcement is fair without creating support burden.
•	Either party can initiate an “Excuse / Resolve” action on the Order or Trade.
•	The other party must explicitly confirm within a defined window (e.g., 72 hours).
•	If confirmed:
o	the deadline violation is marked excused
o	no strike is applied
o	the record stores the reason category (e.g., local pickup, agreed delay, alternative delivery) and a short note (optional)
•	If not confirmed by the deadline:
o	normal strike logic applies based on the original non-shipment rules
•	Admin override exists for edge cases (rare use; default is automated handling).

8.12 Reference Data (Alpha)
Alpha requires consistent metadata to support browse + wanted lists:
•	PA county list (67)
•	license type taxonomy (minimal)
•	era buckets (optional but useful for trades)

Dev -> Prod Flow (Alpha-specific additions)
Because Alpha introduces webhooks + shipping, you need a clean staging discipline:
Staging requirements (Alpha)
•	Separate API keys (Stripe test mode, shipping test mode)
•	Webhook endpoints for staging domain
•	Ability to replay webhook events (Stripe provides this; shipping vendor may as well)
Production requirements (Alpha)
•	Secrets in environment variables only
•	Idempotent webhook handling (avoid double-processing)
•	Polling fallback job for tracking updates
•	Admin override tools for stuck states
9. ALPHA Phase 2
9.0 Overview
ALPHA Phase 2 is the bridge between a working Alpha 1 prototype and a platform that is ready for real users. Its purpose is not to add every possible feature - it is to make what exists stable and trustworthy, fill in the operational gaps that would frustrate or block real collectors, and build the remaining features needed for complete marketplace experience. By the end of Phase 2, KeystoneBid should feel cohesive and collector friendly.
The tasks below are ordered by dependency - foundational work comes first, UI polish and community features follow. Each task represents one focused coding session (or a tightly scoped sprint). Completing them in order prevents rework.

Phase 2 is complete when all of the following are true:
•	Zero P0 defects; zero P1 defects in core transaction flows
•	All required profile fields are self-service editable (no admin intervention needed)
•	State-aware reference data is live with PA as the default experience
•	Navigation and UI reflect the four core pillars: Auction House, General Store, Trading Block, Collections
•	Text-only messaging, block/report, and rate limits are active
•	Public collection browse/search page is available
•	County (geo issuing unit) tracker and year completion tracker are live on collector profiles
•	Staging smoke tests passed
Phase 2 Task Sequence
The 9 tasks below are ordered so that each task builds on a stable foundation. Tasks 1–3 must be completed before work begins on Tasks 4–0.

#	Task	Priority	Depends On
1	Alpha 1 Bug Triage & P0/P1 Resolution	High	—
2	Reference Data Architecture & Cleaning	High	Task 1
3	Account Completeness & Gating UX	High	Tasks 1-2
4	Listing Model Extensions & New Features	High	Tasks 1-3
5	UI Navigation Restructure & Design Revamp	Medium	Tasks 1-3
6	Collection Enhancements & Browse Page	Medium	Tasks 2, 5
7	Q&A Expansion to Buy-Now (+ Moderation)	Medium	Task 5
8	Messaging MVP	Medium	Tasks 1, 3, 5
9	QA Hardening, Smoke Tests & Release Gate	Critical	All
9.1) Alpha 1 Bug Triage & P0/P1 Resolution
What This Is
Before writing a single line of new code, every known defect from Alpha Phase 1 must be categorized, prioritized, and the most critical ones resolved. This is the foundation everything else in Phase 2 is built on. Shipping new features on top of broken auction flows or stuck order states would compound the problems rather than fix them.
Implementation: Bug Triage Board
Create a simple tracking board (spreadsheet) with three severity classes:

Severity	Definition	Must Fix Before Phase 2 Launch
P0 — Critical	Data loss, payment corruption, or a core action that is completely impossible (e.g., auction close does not run, Stripe checkout broken)	Yes - immediately
P1 — Major	Core flow is broken but a manual workaround exists in Django admin (e.g., order gets stuck at "pending_payment")	Yes - before Task 4+
P2 — Minor	Non-blocking defects, cosmetic issues, confusing UX, edge cases	No - schedule for later sessions
Regression Pass Checklist
Manually walk through each of the following scenarios in a dev environment (local host). Document any failure:

Flow	Steps to Test
Auction end-to-end	Create listing → place bids → run close_auctions command → winner gets notification → Stripe checkout → payment_intent webhook fires → Order created → seller notified
Buy-now end-to-end	Create buy-now listing → buyer clicks purchase → Stripe checkout → Order created → listing locked (cannot be purchased again)
Trade end-to-end	Create trade listing → propose trade offer → accept offer → Trade record created → both parties upload tracking → both confirm receipt → status = completed
Strike / excuse flow	Simulate non-shipment → strike applied → one party initiates excuse → other confirms → strike marked excused
Email notifications	Outbid email, auction-won email, ship-by-deadline reminder — verify each arrives with correct content
In-app notifications	Bell badge increments on new events; notifications center shows correct items; deep links work
Profile gating	Attempt to create a listing without an address on file — confirm the action is blocked with an error
Acceptance Criteria
•	Zero open P0 defects after this task is complete
•	Zero open P1 defects in the three core transaction flows
•	Regression checklist documented with pass/fail/notes
•	All P2 items logged for future sessions

🗄 DATABASE IMPACT
No new models or schema changes in this task — fixes only affect existing model fields, view logic, and management commands.
🎨 UI IMPACT
Minor: Add or improve user-facing error messages and empty states where flows were failing silently. Do not redesign layouts — that is Task 5.

9.2)  Reference Data Architecture & Data Cleaning
Overview
Alpha 1 was built with Pennsylvania hardcoded as the only state, using a simple County model and a single pipe-delimited field for license types. This task redesigns the reference data layer end-to-end: it introduces proper multi-state support, a richer seven-dimension license taxonomy, physical attribute fields, a user correction workflow, and a fully rebuilt data pipeline. Pennsylvania remains the default and primary experience throughout; all other states are simply available when needed.

The work divides into two tracks that must be done in order:
•	Data track — four clean source CSV files (located: utilities\ref_data) replace the old reference_data_v0.csv. A rebuilt cleaning script validates and normalizes them into database-ready outputs.
•	Code track — model changes, seed management commands, dynamic form behavior, and admin enrichment are layered on top of the clean data.

What Was Built in the First Pass
Models  (apps/core/models.py)
•	State — code, name, fips_code, min_license_year, min_year_confidence, issuance_unit_type, issuance_unit_label, is_primary_default, slug
•	GeographicUnit — replaces old County model; state FK, name, unit_type, fips_code, slug, sort_order
•	LicenseType — state FK (nullable = universal), name, category (5 choices), slug

Migrations
•	apps/core/migrations/0004_state_geographicunit_licensetype_enrich.py — creates State, renames County → GeographicUnit, adds category + state FK to LicenseType, backfills PA state
•	apps/listings/migrations/0005_listing_license_types_m2m.py — adds license_types ManyToMany, backfills from old FK, removes old FK (legacy license_type CharField remains for now)
•	apps/collections/migrations/0003_collectionitem_license_types_m2m.py — same M2M pattern for CollectionItem

Utilities
•	utilities/clean_reference_data.py — standalone script; reads reference_data_v0.csv, outputs three CSVs to utilities/cleaned/
•	utilities/cleaned/states.csv — 24 rows; one per state
•	utilities/cleaned/license_types.csv — ~314 rows; one per license type token per state, categorized via keyword matching
•	utilities/cleaned/geographic_units.csv — ~590 rows; one per unit per state; most have geo_data_complete=False

Admin
•	Basic CRUD registered for State, GeographicUnit, LicenseType in apps/core/admin.py

Not Yet Built (from original 9.2 plan)
•	Management commands to seed the DB from cleaned CSVs (seed_states, seed_geographic_units, seed_license_types)
•	State-aware dynamic form behavior (JS dropdowns)
•	User-facing forms updated to use M2M license_types
•	Year validation against state min_license_year

Problems With the First Pass
1. Source Data Has Structural Issues
Issue	Description	Impact
license_types_normalized is multi-dimensional	Smashes Residency, Duration, Eligibility, and Activity Scope into one pipe-delimited string (e.g. "Resident|Annual|Youth|Hunting").	Keyword matching in the cleaning script is fragile and produces low-quality categorization.
addons_tags_permits not first-class	Stored as a separate column but the cleaning script doesn't produce distinct addon rows — everything unrecognized falls into a catch-all addon category.	Add-ons cannot be queried or filtered as structured data.
issuance_units truncated	Unit lists are cut off with "[...N total - see source URL]" for nearly every non-PA state.	geo_data_complete=False on ~523 of 590 geographic unit rows.

2. Taxonomy Design Is Incomplete
•	The five categories (residency, duration, eligibility, activity_scope, addon) are not the right shape for filtering and browsing antique licenses.
•	The addon category is too broad — a Federal Duck Stamp, a Deer Tag, and an Archery Permit are all in "addon" but describe fundamentally different things (species, hunting method, federal vs. state).
•	Physical attributes of the item itself are missing entirely: shape and color are critical for antique identification.
•	No classification of which listing fields are required vs. optional.

3. Missing Flexibility for Atypical Issuance Patterns
•	No way to represent "Statewide" as a geographic unit — some licenses were never tied to a county.
•	No way for a user to enter something outside the taxonomy (a rare stamp, a special one-off permit).
•	No "Other / write-in" pathway that still gets captured and flagged for admin review.

4. No Admin Enrichment or User Correction Workflow
•	Admin can do basic CRUD but there is no structured way to flag uncertain data (e.g., min_license_year with low confidence) or manage corrections.
•	Users have no way to suggest that a reference value (year, license type, county) is wrong or missing.
•	No ReferenceDataSuggestion model to capture user-submitted corrections for admin review.

What Needs to Change
A. Source Data Overhaul
The input data must be restructured into four separate clean source CSV files before the cleaning pipeline runs. These files now live at hunt/utilities/ref_data/ and have already been produced as part of the research deliverable for this task.

File	Contents
states.csv	One row per state: name, abbreviation, FIPS, min license year (with confidence and source), issuance scope, unit type/label, agency names (current and historical), licensing start year, and notes.
geographic_units.csv	One row per geographic unit per state — complete, not truncated. Includes unit_type (County, GMU, WMD, WMU, DPA, Hunt Area, Statewide), FIPS code for counties, is_statewide flag, geo_data_complete flag, and sort_order. Every state has a "Statewide" row.
license_classes.csv	One row per base license type per state (licenses a hunter would actually buy). Separate structured columns for residency, holder_eligibility, activity_scope, and duration — not pipe-delimited.
addons_permits.csv	One row per add-on, stamp, tag, or permit per state. Includes a FEDERAL section for the Duck Stamp (1934+) and HIP certification (1998+). Structured columns for addon_type, target_species, hunting_method, is_federal, and is_mandatory.

B. Revised Taxonomy — 7 Dimensions, Not 5 Categories
Replace the five-category LicenseType with a richer, cleaner set of dimensions. Each dimension is a separate section on the listing and collection item form. All are optional except at least one must be filled to indicate what the item is.

Dimension	Field Name	Description	Example Values
Residency	residency	Who was eligible by state residency	Resident, Nonresident, Alien
Holder Eligibility	holder_eligibility	Special eligibility class	General, Youth/Junior, Senior, Disabled, Veteran, Military, Apprentice, Honorary
Activity Scope	activity_scope	What hunting/trapping the license covers	General Hunting, Big Game, Waterfowl/Migratory, Trapping/Furbearer, Combo Hunt+Fish, Sportsman
Duration	duration	How long the license was valid	Annual, Lifetime, Multi-year, 10-day, 7-day, 5-day, 3-day, 1-day
Add-on Type	addon_type	Stamps, tags, permits (add-ons to a base license)	Deer Tag, Turkey Stamp, Federal Duck Stamp, Archery Permit, Habitat Stamp, HIP Record, WMA Access Pass
Physical Form	material	The physical form of the item	Paper/Cardstock, Metal Button, Metal Tag, Celluloid, Fabric/Canvas, Plastic
Shape	shape	Physical shape of the item	Rectangle, Square, Button/Disc, Tag (with hole), Strip, Irregular/Custom
Color(s)	colors	Color(s) of the physical item	Multi-select from controlled list + write-in

Implementation approach:
•	Keep the LicenseType model but expand to 8 categories matching the dimensions above.
•	The listing form groups the M2M picker by category so each dimension is its own UI section.
•	Each category has an "Other" option — selecting Other shows a write-in text field that is submitted as a ReferenceDataSuggestion.

📌  Filter Cleanliness Rule
When a user selects Other and enters free text on a listing, that value is flagged — it does not immediately appear in public browse filters.
Browse filter dropdowns show only admin-approved system values (e.g., General Hunting, Big Game, Waterfowl/Migratory). Free-text Other values remain hidden from filters until an admin promotes them to system values.
Controlled color values: Orange, Yellow, Red, Crimson/Dark Red, Forest Green, Lime/Bright Green, Blue, Navy, White, Cream/Ivory, Gray, Silver, Brown/Tan, Gold, Pink, Purple, Black, Multi-color, Other.
Controlled shape values: Rectangle, Square, Button/Disc, Tag (with hole), Strip, Irregular/Custom, Other.

C.  Required vs. Optional Field Classification
The following field classification applies to the Listing model and, where applicable, CollectionItem.

Level	Fields
Required to publish	Title • Issuing State • License Year (or Era bucket if year is unknown) • Listing Type (auction / buy_now / trade) • At least one image • Condition grade • Price or starting bid (for auction and buy_now)
Strongly recommended (completion indicator shown)	Issuing Geographic Unit • Activity Scope • Physical Form / Material • Condition notes
Optional	Shape • Color(s) • Residency • Duration • Holder Eligibility • Add-on Type • Description • Provenance notes

Add a listing_completeness_score computed property to the Listing model. Do not hard-block publishing for optional fields — only required fields gate publishing.

D.  Statewide / Flexible Issuance Units
Add a "Statewide" GeographicUnit per state (name="Statewide", unit_type="Statewide", is_statewide=True). This lets users select Statewide when the license was not issued by a specific sub-unit. Also add a boolean field is_statewide to GeographicUnit (default False).

This handles three cases:
•	State-level general hunting licenses not tied to a county or management unit.
•	Federal stamps — associate with a "Federal" pseudo-state entry.
•	Licenses from states that do not sub-divide by county (e.g., management-unit states used prior to the unit system being established).

E.  User Suggestion / Correction Workflow
Add a new ReferenceDataSuggestion model in apps/core/ to capture user-submitted corrections and new values for admin review.

Model: ReferenceDataSuggestion
Field	Definition
user	FK(User) — the submitter
suggestion_type	CharField choices: new_value / correction / other
target_model	CharField choices: state / geographic_unit / license_type / other
target_id	IntegerField(null=True) — FK to the record being corrected, if applicable
field_name	CharField(blank=True) — e.g. min_license_year
current_value	TextField(blank=True)
proposed_value	TextField() — required
source_or_evidence	TextField(blank=True) — user can link a source or citation
status	CharField choices: pending / accepted / rejected
admin_notes	TextField(blank=True)
created_at	DateTimeField(auto_now_add=True)
reviewed_at	DateTimeField(null=True)
reviewed_by	FK(User, null=True)

User-Facing Entry Points
•	On any listing or collection form: "Is a value missing?" → opens a small suggestion form inline.
•	On State and GeographicUnit detail pages: "Report an error" → pre-fills target_model and target_id.
•	For min_license_year: if min_year_confidence is low or medium, show a note: "Earliest known year for [State] is [year] — if you know of an earlier license, let us know" with a link to the suggestion form.

Admin Handling
•	Suggestions appear in Django admin with status=pending as a queue.
•	Admin can accept (which applies the change to the referenced record), reject (which saves an admin_notes reason), or leave pending.

F.  Pipeline Rebuild
The cleaning script and seed management commands must be rebuilt against the new source data structure. The complete pipeline is:

Path	Purpose
utilities/ref_data/states.csv	One row per state — clean, no truncation
utilities/ref_data/license_classes.csv	Base license types per state — structured columns
utilities/ref_data/addons_permits.csv	Add-ons, stamps, and tags — separate file
utilities/ref_data/geographic_units.csv	Complete unit lists per state
utilities/clean_reference_data.py	Reads the four source files, validates, and outputs to utilities/cleaned/
utilities/cleaned/	Output files ready to seed
apps/core/management/commands/seed_states.py	Idempotent state seeder
apps/core/management/commands/seed_geographic_units.py	Idempotent geographic unit seeder
apps/core/management/commands/seed_license_types.py	Idempotent license type seeder

All seed commands use update_or_create — they are safe to re-run when source data is updated.

G.  Admin Enrichment Features
Beyond basic CRUD, admin needs the following additions:

Feature	Detail
State list filter	Filter by min_year_confidence to quickly find low / medium confidence records needing review.
GeographicUnit list filter	Filter by geo_data_complete to surface states whose unit lists are still incomplete.
LicenseType inline on StateAdmin	View and edit license types directly from the state record.
GeographicUnit inline on StateAdmin	Paginated inline of geographic units within a state record.
ReferenceDataSuggestion admin	Pending queue with custom actions: accept_and_apply, reject, mark_pending.

Implementation Steps
Step 1 — Verify Source Data
•	Confirm all four CSV files are present at hunt/utilities/ref_data/.
•	Run a quick validation pass: row counts match expected state/unit totals, no missing required columns, FIPS codes are 5 digits for county rows.
•	Flag any states where geo_data_complete=False so they are visible in admin from day one.

Step 2 — Update Core Models
•	GeographicUnit: add is_statewide (BooleanField, default=False). Create a Statewide row for every state during seeding.
•	LicenseType: expand category choices to 8 values matching the taxonomy dimensions above. Add is_system_value (BooleanField, default=True) — False for user-submitted Other entries pending review.
•	Add ReferenceDataSuggestion model (see Section E above).
•	Listing: add shape (CharField, choices), colors (ManyToManyField or JSONField), listing_completeness_score (computed property). Add is_statewide (BooleanField, default=False).
•	CollectionItem: add shape and colors (same as Listing).

Step 3 — Write Migrations
•	New migration in apps/core/ covering: ReferenceDataSuggestion model, GeographicUnit.is_statewide, LicenseType category expansion, LicenseType.is_system_value.
•	New migration in apps/listings/ for Listing.shape and Listing.colors.
•	New migration in apps/collections/ for CollectionItem.shape and CollectionItem.colors.

Step 4 — Rebuild the Cleaning Script
Rebuild utilities/clean_reference_data.py to read from the four new structured source files. The script must:
•	Validate required columns in each source file and surface errors clearly.
•	Output three files to utilities/cleaned/: states.csv, geographic_units.csv, license_types.csv (merged from license_classes.csv and addons_permits.csv, each row tagged with its category dimension).
•	Be idempotent: running it multiple times produces the same output.

Step 5 — Write Seed Management Commands
•	python manage.py seed_states — reads utilities/cleaned/states.csv; update_or_create on State.code.
•	python manage.py seed_geographic_units — reads utilities/cleaned/geographic_units.csv; update_or_create on (State, unit_name); creates a Statewide row for any state that doesn't have one.
•	python manage.py seed_license_types — reads utilities/cleaned/license_types.csv; update_or_create on (State, name, category); sets is_system_value=True on all seeded rows.

Step 6 — Add State-Aware Dynamic Form Behavior
•	Add a small JSON API: GET /api/geo-units/?state=PA returns all GeographicUnit records for that state, ordered by sort_order.
•	Add GET /api/license-types/?state=PA returning LicenseType records grouped by category.
•	Add JavaScript on the listing, collection item, and wanted-list forms: when the state selector changes, update the geographic unit dropdown and each license type section with the new state's options.
•	Default state in all forms is PA. When editing an existing record, the form remembers the record's state.
•	The geographic unit field label updates dynamically to match the state's issuance_unit_label (e.g., County for PA, GMU for CO, WMD for ME).

Step 7 — Write Backfill Migration
•	Assign state=PA to all existing Listing and CollectionItem records that have no state.
•	Migrate all existing County FKs to GeographicUnit FKs.
•	Verify no existing PA listings are broken by the migration.

Step 8 — Enrich Admin
•	Add list filters and inlines as described in Section G.
•	Register ReferenceDataSuggestion with custom accept_and_apply, reject, and mark_pending actions.
•	The accept_and_apply action should write the proposed_value to the referenced field on the referenced model record and set status=accepted.

Acceptance Criteria
#	Criterion
1	All 25 states are seeded from clean source files with complete geographic unit lists.
2	PA geographic units have FIPS codes populated for all 67 counties.
3	License taxonomy has 8 dimensions; each has an "Other" option that triggers a ReferenceDataSuggestion.
4	Shape and color fields exist on Listing and CollectionItem models.
5	Required / optional field classification is enforced: required fields gate publishing, optional fields drive the completeness score.
6	A "Statewide" geographic unit is available for every state.
7	No hardcoded county or license type lists remain in any Django form or template.
8	State change on any form dynamically updates geographic unit and license type dropdowns without a page reload.
9	Year validation enforces each state's min_license_year on listing and collection item forms.
10	ReferenceDataSuggestion model exists; users can submit from listing and collection forms and from State / GeographicUnit detail pages.
11	Admin has a pending suggestion queue with accept_and_apply and reject actions.
12	Seed commands are idempotent — safe to re-run when source data is updated.
13	Existing PA listings and collection items are not broken by the migration.

Files to Create or Modify
Models
•	apps/core/models.py — add is_statewide to GeographicUnit; expand LicenseType categories to 8; add is_system_value to LicenseType; add ReferenceDataSuggestion model.
•	apps/listings/models.py — add shape, colors (ManyToManyField or JSONField), listing_completeness_score property.
•	apps/collections/models.py — add shape and colors.

Migrations
•	New migration in apps/core/ for ReferenceDataSuggestion + GeographicUnit.is_statewide + LicenseType category expansion + LicenseType.is_system_value.
•	New migration in apps/listings/ for shape + colors.
•	New migration in apps/collections/ for shape + colors.
•	Backfill migration: assign state=PA to all existing records; migrate County FKs to GeographicUnit FKs.

Utilities (Rebuilt)
•	utilities/ref_data/ — source data directory (four CSV files, already produced).
•	utilities/clean_reference_data.py — rebuilt to read from structured source files, validate, and output to utilities/cleaned/.
•	utilities/cleaned/ — regenerated output files.

Management Commands (New)
•	apps/core/management/commands/seed_states.py
•	apps/core/management/commands/seed_geographic_units.py
•	apps/core/management/commands/seed_license_types.py

API Endpoints (New)
•	GET /api/geo-units/?state=<abbrev> — returns GeographicUnit list for the given state as JSON.
•	GET /api/license-types/?state=<abbrev> — returns LicenseType list grouped by category as JSON.

Admin
•	apps/core/admin.py — enrich StateAdmin and GeographicUnitAdmin; add ReferenceDataSuggestion admin with accept/reject actions.

Impact Summary

🗄  DATABASE IMPACT
New models (apps/core/): ReferenceDataSuggestion.
GeographicUnit: add is_statewide (BooleanField, default=False).
LicenseType: expand category to 8 choices; add is_system_value (BooleanField, default=True).
Listing: add shape (CharField), colors (M2M or JSONField), listing_completeness_score (computed property).
CollectionItem: add shape and colors (same as Listing).
Backfill migration: assign state=PA to all existing Listing and CollectionItem records; migrate County FKs to GeographicUnit FKs.
All seed commands use update_or_create — safe to re-run.

🎨  UI IMPACT
All listing, collection item, and wanted-list forms gain a state selector (default: PA).
Geographic unit and license type dropdowns become dynamic — they update via JavaScript on state change.
The geographic unit field label changes to match the selected state's unit type (County, GMU, WMD, etc.).
Shape and color fields appear as optional dropdowns / multi-selects on listing and collection item forms.
Year fields gain server-side validation against the selected state's min_license_year.
An "Other" option on each license type dimension shows a write-in text field; submission creates a pending ReferenceDataSuggestion.
Listing completeness indicator shown on seller dashboard.
"Is a value missing?" link on all forms and "Report an error" on State / GeographicUnit detail pages open the suggestion form.
Admin pending queue: suggestion list filtered to status=pending, ordered by created_at.


9.3 Account Completeness & Gating UX
What This Is
After Alpha 1, it was discovered that you could not list or trade because required profile fields (shipping address, email verification) were not filled in - but there was no obvious way to fix this. The gating messages appeared but did not link directly to where the user could resolve the issue. This task closes that gap, making every required field self-service editable and making every blocking error message point directly to the fix.
Implementation Steps
1.	Expand the profile edit view to include all gating-relevant fields
•	Email verification status display + "Resend verification email" button (rate-limited: max 3 per hour)
•	Shipping address CRUD: add, edit, delete, and set-as-default address from the profile page
•	All address fields from the Address model (§5.4): full_name, line1, line2, city, state, postal_code, phone
2.	Add "Account Readiness" checklist widget
•	Display on the dashboard and profile edit page
•	Items: ✓ Email verified, ✓ Shipping address saved, ✓ Phone verified (if trading)
•	Each incomplete item shows a direct CTA button/link ("Add address →", "Verify email →")
3.	Improve all gating error messages
•	Replace generic "You cannot do this action" errors with specific, actionable messages
•	Every blocking error must include a link or button that takes the user directly to the fix
•	Examples: "To create a listing, you need a saved shipping address. → Add address" / "To trade, your email must be verified. → Resend verification email"
4.	Add messaging_disabled fields to UserProfile
•	Fields needed for Task 8 (Messaging): messaging_disabled (BooleanField, default False), messaging_disabled_reason (TextField, blank=True), messaging_disabled_at (DateTimeField, null=True)
•	These are set by admin only; users cannot change them directly
Acceptance Criteria
•	A user can add, edit, and delete shipping addresses from their profile in under 3 clicks
•	A user can resend a verification email from their profile
•	Every gating error includes a direct link to the resolution page
•	Account readiness checklist shows correct status for all gating conditions
•	No action requires admin intervention to resolve a profile completeness issue

🗄 DATABASE IMPACT
Changes to UserProfile (§5.2):
•	Add: messaging_disabled (BooleanField), messaging_disabled_reason (TextField), messaging_disabled_at (DateTimeField, null=True)
No other schema changes. Address model (§5.4) already supports multiple addresses per user via ForeignKey(User).
🎨 UI IMPACT
•	Profile edit page gains: shipping address management section, email verification status + resend button, account readiness checklist
•	Dashboard gains: account readiness checklist widget (compact version, links to profile)
•	All gating error pages/messages gain direct CTA links

9.4 Listing Model Extensions & New Listing Features
Overview
Several listing features were deferred from Alpha 1 and are needed before the platform can handle the full range of what collectors sell and how they want to sell it. This task adds five focused capabilities: scheduled go-live, auto-relisting of unsold auctions, local pickup, maximum year validation, and duplicate listing prevention with automatic collection linking.

This task does not add new physical attribute fields. Material and colors were all established in Task 2 (Section 9.2) as direct fields on Listing and CollectionItem. Nothing in this task revisits that layer.

Data Model Context
Before the feature details, the table below summarises which fields are already in place from 9.2 and which new fields this task introduces. This is the complete picture of item-description fields on Listing and CollectionItem after both tasks are done.

Field Group	Fields	Added In
License classification	residency, holder_eligibility, activity_scope, duration, addon_type	9.2 — ManyToManyField(LicenseType) grouped by category
Physical item attributes	shape, colors, material	9.2 — direct CharField / M2M or JSONField on Listing and CollectionItem
Listing behavior (this task)	scheduled_at, auto_relist, relist_count, original_listing, local_pickup_available, local_pickup_location	9.4 — new fields on Listing
Order behavior (this task)	delivery_method	9.4 — new field on Order
Trade behavior (this task)	local_pickup on TradeShipment	9.4 — new field on TradeShipment

Feature Details
4a.  Scheduled Go-Live
Sellers can choose when their listing becomes visible to buyers. The default is immediately.

•	Add scheduled_at (DateTimeField, null=True, blank=True) to Listing. If null the listing goes live immediately on creation. If set, the listing status is scheduled until that time arrives.
•	Auction duration runs from go-live time, not creation time. A 7-day auction scheduled two days from now closes 9 days from now.
•	A new management command python manage.py activate_scheduled_listings runs on cron every 5 minutes. It transitions any listing with status=scheduled and scheduled_at ≤ now() to status=active.
•	Scheduled listings that have not gone live yet are visible to the seller on their dashboard under a dedicated Scheduled state. They are invisible to buyers until they go live.
•	A date/time picker is added to the listing creation and edit forms. The field is optional — the default is Go live now.

4b.  Auto-Relist for Unsold Auctions
Auctions that close with no bids, or with a highest bid below the reserve price, are automatically relisted on the same terms. This is the default. Sellers can opt out.

•	Add to Listing: auto_relist (BooleanField, default=True), relist_count (IntegerField, default=0), original_listing (ForeignKey to self, null=True, blank=True, on_delete=SET_NULL).
•	When close_auctions finds an expired auction with no winner: if auto_relist=True and relist_count < 3, create a fresh Listing record with the same fields, increment relist_count on the clone, set original_listing to the expired listing's PK, and set the clone's scheduled_at to now so it activates on the next cron tick.
•	The original listing's status becomes expired. The relisted clone is a separate Listing record — not a mutation of the original. The linked CollectionItem and its source_collection_item FK carry over to the clone.
•	Maximum 3 relist cycles. After relist_count reaches 3 with no winner, the listing expires permanently.
•	Sellers can cancel any active listing, including a relisted clone, at any time before a bid is placed. Cancellation restores trade_eligible=True on the linked CollectionItem.
•	The relist chain is surfaced on the listing detail page and the seller's dashboard (e.g., "Relisted — attempt 2 of 3").

4c.  Local Pickup
Sellers can optionally offer local pickup as an alternative to shipping on any listing type. Off by default.

•	Add to Listing: local_pickup_available (BooleanField, default=False) and local_pickup_location (CharField 100, blank=True). Store a general area only (e.g., "Lycoming County, PA"). Do not store an exact address.
•	Add to Order: delivery_method (CharField 20, choices: shipping / local_pickup, default: shipping). The buyer selects this at checkout when the seller has enabled local pickup.
•	Local pickup orders do not require a shipping label. The order lifecycle is: paid → (buyer and seller coordinate offline) → seller marks Handed Off → buyer confirms receipt. The same auto-complete grace window applies as for shipped orders.
•	Trades can also be marked as local pickup. Track this on TradeShipment as local_pickup (BooleanField, default=False). No platform fee is charged for local pickup trades.
•	If local_pickup_available=True, a local pickup badge appears on the listing card and listing detail page so buyers can see it before clicking through.

4d.  Maximum Year Validation
The platform is for antique and vintage licenses. Current or recently issued licenses have no collectible value and must not be listed.

•	Maximum allowed license year is 2000. This is a hardcoded constant — it does not change year over year. Enforced server-side on both Listing and CollectionItem.
•	This is a hard validation error, not a warning: "License year must be 2000 or earlier to be listed on KeystoneBid."
•	This works in combination with the minimum year validation established in Task 2 (Section 9.2): the year field is bounded on both ends — the lower bound is the state's min_license_year (varies by state), and the upper bound is 2000 (fixed for all states).
•	The year field hint text in all listing and collection item forms should reflect both bounds: for example, "Enter the year printed on the license (e.g., 1947). Must be between [state min year] and 2000."

4e.  Automatic Collection Linking and Duplicate Prevention
These two behaviors are defined together because they share the same mechanism: the source_collection_item FK on Listing.

Single Form, Automatic Collection Linking
Creating a listing in the Auction House or General Store and adding an item to a personal collection are the same action. A seller should never have to enter the same item twice.

The listing creation form is the single point of entry. When a seller creates a listing, a CollectionItem is automatically created and linked via source_collection_item. The seller fills in item details once — those details land in both the listing and their collection simultaneously.

•	The listing creation form includes all CollectionItem fields alongside all listing-specific fields (listing type, pricing, auction duration, etc.).
•	On save, the view creates (or updates) a CollectionItem using the item detail fields, then creates the Listing with source_collection_item pointing to it.
•	If the seller is creating a listing from an existing collection item (the "list from collection" flow already in the plan), the form pre-fills from that item and updates it on save rather than creating a duplicate.
•	source_collection_item should be treated as required for all new listings created through the standard form. It remains nullable in the DB only to support legacy records and admin-created listings.
•	The created CollectionItem defaults to is_public=True and trade_eligible=True. The duplicate prevention logic below then immediately sets trade_eligible=False once the listing is active.

Duplicate Listing Prevention
If a collection item is already actively listed in any marketplace section, it cannot be listed again. This prevents the same physical item from appearing simultaneously in both the Auction House and the General Store.

•	A collection item is considered actively listed if it is linked via source_collection_item to any Listing with status in: active, scheduled, or pending.
•	When a seller selects or creates a collection item during listing creation, the form checks this condition. If the item is already actively listed, the form shows: "This item is already listed in [Auction House / General Store]. Cancel that listing first before creating a new one."
•	When a collection item becomes actively listed in the Auction House or General Store, set CollectionItem.trade_eligible=False automatically. This removes it from Trading Block availability for the duration of the listing.
•	When the listing closes — whether sold, expired, or cancelled — restore trade_eligible=True on the linked CollectionItem so it returns to Trading Block eligibility.

The interaction between listing types and collection availability:

Scenario	Rule	Outcome
Item is trade_eligible=True with no active Auction House or General Store listing	Appears in Trading Block. Can be listed in Auction House or General Store at any time.	Trading Block availability is passive and non-exclusive.
Item is listed in Auction House or General Store (status: active, scheduled, or pending)	trade_eligible set to False automatically. Item removed from Trading Block. Cannot be listed in the other section simultaneously.	Prevents the same physical item from being sold or traded twice.
Listing closes (sold, expired, or cancelled)	trade_eligible restored to True on the linked CollectionItem.	Item returns to Trading Block eligibility automatically.
Standalone listing with no source_collection_item (legacy or admin-created)	Duplicate check cannot be performed. This limitation is acceptable for Phase 2.	No collection item FK to check against.

Acceptance Criteria
#	Criterion
1	Scheduling a listing delays go-live. The auction duration clock does not start until the listing transitions to active. Scheduled listings are visible on the seller's dashboard and hidden from buyers until go-live.
2	Unsold auctions auto-relist as a fresh Listing record up to 3 cycles. After 3 unsuccessful cycles the listing expires permanently. Sellers can opt out of auto-relist at creation time.
3	Local pickup option is available on all listing types. Listings with local pickup show a badge on the card and detail page. Local pickup orders follow the Handed Off lifecycle. Local pickup trades incur no platform fee.
4	Maximum year validation (≤ 2000) is enforced server-side on Listing and CollectionItem with a hard error. Minimum year validation from 9.2 (state-dependent) remains in place — both bounds are active simultaneously.
5	Creating a listing in the Auction House or General Store automatically creates a linked CollectionItem via source_collection_item. The seller fills in item details once and the item appears in both their collection and the marketplace.
6	The "list from collection" flow pre-fills from an existing CollectionItem and updates it on save rather than creating a duplicate record.
7	source_collection_item is always populated for listings created through the standard form.
8	When a CollectionItem becomes actively listed, trade_eligible is automatically set to False. When the listing closes (sold, expired, or cancelled), trade_eligible is automatically restored to True.
9	A collection item that is already actively listed cannot be listed again — the form shows a clear message identifying which section it is already in.
10	No new physical attribute fields (shape, colors, material) are added in this task — those fields remain as established in 9.2.

Impact Summary

🗄  DATABASE IMPACT
Changes to Listing (§5.6):
  • Add: scheduled_at (DateTimeField, null=True, blank=True)
  • Add: auto_relist (BooleanField, default=True), relist_count (IntegerField, default=0), original_listing (FK to self, null=True, on_delete=SET_NULL)
  • Add: local_pickup_available (BooleanField, default=False), local_pickup_location (CharField 100, blank=True)
  • source_collection_item FK (already on model) is now treated as required for all listings created through the standard form
Changes to CollectionItem (§5.5):
  • No schema changes — auto-creation on listing is a view-layer behavior, not a model change
Changes to Order (§5.8):
  • Add: delivery_method (CharField 20, choices: shipping / local_pickup, default: shipping)
Changes to TradeShipment (§5.9):
  • Add: local_pickup (BooleanField, default=False)
New management command:
  • python manage.py activate_scheduled_listings — runs on cron every 5 minutes
No changes to LicenseType, shape, colors, or material in this task — all physical attribute and classification fields were established in 9.2.

🎨  UI IMPACT
Listing creation form:
  • All CollectionItem item-detail fields are present on the listing form (title, year, state, geographic unit, license types, condition, images, shape, colors, material) — seller fills in once
  • Scheduled go-live date/time picker (optional; default is Go live now)
  • Auto-relist toggle (default on; auctions only)
  • Local pickup toggle with general location text field
  • Year field hint text updated to show both bounds: state min year and 2000
  • Duplicate check fires when a collection item is selected or auto-created; shows blocking message if already actively listed
Listing detail page:
  • Local pickup badge if local_pickup_available=True
Listing cards (browse view):
  • Local pickup badge if available
Seller dashboard:
  • Scheduled listings in a distinct Scheduled state (separate from Active)
  • Relist count badge on relisted auctions (e.g., "Attempt 2 of 3")
  • Collection and active listings stay in sync automatically — no manual re-entry needed

9.5 UI Navigation Restructure & Design Revamp
What This Is
The Alpha 1 UI worked for development testing but does not yet feel like a collector's platform. The navigation is cluttered, the four core modules are not prominently featured, images are too small, and the overall layout feels fragmented. This task restructures the navigation, improves information hierarchy, makes images more prominent, and polishes the UI for readability — especially for older collectors. It does not rewrite the underlying Django apps, only the templates, CSS, and JavaScript.
Think of this as remodeling the front of the store. The shelves are in a different order than the signs above them, the store logo is tiny, and the main sections are not clearly labeled. This task reorganizes everything so that when a collector opens the site, they immediately know where to go. The Auction House, General Store, Trading Block, and Collections are the four front-and-center sections. Navigation is cleaned up. License images are bigger. The site feels like it belongs to Pennsylvania hunters, not a generic tech startup.
Design Directive (unchanged from §6)
Modern utility meets Pennsylvania heritage. Forest greens (#2C4A1E), aged ambers (#8B5E0A), parchment tones (#F5ECD7). Georgia serif for headings, system sans-serif for body. Warm, trustworthy, distinctly Pennsylvania.
Implementation Steps
5a. Header and Branding
•	"KeystoneBid" text in the header in Georgia serif, forest green, large enough to be the focal point
•	Logo moved to page footer (or treated as a small supplemental mark in the header)
•	Header height reduced — clean, minimal, not heavyweight
5b. Primary Navigation
The four core modules are the primary navigation items. They must be reachable in one click from anywhere on the site:
•	The Auction House
•	The General Store
•	The Trading Block
•	Collections
Secondary nav items (profile, notifications, messages, dashboard, login/logout) move to a collapsed menu that does not compete with the four core pillars. The home/landing page should also be accessible.
5c. Context Switcher Between Marketplace Sections
When a user is inside one marketplace section (e.g., browsing Auction House listings), they can flip to the General Store or Trading Block via a tab/toggle that stays in view without returning to the homepage. This can be a tab bar just below the main nav or at the top of the browse page.

5d. Notification Bell
•	Replace the text "(Bell)" label with an actual bell SVG icon (or a unicode bell symbol)
•	Unread count badge appears as a red/amber circle with a number over the icon, identical to the Facebook notification pattern
•	Clicking the bell opens the notifications dropdown or links to the full notifications center
5e. Image-First Listing Cards
License images are the focal point — not the text. Listing cards should be image-first with minimal text metadata visible by default:
•	Card image: minimum 220px tall. Full-width within the card. No tiny thumbnail approach.
•	Text below the image: title (truncated), county/state badge, year, current bid or price, time remaining
•	On hover/tap: show additional details without navigating away (optional)
•	Browse grid: 3 columns on desktop, 2 on tablet, 1 on mobile
5f. Readability Improvements
The platform's collectors include many older users. Readability is not optional:
•	Sufficient color contrast on all text (WCAG AA as a reasonable target — not exhaustive auditing, just the obvious failures)
•	Clear heading hierarchy on all pages
•	Good line spacing (line-height: 1.6 minimum for body text)
•	A good middle ground that isn’t over the top but accommodates older users
•	It should feel clean

5g. Page Architecture Consolidation
Several things that currently live on separate pages should be grouped under fewer, more logical hubs:
Currently Fragmented	Consolidate Into
Profile edit, address edit, verification, notification settings	One unified "My Account" / profile page with tabbed sections
Active bids, active listings, purchases, sales, trades	Dashboard with tabs or accordions — one place, not 5 pages
Collection items, wanted list, featured items	My Collection/Public Profile page with sections and filters. Can appear under Profile Page. Header with user meta/info (public fields so like not email, etc).
Under user info are user’s collection items. Below the user’s collection is the wanted list (note: wanted list won’t have an image since they don’t have the item yet).
5h. Mobile-Responsive Layout
•	The site must be usable on a phone - older collectors often browse on iPads or phones at shows
•	Navigation collapses to a hamburger menu on mobile
•	All forms stack vertically on small screens
•	Listing cards drop to 1 column on mobile
•	Tap targets are large enough to use without precision

Acceptance Criteria
•	A new visitor can reach each of the four core marketplace sections in one click from the top nav
•	Bell notification icon with unread badge is visible and functional
•	Listing images are dominant on both browse and detail pages
•	Dashboard consolidates all buyer/seller activity in one place
•	Site renders correctly on mobile (375px minimum width)

🗄 DATABASE IMPACT
No database schema changes. This task is templates, CSS, and JavaScript only.
🎨 UI IMPACT
•	New base.html layout with updated header, nav, and footer
•	New listing card component (image-first, consistent across all three marketplaces)
•	New tab/context switcher component for marketplace browse
•	New notification bell icon with unread badge
•	Updated dashboard template (tabbed or accordion layout)
•	Updated profile/account template (tabbed sections)
•	Mobile-responsive breakpoints added to all major layouts

9.6 Collection Enhancements & Public Browse Page
What This Is
Collections are not just a personal inventory tool - they are a community discovery feature. This task adds the missing collection UX: filters, search, groupings, and pinned featured items on the private collection management view. It then makes collections publicly browsable platform-wide, so collectors can discover each other's holdings without having to visit individual profiles.
Right now, a collector's collection is just a flat list with no way to organize or search it. And collections are only visible if you know someone's profile URL. This task adds the ability to filter your collection by county, year, and license type, group items together, and pin your best pieces to the top. It also adds a "Browse Collections" page to the main navigation — so any visitor can discover what other collectors are holding, filtered by state, county, year, or type.
Implementation Steps
6a. Private Collection Management View Enhancements
My Collection/Public Profile page with sections and filters. Can appear under Profile Page – this is basically your public profile. Header with user meta/info (public fields so like not email, etc). Under user info is container with collection items (shows up to 6 ‘featured’ collection items and then scroll in container after. Above this container (but under user info) are collection filters. Below the featured collection is the wanted list (note: wanted list won’t have an image since they don’t have it yet).

•	Add filters to the collection management page: county/geographic unit, year range (min/max), license type, era, material
•	Add basic keyword search across title, description, and notes fields
•	Add groupings: "Group by County", "Group by Year/Decade", "Group by Era" - these are display groupings (accordion sections), not structural changes
•	Add "Featured" flag to CollectionItem: featured (BooleanField, default=False). Limit to 6 featured items per user.
•	Featured items appear at the top of the public collection view in a prominent grid (like a "display case")
•	Add a "Feature / Unfeature" toggle button on each collection item card in the management view
6b. Public Collection Browse Page
A new page accessible from the main navigation: Browse Collections. Shows all public collection items across all users.
•	URL: /collections/ (or /browse/collections/)
•	Filters: state (default PA), geographic unit/county, year range, license type, era, material, owner (by display name)
•	Keyword search across title and description
•	Sort options: Newest added, Oldest year, Newest year, Owner name A–Z
•	Pagination: 24 items per page
•	Only items with is_public=True are shown
•	Each card links to the collector's public profile and optionally to the individual item's detail page
•	Featured items from each collector are visually distinguished (e.g., a small, clean, and discrete "featured" ribbon or border color)
6c. Post-Purchase "Add to Collection" Flow
After an auction or buy-now order is completed, the buyer is prompted to add the purchased license to their collection with one click. This was deferred from Alpha 1.
•	On the Order detail page (status: completed), show a banner: "Add this license to your collection →"
•	Clicking pre-fills a CollectionItem form with title, year, county, and license type from the listing. Buyer can edit before saving. Default is yes add to collection.
•	The main image from the listing are copied to the collection item

Acceptance Criteria
•	Collection management page supports filters, search, and groupings
•	Featured items appear at the top of the public profile collection view
•	Browse Collections page is accessible from main navigation
•	Browse Collections filters are consistent with marketplace browse filters
•	Post-purchase "Add to Collection" CTA appears on completed orders

🗄 DATABASE IMPACT
Changes to CollectionItem (§5.5):
•	Add: featured (BooleanField, default=False)
No other schema changes. Browse uses existing CollectionItem queryset with .filter(is_public=True).
🎨 UI IMPACT
•	Collection management page: add filter sidebar, search bar, group-by toggle, feature/unfeature toggle button
•	New Browse Collections page (/collections/): filter sidebar, item grid, pagination
•	Collector public profile: featured items displayed prominently at top
•	Order detail page: "Add to collection" CTA banner on completed orders

9.7 Q&A Expansion to Buy-Now (+ Moderation Controls)
What This Is
Q&A was built for the Auction House in Alpha 1. This task generalizes it to also work on General Store (buy-now) listings. Q&A remains disabled on the Trading Block (trade negotiations use the messaging system instead). Moderation controls are added to support flagging and hiding abusive use. Q&A is the public question board under a listing - buyers post questions, the seller answers, and everyone can read the thread. This task simply makes it available under buy-now listings as well as auctions. It also adds the ability for anyone to flag an inappropriate question or answer and lets the admin hide flagged content without deleting it.
Implementation Steps
1.	Generalize Q&A to support listing_type in (auction, buy_now)
•	The existing Q&A model should have a listing FK. The Q&A component should be included in the listing detail template for both auction and buy_now listing types.
•	The Q&A widget checks listing_type. If trade: widget is hidden, no Q&A block rendered.
2.	Add moderation fields
•	On the Question model add moderation_state (CharField, choices: ok/flagged/hidden, default: ok)
•	Hidden questions are not shown to public. Flagged questions are visible until the admin reviews.
3.	Add notification hooks
•	Seller is notified (in-app + optional email) when a question is posted on their listing
•	Asker is notified (in-app + optional email) when the seller answers their question
4.	Admin tooling
•	Q&A questions and answers must be searchable in Django admin
•	Admin can set moderation_state to hidden from the admin panel
•	Add a "Flag this question" link on the listing detail page for authenticated users

Acceptance Criteria
•	Q&A appears on auction and buy-now listings; does not appear on trade listings
•	Seller receives notification when a question is posted
•	Asker receives notification when their question is answered
•	Admin can search and hide flagged content

🗄 DATABASE IMPACT
•	Add moderation_state (CharField) to the existing Q&A Question model
•	No new models needed — the existing Q&A data model is extended in place
🎨 UI IMPACT
•	Q&A widget now renders on buy-now listing detail page (same component as auction, no redesign needed)
•	Add "Flag this question/answer" button on each Q&A item
•	Flagged items show a moderation notice to the user who flagged them ("Thank you. This is under review.")

9.8 Messaging MVP
What This Is
A minimal but fully-functioning, safe private messaging system for collector-to-collector and buyer-to-seller communication. Text only (no images, no attachments). Built with trust controls from day one: block/report, rate limits, and admin moderation tooling. Messaging is distinct from Q&A - Q&A is public and tied to a listing; messages are private and two-way. This is a simple private inbox - like email but inside the platform. A buyer who has a question about a specific auction or listing can message the seller directly. Two collectors negotiating a trade can discuss the terms. Messages are private, text-only, and the system includes safeguards: users can block others, report abusive messages, and the admin can disable messaging for any account if needed. The platform does not police off-site deals - if two people want to exchange contact info and deal outside the platform, that is their choice. The messaging system exists to reduce friction for on-platform transactions.

New Django App: apps/messaging/
Create a new Django app with the following structure:
•	models.py — Conversation, Message, MessageRead, Block, MessageReport
•	views.py — inbox, conversation detail, start conversation, send message, report, block
•	urls.py — messaging URL routes
•	services.py — start_conversation(), send_message(), apply_block(), file_report()
•	admin.py — admin views with full message search and report queue
•	templates/messaging/ — inbox.html, conversation_detail.html

Data Models
Conversation
•	id, conversation_type (CharField 20, choices: auction/buy_now/trade)
•	listing (ForeignKey to Listing, null=True, blank=True) — for auction and buy-now context
•	trade_offer (ForeignKey to TradeOffer, null=True, blank=True) — for trade context
•	user_a, user_b (ForeignKey to User) — stored in deterministic order (smaller user_id = user_a) to prevent duplicate conversations
•	created_by (ForeignKey to User), created_at, last_message_at
•	is_closed (BooleanField, default=False) — for locking threads after disputes
•	Unique constraint: (listing, user_a, user_b, conversation_type) for listing-tied conversations
Message
•	conversation (ForeignKey), sender (ForeignKey to User)
•	body (TextField — text only, no HTML, no images)
•	created_at, is_deleted (BooleanField, soft delete), moderation_state (CharField, choices: ok/flagged/hidden)
MessageRead (read tracking)
•	Store last_read_at per user per conversation: conversation (FK), user (FK), last_read_at (DateTimeField)
•	Simpler and lower query overhead than per-message read rows
Block
•	blocker (FK User), blocked (FK User), created_at
•	Unique constraint on (blocker, blocked)
•	Block is bidirectional in effect: neither party can message the other after a block is placed
•	The fact that a block exists is never revealed to the blocked user
•	Blocked users are not able to buy or trade with each other
MessageReport
•	reporter (FK User), message (FK Message, null=True), conversation (FK Conversation, null=True)
•	reason (CharField, choices: scam/harassment/spam/other), notes (TextField, null=True)
•	status (CharField, choices: open/reviewing/resolved/dismissed), created_at, resolved_at, resolved_by (FK User, null=True)

Core Flows
Starting a Conversation
•	POST /messages/start/ — requires authenticated + email-verified user
•	Check block table in both directions. If either user has blocked the other: deny silently (show generic "cannot message this user")
•	Check if a conversation already exists for this (user pair): if yes, redirect to existing conversation
•	Check messaging_disabled on both users' profiles. If either is disabled: deny.
•	Create Conversation, redirect to conversation detail page
Sending a Message
•	POST /messages/<conversation_id>/send/
•	Confirm user is a participant (user_a or user_b). If not: 403.
•	Check blocks and messaging_disabled (re-check on every send, not just at conversation creation)
•	Apply rate limits (see below)
•	Create Message, update Conversation.last_message_at, create/update MessageRead for sender, create Notification for recipient
Rate Limits
Action	Limit	Implementation
Start conversation	5 per hour per user	Django cache (LocMemCache in dev, Redis when available)
Send message	20 per 10 minutes; 200 per day	Same cache-based counter
File a report	10 per day	Cache-based counter
Consecutive messages without response	If last 5 messages in a thread are from the same sender, require 30-min cooldown before next message	Check last 5 messages in thread on send
Inbox & Thread Pages
•	GET /messages/ — inbox ordered by Conversation.last_message_at descending. Show participant name, listing context (if any), snippet, unread indicator.
•	GET /messages/<conversation_id>/ — full message thread, newest at bottom. Mark as read (update MessageRead.last_read_at) on view.
Block & Report
•	Block: button in conversation header. Creates Block record. Existing conversation is closed (is_closed=True). New conversations cannot be started.
•	Block/unblock: manageable from user settings page ("Blocked Users" list)
•	Report: "Report message" link on each message, "Report conversation" in thread header. Creates MessageReport with status=open.
•	After reporting: message.moderation_state set to "flagged" (not hidden — admin reviews before hiding)
Admin Moderation Tools
•	All messages must be searchable via Django admin (search by body, sender, conversation)
•	Open reports queue: list filtered to status=open, ordered by created_at. Admin can view the full thread context.
•	Admin actions: resolve/dismiss report, set message to hidden, toggle messaging_disabled on UserProfile

Scope Limits
The following are explicitly out of scope for this task (defer to post-Beta or later):
•	Real-time chat / WebSockets / typing indicators
•	Image or file attachments in messages
•	Group conversations or multi-party threads
•	Full messaging disable based on account score or automated flagging

Acceptance Criteria
•	Users can start conversations from listing and trade offer pages
•	Messages are text-only and sender/recipient validated
•	Block and report work end-to-end
•	Rate limits prevent message flooding
•	Admin can search message content and resolve the report queue
•	Messaging is disabled for users with messaging_disabled=True on their profile

🗄 DATABASE IMPACT
New models (apps/messaging/):
•	Conversation, Message, MessageRead, Block, MessageReport — all new
Changes to UserProfile (§5.2, added in Task 3):
•	messaging_disabled, messaging_disabled_reason, messaging_disabled_at — added in Task 3, enforced here
🎨 UI IMPACT
•	New inbox page (/messages/) in nav utility area
•	Inbox icon/link with unread message count badge (separate from notification bell)
•	New conversation detail page (/messages/<id>/) with message thread and reply form
•	"Message seller" button on auction and buy-now listing detail pages
•	"Message counterparty" button on trade offer/trade detail pages
•	Block and report controls in conversation header
•	"Blocked Users" section in user settings/profile page

9.9 QA Hardening, Smoke Tests & Release Gate
What This Is
The final task of Phase 2 is to validate that everything built in Tasks 1-8 works together reliably, document what is known to be broken or incomplete, and pass a release gate before moving to the next phase. This is not about writing exhaustive automated test suites (keep momentum) - it is about a disciplined validation pass that gives confidence nothing catastrophic will hit a user on day one.
Smoke Test Suite
The following scenarios must be walked through manually on a staging environment before any release. The test environment must use Stripe test mode and shipping provider test mode.

Scenario	Steps	Expected Result
New user registration	Register → verify email → add shipping address → view account readiness	All steps work without admin help
Auction end-to-end	Create auction → bid → run close_auctions → checkout → pay → ship (enter tracking) → confirm receipt	Order status progresses through all states correctly
Buy-now end-to-end	Create buy-now → purchase → pay → ship → confirm receipt	Listing locks after purchase; order completes
Scheduled listing	Create listing with future go-live time → confirm it shows as "scheduled" → wait for cron → confirm it goes live	Listing activates at correct time
Auto-relist	Create auction → let it expire with no bids → confirm it relists once	Relist count increments; new listing is identical to original
Trade end-to-end	Propose trade → counter → accept → both ship → both confirm receipt	Trade status progresses through all states; both shipments captured
Messaging	User A messages User B on a listing → B replies → A blocks B → confirm no further messages possible	Block is applied; conversation is closed
Notifications	Trigger: outbid, auction won, ship-by reminder, wanted list match → confirm each appears in notification center and email	All notification types fire and link correctly
State-aware forms	Create a listing for a non-PA state (e.g., Ohio) → confirm county dropdown shows Ohio counties, not PA	Dropdowns are state-aware
Multi-state browse	Browse collection with state filter set to Ohio → confirm only Ohio items shown	Browse filters correctly by state
		
Known-Issues Documentation
Before closing Phase 2, document all remaining known issues in the bug tracker with severity class. This documentation is the record to be referenced when planning Phase 3 / Beta.

9.X Phase 2 Risks & Mitigations

Risk	Likelihood	Mitigation
UI revamp delays spill into other tasks	High	Constrain Task 5 to layout, nav, and component CSS — no architectural rewrites. Templates can be updated incrementally.
Messaging moderation burden grows quickly	Medium	Start text-only with strict throttles. The report queue exists to batch admin review — it does not require real-time responses.
Auto-relist creates duplicate/zombie listings	Low	Relist creates a brand new Listing record with original_listing FK. The original is marked expired. Admin can view relist chains.
9.Y Summary of Changes to Section 5 (Database Schema) and Section 6 (Design & UX)
Section 5 and Section 6 remain the authoritative documentation for the database schema and design direction. The changes introduced in Phase 2 are summarized below. These should be incorporated into Section 5 and Section 6 in a future plan revision.

Section 5 — Database Schema Changes
Model / Section	Change	Introduced In
§5.3 Reference Data — State (NEW)	Per section 9.2	Task 2
§5.3 Reference Data — County → GeographicUnit	Per section 9.2	Task 2
§5.3 Reference Data — LicenseType	Per section 9.2	Task 2
§5.2 UserProfile	Add: messaging_disabled, messaging_disabled_reason, messaging_disabled_at, target_county (FK GeographicUnit)	Tasks 3, 7
		Tasks 4, 6
§5.6 Listing	Add: scheduled_at, auto_relist, relist_count, original_listing (FK self), material, local_pickup_available, local_pickup_location.	Tasks 2, 4
§5.6 ListingLotItem (NEW)	New join model: listing (FK), collection_item (FK, nullable), description (CharField), sort_order (IntegerField)	Task 4
§5.8 Order	Add: delivery_method (CharField: shipping/local_pickup)	Task 4
Messaging — New models	Conversation, Message, MessageRead, Block, MessageReport — all new, in apps/messaging/	Task 9
Q&A model	Add: moderation_state (CharField: ok/flagged/hidden) to existing Question model	Task 8
		

Section 6 — Design & UX Direction Changes
Area	Change
§6.2 Navigation (NEW)	Four primary nav pillars: Auction House, General Store, Trading Block, Collections. Secondary utility nav (profile, notifications, messages, dashboard) right-aligned or in collapsed menu.
§6.2 Header	"KeystoneBid" text is the dominant header element. Logo is footer treatment. Clean switcher tab bar between the three marketplace sections.
§6.3 Notifications	Bell icon (SVG) with red/amber unread count badge. Replaces text label.
§6.4 Listing Cards (MVP) + §6.5 (Alpha)	Image-first cards are the highlight and more visible, text metadata below. Browse grid: 3 col desktop, 2 tablet, 1 mobile.
§6.5 New pages added in Phase 2	Browse Collections (/collections/), Messages inbox (/messages/), Conversation detail (/messages/<id>/).
§6.5 Page consolidation	Dashboard consolidates buyer/seller activity in one tabbed view. Profile page consolidates account settings, address management, verification.
§6.5 Mobile	All layouts must be responsive to 375px minimum width. Hamburger nav on mobile.

10. ALPHA Phase 3
10.0 Overview
ALPHA Phase 3 tightens core features and adds some nice-to-haves. Phase 2 made the core flows stable, state-aware, and usable for real collectors. Phase 3 builds the collector-facing product layer on top of that foundation: stronger discovery, stronger public trust signals, better governance controls, richer collection tools, and advanced listing support that still fits the existing Django architecture.
The goal of this phase is not to chase every future nice-to-have. It is to finish the features that make the platform feel complete for early real users while preserving low maintenance overhead and keeping the codebase modular. Every feature in this phase must either improve trust, improve discovery, improve collector utility, or reduce admin friction.
Phase 3 is complete when all of the following are true:
•	Listing and collection records support serial number and era in a way that works cleanly with browse, related listings, and collector tracking. 
•	Public trust signals are live: seller profile links, public reviews, and public favorite counts (eBay like – positive, neutral, negative – no star ratings). 
•	Auction House and General Store browse pages support both list view and map/heatmap view.
•	The Trading Block has a faster, more intuitive offer composer with drag-and-drop and confirmation review before send. 
•	Versioned Terms of Service acceptance is live at sign-up. 
•	Notification preferences, general reports, admin messaging, and appeals are all active and integrated with the existing notifications/enforcement flow. 
•	County Tracker and Year Completion Tracker are live on public collector profiles. 
•	Lot listings, provenance documents and chains, and collection-driven discovery modules are working without breaking the existing order and listing architecture. 
•	A basic admin dashboard exists for usage, listings, enforcement, and financial snapshots. 
•	Phase 3 smoke tests pass on staging. 
Phase 3 Task Sequence
#	Task	Priority	Depends On
1	Metadata Enrichment & Canonical Era Handling	High	Phase 2 complete
2	Public Trust Signals: Reviews, Seller Identity, Favorite Counts	High	Task 1
3	Browse Map Mode & Listing Detail Discovery	Medium	Tasks 1-2
4	Trading Block UX Polish	Medium	Tasks 1-2
5	Governance, Communication Controls & Appeals	High	Phase 2 messaging + enforcement
6	Content, Policy Documents	Medium	Task 5
7	Collection Folders, County Tracker, & Grid Tracker	Medium	Tasks 1, 3
8	Lot Listings, Provenance & Collection-Gap Discovery	High	Tasks 1, 3, 7
9	Admin Dashboard, export, & Release Gate	Critical	All

10.1 Metadata Enrichment, Canonical Era Handling, Improved Listing Form UI
What This Is
Phase 2 introduced much richer listing and collection metadata, but one gap remains: era is referenced throughout the plan, yet it is not fully formalized as a consistent field across listings, collections, browse, and tracker features. Serial number is also useful collector metadata, but it currently has no structured place in the model.
This task closes that gap. It adds serial number as an optional structured field and makes era a first-class concept in a way that works with the existing Listing / CollectionItem split. The key rule is simple: exact year is preferred whenever known, but era must still be supported when the exact year is unknown.

Implementation Steps
Add serial_number to both Listing and CollectionItem as an optional field. This supports collector documentation, provenance notes, and identification without making the field mandatory.
Add era_label to both Listing and CollectionItem as a nullable controlled-choice field. Use these normalized values:
•	Pre-1920 
•	1920s 
•	1930s 
•	1940s 
•	1950s 
•	1960s 
•	1970s 
•	1980s 
•	1990s 
•	2000 
If license_year is known, era_label is auto-derived in model/service logic. If license_year is unknown, era_label becomes required. This avoids inconsistent duplicate entry while still supporting partial historical knowledge.
Create a shared helper, conceptually effective_era, used by:
•	listing filters 
•	collection filters 
•	related listing queries 
•	tracker aggregation 
•	provenance and collection-gap logic 
Update all listing creation, edit, collection, and “add to collection” flows so serial number and era move with the item across marketplace and collection contexts.
Improve listing form UI. put the listing form into 3 sections:
•	required fields (always visible)
•	optional fields (collapsed - says expand to add more details)
•	other listing details (like price, shipping, listing settings)
•	upload/drag-and-drop images on the left
Acceptance Criteria
•	A user can save a listing or collection item with an exact year, or with era only if the exact year is unknown. 
•	Era filters work consistently across marketplace browse and collection browse. 
•	Serial number appears on create/edit forms and detail pages when present. 
•	Related listing logic and tracker logic use the same era normalization. 
Database Impact
Changes to Listing and CollectionItem:
•	Add: serial_number (CharField, blank=True) 
•	Add: era_label (CharField, null=True, blank=True, controlled choices) 
No new app required.
UI Impact
•	Listing and collection forms gain serial number and era support. 
•	Detail pages display serial number and era when available. 
•	Browse filters gain an era option that works even when exact year is missing. 
10.2 Public Trust Signals: Reviews, Seller Identity, Favorite Counts, Seller’s listings tab on profile
What This Is
Phase 2 established public profiles, messaging, and operational trust controls. Phase 3 now adds the public trust layer collectors expect: visible seller identity, transaction-tied public reviews, and visible favorite counts. This should feel closer to a collector marketplace than a generic classified site.
The design should stay restrained. This is not a gamified rating system. It is a light trust layer that helps collectors decide who they are dealing with. Simple eBay style – positive, neutral, negative rating.
This step also adds a tab to a user’s profile for their active listings (from listings in the auction house and general store). This allows users to browse view all the listings of another user. User header and collection remains the main view on profiles, active listings should be a tab.
Implementation Steps
Add a seller card to the listing detail page. It should include:
•	display name 
•	profile link 
•	location summary if public 
•	public review summary (% positive & count)
•	count of completed marketplace transactions, if available 
Create a new reviews app for public transaction reviews.
User listing on profile:
•	public profile has two tabs: Collection and Active Listings 
•	Collection remains the default tab 
•	Active Listings shows the seller’s currently active marketplace listings across Auction House / General Store as applicable
Review model:
•	reviewer — FK to User 
•	reviewed_user — FK to User 
•	order — FK to Order, null=True, blank=True 
•	trade — FK to Trade, null=True, blank=True 
•	sentiment — choices: positive / neutral / negative 
•	body — TextField(blank=True) 
•	moderation_state — choices: ok / flagged / hidden 
•	created_at 
Rules:
•	One review per user per completed transaction context. 
•	Orders unlock review after completion. 
•	Trades unlock review after both sides complete. 
•	Reviews are public unless hidden by moderation. 
•	Public profiles show % positive and review counts, which matches the profile direction already implied elsewhere in the plan. 
•	Keep review text brief (255 characters)
Public favorite counts should be shown for:
•	listings 
•	public collection items 
These should be derived from the existing Favorite table; no separate favorite counter model is needed in Phase 3.
Acceptance Criteria
•	A listing detail page always shows a seller profile entry point. 
•	Completed orders and trades unlock a review form. 
•	Public profiles show review summary and count. 
•	Listings and public collection items show public favorite counts. 
•	Admin can hide abusive reviews without deleting the full record. 
Database Impact
New app: apps/reviews/
New model:
•	Review 
No schema change required for favorites.
UI Impact
•	Listing detail page gains seller card with profile link. 
•	Public profile gains review summary module. 
•	Review form appears on completed order/trade detail pages. 
•	Favorite counts become visible on public cards and detail pages. 

10.3 Browse Map Mode & Listing Detail Discovery
What This Is
Collectors often think geographically first. Phase 2 introduced state-aware reference data and normalized GeographicUnit records for counties and other issuance-unit systems. This task extends that foundation into marketplace browse by adding a toggle between the standard listing grid and a geographic browse mode for the Auction House and General Store.
This task also improves listing detail discovery so users can naturally keep browsing once they land on an item.

Implementation Steps
Add a list / map toggle to the Auction House and General Store browse pages. Do not add map mode to the Trading Block in this phase.
Use the existing reference-data layer as the source of truth :
Utilities\clean\states.csv (added to the db data model but originally from there) / State determines whether the selected state is county-based or another issuance-unit type 
geographic_units.csv (added to the db) / GeographicUnit provides the units to aggregate listings by 
active listing counts are computed from the existing Listing queryset grouped by state + geographic_unit 
For county-based states, render an SVG choropleth using a prebuilt county boundary dataset keyed by county FIPS code. KeystoneBid does not need latitude/longitude coordinates for this. It only needs:
selected state 
county FIPS codes from GeographicUnit 
active listing counts by county 
For non-county states, do not force a polygon map. Render a structured grid/list heatmap instead, using the state’s existing issuance-unit records (GMU, WMD, DPA, Hunt Area, etc.). This keeps the browse experience accurate without introducing a separate GIS data project during Alpha.
Map mode must respect the same filters already applied in list mode. If a user filters by state, era, year range, condition, or license classification, the geographic browse counts must update from that filtered queryset.
Clicking a county or geographic unit in browse mode should apply that unit as a filter and refresh the listing results below.
On listing detail pages, add two discovery modules:
Related Listings — active listings that share state + effective era or overlapping license classification 
More from this Collection — other active listings from the same seller
Acceptance Criteria
Auction House and General Store browse pages can switch cleanly between list mode and geographic browse mode. 
Pennsylvania renders as a county choropleth using FIPS-based matching, not manual coordinates. 
Non-county states render as a structured grid/list heatmap fallback. 
Clicking a county or geographic unit filters the results. 
Listing detail pages show related discovery modules when data exists. 
Database Impact
No new core models required.
Recommended indexes on listing browse fields if not already present:
listing_type 
status 
state 
geographic_unit 
era / year fields used for related-listing logic 
No coordinate fields are required for this task.
UI Impact
New browse toggle on Auction House and General Store pages 
New FIPS-driven county map surface for supported county states 
New grid/list heatmap surface for non-county states 
New “Related Listings” and “More from this Collection” modules on listing detail pages

10.4 Trading Block UX Polish
What This Is
Phase 2 makes the Trading Block functional. Phase 3 makes it feel good. The current offer model is solid, but the UI needs to become faster and more intuitive for collectors who are comparing multiple items and building offers visually.
My original thought was like espn fantasy football esq.
The target experience is a clean four-column trade board:
•	your collection 
•	what you are offering 
•	what they are offering 
•	their collection 
Implementation Steps
Rebuild the trade composer UI around drag-and-drop tiles for collection items. A user should be able to drag an item from their collection into the offer area and remove it just as easily.
Provide a non-drag fallback for accessibility and mobile. Drag-and-drop should enhance the experience, not become the only path.
Add a confirmation review screen before sending any new offer or counteroffer. The review must clearly show:
•	which items each side is giving 
•	any cash add-on 
•	expiration window 
•	listing/trade context 
•	a final confirm action 
Server-side validation remains authoritative. On submit, re-check:
•	item ownership 
•	trade_eligible 
•	block/restriction status 
•	duplicate or stale item use 
•	whether cash is allowed for that trade context 
Acceptance Criteria
•	Users can build an offer visually by moving items between collection and offer zones. 
•	The same flow works on mobile via explicit add/remove controls. 
•	Every offer and counteroffer has a confirmation review step before creation. 
•	Stale or invalid items are caught server-side even if the UI looked valid. 
Database Impact
No schema changes required. This is a view/template/JS enhancement built on existing TradeOffer and TradeOfferItem models.
UI Impact
•	Trade detail page gains a visual offer composer 
•	Confirmation screen added before send/counter 
•	Faster, clearer offer editing on desktop and mobile 

10.5 Governance, Communication Controls & Appeals
What This Is
Phase 2 already established the core enforcement system: strike triggers, the enforcement ladder, account gating, and the mutual resolution / excuse flow. It also established operational notifications tied to real marketplace events such as payment due, payment received, ship-by reminders, tracking updates, and trade offer state changes. Phase 3 extends that foundation with user notification preferences, standardized admin-editable message language, a general report intake form, admin-originated platform messaging, and a lightweight appeals layer tied directly to existing enforcement records.
This task is primarily about reducing admin chaos while keeping the platform fair, consistent, and controlled. It should not create a second, parallel enforcement system. Instead, it should formalize how the existing system communicates with users and how edge cases are reviewed.
Implementation Steps
5a. Notification Categories & User Preferences
Add notification categories and user-configurable preferences.
Suggested categories:
•	transactional
•	shipping / deadlines
•	enforcement / safety
•	wanted list matches
•	favorites / collection activity
•	review activity
•	admin announcements
•	marketing / commercial
Not every category can be disabled.
The following categories must remain non-optional:
•	transactional
•	shipping / deadlines
•	enforcement / safety
•	admin announcements that are marked mandatory
Create a NotificationPreference model keyed by user + category so settings stay explicit and extensible.
The notification preference layer must sit on top of the actual event flows already in the app. In other words, the preference system does not invent new notifications. It controls delivery for events that already exist, including:
•	payment due
•	payment received
•	ship-by reminders
•	tracking updates
•	trade offer received
•	trade offer countered
•	trade accepted
•	trade expired
•	wanted-list match
•	review received
•	strike notice
•	restriction / suspension / ban notice
•	appeal decision
•	admin announcement
Enforcement / safety notifications must always be delivered in-app. Email delivery for those notices should also remain mandatory if the account has a valid email on file.
5b. Standardized Platform Message Templates
Add SystemMessageTemplate records editable in admin for sensitive platform messages. These are not generic canned replies. They are standardized platform messages tied to the actual flows already in the app.
Required template types:
•	warning
•	strike notice
•	restriction notice
•	suspension notice
•	ban notice
•	excuse / mutual resolution request
•	excuse confirmed
•	appeal received
•	appeal decision
•	report receipt
•	admin safety / conduct message
Templates should be written to reduce escalation:
•	concise
•	neutral
•	not overly specific about investigations or internal moderation reasoning
•	clear about what action, if any, the user must take
•	protective of both users and admins
Placeholder templates can be put in place initially, but the full workflow should be implemented so admin can edit and use them through the app.
5c. General Report Form
Add a general in-app report form for reporting:
•	user
•	listing
•	collection item
•	trade
•	order
•	other
After submit, show a standard confirmation that the platform does not disclose the details or outcome of internal investigations.
This report flow is for safety, conduct, listing, and platform concerns. It does not replace the existing operational enforcement logic already triggered by observable failures such as non-payment, non-shipment, or cancellation abuse. Those enforcement events should continue to be handled through the order / trade / strike system already defined elsewhere in the app.
5d. Admin-to-User Messages
Add an admin-to-user message tool in the admin panel.
This should allow admin to send a message to a specific user with:
•	subject
•	message body
•	optional template selection
Delivery behavior:
•	create an in-app notification
•	optionally send an email telling the user they received a message from the platform team
•	store a basic audit trail of who sent the message and when
This tool is for platform communication, not free-form customer support chat.
5e. User-Wide Broadcast Notifications
Add a user-wide broadcast notification tool for sitewide announcements.
Broadcast notifications should:
•	appear in all users’ notifications
•	optionally send email when appropriate
•	support a mandatory flag
•	not be disable-able when marked mandatory
This is for things like major policy updates, platform-wide notices, and important operational announcements.
5f. Appeals Layer Tied to Existing Enforcement
Add an EnforcementAppeal model and simple appeals flow tied directly to existing enforcement records.
Appeals should attach to one or both of:
•	a specific Strike
•	a specific AccountRestriction
This keeps the review process grounded in the actual enforcement event already stored in the system.
The appeal view shown to admin should surface the relevant context:
•	strike reason
•	related order or trade, if any
•	current restriction state
•	excuse / mutual resolution history, if any
•	user-submitted explanation
•	admin decision and notes
Appeals should support a simple lifecycle:
•	submitted
•	under_review
•	approved
•	denied
Approval may result in an override such as:
•	strike marked excused or removed from active enforcement count
•	restriction lifted or adjusted
Denial leaves the original enforcement record in place.
5g. Relationship to the Existing Excuse Flow
Do not replace the existing mutual resolution / excuse flow with appeals.
The intended sequence should remain:
•	first, handle legitimate late-ship or non-ship edge cases through the existing excuse / resolve flow between the parties
•	only after enforcement exists, allow an appeal for admin review
This keeps appeals as the exception path, not the default way users try to resolve routine shipment issues.
5h. Email Rules
Email rules:
•	transactional, shipping / deadline, and enforcement emails ignore commercial opt-out
•	commercial / marketing email must honor opt-out and include required footer language
•	notification settings page should explain that some categories are optional and some are mandatory
Acceptance Criteria
•	Users can change optional notification settings from profile settings.
•	Mandatory categories cannot be disabled.
•	Notification preferences apply to real app events already defined in payments, shipping, trades, reviews, wanted-list matches, and enforcement.
•	General reports route into an admin queue.
•	Admin can send direct platform messages and sitewide announcements.
•	Standardized platform templates exist for strike, restriction, suspension, ban, excuse-flow, appeal, and report messages.
•	Users can submit appeals tied to existing strike or restriction records.
•	Appeals show admin the relevant enforcement context, including related order / trade and excuse history when present.
•	Commercial email respects opt-out and transactional / enforcement email does not break.
Database Impact
New models:
•	NotificationPreference
•	SystemMessageTemplate
•	SupportReport
•	EnforcementAppeal
•	optional AdminAnnouncement record for auditability
Recommended model relationships:
•	EnforcementAppeal → FK to Strike (nullable)
•	EnforcementAppeal → FK to AccountRestriction (nullable)
Best modular placement:
•	preferences / templates / announcements under notifications
•	appeals under enforcement
•	reports in a small new support app
UI Impact
•	Profile/settings page gains notification preference controls
•	New general report form
•	New appeal form on relevant account enforcement pages
•	Admin gets direct message and broadcast tools
•	Admin gains editable system-message templates for sensitive enforcement and safety communications
10.6 Content & Policy Documents
What This Is
Phase 3 adds the public-facing content and policy layer for flows that already exist elsewhere in the app. This task is not about generic “help pages.” It is about making the platform’s actual rules, lifecycle expectations, and user-facing standards visible and understandable so collectors know what happens, when it happens, and what the platform will do if something goes wrong. The app already has concrete operational flows for notifications, shipping deadlines, strikes, excuses, reporting, appeals, and admin messaging. Phase 3 section 10.5 already owns the mechanics for notification preferences, system message templates, general reports, admin-to-user messaging, broadcast notifications, and appeals.
Section 10.5 owns the system mechanics for notification settings, standard admin templates, reports, admin messages, and appeals. This section owns the public-facing pages and policy documents that explain those mechanics in plain language and make acceptance versioned where needed.
The goal is to reduce confusion and support burden by documenting the real platform behavior already defined in the marketplace, shipping, trade, enforcement, and notification flows.
Implementation Steps
Create a lightweight content app for admin-managed public pages. These should be searchable, linkable, editable in admin, and organized around the app’s actual workflows rather than generic marketing copy. On the front end site, a sub navigation should be included to view these documents just called like Documentation or How-Tos or something.
Required content sections:
How KeystoneBid Works
High-level explanation of the three marketplace paths:
•	Auction House: bid → win → pay → ship → receive
•	General Store: buy now → pay → ship → receive
•	Trading Block: offer → counter/accept → both ship → both receive
Buying Guide
Explains what happens after a user wins an auction or buys a fixed-price listing:
•	payment due
•	payment confirmation
•	shipping / local pickup flow
•	tracking updates
•	receipt confirmation
•	all-sales-final policy if that remains the platform rule
Selling Guide
Explains seller responsibilities:
•	listing accuracy
•	ship-by expectations
•	label purchase or tracking entry
•	what happens if the seller misses shipment deadlines
•	when a strike can be applied for non-shipment
Trading Block Guide
Explains the structured trade flow already defined in the app:
•	offer / counter / accept / expire
•	optional cash add-on rules
•	shipping deadlines for both parties
•	tracking requirements
•	local pickup handling if enabled
•	what happens if one side fails to ship
Marketplace Rules / Site Policy
This should be the central public rules page for the platform. It should explain, at minimum:
•	listing accuracy requirements
•	prohibited listing behavior
•	mystery lots are not permitted
•	expectations for payment and shipment
•	standards for buyer, seller, and trader conduct
•	what users can report
•	that the platform does not disclose the outcome of investigations
•	that enforcement may include warnings, restrictions, suspensions, or bans
Enforcement & Appeals Guide
This should explain the existing enforcement logic already defined in the app:
•	strike triggers: non-payment, non-shipment, cancellation abuse
•	that enforcement is based on observable failures in tracked platform flows
•	that some situations may be excused through the mutual resolution / excuse flow
•	that users can submit an appeal for strikes or bans
•	that admin may override in edge cases
This page should explain the process without exposing internal moderation details.
Collections & Discovery Guide
Explains collection profiles, folders, pinned licenses, wanted lists, collection tracker tools, and how collection-based discovery works.
FAQ
Short-answer page for common questions that would otherwise create repetitive support messages.
Create a PolicyDocument model for versioned policy documents that must be managed formally rather than as loose help pages.
Recommended document types:
•	terms_of_service
•	privacy_policy
•	site_policy
Create PolicyAcceptance records storing:
•	user
•	policy_document
•	accepted_at
Terms of Service must be required at sign-up.
If a new required version of Terms of Service is published later, the user should be prompted to accept it on next login before continuing to use account-restricted features.
Privacy Policy and Site Policy should be publicly visible at all times. If you want versioned acknowledgement for Site Policy later, the model should support it, but only Terms of Service needs required acceptance in this phase.
The public content pages should cross-link directly to the corresponding operational surfaces already in the app where appropriate. Examples:
•	Notifications Guide → notification settings page
•	Enforcement & Appeals Guide → appeal form
•	Trading Block Guide → trade detail / help entry
•	Marketplace Rules / Site Policy → report form
Acceptance Criteria
•	Admin can publish and edit workflow-specific help pages without code changes.
•	Public site content reflects the actual platform flows already defined in marketplace, shipping, trade, enforcement, and notification logic.
•	A central Site Policy / Marketplace Rules page exists and is publicly accessible.
•	Terms of Service can be uploaded in admin, versioned, and required at sign-up.
•	Policy acceptance is recorded per user and per policy version.
•	If a new required Terms version is published, the user is prompted to accept it on next login.
•	Public pages clearly explain when notifications are sent, when deadlines apply, when enforcement can occur, and how appeals work.
Database Impact
New models:
•	HelpArticle or equivalent public content page model
•	PolicyDocument
•	PolicyAcceptance
Recommended PolicyDocument fields:
•	doc_type
•	version_label
•	title
•	uploaded_file or rendered content
•	is_active
•	requires_acceptance
•	published_at
No new notification, appeals, or report models belong here; those remain under Section 10.5.
UI Impact
•	New public How It Works / Rules section in site navigation or footer
•	New public workflow pages for buying, selling, trading, notifications, enforcement, collections, and FAQ
•	New public Site Policy page
•	Terms of Service acceptance step in sign-up flow
•	Re-acceptance prompt on login when a new required Terms version is active
10.7 County Tracker, Collection Matrix, & Collection Organization
What This Is
These are personal discovery tools, not competition features. This section improves how a collector’s public collection is organized and how they visualize coverage across geography and time.
The public collection page should feel structured and collector-first:
•	folders first
•	then pinned licenses
•	then one active collection visual at a time
The visual layer should not clutter the page. Instead of showing multiple charts at once, the collector can toggle between two views:
•	State Map View — for geographic coverage
•	Collection Matrix View — for time + geography coverage together
This keeps the profile clean while still giving collectors a meaningful way to see patterns in their collection.
Implementation Steps
7a. Collection Folders
•	users can create up to 5 custom folders
•	each folder has a custom name
•	an All folder exists by default and shows the full collection
•	collection items can be assigned to one folder for Phase 3 simplicity
•	public/profile collection view shows, in this order:
o	folder tabs first
o	then the 6 pinned licenses
o	then the collection visual toggle
o	then the contents of the selected folder
Folders are organizational only. They do not change item ownership, tracker data, or browse logic. Folders organize the broader collection; they do not replace the existing featured/pinned items display, which remains a separate top-of-profile showcase
7b. State Map View
Use an SVG-based interactive map for county-based states and a grid/list fallback for non-county states.
The page should show only one visual at a time. If State Map View is selected, the matrix is hidden.
For county-based states:
•	covered units: forest green fill
•	uncovered units: parchment fill with green outline
•	optional stronger fill or badge for units with higher item counts if desired, but keep the map readable first
Hover tooltip should show:
•	geographic unit name
•	number of licenses in that unit
•	years and/or eras represented in that unit
•	selected-folder context if a folder filter is active
Clicking a unit opens a side panel, modal, or inline detail panel showing the collection items in that unit.
If the collector has items from multiple states, allow a state selector. Default to Pennsylvania or the state most represented in the currently selected folder.
Show a simple progress line such as:
•	“34 of 67 counties represented”
7c. Collection Matrix View
Replace the year completion bar chart with a matrix/grid view.
The matrix should show:
•	X-axis: era
•	Y-axis: geographic unit for the selected state
Each cell represents a county/geographic-unit + era combination.
Cell behavior:
•	empty / parchment = no items for that combination
•	filled / forest green = one or more items in that combination
•	optional darker shade or count badge if more than one item exists, but Phase 3 can keep this binary if that is simpler
Hovering a filled cell should show:
•	geographic unit
•	era
•	item count
•	known years represented
•	optionally top matching license types if useful
Selecting a cell should show the specific collection items for that combination in a detail panel below or beside the grid.
This matrix is the more meaningful coverage view because it shows not just whether the user has a county, but whether they have that county across time.
7d. Visual Toggle + Filters
Only one visual should be visible at a time. Add a simple toggle:
•	Map
•	Grid
Both visuals should respect the same filters so the collector can narrow what is being visualized.
Suggested filters:
•	state
•	folder
•	era
•	year range
•	geographic unit
•	license type dimensions where relevant
•	material / shape / color only if the UI stays clean
Do not dump every possible filter on screen at once. Show the core filters first:
•	state
•	folder
•	era / year
•	geographic unit
•	license type
Then place the more detailed classification filters in a collapsed “More Filters” section.
The visual and the item detail panel should both update from the same filtered queryset.
7e. “Missing From My Collection” Alerts
Connect wanted items to marketplace listings. When a new listing matches a user’s wanted criteria, create an in-app notification and optional email.
Matching logic should use:
•	state
•	geographic unit if specified
•	year or era range
•	relevant license-type overlap based on the structured classification system already in place
This should stay lightweight. It is a matching helper, not a recommendation engine.
Acceptance Criteria
•	Public/profile collection view shows folders first, then pinned licenses, then the visual toggle, then the selected folder contents.
•	Users can create up to 5 custom folders plus the default All folder.
•	County tracker renders correctly for county-based states and falls back cleanly elsewhere.
•	Collection Matrix view renders geographic unit by era for the selected state.
•	Only one visual is shown at a time, switchable by a simple toggle.
•	Both the map and matrix respect the same collection filters.
•	Hover and selection reveal the licenses represented by a geographic unit or grid cell.
•	Target county/geographic unit can be saved.
•	Wanted-list match notifications fire correctly.
Database Impact
Changes to UserProfile:
Uses the existing UserProfile.target_county field from Phase 2
Add collection folder support:
•	CollectionFolder
o	owner — FK to User
o	name — CharField
o	sort_order — IntegerField
o	is_default_all — BooleanField(default=False)
Changes to CollectionItem:
•	add: folder (FK to CollectionFolder, null=True, blank=True)
Tracker and matrix data should be computed from filtered collection queries and do not require separate tracker tables.
UI Impact
•	Public collector profile gains folder tabs
•	Public collector profile keeps 6 pinned licenses near the top
•	Public collector profile gains a single visual toggle:
o	State Map View
o	Collection Matrix View
•	Visual filter controls added above the active visual
•	Detail panel opens from map selection or matrix cell selection
•	Browse cards can highlight the user’s target county/geographic unit
•	Wanted-list alerts surface through notifications/email
10.8 Lot Listings, Provenance, & Collection-Gap Discovery
What This Is
This task introduces grouped sales, provenance support, and collection-aware discovery features. These are high-value collector features, but they must fit the current listing/order architecture cleanly.
The critical modeling rule is this: a lot is not a new marketplace channel. Auction House and General Store already exist as the sale channels. A lot is simply a grouped inventory format used inside those channels.
Implementation Steps
Keep listing_type unchanged as:
•	auction 
•	buy_now 
•	trade 
Add a separate lot/grouping field on Listing, such as:
•	inventory_format = single / lot 
•	Default=single
Lots are allowed only when listing_type is auction or buy_now.
Create ListingLotItem:
•	listing — FK to Listing 
•	collection_item — FK to CollectionItem, null=True, blank=True 
•	description — CharField(200, blank=True) 
•	sort_order — IntegerField 
Rules:
•	all lot contents must be disclosed 
•	no mystery lots 
•	one top-level price or starting bid only 
•	individual lot items are not individually purchasable 
•	top-level source_collection_item remains null for lot listings 
•	lots are not added to collections
Duplicate and exclusivity rules should run at the ListingLotItem level for linked collection items. If an included collection item is already actively listed elsewhere, it cannot be added to the lot.
The Alpha Phase 2 (Section 9) rule that source_collection_item is required applies to standard single-item listings only; lot listings are the explicit exception and use ListingLotItem as the inventory linkage layer.
Provenance Documents & Platform Ownership Chain
Add provenance support to both listings and collection items.
In the listing form and collection-item form, allow the user to upload original documents related to the license, such as paperwork, receipts, letters, envelopes, certificates, or other supporting historical material. These documents become part of the item’s provenance record.
On the listing detail page and collection-item detail page, show a dedicated provenance section with a more polished visual treatment than a plain file list. This section should include:
•	uploaded provenance documents
•	a platform ownership chain when the item has moved through KeystoneBid more than once
Platform ownership chain logic:
If a buyer purchases a license on KeystoneBid, adds it to their collection, and later resells that same item through the platform, the next listing or collection detail can show a platform-history note such as:
•	“Previously in the collection of [username]”
Over time, licenses can accumulate a visible KeystoneBid ownership chain. This should be derived from existing order history and linked collection/listing records rather than from a separate manually entered ownership-chain system.
This feature is valuable because collectors care about provenance, and it becomes stronger as more items circulate through the platform.
•	Users can upload provenance documents when creating or editing a listing or collection item.
•	Provenance documents appear on listing detail and collection-item detail pages.
•	If an item has prior KeystoneBid ownership history, that history is shown as a platform ownership chain.
•	Platform ownership history is derived from existing transaction and linked collection/listing records.

Collection-Gap Discovery in Browse
Add a collection-driven discovery option to marketplace browse.
When a signed-in user is browsing active listings, allow them to turn on a filter such as:
•	Needed for My Collection
When enabled, browse prioritizes or filters to listings that appear to fill gaps in the user’s collection based on the collection data already stored on the platform.
This matching should use the collector’s existing collection and compare it against active listings using dimensions such as:
•	state
•	geographic unit
•	era / year
•	relevant license-type dimensions
This feature belongs in browse and listing discovery, not in provenance. Provenance is about ownership and supporting documents; collection-gap discovery is about what the user is still missing.
•	Signed-in users can enable a “Needed for My Collection” browse filter or toggle.
•	Matching active listings are filtered or highlighted based on the user’s collection gaps.
•	Matching logic uses existing collection metadata and active listing metadata.
•	The feature appears in browse/discovery surfaces, not in the operational dashboard.
Acceptance Criteria
•	Lots can be created only in Auction House and General Store flows. 
•	Duplicate protection works at the included-item level. 
•	Provenance documents can be uploaded to listings and collection items. 
•	Platform history appears when there is real KeystoneBid transaction history behind the item. 
•	Collection-gap suggestions surface relevant active listings. 
Database Impact
Changes to Listing:
•	Add: inventory_format (single / lot) 
New models:
•	ListingLotItem 
•	ProvenanceDocument 
No change to top-level listing_type.
UI Impact
•	Listing create/edit flow supports single-item vs lot mode 
•	Listing detail page can render lot contents 
•	Collection items and listings can show provenance docs/history 
•	Browse gains collection-gap discovery

10.9 Admin Dashboard, Order History Export, Dashboard Stats & Phase 3 Release Gate
What This Is
The last task of Phase 3 is operational visibility and release readiness. By this point the platform has enough moving parts that both admin and users need clear, lightweight reporting surfaces. Admin needs a simple internal overview of platform health and financial activity. Users need a practical dashboard summary and the ability to query and export their own recent buying and selling history without admin help. This task keeps reporting intentionally simple. It is not a full analytics suite or BI layer. It is a lightweight operational dashboard plus export functionality that supports day-to-day use, reconciliation, and pre-Beta validation. 

Implementation Steps
Add a basic admin dashboard showing:
•	total users 
•	verified users 
•	active listings by section 
•	completed orders 
•	completed trades 
•	open reports 
•	open appeals 
•	active restrictions / suspensions 
•	GMV / item sales totals 
•	shipments in exception status 
Keep this lightweight. It is an internal summary page, not a BI product.

Add simple user dashboard summary cards at the top of the dashboard. These should be based on the last 3 months and give the user a quick snapshot of activity:
•	active listings count 
•	sold count 
•	bought count 
•	trades count
•	collection count 
These should be simple count cards only. No charts are needed in this phase.

Add user history query and export in the dashboard view.
User export requirements:
•	users can query purchase history and sales history for up to the prior 12 months 
•	filter by date range 
•	filter to purchases, sales, or both 
•	export results in a simple format such as CSV 
exported fields should include core transaction information only, such as date, listing title, order type, buyer/seller role, item amount, shipping amount, total amount, and order status. this is just a data dump

Add admin order-history query and export.
Admin export requirements:
•	admin can query and export order history for reconciliation, financial review, and platform reporting 
•	filters should include at minimum date range, order status, order type, and seller 
•	export format should be CSV 
•	admin export should include the fields needed for financial review, including order totals, shipping, platform fees, and payment status 

Run a final smoke test pass in staging covering:
metadata entry with era-only and year-known cases 
review creation and public display 
map browse mode 
trade drag-and-drop + confirmation 
notification preference enforcement 
general report intake 
appeal workflow 
ToS versioned acceptance 
brand store purchase flow 
tracker correctness 
lot listing creation and lot purchase import flow 
provenance upload and display 
user history query and export 
admin order-history query and export 
dashboard summary cards showing correct 3-month counts 

Acceptance Criteria
Admin can see platform health from one dashboard page. 
Users see simple buyer/seller summary cards at the top of their dashboard for the last 3 months. 
Users can query and export their own purchase and sales history for up to the prior 12 months. 
Admin can query and export order history for reconciliation and financial review. 
All new Phase 3 flows have staging smoke test results logged. 
Known issues are documented before moving to Beta. 
Database Impact
No new core business models required beyond prior Phase 3 tasks. Dashboard views and export queries should run from existing order, trade, listing, collection, and enforcement data.
If needed for performance, add or verify indexes on:
order created date 
order status 
order type 
buyer 
seller 

UI Impact
New admin-only dashboard page 
User dashboard gains four top summary cards: 
Active Listings 
Sold 
Bought 
In Collection 
User dashboard gains purchase/sales history filter and export controls 
Admin dashboard gains order-history filter and export controls 
If you want, I can also tighten the title so it reads a little cleaner, because right now “User/admin order-history query + export” is doing a lot of work in one phrase.

10.X Phase 3 Risks & Mitigations
Risk	Likelihood	Mitigation
Reviews create moderation burden	Medium	Keep reviews lightweight: positive / neutral / negative with optional short text, allow admin hide without deleting the record, and do not build a full review-dispute system in Phase 3.
Governance tools drift away from the existing strike / enforcement system	High	Keep Phase 3 governance tied to existing enforcement records and flows. Appeals attach to Strike and/or AccountRestriction, system templates mirror real enforcement states, and the general report form does not replace automated order/trade enforcement triggers.
Notification preferences accidentally suppress critical emails or in-app notices	High	Enforce mandatory categories in the service layer, not just the settings UI. Transactional, shipping / deadline, enforcement / safety, and mandatory admin announcements must always be deliverable regardless of user preferences.
Map browse becomes inconsistent across non-county states	Medium	Restrict true choropleth rendering to verified county-based states using FIPS-linked geographic units. Use a structured grid/list fallback for non-county issuance-unit states rather than forcing incomplete map behavior.
Collection Matrix becomes cluttered or hard to read with too many filters or dimensions	Medium	Show only one visual at a time, use a simple map/grid toggle, default to one selected state, keep core filters visible, and move secondary filters into a collapsed “More Filters” section.
Collection folders become confusing or too flexible for early users	Low	Keep the model simple in Phase 3: one default All folder, up to 5 custom folders, and each collection item assigned to at most one folder. Avoid nested folders, sharing rules, or folder-specific permissions.
Lot modeling breaks existing listing, browse, or order logic	High	Keep listing_type unchanged and introduce lots as a separate inventory/grouping layer on top of auction and buy-now only. Validate lot contents explicitly and run duplicate / exclusivity checks at the ListingLotItem level.
Provenance and platform-history data becomes misleading if over-inferred	Medium	Limit provenance history to actual KeystoneBid-linked transaction history and uploaded provenance documents. Do not imply a full ownership chain unless the platform has direct records for it.
Order-history export exposes the wrong data or becomes a financial/privacy issue	Medium	Separate user and admin export scopes. Users can export only their own purchase/sales history within the allowed window; admin export includes financial fields needed for reconciliation. Keep exports filterable, audit-friendly, and limited to necessary columns.
Dashboard scope grows into a reporting product instead of a lightweight operational view	Medium	Keep Phase 3 dashboards card-based and summary-oriented. Use counts, totals, and simple filters only; no custom analytics suite, forecasting, or BI-style drilldowns in this phase.
10.Y Summary of Changes
Section 5 - Database Schema Changes
Users / Profiles
Uses the existing UserProfile.target_county field from Phase 2 – no change
Listings
•	Listing: add serial_number
•	Listing: add era_label
•	Listing: add inventory_format (single / lot)
Collections
•	CollectionItem: add serial_number
•	CollectionItem: add era_label
•	CollectionFolder: new model for public/profile collection organization
o	owner
o	name
o	sort_order
o	is_default_all
•	CollectionItem: add folder (FK to CollectionFolder, null=True, blank=True)
Reviews / Public Trust
•	new Review model tied to completed Order or Trade
Governance / Notifications / Appeals
•	new NotificationPreference model
•	new SystemMessageTemplate model
•	new SupportReport model
•	new EnforcementAppeal model tied to existing Strike and/or AccountRestriction
Policy / Content
•	new HelpArticle or equivalent public content-page model
•	new PolicyDocument model
•	new PolicyAcceptance model
Lots / Provenance
•	new ListingLotItem model
•	new ProvenanceDocument model
No brand-store models are included in Phase 3.
Section 6 - Design & UX Changes
Public Trust / Seller Identity
•	seller card and public trust summary on listing detail pages
•	public review summaries on collector profiles
•	seller profile includes a second tab for active listings, with collection remaining the default tab
Browse / Discovery
•	map/list browse toggle for Auction House and General Store
•	FIPS-driven county map for supported county-based states
•	structured grid/list fallback for non-county states
•	listing detail discovery modules such as related listings and more from this seller’s collection
Listing / Trade UX
•	listing form reorganized into:
o	required fields
o	optional fields (collapsed)
o	other listing details
•	image upload / drag-and-drop area placed on the left
•	drag-and-drop Trading Block composer with confirmation review step
Collection Profile UX
•	public/profile collection view gains:
o	folder tabs
o	pinned licenses near the top
o	a single visual toggle beneath the pins
•	only one collection visual shown at a time:
o	state map view
o	collection matrix view
•	collection matrix replaces the simple era bar chart and shows geographic unit by era with hover/select detail behavior
Governance / Policy UX
•	notification settings screen
•	general report entry point
•	appeal entry point on relevant enforcement pages
•	public How It Works / Rules / Policy content hub
•	Terms of Service acceptance step in sign-up flow and re-acceptance prompt when a new required version is active
Dashboard / Export UX
•	user dashboard gains simple top summary cards for the last 3 months:
o	active listings
o	sold
o	bought
o	in collection
•	user dashboard gains order-history query and export controls
•	admin dashboard gains operational summary cards plus order-history query/export controls
Lots / Provenance UX
•	lot display and lot-detail presentation on listing pages
•	provenance documents and platform-history modules on listing/detail and collection surfaces


11. BETA – The Best ‘Nice-to-Have’s’
This phase implements the most useful nice-to-have features. Features should focus on bringing the site from a normal online marketplace to one focused and tailored to the collecting community.

Features include:
•	Any trade matching suggestions beyond “wanted list” hints
•	Add google and apple account setup

license and general hunting trivia. 3 questions a day - 20 seconds to answer each. keep monthly leaderboard (most correct answers last 30 days, and current active streak leaderboard (since last wrong answer). 3 new questions shown each day from question bank. all multiple choice. leaderboard shown after user answers all 3.

Make sure databases are set up for future enhancements on showing visualizations and data on Price History & Market Data from platform’s transactions/trades/collections
Set up production in AWS. Establish clean flow from dev to prod.
12. App Launch
Section is TBD. BETA Recovery based on beta users’ feedback. Implement user feedback and full website launch.

12.1 Beta Recovery
•	fix issues from beta testers
•	tune shipping deadlines, strike rules, and trade gating thresholds
12.2 Launch Readiness Gate
•	Stripe webhooks verified (prod)
•	Shipping webhooks verified (prod) + polling fallback tested
•	Background jobs stable (cron/management commands)
•	Email deliverability verified (SES)
•	Order + trade lifecycle state transitions validated end-to-end
•	Admin tooling ready for:
o	manual overrides (edge cases)
o	bans/suspensions
o	viewing shipment and offer history
12.3 Launch
•	invite collectors first (controlled ramp)
•	then public
  
13. Additional Features (After Launch)
*Updated needed, several features moved to Section 8 Alpha.

Group chats - public and private.
Grading system model.
Estimated value ranges.

Newsletter - send through email by admins and system.

OP-ED / Journal
- users can submit opinions pieces and stories
- comment section at bottom
- not forums
- Style it like a newspaper

13.1 Community Features
•	Education Hub - Historical articles, license timeline
•	County Spotlights - One article per PA county
•	User Stories - Collector blogs with admin review

13.2 Collector Engagement
•	Badges - Achievement system (Keystone Collector, etc)

13.3 Marketplace Enhancements
•	Proxy Bidding - Auto-bidding up to max
•	Advanced Search - Full-text search via PostgreSQL

13.4 Education Hub
The Education Hub is a core differentiator for KeystoneBid. It positions the platform as the authoritative resource for Pennsylvania hunting license history — driving organic search traffic, building community trust, and giving collectors context that makes their collections more meaningful.

License History Timeline
An interactive visual timeline of Pennsylvania hunting licenses from the earliest known examples to the present day. Each era is clickable and expands to show representative license designs, regulatory changes, and historical context. Built with vanilla JS and CSS transitions — no heavy library needed.

County Spotlight Articles
A dedicated article for each of Pennsylvania's 67 counties covering: notable hunting heritage, famous game wardens or hunters from the county, notable licenses from that county seen in collections, the county's wildlife management history, and any unique local traditions. These articles also connect to the collector county tracker feature.

Era Guides
Long-form guides to distinct eras of Pennsylvania hunting licenses: pre-1915 (early license era), 1915–1940 (standardization), 1940–1960 (post-war growth), 1960–1980 (conservation era), 1980–present (modern era). Each guide covers design evolution, printing methods, issuing agents, and what makes licenses from that era desirable to collectors.

Notable Figures
Articles profiling notable figures in Pennsylvania hunting history: early game wardens, conservationists, famous hunters, and the administrators who shaped the licensing system. Written with the same care as encyclopedia entries — sourced, respectful, and informative.

Collector's Guide
Practical guides for new collectors: How to grade condition, how to research provenance, how to store and preserve antique licenses, what to look for when buying, and how to build a focused collection. Positioned as the 'getting started' resource for the PA antique hunting license collecting community.

13.5 Collector Stories
Users can submit written stories about their collecting experiences, significant finds, family license histories, or county-specific research. Stories are submitted through a simple form and enter an admin review queue before publication. This keeps quality high and prevents spam while giving the community a voice.

•	Story submission form: title, body text (rich text editor with basic formatting), optional county and year tags, optional cover photo
•	Admin review queue: approve, request edits, or reject with a reason sent to the author
•	Published stories appear in a Stories section, browsable by county and year
•	Story authors get attribution with a link to their collector profile
•	No comments section on stories — keeps moderation simple. Instead, a 'Contact the Author' link routes to the platform's messaging system

13.6 Price History & Market Data
Completed sale prices are recorded and displayed publicly after transaction completion. Users can view price history charts for listings filtered by county, year, license type, and condition grade. This serves both buyers (understanding fair value) and the community (documenting the historical record of what these licenses are worth). Built with simple Canvas-based charts — no heavy charting library required.

13.7 System Condition Grading
An ML model for grading condition of antique hunting licenses.
Integrated in the listing or collection modules.
Backend uses AWS Lambda call to python package

13.b Feature Specifications — Collector Engagement
13.b.1 Design Philosophy
Gamification on KeystoneBid is purely about personal joy, discovery, and community recognition — not competition. There are no leaderboards, no rankings, no points for buying more. Every mechanic is designed to make an individual collector's experience richer, more organized, and more fun. The historical and community spirit comes first.

13.b.2 County Tracker (moving to ALPHA Phase 2/3)
Every collector has a personal Pennsylvania county tracker — a visual map of all 67 counties. Each county lights up when a collector adds a license from that county to their collection. Hovering over a county shows how many licenses from that county they have and what years are represented.

•	Counties with 1+ license: highlighted in forest green
•	Counties with no license: outline only on parchment background
•	Click any county: see your collection items from that county + any active marketplace listings from that county
•	Progress display: '34 of 67 counties represented' — framed as personal discovery, not a competition
•	Collectors can set a 'target county' — listings from that county are highlighted in their browse experience

13.b.3 Year Completion Tracker (moving to ALPHA Phase 2/3)
Collectors can see how many licenses they have from each decade or specific year range. A simple decade-by-decade bar chart on the collector dashboard showing collection coverage by era. No ranking against other users — purely a personal reference tool.

13.b.4 Badges (Tags)
Badges are earned automatically based on collection milestones and platform contributions. They are displayed on the public collector profile. Badges are never taken away. The emphasis is on recognition of genuine collecting, not gaming the system. Call them tags for hunting reference.

Collection Badges (Tags)
•	Keystone Collector — first license added to collection
•	County Scout — 10 counties represented
•	County Explorer — 25 counties represented
•	County Pilgrim — 50 counties represented
•	Commonwealth Collector — all 67 counties represented
•	Century Mark — licenses spanning 100+ years in the collection
•	Early Bird — owns a license from before 1920
•	The Classics — 10+ licenses from the 1920s–1940s

Community Badges
•	Storyteller — first approved Collector Story published
•	Chronicler — 5 approved Collector Stories published
•	Trusted Seller — 25+ completed sales with 4.8+ rating
•	Trusted Buyer — 25+ completed purchases with 4.8+ rating
•	Heritage Scholar — read all Education Hub era guides (tracked by session)

13.b.5 Collection Showcase (moving to ALPHA Phase 1)
Each collector's public profile includes a curated showcase section where they can show collection items as featured pieces. Each featured piece shows an image, year, county, and the collector's own caption. This is the digital equivalent of a display case — personal, curated, and meaningful.

13.b.6 'Missing From My Collection' Alerts
Collectors can mark specific county / year / type combinations as 'wanted' in their tracker. When a matching listing is posted on the marketplace, they receive an automatic notification. This bridges the collector tracking and marketplace features in a natural, non-competitive way.
 
14. Development Plan: Git to MVP (4 Weeks)
Phase 0: Setup (Week 1, Days 1-2)
•	Create GitHub repo, clone locally, create branch strategy (main/develop)
•	Install Django 5.0 in virtual environment: pip install django
•	Start project: django-admin startproject config .
•	Create apps directory: mkdir apps
•	Create MVP apps: python manage.py startapp accounts apps/accounts (repeat for listings, bids, payments, notifications)
•	Configure settings split: config/settings/base.py, development.py, production.py
•	Create .env.example, add .env to .gitignore
•	Create requirements/base.txt, development.txt, production.txt
•	Run migrations: python manage.py migrate
•	Create superuser: python manage.py createsuperuser
•	First commit: 'Initial Django project structure'

Phase 1: Authentication (Week 1, Days 3-7)
•	Create UserProfile model extending User via OneToOne
•	Create registration form with email verification
•	Configure Django's email backend (console for dev, SES for prod)
•	Create login/logout views (use Django's built-in)
•	Create profile edit view and template
•	Create public profile view
•	Add CSS to base.html
•	Test registration flow end-to-end
•	Commit: 'Accounts app complete'

Phase 2: Listings (Week 2, Days 1-4)
•	Create Listing and ListingImage models
•	Configure MEDIA_ROOT and MEDIA_URL
•	Create ListingForm with ImageFormSet
•	Create listing_create view
•	Create listing_detail, listing_list views
•	Implement filtering via QuerySets
•	Add pagination (Django Paginator)
•	Register models in Django admin
•	Test: Create listing with images, browse, filter
•	Commit: 'Listings app complete'

Phase 3: Bidding (Week 2, Days 5-7)
•	Create Bid model
•	Create bids/services.py with place_bid() logic
•	Implement bid validation and current_bid updates
•	Add HTMX via CDN, create bid_status API endpoint
•	Add Alpine.js countdown timer
•	Test bidding flow, verify outbid notifications
•	Commit: 'Bidding system complete'

Phase 4: Payments & Auction Close (Week 3)
•	Create Transaction model
•	Create close_auctions management command
•	Integrate Stripe Checkout
•	Create Stripe webhook handler
•	Test end-to-end auction close and payment
•	Commit: 'Payments and auction close complete'

Phase 5: Notifications & Dashboard (Week 3-4)
•	Create Notification model
•	Create send_notifications management command
•	Create email templates
•	Build user dashboard views
•	Polish Django admin interface
•	Commit: 'Notifications and dashboard complete'

Phase 6: Production Deployment (Week 4)
•	Provision EC2 t3.micro, install PostgreSQL
•	Clone repo, set up venv, install requirements
•	Configure production settings and .env
•	Run migrations, collect static files
•	Set up Gunicorn systemd service
•	Configure Nginx reverse proxy
•	Obtain SSL certificate via Certbot
•	Set up cron jobs for auction close and notifications
•	Configure AWS SES
•	Test production deployment
•	Commit: 'Production deployment complete'

Phase 7: Alpha – Core Expansion (2–4 Weeks)
Purpose: implement buy-now, trades, collections, shipping, strikes/excuses, in-app notifications—end-to-end.
7.1 Project Structure Updates (Alpha Apps)
7.	Add new apps (or modules) aligned to Alpha:
o	core (County, LicenseType + seed commands)
o	collections (CollectionItem, WantedItem)
o	orders (Order + AddressSnapshot + receipt confirmation)
o	shipping (Shipment + provider wrappers + webhooks/polling)
o	trades (TradeOffer, Trade, TradeShipment)
o	favorites (Favorite)
o	enforcement (Strike + excuse fields + AccountRestriction)
8.	Update settings for new app registrations + env vars:
o	shipping provider keys
o	webhook secrets
9.	Commit: Alpha app scaffolding
7.2 Database Migrations (Alpha Models)
10.	Replace/extend MVP models where needed:
•	Listing: add listing_type, reserve_price, buy-now fields, trade fields, reference FK fields
•	Payments: introduce Order + PaymentTransaction split
•	Add shipping snapshot tables (AddressSnapshot)
11.	Create and run migrations (SQLite + Postgres validation)
12.	Seed reference data (PA counties + minimal license types)
13.	Commit: Alpha schema complete
7.3 Collections (Inventory Backbone)
14.	Implement collection CRUD:
•	add/edit item, images, visibility, trade eligibility
15.	Add wanted list (“Looking For”) CRUD
16.	Add “list from collection” to listing create flow
17.	Add public collector profile view + private collection management view
18.	Commit: Collections + wanted list complete
7.4 Buy-Now (General Store)
19.	Add Buy-now listing creation path via listing_type=buy_now
20.	Add buy-now browse page and filters
21.	Implement purchase lock (one-to-one Order) to prevent double-selling
22.	Implement buy-now checkout (Stripe) → Order paid state
23.	Commit: Buy-now complete
7.5 Shipping Integration (Sales + Optional Trades)
24.	Add seller package fields (weight/dimensions) needed for rate quoting
25.	Implement shipping quote selection at checkout (buyer pays shipping)
26.	After payment: seller can generate label OR enter external tracking
27.	Implement shipment status progression:
•	label_created → in_transit → delivered → completed
28.	Implement webhook ingestion for tracking updates (provider)
29.	Implement polling fallback job for tracking updates (cron/management command)
30.	Commit: Shipping integration complete
7.6 Trading Block (Negotiation + Agreement + Dual Shipping)
31.	Implement trade listing (listing_type=trade) tied to collection inventory
32.	Implement offer + counteroffer:
•	offer expiration
•	accept/decline/counter
33.	On accept: create Trade agreement record + deadlines
34.	Implement dual shipment capture + tracking for trade shipments
35.	Implement trade completion:
•	both delivered + both confirm receipt (or auto-complete grace window)
36.	Commit: Trading block complete
7.7 Enforcement + Exceptions (“Excuse” Flow)
37.	Implement strike triggers:
•	non-payment
•	non-shipment
•	cancellation abuse
38.	Implement enforcement ladder (1 → 2 → 3 strikes within 12 months)
39.	Add “mutual resolution / excused” flow:
•	one party initiates excuse
•	other party confirms within 72 hours
•	if confirmed: strike marked excused, doesn’t count
40.	Add gating:
•	no selling without address
•	no trading without verification gate
41.	Commit: Enforcement + excuses complete
7.8 In-App Notifications (not just email)
42.	Add notification bell + unread count
43.	Add notifications center page
44.	Add key Alpha notifications:
•	payment due / payment received
•	ship-by reminders
•	tracking updates
•	trade offer received / countered / accepted / expired
45.	Commit: In-app notifications complete
7.9 Alpha End-to-End Validation (Staging)
46.	Create a staging environment:
•	separate Stripe test keys + shipping test keys
•	webhook endpoints for staging domain
47.	Run full test scenarios:
•	auction → win → pay → label → delivered → complete
•	buy-now → pay → ship → delivered → complete
•	trade → offer → accept → both ship → complete
48.	Add admin tools for manual overrides (minimal):
•	mark delivered / cancel / excuse override (rare)
49.	Commit: Alpha end-to-end complete

Phase 8: Beta – Community Nice-to-Haves (2–6 Weeks)
Purpose: add the best engagement features without creating heavy moderation load.
50.	Add public Reviews (positive/neutral/negative + text) with basic abuse rules
51.	Add Auction Q&A (with moderation constraints and rate-limits)
52.	Add county map browse / heatmap (if still desired)
53.	Add public favorite counts (optional)
54.	Add quality-of-life improvements:
•	search improvements
•	better filtering
•	listing UX polish
55.	Beta testing loop + bug triage
56.	Commit: Beta feature set complete

Phase 9: Beta Recovery + Launch (1–3 Weeks)
Purpose: stabilize, lock down configuration, and launch with controlled risk.
57.	Beta recovery sprint:
•	fix critical bugs
•	tighten trade gating rules
•	adjust shipping deadlines and strike tuning
58.	Launch readiness gate checklist:
•	Stripe webhooks (prod) verified, idempotent
•	shipping webhooks (prod) verified + polling fallback works
•	background jobs stable
•	SES deliverability verified
•	admin override tools tested
59.	Production deployment updates:
•	environment variable secrets
•	migration runbook
•	rollback plan (DB + app)
60.	Soft launch (invite-only) → full launch
61.	Commit: Launch complete

 
15. AWS Deployment & Cost Strategy
15.1 Free Tier Strategy
MVP runs on single EC2 t3.micro (free tier 12 months) with PostgreSQL installed locally. Media files in EC2 filesystem. Cost: $0.50/month for Route 53 only.

15.2 Services Used
Service	Free Tier	Usage	Post-Free Cost
EC2 t3.micro	750 hrs/mo, 12 mo	Django + PostgreSQL	~$8/mo
SES	62k emails/mo	Notifications	$0.10/1000
Route 53	N/A	DNS	~$0.50/mo

15.3 Alternative: SQLite for Zero Cost
For absolute minimum cost during development, use SQLite (Django's default). Migrate to PostgreSQL when ready by exporting/importing data. Saves infrastructure cost until you have users.
 
16. Scaling Path
16.1 Scaling Triggers
•	500+ listings OR 100+ concurrent users → Move PostgreSQL to RDS
•	1000+ images → Move to S3 via django-storages
•	Complex background jobs → Add Celery + Redis
•	Traffic spikes → Add ALB + second EC2 instance

16.2 Seamless Upgrades
Every upgrade is a configuration change, not code rewrite:
•	SQLite → PostgreSQL: Change DATABASES in settings.py
•	Local media → S3: Install django-storages, update settings
•	Cron → Celery: Swap task runner, business logic unchanged
•	Single EC2 → Load Balancer: Add instances, no app changes

16.3 Cost Scaling
•	Months 1-12: $0-$5/month
•	After free tier: $20-$35/month (EC2 + RDS + S3)
•	At 500 sales/month: ~$50/month infrastructure, $750 revenue (5% fee)
 
17. Security & Legal
17.1 Security (Django Defaults)
•	CSRF protection enabled by default
•	SQL injection prevention via ORM
•	XSS protection via template auto-escaping
•	Password hashing via PBKDF2
•	HTTPS enforced via Nginx
•	Secrets in .env, never in Git

17.2 Legal Considerations
•	Can’t be an auction house need to follow eBay model – users set all the terms. Not an auctioneer.
•	Terms of Service: Expired licenses only
•	Privacy Policy: Required for user data collection
•	DMCA policy for image copyright claims

17.3 Pre-Launch Checklist
•	All user flows tested end-to-end
•	Email verification working in production
•	Stripe webhooks verified
•	Django admin secured
•	HTTPS working, auto-renewal configured
•	Cron jobs running
•	Database backups configured
•	Terms and Privacy pages live
•	Beta testers invited

This Django development plan provides a complete, cost-conscious path from initial setup to production deployment. The modular architecture ensures seamless scaling as your marketplace grows.

Start building, validate with real users, then layer on community and collector features based on feedback. Django's batteries-included approach means you'll spend more time building marketplace features and less time configuring infrastructure.
