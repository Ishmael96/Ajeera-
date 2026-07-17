import hashlib
import os
import random
import re
import secrets
import sqlite3
from datetime import datetime, timedelta

from flask import Flask, g, jsonify, request, send_from_directory
from werkzeug.security import check_password_hash, generate_password_hash

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "ajeer.db")

app = Flask(__name__)

DEFAULT_ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "880296")
SESSION_DAYS = 30

# ----------------------------------------------------------------------------
# Reference data
# ----------------------------------------------------------------------------
COUNTRIES = {
    "UAE": {"name": "UAE", "flag": "\U0001F1E6\U0001F1EA", "currency": "AED",
            "cities": ["Dubai", "Abu Dhabi", "Sharjah", "Ajman"]},
    "QAT": {"name": "Qatar", "flag": "\U0001F1F6\U0001F1E6", "currency": "QAR",
            "cities": ["Doha", "Al Rayyan", "Al Wakrah"]},
    "TUR": {"name": "Turkey", "flag": "\U0001F1F9\U0001F1F7", "currency": "TRY",
            "cities": ["Istanbul", "Ankara", "Izmir", "Antalya"]},
    "OMN": {"name": "Oman", "flag": "\U0001F1F4\U0001F1F2", "currency": "OMR",
            "cities": ["Muscat", "Sohar", "Salalah"]},
    "BHR": {"name": "Bahrain", "flag": "\U0001F1E7\U0001F1ED", "currency": "BHD",
            "cities": ["Manama", "Riffa", "Muharraq"]},
    "JOR": {"name": "Jordan", "flag": "\U0001F1EF\U0001F1F4", "currency": "JOD",
            "cities": ["Amman", "Zarqa", "Irbid"]},
    "KWT": {"name": "Kuwait", "flag": "\U0001F1F0\U0001F1FC", "currency": "KWD",
            "cities": ["Kuwait City", "Hawalli", "Salmiya"]},
    # Long-haul driver destinations only (Central / Eastern / Northern Europe).
    # No agents in Germany/UK, and immigration rules there are tougher, so
    # those two are deliberately excluded per the business decision.
    "LUX": {"name": "Luxembourg", "flag": "\U0001F1F1\U0001F1FA", "currency": "EUR",
            "cities": ["Luxembourg City", "Esch-sur-Alzette"]},
    "HUN": {"name": "Hungary", "flag": "\U0001F1ED\U0001F1FA", "currency": "EUR",
            "cities": ["Budapest", "Debrecen"]},
    "BGR": {"name": "Bulgaria", "flag": "\U0001F1E7\U0001F1EC", "currency": "EUR",
            "cities": ["Sofia", "Plovdiv"]},
    "SRB": {"name": "Serbia", "flag": "\U0001F1F7\U0001F1F8", "currency": "EUR",
            "cities": ["Belgrade", "Novi Sad"]},
    "FIN": {"name": "Finland", "flag": "\U0001F1EB\U0001F1EE", "currency": "EUR",
            "cities": ["Helsinki", "Tampere"]},
    "SWE": {"name": "Sweden", "flag": "\U0001F1F8\U0001F1EA", "currency": "EUR",
            "cities": ["Stockholm", "Gothenburg"]},
    "NOR": {"name": "Norway", "flag": "\U0001F1F3\U0001F1F4", "currency": "EUR",
            "cities": ["Oslo", "Bergen"]},
}
GULF_COUNTRY_CODES = ["UAE", "QAT", "TUR", "OMN", "BHR", "JOR", "KWT"]
EUROPE_COUNTRY_CODES = ["LUX", "HUN", "BGR", "SRB", "FIN", "SWE", "NOR"]

SECURITY_QUESTIONS = [
    "What is the name of your favorite football club?",
    "What is the name of your primary school?",
    "What is your sibling's first name?",
    "What is the name of a childhood pet?",
    "What is the name of your childhood best friend?",
]

CATEGORIES = {
    "clean": {"label": "Cleaning", "icon": "\U0001F9F9",
              "range": {"UAE": (1200, 1900), "QAT": (1300, 2000), "TUR": (14000, 19500),
                        "OMN": (95, 150), "BHR": (95, 145), "JOR": (190, 270), "KWT": (95, 155)},
              "titles": ["Live-in Housemaid", "Daily Cleaner", "Office Cleaner", "Villa Housekeeper", "Deep-Clean Crew Member"],
              "desc": "Daily housekeeping duties including sweeping, mopping, laundry and general tidiness. Cleaning materials provided on site."},
    "cook": {"label": "Cooking", "icon": "\U0001F372",
             "range": {"UAE": (1600, 2500), "QAT": (1700, 2600), "TUR": (16000, 23500),
                       "OMN": (115, 175), "BHR": (115, 180), "JOR": (230, 330), "KWT": (125, 205)},
             "titles": ["Family Cook", "Household Chef", "Kitchen Helper", "South Asian Cuisine Cook", "Private Cook (Live-out)"],
             "desc": "Prepare daily family meals; experience with home-style South Asian and Arabic dishes preferred. Groceries budget provided."},
    "driver": {"label": "Driver", "icon": "\U0001F697",
               "range": {"UAE": (2000, 3200), "QAT": (2100, 3300), "TUR": (18000, 27000),
                         "OMN": (135, 205), "BHR": (140, 225), "JOR": (260, 390), "KWT": (150, 255)},
               "titles": ["Family Driver", "Light Truck Driver", "Company Driver", "School Run Driver", "Personal Chauffeur"],
               "desc": "Drop-off and pick-up for family members, occasional errands. Clean driving record and valid local license required."},
    "watch": {"label": "Watchman / Security", "icon": "\U0001F6E1",
              "range": {"UAE": (1400, 2100), "QAT": (1450, 2200), "TUR": (15000, 20500),
                        "OMN": (95, 135), "BHR": (95, 145), "JOR": (190, 270), "KWT": (100, 165)},
              "titles": ["Compound Watchman", "Night Security Guard", "Site Security Guard", "Building Watchman", "Warehouse Guard"],
              "desc": "Rotating shift security at residential compound / site gate. Basic English or Arabic and prior guard experience preferred."},
    "construction": {"label": "Construction", "icon": "\U0001F3D7",
                      "range": {"UAE": (1300, 2000), "QAT": (1350, 2100), "TUR": (15500, 22500),
                                "OMN": (95, 145), "BHR": (95, 155), "JOR": (195, 285), "KWT": (105, 165)},
                      "titles": ["General Construction Laborer", "Steel Fixer Helper", "Site Cleanup Crew", "Scaffolding Helper", "Concrete Laborer"],
                      "desc": "General labor on active build site \u2014 lifting, mixing, cleanup. Safety boots and helmet provided."},
    "garden": {"label": "Gardening", "icon": "\U0001F33F",
               "range": {"UAE": (1200, 1750), "QAT": (1250, 1800), "TUR": (13500, 18500),
                         "OMN": (85, 125), "BHR": (85, 135), "JOR": (165, 235), "KWT": (95, 145)},
               "titles": ["Villa Gardener", "Landscaping Helper", "Compound Gardener", "Palm Tree Maintenance Worker"],
               "desc": "Weekly maintenance of lawns, hedges and irrigation lines for a private villa or compound."},
    "nanny": {"label": "Nanny / Childcare", "icon": "\U0001F9F8",
              "range": {"UAE": (1800, 2900), "QAT": (1900, 3000), "TUR": (17500, 25500),
                        "OMN": (115, 185), "BHR": (125, 205), "JOR": (225, 325), "KWT": (135, 225)},
              "titles": ["Live-in Nanny", "Part-time Babysitter", "Newborn Care Nanny", "After-school Nanny"],
              "desc": "Care for two young children, light housekeeping related to childcare. First-aid knowledge a plus."},
    "waiter": {"label": "Waiter / Hospitality", "icon": "\U0001F37D",
               "range": {"UAE": (1500, 2300), "QAT": (1550, 2400), "TUR": (15500, 21500),
                         "OMN": (105, 155), "BHR": (105, 165), "JOR": (195, 275), "KWT": (115, 185)},
               "titles": ["Restaurant Waiter", "Cafe Staff", "Banquet Server", "Room Service Attendant"],
               "desc": "Front-of-house service for a busy family restaurant / cafe. Weekend availability required."},
    "plumber": {"label": "Plumber", "icon": "\U0001F527",
                "range": {"UAE": (2200, 3600), "QAT": (2300, 3700), "TUR": (19500, 28500),
                          "OMN": (135, 225), "BHR": (145, 255), "JOR": (235, 365), "KWT": (155, 285)},
                "titles": ["Maintenance Plumber", "Plumber Helper", "Villa Plumbing Technician"],
                "desc": "Basic plumbing repairs and maintenance across serviced apartments. Own hand tools preferred."},
    "electrician": {"label": "Electrician", "icon": "\U0001F4A1",
                     "range": {"UAE": (2500, 3900), "QAT": (2600, 4000), "TUR": (20500, 30500),
                               "OMN": (155, 235), "BHR": (165, 265), "JOR": (265, 385), "KWT": (185, 305)},
                     "titles": ["Maintenance Electrician", "Electrician Helper", "Site Electrician"],
                     "desc": "Routine maintenance wiring and fixture repairs across a residential compound."},
    "painter": {"label": "Painter", "icon": "\U0001F3A8",
                "range": {"UAE": (1800, 2700), "QAT": (1850, 2800), "TUR": (16500, 23500),
                          "OMN": (110, 175), "BHR": (125, 185), "JOR": (205, 295), "KWT": (135, 205)},
                "titles": ["Villa Painter", "Spray Painter Helper", "Building Painter"],
                "desc": "Interior and exterior touch-up painting for villas ahead of tenant handover."},
    "mason": {"label": "Mason / Tiler", "icon": "\U0001F9F1",
              "range": {"UAE": (2000, 3100), "QAT": (2050, 3200), "TUR": (17500, 25500),
                        "OMN": (125, 195), "BHR": (135, 215), "JOR": (225, 335), "KWT": (150, 245)},
              "titles": ["Tiling Mason", "Block-work Mason", "Finishing Mason"],
              "desc": "Tiling and block-work finishing on a mid-rise residential build."},
    "caregiver": {"label": "Caregiver / Elderly Care", "icon": "\U0001FA7A",
                  "range": {"UAE": (1900, 3000), "QAT": (2000, 3100), "TUR": (18000, 26000),
                            "OMN": (120, 190), "BHR": (130, 210), "JOR": (235, 335), "KWT": (140, 230)},
                  "titles": ["Live-in Elderly Caregiver", "Home Health Aide", "Patient Care Assistant", "Post-Surgery Care Attendant"],
                  "desc": "Daily care and companionship for an elderly or convalescing family member. Basic first-aid or nursing-assistant background preferred."},
    "hotel": {"label": "Hotel Worker", "icon": "\U0001F3E8",
              "range": {"UAE": (1600, 2500), "QAT": (1650, 2600), "TUR": (16500, 23000),
                        "OMN": (110, 165), "BHR": (110, 175), "JOR": (205, 290), "KWT": (120, 195)},
              "titles": ["Hotel Housekeeping Attendant", "Front Desk Assistant", "Hotel Laundry Attendant", "Bellhop / Porter"],
              "desc": "Guest-facing or back-of-house hotel role. Shift-based, uniform and meals typically provided on site."},
    "longhaul": {"label": "International Long-Haul Driver", "icon": "\U0001F69B",
                 "range": {"LUX": (2900, 3800), "HUN": (1800, 2600), "BGR": (1700, 2500), "SRB": (1700, 2500),
                           "FIN": (2600, 3400), "SWE": (2700, 3500), "NOR": (3200, 4200)},
                 "titles": ["International Long-Haul Truck Driver", "Cross-Border Container Driver",
                            "Refrigerated Long-Haul Driver", "HGV Driver \u2014 International Routes"],
                 "desc": "Category CE / CPC license and long-haul experience required. Practical interview only \u2014 no paperwork needed upfront: candidates demonstrate reversing, parking and maneuvering a long-haul vehicle on site. Ajeer Expert members get priority placement and a Verified Driver badge for this category."},
}

EUROPE_CLIENT_PREFIXES = ["Nordwest", "Baltic Freight", "TransEuro", "Alpine Cargo", "Danube", "Carpathia",
                           "Fjord Line", "Continental", "Via Nord", "Balkan Express", "Polaris Haulage", "Silk Route"]
EUROPE_CLIENT_SUFFIXES = ["Logistics", "Freight Group", "Haulage Ltd", "Transport AB", "Spedition", "Cargo Lines", "Trucking Co."]

CLIENT_PREFIXES = ["Al Falah", "Marina Bay", "Zafer Family", "Palm Residency", "Al Waha", "Corniche Tower",
                    "Bayti", "Green Valley", "Al Noor", "Sunrise", "Al Reem Island", "Bosphorus View",
                    "Dilmun", "Petra Heights", "Salmiya Business", "Wadi Al Nakhil", "Al Manar", "Cedar Court",
                    "Yildiz", "Deira"]
CLIENT_SUFFIXES = ["Household", "Villa Community", "Family Residence", "Facilities Management", "Compound",
                    "Contracting Co.", "Site Office", "Trading LLC", "Apartments", "Group", "Residence",
                    "Property Management", "Construction Co.", "Hospitality Group"]
JOB_TYPES = ["Full-time - Live-in", "Full-time - Live-out", "Daily wage", "Part-time", "2-week contract"]
JOB_STATUSES = ["open", "in_process", "gone"]

APPLICATION_STATUSES = ["submitted", "viewed", "contacted", "hired", "closed"]
EXPERT_PRICE = {"currency": "USD", "amount": 15}
APPLICATIONS_DISPLAY_BASELINE = 643  # shown-count floor so the stat bar never reads 0 on a fresh deploy
GONE_JOB_RETENTION_HOURS = 24

FAQ = [
    {"keywords": ["salary", "pay", "wage", "money"], "answer": "Salaries shown are realistic going-rates per country and role, either per month or per day \u2014 check the amount under each listing."},
    {"keywords": ["urgent"], "answer": "Jobs marked URGENT need someone within 48 hours. Use the status filter on the job board to see just those."},
    {"keywords": ["apply", "application"], "answer": "Tap Apply now on any listing, fill in your name and phone, and the employer gets it immediately. Track it later from My Account."},
    {"keywords": ["post", "hire", "employer"], "answer": "Use 'Post a Job' under the Employers menu. You'll get an account automatically so you can check applications later."},
    {"keywords": ["expert", "premium", "cv", "resume"], "answer": "Ajeer Expert is our paid tier: a professionally drafted CV, a Verified badge, and priority placement. See the Premium menu to express interest."},
    {"keywords": ["country", "countries"], "answer": "Household and trade roles cover UAE, Qatar, Turkey, Oman, Bahrain, Jordan and Kuwait. International long-haul driver roles are based in Luxembourg, Hungary, Bulgaria, Serbia, Finland, Sweden and Norway."},
    {"keywords": ["pin", "password", "login", "log in", "account"], "answer": "First time logging in? Start with the last 5 digits of your phone number as a one-time PIN. You can set your own PIN, add a security question, and change your display name anytime from My Account."},
    {"keywords": ["longhaul", "long-haul", "long haul", "truck", "hgv"], "answer": "Long-haul driving roles are based in Luxembourg, Hungary, Bulgaria, Serbia, Finland, Sweden and Norway. The interview is practical, not paperwork-based \u2014 you demonstrate reversing, parking and maneuvering the vehicle. Applying is free; Ajeer Expert members get priority placement and a Verified Driver badge."},
    {"keywords": ["driver jobs", "driver"], "answer": "Local driver roles (family drivers, company drivers) are open across all seven Gulf/Levant countries. International long-haul driver roles are a separate category based in Europe \u2014 ask me about 'long haul' for details."},
    {"keywords": ["caregiver", "elderly", "care"], "answer": "Caregiver roles cover elderly companionship and home health support. Prior care experience is preferred but check each listing for specifics."},
    {"keywords": ["nanny jobs"], "answer": "Nanny and childcare roles range from live-in to part-time after-school care \u2014 filter by the Nanny / Childcare category."},
    {"keywords": ["hotel"], "answer": "Hotel roles include housekeeping, front desk and porter positions, usually shift-based with uniform and meals provided."},
]


# ----------------------------------------------------------------------------
# Database helpers
# ----------------------------------------------------------------------------
def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(exception=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db(reseed=False):
    fresh = reseed or not os.path.exists(DB_PATH)
    conn = sqlite3.connect(DB_PATH)
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ref_code TEXT UNIQUE,
            category TEXT,
            title TEXT,
            country_code TEXT,
            city TEXT,
            client_name TEXT,
            contact_phone TEXT,
            contact_email TEXT,
            lat REAL,
            lng REAL,
            salary_amount INTEGER,
            salary_unit TEXT,
            currency TEXT,
            job_type TEXT,
            positions INTEGER,
            urgent INTEGER,
            description TEXT,
            posted_at TEXT,
            status TEXT DEFAULT 'open',
            status_updated_at TEXT,
            source TEXT DEFAULT 'seed'
        );

        CREATE TABLE IF NOT EXISTS applications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id INTEGER,
            name TEXT,
            phone TEXT,
            nationality TEXT,
            experience_years INTEGER,
            message TEXT,
            status TEXT DEFAULT 'submitted',
            lat REAL,
            lng REAL,
            created_at TEXT,
            updated_at TEXT,
            FOREIGN KEY (job_id) REFERENCES jobs (id)
        );

        CREATE TABLE IF NOT EXISTS workers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            phone TEXT,
            nationality TEXT,
            category TEXT,
            experience_years INTEGER,
            preferred_countries TEXT,
            bio TEXT,
            tier TEXT DEFAULT 'standard',
            created_at TEXT
        );

        CREATE TABLE IF NOT EXISTS cv_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            worker_phone TEXT,
            name TEXT,
            current_role TEXT,
            experience_summary TEXT,
            target_country TEXT,
            status TEXT DEFAULT 'received',
            created_at TEXT
        );

        CREATE TABLE IF NOT EXISTS support_tickets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            contact TEXT,
            message TEXT,
            status TEXT DEFAULT 'open',
            created_at TEXT
        );

        CREATE TABLE IF NOT EXISTS accounts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            phone TEXT UNIQUE,
            email TEXT,
            username TEXT,
            password_hash TEXT,
            security_question TEXT,
            security_answer_hash TEXT,
            created_at TEXT
        );

        CREATE TABLE IF NOT EXISTS verified_sessions (
            token TEXT PRIMARY KEY,
            phone TEXT,
            expires_at TEXT,
            created_at TEXT
        );

        CREATE TABLE IF NOT EXISTS premium_leads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            phone TEXT,
            name TEXT,
            preferred_payment_method TEXT,
            note TEXT,
            status TEXT DEFAULT 'pending',
            created_at TEXT
        );

        CREATE TABLE IF NOT EXISTS admin_settings (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            password_hash TEXT
        );

        CREATE TABLE IF NOT EXISTS chat_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            phone TEXT,
            sender TEXT,
            message TEXT,
            created_at TEXT
        );
        """
    )
    conn.commit()

    def cols(table):
        return [r[1] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()]

    if "contact_phone" not in cols("jobs"):
        conn.execute("ALTER TABLE jobs ADD COLUMN contact_phone TEXT DEFAULT ''")
    if "contact_email" not in cols("jobs"):
        conn.execute("ALTER TABLE jobs ADD COLUMN contact_email TEXT DEFAULT ''")
    if "lat" not in cols("jobs"):
        conn.execute("ALTER TABLE jobs ADD COLUMN lat REAL")
    if "lng" not in cols("jobs"):
        conn.execute("ALTER TABLE jobs ADD COLUMN lng REAL")
    if "status_updated_at" not in cols("jobs"):
        conn.execute("ALTER TABLE jobs ADD COLUMN status_updated_at TEXT")
    if "username" not in cols("accounts"):
        conn.execute("ALTER TABLE accounts ADD COLUMN username TEXT")
    if "security_question" not in cols("accounts"):
        conn.execute("ALTER TABLE accounts ADD COLUMN security_question TEXT")
    if "security_answer_hash" not in cols("accounts"):
        conn.execute("ALTER TABLE accounts ADD COLUMN security_answer_hash TEXT")
    if "tier" not in cols("workers"):
        conn.execute("ALTER TABLE workers ADD COLUMN tier TEXT DEFAULT 'standard'")
    if "status" not in cols("applications"):
        conn.execute("ALTER TABLE applications ADD COLUMN status TEXT DEFAULT 'submitted'")
    if "updated_at" not in cols("applications"):
        conn.execute("ALTER TABLE applications ADD COLUMN updated_at TEXT")
    if "lat" not in cols("applications"):
        conn.execute("ALTER TABLE applications ADD COLUMN lat REAL")
    if "lng" not in cols("applications"):
        conn.execute("ALTER TABLE applications ADD COLUMN lng REAL")
    conn.commit()

    if conn.execute("SELECT COUNT(*) c FROM admin_settings").fetchone()[0] == 0:
        conn.execute("INSERT INTO admin_settings (id, password_hash) VALUES (1, ?)",
                     (generate_password_hash(DEFAULT_ADMIN_PASSWORD),))
        conn.commit()

    if fresh:
        conn.execute("DELETE FROM jobs")
        conn.execute("DELETE FROM applications")
        seed_jobs(conn)
    conn.close()


def seed_jobs(conn, per_category=105):
    rnd = random.Random(42)
    category_keys = list(CATEGORIES.keys())
    seed_phones_gulf = ["+971501002200", "+974334419021", "+905327782201", "+968923301147",
                        "+973390002214", "+962795418820", "+96566003391"]
    seed_phones_europe = ["+352691002200", "+36301112233", "+359877001122", "+381641122334",
                          "+358401122334", "+46701122334", "+4791122334"]
    seed_coords = {"UAE": (25.2048, 55.2708), "QAT": (25.2854, 51.5310), "TUR": (39.9334, 32.8597),
                   "OMN": (23.5859, 58.4059), "BHR": (26.2285, 50.5860), "JOR": (31.9454, 35.9284),
                   "KWT": (29.3759, 47.9774),
                   "LUX": (49.6116, 6.1319), "HUN": (47.4979, 19.0402), "BGR": (42.6977, 23.3219),
                   "SRB": (44.7866, 20.4489), "FIN": (60.1699, 24.9384), "SWE": (59.3293, 18.0686),
                   "NOR": (59.9139, 10.7522)}
    rows = []
    counters = {code: 1000 for code in COUNTRIES.keys()}
    now = datetime.utcnow()

    def weighted_status():
        r = rnd.random()
        if r < 0.82:
            return "open"
        if r < 0.92:
            return "in_process"
        return "gone"

    for cat_key in category_keys:
        cat = CATEGORIES[cat_key]
        is_longhaul = cat_key == "longhaul"
        country_pool = EUROPE_COUNTRY_CODES if is_longhaul else GULF_COUNTRY_CODES
        client_prefixes = EUROPE_CLIENT_PREFIXES if is_longhaul else CLIENT_PREFIXES
        client_suffixes = EUROPE_CLIENT_SUFFIXES if is_longhaul else CLIENT_SUFFIXES
        seed_phones = seed_phones_europe if is_longhaul else seed_phones_gulf
        n = per_category + rnd.randint(0, 20)
        for _ in range(n):
            code = rnd.choice(country_pool)
            country = COUNTRIES[code]
            lo, hi = cat["range"][code]
            raw = rnd.randint(lo, hi)
            salary = round(raw / 5) * 5
            is_daily = cat_key == "construction" and rnd.random() < 0.4
            daily_rate = round((salary / 26) / 5) * 5
            city = rnd.choice(country["cities"])
            client = f"{rnd.choice(client_prefixes)} {rnd.choice(client_suffixes)}"
            title = rnd.choice(cat["titles"])
            urgent = 1 if rnd.random() < 0.22 else 0
            days_ago = rnd.randint(0, 21)
            posted_at = (now - timedelta(days=days_ago)).isoformat()
            job_type = "2-week contract" if is_longhaul else ("Daily wage" if is_daily else rnd.choice(JOB_TYPES))
            positions = rnd.randint(2, 6) if (rnd.random() < 0.2 and not is_longhaul) else 1
            counters[code] += 1
            ref_code = f"AJ-{code}-{counters[code]}"
            phone = rnd.choice(seed_phones)
            base_lat, base_lng = seed_coords[code]
            lat = base_lat + rnd.uniform(-0.15, 0.15)
            lng = base_lng + rnd.uniform(-0.15, 0.15)
            status = weighted_status()
            status_age_hours = rnd.uniform(0, 20 * 24) if status == "gone" else 0
            status_updated_at = (now - timedelta(hours=status_age_hours)).isoformat()

            rows.append((
                ref_code, cat_key, title, code, city, client, phone, "",
                round(lat, 5), round(lng, 5),
                daily_rate if is_daily else salary,
                "/ day" if is_daily else "/ month",
                country["currency"], job_type, positions, urgent,
                cat["desc"], posted_at, status, status_updated_at, "seed",
            ))

    conn.executemany(
        """INSERT INTO jobs
           (ref_code, category, title, country_code, city, client_name, contact_phone, contact_email, lat, lng,
            salary_amount, salary_unit, currency, job_type, positions, urgent,
            description, posted_at, status, status_updated_at, source)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        rows,
    )
    conn.commit()


def job_to_dict(row):
    country = COUNTRIES[row["country_code"]]
    cat = CATEGORIES[row["category"]]
    posted = datetime.fromisoformat(row["posted_at"])
    days_ago = (datetime.utcnow() - posted).days
    return {
        "id": row["id"], "ref_code": row["ref_code"], "category": row["category"],
        "category_label": cat["label"], "category_icon": cat["icon"], "title": row["title"],
        "country_code": row["country_code"], "country_name": country["name"], "country_flag": country["flag"],
        "city": row["city"], "client_name": row["client_name"], "contact_phone": row["contact_phone"],
        "lat": row["lat"], "lng": row["lng"],
        "salary_amount": row["salary_amount"], "salary_unit": row["salary_unit"], "currency": row["currency"],
        "job_type": row["job_type"], "positions": row["positions"], "urgent": bool(row["urgent"]),
        "description": row["description"], "days_ago": max(days_ago, 0), "status": row["status"],
    }


def application_to_dict(row, with_job=None):
    d = {
        "id": row["id"], "job_id": row["job_id"], "name": row["name"], "phone": row["phone"],
        "nationality": row["nationality"], "experience_years": row["experience_years"],
        "message": row["message"], "status": row["status"] or "submitted", "created_at": row["created_at"],
        "lat": row["lat"], "lng": row["lng"],
    }
    if with_job is not None:
        d["job"] = {"ref_code": with_job["ref_code"], "title": with_job["title"],
                     "city": with_job["city"], "country_name": COUNTRIES[with_job["country_code"]]["name"]}
    return d


def worker_to_dict(row):
    return {
        "id": row["id"], "name": row["name"], "phone": row["phone"], "nationality": row["nationality"],
        "category": row["category"], "category_label": CATEGORIES.get(row["category"], {}).get("label", row["category"]),
        "experience_years": row["experience_years"],
        "preferred_countries": row["preferred_countries"].split(",") if row["preferred_countries"] else [],
        "bio": row["bio"], "tier": row["tier"] or "standard", "created_at": row["created_at"],
    }


# ----------------------------------------------------------------------------
# Account helpers
# ----------------------------------------------------------------------------
def derive_password(phone):
    digits = re.sub(r"\D", "", phone or "")
    return digits[-5:] if len(digits) >= 5 else digits.rjust(5, "0")


def create_session(db, phone):
    token = secrets.token_hex(24)
    expires_at = (datetime.utcnow() + timedelta(days=SESSION_DAYS)).isoformat()
    db.execute("INSERT INTO verified_sessions (token, phone, expires_at, created_at) VALUES (?,?,?,?)",
               (token, phone, expires_at, datetime.utcnow().isoformat()))
    db.commit()
    return token, expires_at


def session_is_valid(db, phone, token):
    if not token:
        return False
    row = db.execute("SELECT * FROM verified_sessions WHERE token = ? AND phone = ?", (token, phone)).fetchone()
    if not row:
        return False
    return datetime.fromisoformat(row["expires_at"]) > datetime.utcnow()


def get_or_create_account(db, phone, email="", username=""):
    row = db.execute("SELECT * FROM accounts WHERE phone = ?", (phone,)).fetchone()
    password = derive_password(phone)
    if row:
        if email and not row["email"]:
            db.execute("UPDATE accounts SET email = ? WHERE id = ?", (email, row["id"]))
            db.commit()
        if username and not row["username"]:
            db.execute("UPDATE accounts SET username = ? WHERE id = ?", (username, row["id"]))
            db.commit()
        return password, False, (row["username"] or username or "")
    default_username = username or ("Member " + derive_password(phone))
    db.execute("INSERT INTO accounts (phone, email, username, password_hash, created_at) VALUES (?,?,?,?,?)",
               (phone, email, default_username, generate_password_hash(password), datetime.utcnow().isoformat()))
    db.commit()
    return password, True, default_username


def get_admin_password_hash(db):
    row = db.execute("SELECT * FROM admin_settings WHERE id = 1").fetchone()
    return row["password_hash"] if row else generate_password_hash(DEFAULT_ADMIN_PASSWORD)


def check_admin(data_or_args):
    db = get_db()
    return check_password_hash(get_admin_password_hash(db), str(data_or_args.get("password", "")))


# ----------------------------------------------------------------------------
# API: meta / stats
# ----------------------------------------------------------------------------
@app.route("/api/meta")
def api_meta():
    return jsonify({
        "countries": [{"code": code, **{k: v for k, v in data.items() if k != "cities"}}
                      for code, data in COUNTRIES.items()],
        "gulf_countries": [{"code": code, **{k: v for k, v in COUNTRIES[code].items() if k != "cities"}} for code in GULF_COUNTRY_CODES],
        "europe_countries": [{"code": code, **{k: v for k, v in COUNTRIES[code].items() if k != "cities"}} for code in EUROPE_COUNTRY_CODES],
        "categories": [{"key": key, "label": cat["label"], "icon": cat["icon"]}
                       for key, cat in CATEGORIES.items()],
        "expert_price": EXPERT_PRICE,
        "faq": FAQ,
        "security_questions": SECURITY_QUESTIONS,
        "job_statuses": JOB_STATUSES,
    })


@app.route("/api/stats")
def api_stats():
    db = get_db()
    cleanup_stale_gone_jobs(db)
    total_open = db.execute("SELECT COUNT(*) c FROM jobs WHERE status='open'").fetchone()["c"]
    total_all = db.execute("SELECT COUNT(*) c FROM jobs").fetchone()["c"]
    urgent = db.execute("SELECT COUNT(*) c FROM jobs WHERE status='open' AND urgent=1").fetchone()["c"]
    real_applications = db.execute("SELECT COUNT(*) c FROM applications").fetchone()["c"]
    return jsonify({"live_jobs": total_open, "total_jobs": total_all, "urgent_jobs": urgent,
                     "applications": real_applications + APPLICATIONS_DISPLAY_BASELINE,
                     "countries": len(COUNTRIES)})


# ----------------------------------------------------------------------------
# API: jobs
# ----------------------------------------------------------------------------
@app.route("/api/jobs")
def api_jobs_list():
    db = get_db()
    cleanup_stale_gone_jobs(db)
    country = request.args.get("country")
    category = request.args.get("category")
    urgent_only = request.args.get("urgent") == "1"
    open_only = request.args.get("open_only") == "1"
    status_filter = request.args.get("status")  # 'open' | 'in_process' | 'gone' | None (=all)
    q = request.args.get("q", "").strip().lower()
    sort = request.args.get("sort", "new")

    sql = "SELECT * FROM jobs WHERE 1=1"
    params = []
    if open_only:
        sql += " AND status = 'open'"
    if status_filter and status_filter in JOB_STATUSES:
        sql += " AND status = ?"
        params.append(status_filter)
    if country and country != "ALL":
        sql += " AND country_code = ?"
        params.append(country)
    if category and category != "ALL":
        sql += " AND category = ?"
        params.append(category)
    if urgent_only:
        sql += " AND urgent = 1"

    rows = db.execute(sql, params).fetchall()
    jobs = [job_to_dict(r) for r in rows]

    if q:
        jobs = [j for j in jobs if q in j["title"].lower() or q in j["category_label"].lower()
                or q in j["city"].lower() or q in j["client_name"].lower()]

    if sort == "salary_desc":
        jobs.sort(key=lambda j: j["salary_amount"], reverse=True)
    elif sort == "salary_asc":
        jobs.sort(key=lambda j: j["salary_amount"])
    else:
        jobs.sort(key=lambda j: j["days_ago"])

    return jsonify({"count": len(jobs), "jobs": jobs})


@app.route("/api/jobs/<int:job_id>")
def api_job_detail(job_id):
    db = get_db()
    row = db.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
    if not row:
        return jsonify({"error": "Job not found"}), 404
    return jsonify(job_to_dict(row))


@app.route("/api/jobs", methods=["POST"])
def api_job_create():
    data = request.get_json(silent=True) or {}
    required = ["title", "category", "country_code", "city", "client_name", "contact_phone", "salary_amount", "job_type"]
    missing = [f for f in required if not str(data.get(f, "")).strip()]
    if missing:
        return jsonify({"error": f"Missing fields: {', '.join(missing)}"}), 400
    if data["category"] not in CATEGORIES:
        return jsonify({"error": "Unknown category"}), 400
    if data["country_code"] not in COUNTRIES:
        return jsonify({"error": "Unknown country"}), 400

    db = get_db()
    country = COUNTRIES[data["country_code"]]
    count = db.execute("SELECT COUNT(*) c FROM jobs").fetchone()["c"]
    ref_code = f"AJ-{data['country_code']}-{2000 + count}"
    posted_at = datetime.utcnow().isoformat()
    phone = data["contact_phone"].strip()

    cur = db.execute(
        """INSERT INTO jobs
           (ref_code, category, title, country_code, city, client_name, contact_phone, contact_email, lat, lng,
            salary_amount, salary_unit, currency, job_type, positions, urgent,
            description, posted_at, status, status_updated_at, source)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (ref_code, data["category"], data["title"], data["country_code"], data["city"],
         data["client_name"], phone, data.get("contact_email", ""),
         data.get("lat"), data.get("lng"),
         int(data["salary_amount"]), data.get("salary_unit", "/ month"),
         country["currency"], data["job_type"], int(data.get("positions", 1)),
         1 if data.get("urgent") else 0, data.get("description", ""), posted_at, "open", posted_at, "employer"),
    )
    db.commit()

    password, is_new, username = get_or_create_account(db, phone, data.get("contact_email", ""), data.get("username", ""))
    token, expires_at = create_session(db, phone)

    new_row = db.execute("SELECT * FROM jobs WHERE id = ?", (cur.lastrowid,)).fetchone()
    result = job_to_dict(new_row)
    result["account"] = {"phone": phone, "password": password, "is_new": is_new, "token": token, "username": username}
    return jsonify(result), 201


@app.route("/api/jobs/<int:job_id>/status", methods=["POST"])
def api_job_status(job_id):
    data = request.get_json(silent=True) or {}
    new_status = data.get("status")
    if new_status not in JOB_STATUSES:
        return jsonify({"error": f"Status must be one of {JOB_STATUSES}"}), 400
    db = get_db()
    row = db.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
    if not row:
        return jsonify({"error": "Job not found"}), 404
    db.execute("UPDATE jobs SET status = ?, status_updated_at = ? WHERE id = ?",
               (new_status, datetime.utcnow().isoformat(), job_id))
    db.commit()
    return jsonify({"ok": True, "status": new_status})


def cleanup_stale_gone_jobs(db):
    """Jobs marked 'gone' for more than GONE_JOB_RETENTION_HOURS are removed
    from the board automatically \u2014 triggered on every job-list fetch, which
    happens naturally after every login/logout refresh."""
    cutoff = (datetime.utcnow() - timedelta(hours=GONE_JOB_RETENTION_HOURS)).isoformat()
    db.execute("DELETE FROM jobs WHERE status = 'gone' AND status_updated_at IS NOT NULL AND status_updated_at < ?", (cutoff,))
    db.commit()


# ----------------------------------------------------------------------------
# API: applications
# ----------------------------------------------------------------------------
@app.route("/api/jobs/<int:job_id>/apply", methods=["POST"])
def api_job_apply(job_id):
    db = get_db()
    job = db.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
    if not job:
        return jsonify({"error": "Job not found"}), 404

    data = request.get_json(silent=True) or {}
    if not str(data.get("name", "")).strip() or not str(data.get("phone", "")).strip():
        return jsonify({"error": "Name and phone are required"}), 400

    now = datetime.utcnow().isoformat()
    db.execute(
        """INSERT INTO applications (job_id, name, phone, nationality, experience_years, message, status, lat, lng, created_at, updated_at)
           VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
        (job_id, data["name"], data["phone"], data.get("nationality", ""),
         int(data.get("experience_years") or 0), data.get("message", ""), "submitted",
         data.get("lat"), data.get("lng"), now, now),
    )
    db.commit()

    password, is_new, username = get_or_create_account(db, data["phone"], "", data.get("name", ""))
    token, expires_at = create_session(db, data["phone"])

    return jsonify({"ok": True, "message": f"Application received for {job['title']} ({job['ref_code']}).",
                     "account": {"phone": data["phone"], "password": password, "is_new": is_new, "token": token, "username": username}}), 201


@app.route("/api/applications/<int:app_id>/status", methods=["POST"])
def api_application_status(app_id):
    data = request.get_json(silent=True) or {}
    new_status = data.get("status")
    if new_status not in APPLICATION_STATUSES:
        return jsonify({"error": f"Status must be one of {APPLICATION_STATUSES}"}), 400
    db = get_db()
    row = db.execute("SELECT * FROM applications WHERE id = ?", (app_id,)).fetchone()
    if not row:
        return jsonify({"error": "Application not found"}), 404
    db.execute("UPDATE applications SET status = ?, updated_at = ? WHERE id = ?",
               (new_status, datetime.utcnow().isoformat(), app_id))
    db.commit()
    return jsonify({"ok": True, "status": new_status})


# ----------------------------------------------------------------------------
# API: accounts (register / login / reset)
# ----------------------------------------------------------------------------
@app.route("/api/accounts/register", methods=["POST"])
def api_account_register():
    data = request.get_json(silent=True) or {}
    phone = str(data.get("phone", "")).strip()
    email = str(data.get("email", "")).strip()
    if not phone:
        return jsonify({"error": "Phone number required"}), 400
    db = get_db()
    existing = db.execute("SELECT * FROM accounts WHERE phone = ?", (phone,)).fetchone()
    if existing:
        return jsonify({"error": "That phone number already has an account \u2014 please log in instead."}), 409
    password, _, username = get_or_create_account(db, phone, email, data.get("username", ""))
    token, expires_at = create_session(db, phone)
    return jsonify({"ok": True, "password": password, "token": token, "expires_at": expires_at, "username": username}), 201


@app.route("/api/accounts/login", methods=["POST"])
def api_account_login():
    data = request.get_json(silent=True) or {}
    phone = str(data.get("phone", "")).strip()
    password = str(data.get("password", "")).strip()
    if not phone or not password:
        return jsonify({"error": "Phone and password are required"}), 400
    db = get_db()
    row = db.execute("SELECT * FROM accounts WHERE phone = ?", (phone,)).fetchone()
    if not row:
        return jsonify({"error": "No account found for that phone number yet \u2014 post a job or apply to one first."}), 404
    if not check_password_hash(row["password_hash"], password):
        return jsonify({"error": "Incorrect PIN/password."}), 401
    token, expires_at = create_session(db, phone)
    return jsonify({"ok": True, "token": token, "expires_at": expires_at, "username": row["username"] or ""})


@app.route("/api/accounts/reset", methods=["POST"])
def api_account_reset():
    data = request.get_json(silent=True) or {}
    phone = str(data.get("phone", "")).strip()
    email = str(data.get("email", "")).strip()
    previous_password = str(data.get("previous_password", "")).strip()
    db = get_db()
    row = db.execute("SELECT * FROM accounts WHERE phone = ?", (phone,)).fetchone()
    if not row:
        return jsonify({"error": "No account found for that phone number."}), 404
    if row["email"] and email and row["email"].lower() != email.lower():
        return jsonify({"error": "That email doesn't match what's on file for this phone number."}), 401
    if not check_password_hash(row["password_hash"], previous_password):
        return jsonify({"error": "That PIN/password doesn't match our records for this phone number."}), 401
    token, expires_at = create_session(db, phone)
    return jsonify({"ok": True, "token": token, "expires_at": expires_at, "username": row["username"] or ""})


@app.route("/api/accounts/reset-with-security", methods=["POST"])
def api_account_reset_with_security():
    """Real 'forgot PIN' recovery: verify a security question instead of the
    old PIN, then let the person set a brand-new one directly."""
    data = request.get_json(silent=True) or {}
    phone = str(data.get("phone", "")).strip()
    answer = str(data.get("answer", "")).strip().lower()
    new_pin = str(data.get("new_pin", "")).strip()
    db = get_db()
    row = db.execute("SELECT * FROM accounts WHERE phone = ?", (phone,)).fetchone()
    if not row or not row["security_answer_hash"]:
        return jsonify({"error": "No security question set up for this account."}), 404
    if not check_password_hash(row["security_answer_hash"], answer):
        return jsonify({"error": "That answer doesn't match."}), 401
    if len(new_pin) < 4:
        return jsonify({"error": "New PIN must be at least 4 characters."}), 400
    db.execute("UPDATE accounts SET password_hash = ? WHERE id = ?", (generate_password_hash(new_pin), row["id"]))
    db.commit()
    token, expires_at = create_session(db, phone)
    return jsonify({"ok": True, "token": token, "expires_at": expires_at, "username": row["username"] or ""})


@app.route("/api/accounts/username", methods=["POST"])
def api_account_set_username():
    data = request.get_json(silent=True) or {}
    phone = str(data.get("phone", "")).strip()
    token = str(data.get("token", "")).strip()
    username = str(data.get("username", "")).strip()
    db = get_db()
    if not session_is_valid(db, phone, token):
        return jsonify({"error": "Please log in first."}), 401
    if not username:
        return jsonify({"error": "Username required"}), 400
    db.execute("UPDATE accounts SET username = ? WHERE phone = ?", (username, phone))
    db.commit()
    return jsonify({"ok": True, "username": username})


@app.route("/api/accounts/security-question", methods=["POST"])
def api_account_set_security_question():
    data = request.get_json(silent=True) or {}
    phone = str(data.get("phone", "")).strip()
    token = str(data.get("token", "")).strip()
    question = str(data.get("question", "")).strip()
    answer = str(data.get("answer", "")).strip().lower()
    db = get_db()
    if not session_is_valid(db, phone, token):
        return jsonify({"error": "Please log in first."}), 401
    if question not in SECURITY_QUESTIONS or not answer:
        return jsonify({"error": "Choose one of the listed questions and provide an answer."}), 400
    db.execute("UPDATE accounts SET security_question = ?, security_answer_hash = ? WHERE phone = ?",
               (question, generate_password_hash(answer), phone))
    db.commit()
    return jsonify({"ok": True})


@app.route("/api/accounts/security-question")
def api_account_get_security_question():
    phone = request.args.get("phone", "").strip()
    db = get_db()
    row = db.execute("SELECT * FROM accounts WHERE phone = ?", (phone,)).fetchone()
    if not row or not row["security_question"]:
        return jsonify({"has_question": False})
    return jsonify({"has_question": True, "question": row["security_question"]})


@app.route("/api/accounts/change-password", methods=["POST"])
def api_account_change_password():
    data = request.get_json(silent=True) or {}
    phone = str(data.get("phone", "")).strip()
    token = str(data.get("token", "")).strip()
    current_password = str(data.get("current_password", "")).strip()
    new_password = str(data.get("new_password", "")).strip()
    db = get_db()
    if not session_is_valid(db, phone, token):
        return jsonify({"error": "Please log in first."}), 401
    if len(new_password) < 4:
        return jsonify({"error": "New password must be at least 4 characters."}), 400
    row = db.execute("SELECT * FROM accounts WHERE phone = ?", (phone,)).fetchone()
    if not row:
        return jsonify({"error": "No account found."}), 404
    if not check_password_hash(row["password_hash"], current_password):
        return jsonify({"error": "Current password is incorrect."}), 401
    db.execute("UPDATE accounts SET password_hash = ? WHERE id = ?", (generate_password_hash(new_password), row["id"]))
    db.commit()
    return jsonify({"ok": True, "message": "Password updated."})


@app.route("/api/session/check")
def api_session_check():
    phone = request.args.get("phone", "").strip()
    token = request.args.get("token", "").strip()
    db = get_db()
    return jsonify({"valid": session_is_valid(db, phone, token)})


# ----------------------------------------------------------------------------
# API: dashboards
# ----------------------------------------------------------------------------
@app.route("/api/dashboard/employer")
def api_employer_dashboard():
    phone = request.args.get("phone", "").strip()
    token = request.args.get("token", "").strip()
    if not phone:
        return jsonify({"error": "Phone number required"}), 400
    db = get_db()
    if not session_is_valid(db, phone, token):
        return jsonify({"error": "Please log in first.", "needs_login": True}), 401
    jobs_rows = db.execute("SELECT * FROM jobs WHERE contact_phone = ? ORDER BY posted_at DESC", (phone,)).fetchall()
    result = []
    for jr in jobs_rows:
        jd = job_to_dict(jr)
        apps = db.execute("SELECT * FROM applications WHERE job_id = ? ORDER BY created_at DESC", (jr["id"],)).fetchall()
        jd["applications"] = [application_to_dict(a) for a in apps]
        jd["application_count"] = len(jd["applications"])
        result.append(jd)
    return jsonify({"phone": phone, "jobs": result, "job_count": len(result)})


@app.route("/api/dashboard/worker")
def api_worker_dashboard():
    phone = request.args.get("phone", "").strip()
    token = request.args.get("token", "").strip()
    if not phone:
        return jsonify({"error": "Phone number required"}), 400
    db = get_db()
    if not session_is_valid(db, phone, token):
        return jsonify({"error": "Please log in first.", "needs_login": True}), 401
    profile_row = db.execute("SELECT * FROM workers WHERE phone = ? ORDER BY created_at DESC LIMIT 1", (phone,)).fetchone()
    profile = worker_to_dict(profile_row) if profile_row else None

    apps = db.execute("SELECT * FROM applications WHERE phone = ? ORDER BY created_at DESC", (phone,)).fetchall()
    apps_out = []
    for a in apps:
        job_row = db.execute("SELECT * FROM jobs WHERE id = ?", (a["job_id"],)).fetchone()
        apps_out.append(application_to_dict(a, with_job=job_row))

    cvs = db.execute("SELECT * FROM cv_requests WHERE worker_phone = ? ORDER BY created_at DESC", (phone,)).fetchall()
    cv_out = [{"id": c["id"], "status": c["status"], "created_at": c["created_at"], "target_country": c["target_country"]} for c in cvs]

    return jsonify({"phone": phone, "profile": profile, "applications": apps_out, "cv_requests": cv_out})


# ----------------------------------------------------------------------------
# API: workers + premium tier
# ----------------------------------------------------------------------------
@app.route("/api/workers", methods=["POST"])
def api_worker_register():
    data = request.get_json(silent=True) or {}
    required = ["name", "phone", "category"]
    missing = [f for f in required if not str(data.get(f, "")).strip()]
    if missing:
        return jsonify({"error": f"Missing fields: {', '.join(missing)}"}), 400

    db = get_db()
    prefs = data.get("preferred_countries", "")
    if isinstance(prefs, list):
        prefs = ",".join(prefs)
    phone = data["phone"].strip()
    db.execute(
        """INSERT INTO workers (name, phone, nationality, category, experience_years,
                                 preferred_countries, bio, tier, created_at)
           VALUES (?,?,?,?,?,?,?,?,?)""",
        (data["name"], phone, data.get("nationality", ""), data["category"],
         int(data.get("experience_years") or 0), prefs, data.get("bio", ""), "standard",
         datetime.utcnow().isoformat()),
    )
    db.commit()

    password, is_new, username = get_or_create_account(db, phone, data.get("email", ""), data.get("username", "") or data["name"])
    token, expires_at = create_session(db, phone)
    return jsonify({"ok": True, "message": "Worker profile registered.",
                     "account": {"phone": phone, "password": password, "is_new": is_new, "token": token, "username": username}}), 201


@app.route("/api/premium/interest", methods=["POST"])
def api_premium_interest():
    data = request.get_json(silent=True) or {}
    phone = str(data.get("phone", "")).strip()
    name = str(data.get("name", "")).strip()
    if not phone or not name:
        return jsonify({"error": "Name and phone are required"}), 400

    db = get_db()
    worker = db.execute("SELECT * FROM workers WHERE phone = ? ORDER BY created_at DESC LIMIT 1", (phone,)).fetchone()
    if not worker:
        return jsonify({"error": "No worker profile found for that phone number. Register a profile first."}), 404

    db.execute(
        """INSERT INTO premium_leads (phone, name, preferred_payment_method, note, status, created_at)
           VALUES (?,?,?,?,?,?)""",
        (phone, name, data.get("preferred_payment_method", ""), data.get("note", ""),
         "pending", datetime.utcnow().isoformat()),
    )
    db.commit()
    return jsonify({"ok": True, "message": "Got it \u2014 our team will reach out on this number to arrange payment and activate Expert."}), 201


@app.route("/api/cv-requests", methods=["POST"])
def api_cv_request():
    data = request.get_json(silent=True) or {}
    phone = str(data.get("worker_phone", "")).strip()
    if not phone:
        return jsonify({"error": "Phone number required"}), 400

    db = get_db()
    worker = db.execute("SELECT * FROM workers WHERE phone = ? ORDER BY created_at DESC LIMIT 1", (phone,)).fetchone()
    if not worker or (worker["tier"] or "standard") != "expert":
        return jsonify({"error": "CV drafting is an Ajeer Expert benefit. Upgrade your profile first."}), 403

    db.execute(
        """INSERT INTO cv_requests (worker_phone, name, current_role, experience_summary, target_country, status, created_at)
           VALUES (?,?,?,?,?,?,?)""",
        (phone, data.get("name", ""), data.get("current_role", ""), data.get("experience_summary", ""),
         data.get("target_country", ""), "received", datetime.utcnow().isoformat()),
    )
    db.commit()
    return jsonify({"ok": True, "message": "CV request received. Our team will send a draft within 48 hours."}), 201


# ----------------------------------------------------------------------------
# API: geocoding proxy
# ----------------------------------------------------------------------------
@app.route("/api/geocode")
def api_geocode():
    query = request.args.get("q", "").strip()
    if not query:
        return jsonify({"error": "Query required"}), 400
    try:
        import json
        import urllib.parse
        import urllib.request
        url = "https://nominatim.openstreetmap.org/search?" + urllib.parse.urlencode({
            "q": query, "format": "json", "limit": 1,
        })
        req = urllib.request.Request(url, headers={"User-Agent": "AjeerPrototype/1.0"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            results = json.loads(resp.read().decode())
        if not results:
            return jsonify({"found": False})
        return jsonify({"found": True, "lat": float(results[0]["lat"]), "lng": float(results[0]["lon"])})
    except Exception:
        return jsonify({"found": False, "error": "Geocoding service unavailable \u2014 place the pin manually."})


# ----------------------------------------------------------------------------
# API: support + two-way chat
# ----------------------------------------------------------------------------
@app.route("/api/support", methods=["POST"])
def api_support():
    data = request.get_json(silent=True) or {}
    if not str(data.get("message", "")).strip():
        return jsonify({"error": "Message is required"}), 400
    db = get_db()
    db.execute(
        "INSERT INTO support_tickets (name, contact, message, status, created_at) VALUES (?,?,?,?,?)",
        (data.get("name", ""), data.get("contact", ""), data["message"], "open", datetime.utcnow().isoformat()),
    )
    db.commit()
    return jsonify({"ok": True, "message": "Got it \u2014 our team will follow up shortly."}), 201


@app.route("/api/chat/send", methods=["POST"])
def api_chat_send():
    data = request.get_json(silent=True) or {}
    phone = str(data.get("phone", "")).strip()
    message = str(data.get("message", "")).strip()
    if not phone or not message:
        return jsonify({"error": "Phone and message are required"}), 400
    db = get_db()
    db.execute("INSERT INTO chat_messages (phone, sender, message, created_at) VALUES (?,?,?,?)",
               (phone, "user", message, datetime.utcnow().isoformat()))
    db.commit()
    return jsonify({"ok": True}), 201


@app.route("/api/chat/thread")
def api_chat_thread():
    phone = request.args.get("phone", "").strip()
    if not phone:
        return jsonify({"error": "Phone number required"}), 400
    db = get_db()
    rows = db.execute("SELECT * FROM chat_messages WHERE phone = ? ORDER BY created_at ASC", (phone,)).fetchall()
    return jsonify({"messages": [{"id": r["id"], "sender": r["sender"], "message": r["message"], "created_at": r["created_at"]} for r in rows]})


# ----------------------------------------------------------------------------
# API: admin
# ----------------------------------------------------------------------------
@app.route("/api/admin/login", methods=["POST"])
def api_admin_login():
    data = request.get_json(silent=True) or {}
    if not check_admin(data):
        return jsonify({"error": "Invalid admin password"}), 401
    return jsonify({"ok": True})


@app.route("/api/admin/change-password", methods=["POST"])
def api_admin_change_password():
    data = request.get_json(silent=True) or {}
    if not check_admin({"password": data.get("current_password", "")}):
        return jsonify({"error": "Current password is incorrect"}), 401
    new_password = str(data.get("new_password", "")).strip()
    if len(new_password) < 4:
        return jsonify({"error": "New password must be at least 4 characters"}), 400
    db = get_db()
    db.execute("UPDATE admin_settings SET password_hash = ? WHERE id = 1", (generate_password_hash(new_password),))
    db.commit()
    return jsonify({"ok": True, "message": "Admin password updated."})


@app.route("/api/admin/analytics")
def api_admin_analytics():
    if not check_admin(request.args):
        return jsonify({"error": "Invalid admin password"}), 401
    db = get_db()

    totals = {
        "jobs_total": db.execute("SELECT COUNT(*) c FROM jobs").fetchone()["c"],
        "jobs_open": db.execute("SELECT COUNT(*) c FROM jobs WHERE status='open'").fetchone()["c"],
        "jobs_in_process": db.execute("SELECT COUNT(*) c FROM jobs WHERE status='in_process'").fetchone()["c"],
        "jobs_gone": db.execute("SELECT COUNT(*) c FROM jobs WHERE status='gone'").fetchone()["c"],
        "applications_total": db.execute("SELECT COUNT(*) c FROM applications").fetchone()["c"],
        "accounts_total": db.execute("SELECT COUNT(*) c FROM accounts").fetchone()["c"],
        "workers_total": db.execute("SELECT COUNT(*) c FROM workers").fetchone()["c"],
    }

    by_category = db.execute(
        """SELECT j.category as category, COUNT(a.id) as n
           FROM applications a JOIN jobs j ON a.job_id = j.id
           GROUP BY j.category ORDER BY n DESC"""
    ).fetchall()
    by_category_out = [{"category": r["category"], "label": CATEGORIES.get(r["category"], {}).get("label", r["category"]), "count": r["n"]} for r in by_category]

    by_country = db.execute(
        """SELECT j.country_code as country_code, COUNT(a.id) as n
           FROM applications a JOIN jobs j ON a.job_id = j.id
           GROUP BY j.country_code ORDER BY n DESC"""
    ).fetchall()
    by_country_out = [{"country_code": r["country_code"], "name": COUNTRIES.get(r["country_code"], {}).get("name", r["country_code"]), "count": r["n"]} for r in by_country]

    top_jobs = db.execute(
        """SELECT j.id as id, j.ref_code as ref_code, j.title as title, j.city as city, j.country_code as country_code,
                  COUNT(a.id) as n
           FROM applications a JOIN jobs j ON a.job_id = j.id
           GROUP BY j.id ORDER BY n DESC LIMIT 10"""
    ).fetchall()
    top_jobs_out = [{"ref_code": r["ref_code"], "title": r["title"], "city": r["city"],
                      "country": COUNTRIES.get(r["country_code"], {}).get("name", r["country_code"]), "count": r["n"]} for r in top_jobs]

    return jsonify({"totals": totals, "by_category": by_category_out, "by_country": by_country_out, "top_jobs": top_jobs_out})


@app.route("/api/admin/accounts")
def api_admin_accounts_search():
    if not check_admin(request.args):
        return jsonify({"error": "Invalid admin password"}), 401
    phone = request.args.get("phone", "").strip()
    db = get_db()
    if phone:
        rows = db.execute("SELECT * FROM accounts WHERE phone LIKE ?", (f"%{phone}%",)).fetchall()
    else:
        rows = db.execute("SELECT * FROM accounts ORDER BY created_at DESC LIMIT 50").fetchall()
    return jsonify({"accounts": [{"id": r["id"], "phone": r["phone"], "email": r["email"], "created_at": r["created_at"]} for r in rows]})


@app.route("/api/admin/accounts/<path:phone>", methods=["DELETE"])
def api_admin_delete_account(phone):
    data = request.get_json(silent=True) or {}
    if not check_admin(data):
        return jsonify({"error": "Invalid admin password"}), 401
    db = get_db()
    row = db.execute("SELECT * FROM accounts WHERE phone = ?", (phone,)).fetchone()
    if not row:
        return jsonify({"error": "No account found for that phone number."}), 404
    db.execute("DELETE FROM accounts WHERE phone = ?", (phone,))
    db.execute("DELETE FROM verified_sessions WHERE phone = ?", (phone,))
    db.commit()
    return jsonify({"ok": True, "message": f"Account for {phone} deleted. Their job/application records remain for your history but they can no longer log in with this number until they re-register."})


@app.route("/api/admin/premium-leads")
def api_admin_leads():
    if not check_admin(request.args):
        return jsonify({"error": "Invalid admin password"}), 401
    db = get_db()
    rows = db.execute("SELECT * FROM premium_leads ORDER BY created_at DESC").fetchall()
    leads = [{"id": r["id"], "phone": r["phone"], "name": r["name"],
              "preferred_payment_method": r["preferred_payment_method"], "note": r["note"],
              "status": r["status"], "created_at": r["created_at"]} for r in rows]
    return jsonify({"leads": leads})


@app.route("/api/admin/premium-leads/<int:lead_id>/approve", methods=["POST"])
def api_admin_approve_lead(lead_id):
    data = request.get_json(silent=True) or {}
    if not check_admin(data):
        return jsonify({"error": "Invalid admin password"}), 401
    db = get_db()
    lead = db.execute("SELECT * FROM premium_leads WHERE id = ?", (lead_id,)).fetchone()
    if not lead:
        return jsonify({"error": "Lead not found"}), 404
    worker = db.execute("SELECT * FROM workers WHERE phone = ? ORDER BY created_at DESC LIMIT 1", (lead["phone"],)).fetchone()
    if worker:
        db.execute("UPDATE workers SET tier = 'expert' WHERE id = ?", (worker["id"],))
    db.execute("UPDATE premium_leads SET status = 'approved' WHERE id = ?", (lead_id,))
    db.commit()
    return jsonify({"ok": True, "message": "Approved and upgraded to Expert."})


@app.route("/api/admin/premium-leads/<int:lead_id>/decline", methods=["POST"])
def api_admin_decline_lead(lead_id):
    data = request.get_json(silent=True) or {}
    if not check_admin(data):
        return jsonify({"error": "Invalid admin password"}), 401
    db = get_db()
    db.execute("UPDATE premium_leads SET status = 'declined' WHERE id = ?", (lead_id,))
    db.commit()
    return jsonify({"ok": True})


@app.route("/api/admin/support-tickets")
def api_admin_tickets():
    if not check_admin(request.args):
        return jsonify({"error": "Invalid admin password"}), 401
    db = get_db()
    rows = db.execute("SELECT * FROM support_tickets ORDER BY created_at DESC").fetchall()
    tickets = [{"id": r["id"], "name": r["name"], "contact": r["contact"], "message": r["message"],
                "status": r["status"], "created_at": r["created_at"]} for r in rows]
    return jsonify({"tickets": tickets})


@app.route("/api/admin/support-tickets/<int:ticket_id>/resolve", methods=["POST"])
def api_admin_resolve_ticket(ticket_id):
    data = request.get_json(silent=True) or {}
    if not check_admin(data):
        return jsonify({"error": "Invalid admin password"}), 401
    db = get_db()
    db.execute("UPDATE support_tickets SET status = 'resolved' WHERE id = ?", (ticket_id,))
    db.commit()
    return jsonify({"ok": True})


@app.route("/api/admin/chats")
def api_admin_chats():
    if not check_admin(request.args):
        return jsonify({"error": "Invalid admin password"}), 401
    db = get_db()
    rows = db.execute(
        """SELECT phone, MAX(created_at) as last_at,
                  (SELECT message FROM chat_messages m2 WHERE m2.phone = m1.phone ORDER BY created_at DESC LIMIT 1) as last_message
           FROM chat_messages m1 GROUP BY phone ORDER BY last_at DESC"""
    ).fetchall()
    return jsonify({"conversations": [{"phone": r["phone"], "last_at": r["last_at"], "last_message": r["last_message"]} for r in rows]})


@app.route("/api/admin/chats/<path:phone>/reply", methods=["POST"])
def api_admin_chat_reply(phone):
    data = request.get_json(silent=True) or {}
    if not check_admin(data):
        return jsonify({"error": "Invalid admin password"}), 401
    message = str(data.get("message", "")).strip()
    if not message:
        return jsonify({"error": "Message required"}), 400
    db = get_db()
    db.execute("INSERT INTO chat_messages (phone, sender, message, created_at) VALUES (?,?,?,?)",
               (phone, "admin", message, datetime.utcnow().isoformat()))
    db.commit()
    return jsonify({"ok": True}), 201


# ----------------------------------------------------------------------------
# Frontend
# ----------------------------------------------------------------------------
@app.route("/")
@app.route("/<path:_ignored>")
def serve_index(_ignored=None):
    return send_from_directory(BASE_DIR, "index.html")


if __name__ == "__main__":
    init_db(reseed=os.environ.get("RESEED") == "1")
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
else:
    init_db(reseed=False)
