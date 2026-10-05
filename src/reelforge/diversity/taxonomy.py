"""Taxonomy of diversity axes for ReelForge.
Defines all dimensions, weighted options, locales, verticals, scenarios, hooks, and visual/audio styles.
"""
from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class VerticalInfo:
    id: str
    name: str
    category: str
    typical_services: List[str]
    booking_unit: str  # slot, consultation, session, table
    default_duration_mins: int
    is_sensitive_administrative_only: bool = False


@dataclass
class LocaleInfo:
    city: str
    country: str
    currency_symbol: str
    currency_code: str
    phone_pattern: str  # Always clearly fictional
    time_format: str  # "12h" or "24h"
    typical_hours: str
    speech_style: str  # natural regional phrasing hint, respectful and realistic


@dataclass
class HookTemplate:
    id: str
    family: str
    template_pattern: str
    description: str


# 22 rich verticals
VERTICALS: List[VerticalInfo] = [
    VerticalInfo("hair_salon", "Hair Salon", "beauty", ["Balayage & Color", "Keratin Treatment", "Blowout & Style", "Root Touchup", "Haircut & Wash"], "slot", 45),
    VerticalInfo("barbershop", "Barbershop", "beauty", ["Classic Beard Trim", "Hot Towel Shave", "Fade & Style", "Skin Fade", "Haircut"], "slot", 30),
    VerticalInfo("nail_beauty_studio", "Nail & Beauty Studio", "beauty", ["Gel Manicure", "Acrylic Extensions", "Pedicure Deluxe", "Lash Lift", "Nail Art"], "slot", 45),
    VerticalInfo("dental_clinic", "Dental Clinic Front Desk", "health_admin", ["Routine Checkup & Cleaning", "Teeth Whitening Consultation", "Crown Assessment", "X-Ray Appointment"], "slot", 30, True),
    VerticalInfo("physiotherapy_clinic", "Physiotherapy Clinic", "health_admin", ["Initial Assessment", "Sports Injury Session", "Post-Op Rehab", "Ergonomic Evaluation"], "session", 45, True),
    VerticalInfo("veterinary_clinic", "Veterinary Clinic", "pets", ["Annual Vaccination", "Wellness Exam", "Microchipping", "Routine Health Check"], "slot", 30, True),
    VerticalInfo("restaurant_cafe", "Restaurant & Cafe", "hospitality", ["Dinner Table Reservation", "Private Dining Inquiry", "Weekend Brunch Booking", "Birthday Party Table"], "table", 90),
    VerticalInfo("bakery_orders", "Bakery & Patisserie", "food", ["Custom Tiered Birthday Cake", "Pastry Box Pre-order", "Sourdough Catering Batch", "Gluten-Free Cupcake Box"], "consultation", 20),
    VerticalInfo("home_plumbing", "Plumbing & Leak Repair", "home_services", ["Emergency Pipe Leak Inspection", "Water Heater Repair", "Drain Unclogging", "Fixture Replacement"], "slot", 60),
    VerticalInfo("home_electrical", "Electrical Services", "home_services", ["Circuit Breaker Tripping Diagnostic", "EV Charger Installation Quote", "Lighting Fixture Wiring", "Safety Inspection"], "slot", 60),
    VerticalInfo("home_ac_repair", "HVAC & AC Repair", "home_services", ["Seasonal AC Servicing", "Compressor Diagnostics", "Gas Refill & Filter Clean", "Duct Inspection"], "slot", 60),
    VerticalInfo("cleaning_service", "Cleaning Services", "home_services", ["Deep Home Cleaning", "Move-In Move-Out Cleaning", "Sofa & Carpet Shampooing", "Office Cleaning"], "slot", 120),
    VerticalInfo("auto_repair", "Auto Repair & Garage", "automotive", ["Brake Pad Replacement", "Diagnostic Engine Scan", "Periodic Maintenance Service", "Suspension Check"], "slot", 60),
    VerticalInfo("real_estate_agency", "Real Estate Agency", "professional_admin", ["Property Viewing Appointment", "Rental Listing Intake", "Home Valuation Consultation", "Buyer Consultation"], "slot", 30, True),
    VerticalInfo("accounting_front_desk", "Accounting & Tax Front Desk", "professional_admin", ["Tax Filing Intake Appointment", "Bookkeeping Consultation", "Quarterly Audit Review", "Payroll Onboarding"], "consultation", 45, True),
    VerticalInfo("legal_front_desk", "Law Office Front Desk", "professional_admin", ["New Client Intake Consultation", "Contract Review Slot", "Notary Scheduling", "Case File Follow-up"], "consultation", 30, True),
    VerticalInfo("yoga_fitness_studio", "Yoga & Fitness Studio", "fitness", ["Trial Pilates Reformer Class", "Private Personal Training", "Intro Vinyasa Flow", "Group Strength Session"], "slot", 60),
    VerticalInfo("driving_school", "Driving School", "education", ["Beginner Driving Lesson", "Refresher Road Test Session", "Parallel Parking Coaching", "Highway Practice"], "lesson", 60),
    VerticalInfo("coaching_center", "Tutoring & Coaching Center", "education", ["SAT/ACT Diagnostic Assessment", "Math Coaching Session", "Science Intake Consultation", "Trial Coding Class"], "consultation", 45),
    VerticalInfo("photography_studio", "Photography Studio", "creative", ["Family Portrait Session", "Corporate Headshots", "Maternity Shoot", "Product Catalog Session"], "session", 60),
    VerticalInfo("pet_grooming", "Pet Grooming & Spa", "pets", ["Full Dog Bath & Haircut", "Cat Deshedding Spa", "Nail Clipping & Ear Cleaning", "Puppy First Groom"], "slot", 60),
    VerticalInfo("florist_boutique", "Florist Boutique", "retail", ["Custom Wedding Floral Consultation", "Weekly Office Arrangement", "Anniversary Bouquet Delivery", "Sympathy Wreath"], "consultation", 30),
]

# 14 Locales
LOCALES: List[LocaleInfo] = [
    LocaleInfo("Pune", "India", "₹", "INR", "+91 91234 XXXXX", "12h", "10:00 AM - 8:00 PM", "Polite and prompt Indian English, courteous register"),
    LocaleInfo("Jaipur", "India", "₹", "INR", "+91 98290 XXXXX", "12h", "10:00 AM - 7:30 PM", "Warm, hospitable and respectful tone"),
    LocaleInfo("Kochi", "India", "₹", "INR", "+91 94470 XXXXX", "12h", "9:30 AM - 7:00 PM", "Gentle, crisp and articulate professional phrasing"),
    LocaleInfo("Lucknow", "India", "₹", "INR", "+91 94150 XXXXX", "12h", "10:30 AM - 8:30 PM", "Gracious, attentive and polite demeanor"),
    LocaleInfo("Bengaluru", "India", "₹", "INR", "+91 98450 XXXXX", "12h", "9:00 AM - 8:00 PM", "Fast-paced, modern, clear tech-savvy register"),
    LocaleInfo("Indore", "India", "₹", "INR", "+91 97550 XXXXX", "12h", "10:00 AM - 8:00 PM", "Welcoming, humble and direct commercial phrasing"),
    LocaleInfo("Delhi NCR", "India", "₹", "INR", "+91 98110 XXXXX", "12h", "10:00 AM - 8:30 PM", "Energetic, clear and confident professional speech"),
    LocaleInfo("Mumbai", "India", "₹", "INR", "+91 98200 XXXXX", "12h", "9:30 AM - 9:00 PM", "Brisk, efficient, solutions-oriented cadence"),
    LocaleInfo("Hyderabad", "India", "₹", "INR", "+91 98490 XXXXX", "12h", "10:00 AM - 8:00 PM", "Warm, respectful, articulate and patient"),
    LocaleInfo("Chandigarh", "India", "₹", "INR", "+91 98140 XXXXX", "12h", "10:00 AM - 7:30 PM", "Upbeat, hearty and polite conversational style"),
    LocaleInfo("Singapore", "Singapore", "S$", "SGD", "+65 6123 XXXX", "24h", "09:00 - 18:30", "Concise, organized, Singapore-international English"),
    LocaleInfo("Dubai", "UAE", "AED", "AED", "+971 4 234 XXXX", "12h", "9:00 AM - 9:00 PM", "Polite, international executive hospitality phrasing"),
    LocaleInfo("London", "UK", "£", "GBP", "+44 20 7946 XXXX", "12h", "08:30 AM - 06:00 PM", "Courteous, understated, British service English"),
    LocaleInfo("Austin", "USA", "$", "USD", "+1 512 555 XXXX", "12h", "8:00 AM - 6:00 PM", "Friendly, warm, conversational American English"),
]

# Business Personas
BUSINESS_PERSONAS = [
    {"type": "solo_owner", "name": "Solo Artisan / Craftsman", "vibe": "hands-on, personal, passionate"},
    {"type": "family_run", "name": "Family-Run Tradition", "vibe": "trusted for generations, warm, community-first"},
    {"type": "small_team", "name": "Boutique Team of 3-8", "vibe": "specialized, collaborative, attentive"},
    {"type": "multi_branch", "name": "Growing Local Brand", "vibe": "organized, modern, high standards"},
]

# Caller Personas
CALLER_PERSONAS = [
    {"mood": "rushed", "age_band": "25-35", "relationship": "new", "desc": "in a rush between meetings, needs slot quick"},
    {"mood": "curious", "age_band": "30-45", "relationship": "referred", "desc": "referred by a friend, asks about pricing/process"},
    {"mood": "anxious", "age_band": "40-60", "relationship": "new", "desc": "worried about urgent issue, needs reassurance"},
    {"mood": "cheerful", "age_band": "20-30", "relationship": "returning", "desc": "loves the business, wants regular repeat service"},
    {"mood": "impatient", "age_band": "35-50", "relationship": "new", "desc": "values speed and clarity, no time for fluff"},
    {"mood": "confused", "age_band": "50-70", "relationship": "new", "desc": "needs gentle step-by-step guidance on booking"},
]

# Scenarios
SCENARIO_TYPES = [
    {"id": "new_booking", "name": "New Service Booking", "outcome": "booked"},
    {"id": "reschedule", "name": "Reschedule Existing Booking", "outcome": "rescheduled"},
    {"id": "cancellation_waitlist", "name": "Cancellation with Waitlist Replacement", "outcome": "waitlist_filled"},
    {"id": "price_inquiry", "name": "Price & Scope Inquiry", "outcome": "lead_captured"},
    {"id": "after_hours_urgent", "name": "After-Hours Urgent Service Request", "outcome": "booked"},
    {"id": "availability_check", "name": "Real-Time Slot Availability Check", "outcome": "booked"},
    {"id": "faq_resolution", "name": "Business FAQ (Parking/Policy/Prep)", "outcome": "faq_resolved"},
    {"id": "group_booking", "name": "Group / Large Party Booking", "outcome": "booked"},
    {"id": "lead_capture_callback", "name": "Custom Quote Lead Capture & Callback", "outcome": "lead_captured"},
    {"id": "upset_customer_escalated", "name": "Upset Caller Contextually Escalated", "outcome": "escalated_to_human"},
    {"id": "busy_owner_interruption", "name": "Owner Busy Handling In-Person Client", "outcome": "booked"},
    {"id": "repeat_client_preferences", "name": "Repeat Client with Specific Preferences", "outcome": "booked"},
    {"id": "multi_intent_call", "name": "Multi-Intent Inquiry (Price + Booking)", "outcome": "booked"},
]

# Hook Styles (Template Families)
HOOK_TEMPLATES: List[HookTemplate] = [
    HookTemplate("pov_hands_full", "POV Hands Full", "POV: You're busy with a client when the phone rings", "Visual hook showing busy owner context"),
    HookTemplate("after_hours_3am", "After Hours Urgency", "It's 10 PM. Watch who answered their client's call.", "Night-time / after hours availability hook"),
    HookTemplate("question_hook", "Direct Question", "What happens when a new customer calls your business right now?", "Engaging founder-direct question"),
    HookTemplate("watch_this_call", "Watch This Call", "Listen to how this AI receptionist handles a tough booking", "Live demonstration curiosity hook"),
    HookTemplate("contrast_missed", "Contrast Hook", "A missed call is a missed client. Here's the fix.", "Value-driven contrast between voicemail and AI"),
    HookTemplate("what_owner_sees", "Owner Notification", "This is the text the owner received 5 seconds later.", "Messenger summary / instant notification curiosity"),
    HookTemplate("rapid_cold_open", "Cold Open", "Hi, do you have any appointments left for this afternoon?", "In medias res starting immediately with caller dialogue"),
    HookTemplate("myth_bust", "Myth Buster", "Think an AI receptionist sounds robotic? Listen to this.", "Expectation-inverting demo hook"),
]

# Visual Layouts
LAYOUTS = ["ReelA-Split", "ReelB-Phone", "ReelC-Chat"]

# Palette IDs (matching render/src/themes/palettes.ts)
PALETTE_IDS = [
    "midnight_indigo",
    "emerald_luxury",
    "sunset_crimson",
    "cyber_slate",
    "royal_amethyst",
    "warm_amber",
    "oceanic_teal",
    "monochrome_stealth",
    "copper_bronze",
    "nordic_frost",
    "deep_plum",
    "forest_sage",
]

# OFL Font Pairings (matching render/src/themes/fonts.ts)
FONT_PAIRING_IDS = [
    "modern_clean",
    "tech_grotesk",
    "corporate_sleek",
    "editorial_chic",
    "friendly_rounded",
    "bold_impact",
]

# Caption Styles
CAPTION_STYLES = ["word-highlight", "karaoke", "boxed"]

# Motion Profiles
MOTION_PROFILE_IDS = ["snappy_modern", "smooth_gentle", "energetic_bounce"]

# Kokoro Voice Pools (54 voices available)
# US Female: af_heart, af_bella, af_sarah, af_nicole, af_sky, af_nova, af_jessica, af_river
# US Male: am_adam, am_michael, am_fenrir, am_puck, am_liam, am_onyx, am_eric
# British: bf_emma, bf_isabella, bf_alice, bm_george, bm_lewis, bm_daniel
# Indian English: hf_alpha, hf_beta, hm_omega, hm_psi
VOICE_PAIRS = [
    # US English Pairs
    {"agent": "af_heart", "caller": "am_adam", "agent_gender": "female", "caller_gender": "male", "accent": "us"},
    {"agent": "af_bella", "caller": "am_michael", "agent_gender": "female", "caller_gender": "male", "accent": "us"},
    {"agent": "am_adam", "caller": "af_sarah", "agent_gender": "male", "caller_gender": "female", "accent": "us"},
    {"agent": "af_nicole", "caller": "am_liam", "agent_gender": "female", "caller_gender": "male", "accent": "us"},
    {"agent": "am_michael", "caller": "af_jessica", "agent_gender": "male", "caller_gender": "female", "accent": "us"},
    {"agent": "af_nova", "caller": "am_onyx", "agent_gender": "female", "caller_gender": "male", "accent": "us"},
    {"agent": "am_fenrir", "caller": "af_sky", "agent_gender": "male", "caller_gender": "female", "accent": "us"},
    {"agent": "af_river", "caller": "am_eric", "agent_gender": "female", "caller_gender": "male", "accent": "us"},
    {"agent": "am_puck", "caller": "af_bella", "agent_gender": "male", "caller_gender": "female", "accent": "us"},
    
    # British English Pairs
    {"agent": "bf_emma", "caller": "bm_george", "agent_gender": "female", "caller_gender": "male", "accent": "british"},
    {"agent": "bm_lewis", "caller": "bf_isabella", "agent_gender": "male", "caller_gender": "female", "accent": "british"},
    {"agent": "bf_alice", "caller": "bm_daniel", "agent_gender": "female", "caller_gender": "male", "accent": "british"},
    
    # Indian / Global English Pairs
    {"agent": "hf_alpha", "caller": "hm_omega", "agent_gender": "female", "caller_gender": "male", "accent": "indian"},
    {"agent": "hm_psi", "caller": "hf_beta", "agent_gender": "male", "caller_gender": "female", "accent": "indian"},
    {"agent": "af_heart", "caller": "bm_george", "agent_gender": "female", "caller_gender": "male", "accent": "cross_accent"},
    {"agent": "bf_emma", "caller": "am_adam", "agent_gender": "female", "caller_gender": "male", "accent": "cross_accent"},
]

MUSIC_TRACKS = [
    "ambient_corporate_minimal.mp3",
    "upbeat_clean_acoustic.mp3",
    "modern_lofi_warm.mp3",
    "calm_reception_piano.mp3",
]
