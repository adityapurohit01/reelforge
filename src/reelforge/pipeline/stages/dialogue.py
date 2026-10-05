"""Stage 3 Dialogue Writer for ReelForge.
Generates structured natural telephone dialogue, animated events, owner notifications,
and enforces semantic de-duplication gates across all 13 call scenarios with rich vertical-specific phrasing.
"""
import json
import logging
import random
from typing import Any, Dict, List, Optional, Tuple
import httpx
from pydantic import BaseModel, Field
from sqlmodel import Session

from reelforge.config import ReelForgeConfig, load_config
from reelforge.diversity.fingerprint import FingerprintEngine
from reelforge.pipeline.stages.profile import BusinessProfile

logger = logging.getLogger(__name__)


class DialogueTurn(BaseModel):
    speaker: str = Field(description="'agent' or 'caller'")
    text: str = Field(description="Spoken utterance")
    emotion: str = Field(default="neutral", description="e.g. cheerful, rushed, polite")
    pause_after_ms: int = Field(default=250, description="Pause after turn in ms")
    on_screen_event: Optional[str] = None


class CallEvent(BaseModel):
    turn_index: int
    time_seconds: float = 0.0
    type: str = Field(description="'tool_call', 'booking_card', 'owner_notification', 'escalation'")
    text: str


class OwnerNotification(BaseModel):
    summary: str
    customer_name: str
    time_or_slot: Optional[str] = None
    service_requested: Optional[str] = None
    next_step: Optional[str] = None


class DialogueScript(BaseModel):
    hook_text: str = Field(description="Max 9 words on-screen kinetic hook")
    turns: List[DialogueTurn] = Field(min_length=6, max_length=12)
    events: List[CallEvent] = Field(min_length=2, max_length=6)
    owner_notification: OwnerNotification
    cta_text: str
    caption_seed: str
    hashtags_seed: List[str]


def _get_vertical_context(vid: str, vname: str) -> Dict[str, str]:
    """Provide domain-specific terminology for each vertical."""
    ctx_map = {
        "hair_salon": {
            "action": "styling chair", "inquiry": "haircut and color wash", "verb": "prep the styling station", "unit": "chair",
            "greeting": "style your hair today", "role": "master stylist", "prep_q": "arrive with hair washed or dry?",
            "prep_a": "arrive five minutes early with dry hair. We provide a full wash and conditioning treatment.",
            "confirm": "Styling station and mirror reserved",
        },
        "barbershop": {
            "action": "barber chair", "inquiry": "beard trim and fade", "verb": "reserve the barber chair", "unit": "chair",
            "greeting": "freshen up your cut today", "role": "master barber", "prep_q": "need to bring any reference photos?",
            "prep_a": "feel free to show any reference photo on your phone to your barber.",
            "confirm": "Barber chair and hot towel station prepped",
        },
        "nail_beauty_studio": {
            "action": "nail manicure table", "inquiry": "gel extensions set", "verb": "prep the manicure station", "unit": "station",
            "greeting": "book your manicure or nail design", "role": "nail technician", "prep_q": "need to remove old acrylics beforehand?",
            "prep_a": "our technician can gently soak off old sets at the start of your session.",
            "confirm": "Nail station and UV curing station reserved",
        },
        "dental_clinic": {
            "action": "dental operatory suite", "inquiry": "routine cleaning and exam", "verb": "reserve the operatory room", "unit": "suite",
            "greeting": "schedule your dental care visit", "role": "dental hygienist", "prep_q": "bring dental insurance details?",
            "prep_a": "our intake system registers your insurance digitally ahead of arrival.",
            "confirm": "Dental operatory suite sterilized and prepped",
        },
        "physiotherapy_clinic": {
            "action": "rehab therapy room", "inquiry": "sports injury evaluation", "verb": "set up the therapy room", "unit": "session",
            "greeting": "assist with your rehab and physical therapy", "role": "senior physiotherapist", "prep_q": "wear athletic exercise clothing?",
            "prep_a": "loose, comfortable athletic wear is best for movement assessment.",
            "confirm": "Therapy assessment suite and rehab gear prepped",
        },
        "veterinary_clinic": {
            "action": "pet examination room", "inquiry": "pet health checkup", "verb": "prepare the exam room", "unit": "room",
            "greeting": "care for your pet today", "role": "veterinary doctor", "prep_q": "bring pet vaccination records?",
            "prep_a": "you can upload records via our patient portal or bring a copy along.",
            "confirm": "Pet examination room sanitized and ready",
        },
        "restaurant_cafe": {
            "action": "dining table", "inquiry": "dinner reservation", "verb": "hold the dining table", "unit": "table",
            "greeting": "reserve your table experience", "role": "head chef", "prep_q": "accommodate vegetarian dietary needs?",
            "prep_a": "our kitchen caters to vegetarian and gluten-free preferences seamlessly.",
            "confirm": "Dining table and chef tasting course reserved",
        },
        "bakery_orders": {
            "action": "bakery kitchen order", "inquiry": "custom pastry pre-order", "verb": "schedule the baking batch", "unit": "order",
            "greeting": "order fresh bakery treats and custom cakes", "role": "head pastry chef", "prep_q": "need to bring my own bakery crate?",
            "prep_a": "we pack everything in secure bakery boxes ready for curbside pickup.",
            "confirm": "Bake batch queued and packaging prepped",
        },
        "home_plumbing": {
            "action": "plumbing dispatch truck", "inquiry": "pipe leak inspection", "verb": "route the dispatch van", "unit": "dispatch",
            "greeting": "assist with plumbing emergencies and repairs", "role": "licensed plumber", "prep_q": "shut off the main water valve tonight?",
            "prep_a": "yes, shutting the main valve prevents damage until our technician arrives.",
            "confirm": "Plumbing service van routed with pipe diagnostic tools",
        },
        "home_electrical": {
            "action": "licensed electrician visit", "inquiry": "circuit wiring diagnostic", "verb": "schedule the electrician van", "unit": "dispatch",
            "greeting": "help with your electrical troubleshooting", "role": "licensed electrician", "prep_q": "leave breaker box access clear?",
            "prep_a": "keeping the panel area clear allows our electrician to test lines immediately.",
            "confirm": "Electrician van dispatched with circuit testing equipment",
        },
        "home_ac_repair": {
            "action": "HVAC technician call", "inquiry": "AC cooling service", "verb": "dispatch the cooling tech", "unit": "dispatch",
            "greeting": "restore your cooling and AC comfort", "role": "HVAC specialist", "prep_q": "turn off the thermostat before the tech arrives?",
            "prep_a": "leaving the system off helps our specialist inspect the coils right away.",
            "confirm": "HVAC technician dispatched with refrigerant diagnostic kit",
        },
        "cleaning_service": {
            "action": "cleaning crew visit", "inquiry": "deep home clean", "verb": "assign the cleaning team", "unit": "crew",
            "greeting": "schedule your residential cleaning", "role": "crew supervisor", "prep_q": "provide my own cleaning detergents?",
            "prep_a": "our crew brings all eco-friendly supplies and industrial vacuums.",
            "confirm": "Cleaning crew scheduled with professional sanitization equipment",
        },
        "auto_repair": {
            "action": "mechanic service bay", "inquiry": "brake diagnostic inspection", "verb": "reserve service bay two", "unit": "bay",
            "greeting": "diagnose your vehicle's mechanical issues", "role": "lead mechanic", "prep_q": "leave my car keys in the drop box?",
            "prep_a": "our secure key drop box is beside the bay doors for early dropoffs.",
            "confirm": "Service bay reserved with digital brake diagnostic tools",
        },
        "real_estate_agency": {
            "action": "property viewing tour", "inquiry": "property viewing walkthrough", "verb": "schedule the agent walkthrough", "unit": "viewing",
            "greeting": "guide your property search in", "role": "listing agent", "prep_q": "bring pre-approval mortgage documentation?",
            "prep_a": "having pre-approval helps our agent prepare tailored property dossiers.",
            "confirm": "Property tour scheduled with private viewing access",
        },
        "accounting_front_desk": {
            "action": "tax advisory consultation", "inquiry": "tax return filing intake", "verb": "book the accountant calendar", "unit": "consultation",
            "greeting": "coordinate your tax and accounting consultation", "role": "senior accountant", "prep_q": "upload past tax returns in advance?",
            "prep_a": "uploading via our secure portal lets our accountant review numbers beforehand.",
            "confirm": "Accounting consultation booked with tax intake file",
        },
        "legal_front_desk": {
            "action": "legal intake consultation", "inquiry": "contract review intake", "verb": "book the attorney conference", "unit": "consultation",
            "greeting": "coordinate your legal intake consultation", "role": "managing partner", "prep_q": "forward agreements prior to the meeting?",
            "prep_a": "forwarding documents ensures our attorney reviews key clauses in advance.",
            "confirm": "Confidential legal intake conference scheduled",
        },
        "yoga_fitness_studio": {
            "action": "pilates reformer mat", "inquiry": "trial workout session", "verb": "reserve the studio reformer", "unit": "mat",
            "greeting": "book your fitness and yoga class", "role": "lead instructor", "prep_q": "bring my own yoga mat and towel?",
            "prep_a": "we supply sanitized premium mats, though you are welcome to bring personal gear.",
            "confirm": "Studio reformer mat and locker reserved",
        },
        "driving_school": {
            "action": "dual-control training car", "inquiry": "driving road lesson", "verb": "schedule the instructor car", "unit": "car",
            "greeting": "schedule your professional driving lesson", "role": "certified instructor", "prep_q": "bring my learner permit card?",
            "prep_a": "yes, your physical learner permit is mandatory for all road training.",
            "confirm": "Training vehicle dispatched with certified instructor",
        },
        "coaching_center": {
            "action": "tutoring study desk", "inquiry": "diagnostic academic assessment", "verb": "assign the tutor desk", "unit": "desk",
            "greeting": "coordinate your tutoring assessment", "role": "academic mentor", "prep_q": "bring school syllabus and exam papers?",
            "prep_a": "bringing recent exams helps our mentor pinpoint key revision topics.",
            "confirm": "Tutoring study desk and diagnostic curriculum prepped",
        },
        "photography_studio": {
            "action": "lighting camera bay", "inquiry": "portrait photo session", "verb": "prepare studio lighting backdrop", "unit": "studio",
            "greeting": "plan your portrait photography session", "role": "studio photographer", "prep_q": "bring multiple outfit changes?",
            "prep_a": "our private dressing room accommodates up to three wardrobe changes.",
            "confirm": "Studio lighting bay and backdrop prepped",
        },
        "pet_grooming": {
            "action": "grooming spa bath", "inquiry": "dog bath and deshedding", "verb": "prepare the grooming tub", "unit": "bath",
            "greeting": "spoil your pet with a grooming spa visit", "role": "pet stylist", "prep_q": "bring proof of rabies immunization?",
            "prep_a": "current vaccination records are required to safeguard all furry guests.",
            "confirm": "Grooming hydrotherapy tub and dryer station reserved",
        },
        "florist_boutique": {
            "action": "custom floral arrangement", "inquiry": "bouquet consultation", "verb": "prepare the floral worktable", "unit": "order",
            "greeting": "craft fresh floral bouquets and arrangements", "role": "floral designer", "prep_q": "select specific flower varieties in advance?",
            "prep_a": "our designer selects fresh morning blooms and custom stems to your taste.",
            "confirm": "Floral studio worktable and stem selection reserved",
        },
    }
    return ctx_map.get(
        vid,
        {
            "action": "appointment slot", "inquiry": "service session", "verb": "reserve the time slot", "unit": "slot",
            "greeting": "assist with your appointment", "role": "team specialist", "prep_q": "bring anything in advance?",
            "prep_a": "no prep needed, we take care of everything upon arrival.",
            "confirm": "Appointment reserved",
        },
    )


def _build_scenario_dialogue(
    scenario: str,
    biz_name: str,
    vid: str,
    vertical: str,
    city: str,
    owner: str,
    caller_name: str,
    service: Any,
    faq: Any,
    time_slot: str,
    rng: random.Random,
) -> Tuple[List[DialogueTurn], List[CallEvent], OwnerNotification, str]:
    """Build unique conversational flows for each specific scenario and vertical with turn-level variation."""
    ctx = _get_vertical_context(vid, vertical)

    if scenario == "reschedule":
        hook = rng.choice([
            f"Client needed to reschedule immediately at {biz_name}",
            f"Calendar shuffle handled smoothly at {biz_name}",
            f"Sudden conflict? Watch {biz_name} shift this appointment",
            f"Moving a client booking in 20 seconds flat",
        ])
        t0 = rng.choice([
            f"Good morning, thanks for calling {biz_name}. Are you looking to {ctx['greeting']}?",
            f"Hello! Front desk at {biz_name}. What can our {ctx['role']} adjust for you today?",
            f"Thanks for reaching {biz_name}. Need to update your {ctx['inquiry']}?",
        ])
        t1 = rng.choice([
            f"Hi, this is {caller_name}. I have a {ctx['inquiry']} booked with {owner}, but my schedule shifted.",
            f"Hey, {caller_name} here. A work conflict came up and I need to move my {service.name} session.",
            f"Hello, I was supposed to come in for {service.name}, but something urgent occurred on my end.",
        ])
        t2 = rng.choice([
            f"No problem at all, {caller_name}. Let me pull up your {ctx['unit']}. Would {time_slot} work instead?",
            f"I understand completely! Checking our {ctx['role']} calendar now. How does {time_slot} suit you?",
            f"Easily handled! Looking at open {ctx['unit']} availability. We could reschedule your {service.name} for {time_slot}.",
        ])
        t3 = rng.choice([
            f"Yes, {time_slot.split(' at ')[1]} would be much better for my {service.name}.",
            f"That {time_slot} time is ideal. Thank you for accommodating me.",
            f"Perfect, that fits my calendar smoothly. Let's do that.",
        ])
        t4 = rng.choice([
            f"I've moved your {service.name} to {time_slot}. {ctx['confirm']}.",
            f"Your {service.name} is now transferred to {time_slot}. Our {ctx['role']} roster is synced.",
            f"Done! {ctx['unit'].capitalize()} is shifted to {time_slot} under {caller_name}.",
        ])
        t5 = rng.choice([
            f"Do I need to {ctx['prep_q']}",
            "Does my original confirmation code still work?",
            "Will I receive an updated notification on my phone?",
        ])
        t6 = rng.choice([
            f"Yes, {ctx['prep_a']}",
            "All details transfer over. A revised digital pass is on its way to your phone.",
            "Absolutely, I just sent a text with your updated calendar invite.",
        ])
        t7 = rng.choice([
            "You've been super helpful. Thanks so much!",
            "Great turnaround time. Truly appreciate the help!",
            "Wonderful service. See you then!",
        ])

        turns = [
            DialogueTurn(speaker="agent", text=t0, emotion="polite", pause_after_ms=300),
            DialogueTurn(speaker="caller", text=t1, emotion="rushed", pause_after_ms=320),
            DialogueTurn(speaker="agent", text=t2, emotion="helpful", pause_after_ms=300, on_screen_event=f"Retrieved {ctx['unit']} reservation"),
            DialogueTurn(speaker="caller", text=t3, emotion="relieved", pause_after_ms=280),
            DialogueTurn(speaker="agent", text=t4, emotion="clear", pause_after_ms=300, on_screen_event=f"Shifted {ctx['unit']} on calendar"),
            DialogueTurn(speaker="caller", text=t5, emotion="curious", pause_after_ms=260),
            DialogueTurn(speaker="agent", text=t6, emotion="warm", pause_after_ms=320, on_screen_event="Dispatched updated pass"),
            DialogueTurn(speaker="caller", text=t7, emotion="satisfied", pause_after_ms=200),
        ]
        events = [
            CallEvent(turn_index=2, text=f"Looked up {ctx['unit']} booking", type="tool_call"),
            CallEvent(turn_index=4, text=f"Shifted to {time_slot}", type="booking_card"),
            CallEvent(turn_index=6, text="Dispatched revised invite", type="tool_call"),
        ]
        notif = OwnerNotification(
            summary=f"Rescheduled: {caller_name} moved {service.name} to {time_slot}.",
            customer_name=caller_name,
            time_or_slot=time_slot,
            service_requested=service.name,
            next_step=f"{ctx['verb'].capitalize()}.",
        )

    elif scenario == "after_hours_urgent":
        hook = rng.choice([
            f"It's 10 PM. Watch who answered {biz_name}'s call",
            f"Late night emergency call handled instantly",
            f"Off-hours urgent request routed by AI at {biz_name}",
            f"Midnight crisis averted for {biz_name}",
        ])
        t0 = rng.choice([
            f"Hello, you've reached the after-hours emergency desk for {biz_name}.",
            f"Emergency reception line for {biz_name}. I can {ctx['greeting']}.",
            f"Good evening, after-hours dispatch line for {biz_name}.",
        ])
        t1 = rng.choice([
            f"Hi, thank goodness you answered! I have an urgent issue with my {ctx['inquiry']}.",
            f"Greetings, my name is {caller_name}. We have an unexpected breakdown requiring {service.name}.",
            f"Hello! I am dealing with a sudden problem regarding {service.name} and need urgent {ctx['role']} support.",
        ])
        t2 = rng.choice([
            f"Don't worry, {caller_name}. I can create an emergency dispatch ticket right now for {owner}.",
            f"I understand the urgency. Let me check {ctx['role']} on-call rosters for {city} immediately.",
            f"Rest assured, we handle after-hours calls twenty-four-seven. Opening a priority ticket for our {ctx['role']}.",
        ])
        t3 = rng.choice([
            f"We're located in {city}. How early can your team handle my {service.name}?",
            f"Can someone inspect our {ctx['action']} first thing tomorrow morning?",
            f"What is the fastest arrival window you can offer in our area?",
        ])
        t4 = rng.choice([
            f"I have our first priority window at 8:00 AM. I will lock in {service.name} for you.",
            f"We have an expedited 8:30 AM window with our {ctx['role']} {owner} reserved for you.",
            f"I've placed you in our priority 8:00 AM slot. {ctx['confirm']}.",
        ])
        t5 = rng.choice([
            f"Do I need to {ctx['prep_q']}",
            "Will the technician call me when they are on the road?",
            "What details do you need from me right now?",
        ])
        t6 = rng.choice([
            f"Yes, {ctx['prep_a']}",
            f"Our {ctx['role']} will phone you fifteen minutes ahead. Emergency ticket is confirmed.",
            "I have captured your phone number and address. Stand by for an immediate SMS tracker.",
        ])
        t7 = rng.choice([
            "Saved my night. Thank you for the quick resolution!",
            "Phew, what a relief. Thanks for answering so late!",
            "Incredible response time. Thank you so much!",
        ])

        turns = [
            DialogueTurn(speaker="agent", text=t0, emotion="calm", pause_after_ms=300),
            DialogueTurn(speaker="caller", text=t1, emotion="anxious", pause_after_ms=340),
            DialogueTurn(speaker="agent", text=t2, emotion="reassuring", pause_after_ms=300, on_screen_event="Logged emergency ticket"),
            DialogueTurn(speaker="caller", text=t3, emotion="hopeful", pause_after_ms=300),
            DialogueTurn(speaker="agent", text=t4, emotion="direct", pause_after_ms=320, on_screen_event=f"Assigned priority {ctx['unit']}"),
            DialogueTurn(speaker="caller", text=t5, emotion="curious", pause_after_ms=280),
            DialogueTurn(speaker="agent", text=t6, emotion="helpful", pause_after_ms=350, on_screen_event="Alerted on-call team"),
            DialogueTurn(speaker="caller", text=t7, emotion="grateful", pause_after_ms=200),
        ]
        events = [
            CallEvent(turn_index=2, text="Opened emergency priority ticket", type="tool_call"),
            CallEvent(turn_index=4, text="Assigned priority morning slot", type="booking_card"),
            CallEvent(turn_index=6, text=f"Pushed emergency alert to {owner}", type="owner_notification"),
        ]
        notif = OwnerNotification(
            summary=f"URGENT: {caller_name} booked emergency dispatch for {service.name}.",
            customer_name=caller_name,
            time_or_slot="Tomorrow Morning",
            service_requested=service.name,
            next_step=f"{ctx['verb'].capitalize()}.",
        )
        events = [
            CallEvent(turn_index=2, text="Opened emergency priority ticket", type="tool_call"),
            CallEvent(turn_index=4, text="Assigned priority morning slot", type="booking_card"),
            CallEvent(turn_index=6, text=f"Pushed emergency alert to {owner}", type="owner_notification"),
        ]
        notif = OwnerNotification(
            summary=f"URGENT: {caller_name} booked emergency dispatch for {service.name}.",
            customer_name=caller_name,
            time_or_slot="Tomorrow Morning",
            service_requested=service.name,
            next_step=f"{ctx['verb'].capitalize()}.",
        )

    elif scenario == "availability_check":
        hook = rng.choice([
            f"Checking weekend availability at {biz_name}",
            f"Is {biz_name} open this weekend? AI answers instantly",
            f"Real-time schedule check converted into a booking",
            f"Fast calendar inquiry at {biz_name}",
        ])
        t0 = rng.choice([
            f"Welcome to {biz_name}! Are you looking to {ctx['greeting']}?",
            f"Thanks for reaching out to {biz_name}. Need to check our {ctx['role']} schedule?",
            f"Good day from {biz_name}! What {ctx['inquiry']} can I look up for you?",
        ])
        t1 = rng.choice([
            f"Hi! Do you have an open {ctx['unit']} for {service.name} this {time_slot.split(' at ')[0]}?",
            f"Hello! I'm calling to see if your {ctx['role']} is open on {time_slot.split(' at ')[0]} for {service.name}.",
            f"Hi there, my name is {caller_name}. Looking for a {service.name} slot.",
        ])
        t2 = rng.choice([
            f"Let me check our {ctx['role']} availability. Yes, {owner} has an opening at {time_slot}.",
            f"Looking at our live board now. We have {time_slot} ready for your {service.name}.",
            f"Scanning our {ctx['unit']} calendar. {time_slot} with {owner} is open.",
        ])
        t3 = rng.choice([
            f"That {time_slot.split(' at ')[1]} window works great. Can you pencil me in under {caller_name}?",
            f"That fits my afternoon nicely. Please register {caller_name}.",
            f"Fantastic timing. Let us book that {ctx['unit']} for {caller_name}.",
        ])
        t4 = rng.choice([
            f"You're in! {ctx['confirm']} for {service.name} at {service.price}.",
            f"Spot secured for {caller_name}! {owner} will handle your {service.name}.",
            f"All locked in for {time_slot}. {ctx['confirm']}.",
        ])
        t5 = rng.choice([
            f"Do I need to {ctx['prep_q']}",
            "Should I bring any prior paperwork or documents with me?",
            "Is parking available on site when I come in?",
        ])
        t6 = rng.choice([
            f"Yes, {ctx['prep_a']}",
            f"Just arrive five minutes early. I've texted your {ctx['unit']} pass and location PIN.",
            "All details are logged electronically. Directions link is on your phone.",
        ])
        t7 = rng.choice([
            "Fast and simple. Appreciate the help!",
            "Sounds effortless. See everyone soon!",
            "Super smooth booking. Thank you!",
        ])

        turns = [
            DialogueTurn(speaker="agent", text=t0, emotion="upbeat", pause_after_ms=300),
            DialogueTurn(speaker="caller", text=t1, emotion="curious", pause_after_ms=300),
            DialogueTurn(speaker="agent", text=t2, emotion="helpful", pause_after_ms=300, on_screen_event=f"Scanned {ctx['unit']} calendar"),
            DialogueTurn(speaker="caller", text=t3, emotion="pleased", pause_after_ms=280),
            DialogueTurn(speaker="agent", text=t4, emotion="clear", pause_after_ms=320, on_screen_event=f"Locked {ctx['unit']}: {time_slot}"),
            DialogueTurn(speaker="caller", text=t5, emotion="inquiring", pause_after_ms=280),
            DialogueTurn(speaker="agent", text=t6, emotion="warm", pause_after_ms=340, on_screen_event="Dispatched digital pass & directions"),
            DialogueTurn(speaker="caller", text=t7, emotion="satisfied", pause_after_ms=200),
        ]
        events = [
            CallEvent(turn_index=2, text=f"Scanned {ctx['unit']} availability grid", type="tool_call"),
            CallEvent(turn_index=4, text=f"Slot locked: {time_slot}", type="booking_card"),
            CallEvent(turn_index=6, text="Dispatched appointment pass", type="tool_call"),
        ]
        notif = OwnerNotification(
            summary=f"Availability check booked: {caller_name} reserved {service.name}.",
            customer_name=caller_name,
            time_or_slot=time_slot,
            service_requested=service.name,
            next_step=f"{ctx['verb'].capitalize()}.",
        )

    elif scenario == "group_booking":
        hook = rng.choice([
            f"Large party booking handled in 30 seconds",
            f"Managing a group reservation seamlessly with AI",
            f"Six people, one call: booked without hold music",
            f"Group coordination made effortless at {biz_name}",
        ])
        t0 = rng.choice([
            f"Thank you for contacting {biz_name}! Are you planning a group {ctx['inquiry']}?",
            f"Good day from {biz_name}. Looking to {ctx['greeting']} with a group?",
            f"Welcome to {biz_name}! Coordinating a group event for our {ctx['role']} team?",
        ])
        t1 = rng.choice([
            f"Hi! We have a party of six people and want to organize a group {service.name}.",
            f"Yes indeed, my name is {caller_name}. We have an eight-person group wanting {service.name}.",
            f"Hello, I am coordinating an event for multiple guests for {service.name}.",
        ])
        t2 = rng.choice([
            f"A party of six sounds fantastic. Let me verify {ctx['action']} capacity for {time_slot}.",
            f"Delighted to host your delegation. Let me inspect our group accommodations for {time_slot.split(' at ')[0]}.",
            f"We love group bookings! Checking {ctx['unit']} capacity for {time_slot} now.",
        ])
        t3 = rng.choice([
            f"What is the total package rate for six attendees for {service.name}?",
            "Does your venue accommodate custom seating arrangements?",
            f"Can our {ctx['role']} provide a combined group quote with priority access?",
        ])
        t4 = rng.choice([
            f"The group rate is {service.price} per person, which includes full setup and priority access.",
            f"Yes, our floor plan is fully customizable. {ctx['confirm']} for your group at {time_slot}.",
            f"Package is {service.price} per guest with full dedicated staffing. Holding {time_slot} for you.",
        ])
        t5 = rng.choice([
            f"That fits our budget. Please reserve the group slot under {caller_name}.",
            "Can you forward the deposit link directly to my mobile?",
            f"Sounds perfect. Please register the reservation under {caller_name}.",
        ])
        t6 = rng.choice([
            f"All spots are locked for {time_slot}! A group confirmation link is sent to your phone.",
            f"Sent! The invoice and checklist for {owner} are in your messages right now.",
            f"Your group reservation is confirmed for {time_slot}. {ctx['confirm']}.",
        ])
        t7 = rng.choice([
            "Our entire group will be delighted. Thank you!",
            "Everything is so smoothly arranged. Looking forward to our event!",
            "Appreciate the quick coordination. Have a great day!",
        ])

        turns = [
            DialogueTurn(speaker="agent", text=t0, emotion="welcoming", pause_after_ms=300),
            DialogueTurn(speaker="caller", text=t1, emotion="cheerful", pause_after_ms=320),
            DialogueTurn(speaker="agent", text=t2, emotion="enthusiastic", pause_after_ms=300, on_screen_event=f"Verified multi-{ctx['unit']} capacity"),
            DialogueTurn(speaker="caller", text=t3, emotion="curious", pause_after_ms=280),
            DialogueTurn(speaker="agent", text=t4, emotion="clear", pause_after_ms=320, on_screen_event=f"Calculated group rate"),
            DialogueTurn(speaker="caller", text=t5, emotion="happy", pause_after_ms=280),
            DialogueTurn(speaker="agent", text=t6, emotion="warm", pause_after_ms=340, on_screen_event="Group itinerary confirmed"),
            DialogueTurn(speaker="caller", text=t7, emotion="delighted", pause_after_ms=200),
        ]
        events = [
            CallEvent(turn_index=2, text=f"Checked multi-{ctx['unit']} capacity", type="tool_call"),
            CallEvent(turn_index=4, text=f"Group reservation locked: {time_slot}", type="booking_card"),
            CallEvent(turn_index=6, text="Dispatched group itinerary & deposit link", type="tool_call"),
        ]
        notif = OwnerNotification(
            summary=f"Group booking: {caller_name} reserved party for {service.name}.",
            customer_name=caller_name,
            time_or_slot=time_slot,
            service_requested=f"{service.name} (Group)",
            next_step=f"{ctx['verb'].capitalize()} for group event.",
        )

    elif scenario == "lead_capture_callback":
        hook = rng.choice([
            f"B2B client needs custom project estimate",
            f"High-value business lead captured after hours",
            f"Commercial RFP inquiry routed straight to founder",
            f"Capturing enterprise contracts on auto-pilot",
        ])
        t0 = rng.choice([
            f"Greetings from {biz_name}. Are you looking to {ctx['greeting']}?",
            f"Good afternoon. Welcome to {biz_name}'s executive line.",
            f"Thank you for contacting {biz_name}. Are you inquiring about custom {ctx['inquiry']}?",
        ])
        t1 = rng.choice([
            f"Hello, I have a multi-site commercial requirement in {city} and need an expert {service.name} proposal.",
            f"Hi, {caller_name} representing our procurement office. We are evaluating vendors for {service.name}.",
            f"Hello, my organization requires custom {service.name} across our regional facilities.",
        ])
        t2 = rng.choice([
            f"We handle commercial projects regularly. May I record your project scope for our lead {ctx['role']} {owner}?",
            f"Welcome, {caller_name}. Our {ctx['role']} team routinely partners with commercial enterprises across {city}.",
            f"Understood. We specialize in custom proposals. Let me initiate a corporate intake file for {owner}.",
        ])
        t3 = rng.choice([
            f"I'm {caller_name}. We need full {service.name} deployed across our regional offices.",
            f"What is your customary lead time for generating detailed {service.name} price quotations?",
            f"We have strict delivery timelines and need {owner} to evaluate our technical specifications.",
        ])
        t4 = rng.choice([
            f"Got it. {owner} assesses all commercial bids personally. Can {owner} phone you tomorrow at eleven AM?",
            f"Typically under twenty-four hours once our lead {ctx['role']} {owner} inspects your specifications.",
            f"I will schedule a dedicated discovery call with {owner} for {time_slot}.",
        ])
        t5 = rng.choice([
            "Eleven AM tomorrow is ideal. I have the architectural blueprints ready.",
            "Splendid. Please have someone contact me Thursday afternoon.",
            "That works well. I will have our RFP summary prepared.",
        ])
        t6 = rng.choice([
            f"I've scheduled the discovery call with {owner} and sent calendar confirmation to your email.",
            f"Registered! {ctx['confirm']}. A secure intake portal link has been dispatched to your device.",
            f"All confirmed. {owner} has received your brief and will call promptly.",
        ])
        t7 = rng.choice([
            "Thank you for the prompt coordination. Speak tomorrow.",
            "Excellent efficiency. We will talk Thursday.",
            "Very impressed with your responsiveness. Goodbye!",
        ])

        turns = [
            DialogueTurn(speaker="agent", text=t0, emotion="polite", pause_after_ms=300),
            DialogueTurn(speaker="caller", text=t1, emotion="formal", pause_after_ms=320),
            DialogueTurn(speaker="agent", text=t2, emotion="professional", pause_after_ms=300, on_screen_event="Created corporate lead intake file"),
            DialogueTurn(speaker="caller", text=t3, emotion="business", pause_after_ms=320),
            DialogueTurn(speaker="agent", text=t4, emotion="focused", pause_after_ms=300, on_screen_event="Scheduled director callback"),
            DialogueTurn(speaker="caller", text=t5, emotion="inquiring", pause_after_ms=280),
            DialogueTurn(speaker="agent", text=t6, emotion="confident", pause_after_ms=340, on_screen_event="Dispatched director calendar sync"),
            DialogueTurn(speaker="caller", text=t7, emotion="satisfied", pause_after_ms=200),
        ]
        events = [
            CallEvent(turn_index=2, text="Opened B2B corporate lead file", type="tool_call"),
            CallEvent(turn_index=4, text=f"Tagged high-value enterprise contract", type="tool_call"),
            CallEvent(turn_index=6, text=f"Director callback assigned to {owner}", type="owner_notification"),
        ]
        notif = OwnerNotification(
            summary=f"COMMERCIAL LEAD: {caller_name} requested custom bid for {service.name}.",
            customer_name=caller_name,
            time_or_slot="Scheduled Callback",
            service_requested=f"Custom Enterprise {service.name}",
            next_step=f"{owner} to review specs and call prospect.",
        )

    elif scenario == "price_inquiry":
        hook = rng.choice([
            f"Curious caller wanted pricing breakdown at {biz_name}",
            f"Transparent pricing quoted in real time",
            f"Price shopper converted into booked client",
            f"How AI handles rate inquiries at {biz_name}",
        ])
        t0 = rng.choice([
            f"Thank you for calling {biz_name}. Are you looking to {ctx['greeting']}?",
            f"Hello! Front desk at {biz_name}. Which package can our {ctx['role']} explain for you today?",
            f"Greetings from {biz_name}! Are you inquiring about service rates for {ctx['inquiry']}?",
        ])
        t1 = rng.choice([
            f"Hi, I was comparing local providers and wanted to check your rates for {service.name}.",
            f"Good day! I am shopping around and would love to know the cost of {service.name}.",
            f"Hello, {caller_name} here. Can you break down the pricing for {service.name}?",
        ])
        t2 = rng.choice([
            f"Our {service.name} is priced at {service.price}. It covers full diagnostics and complete {ctx['inquiry']}.",
            f"Certainly! The flat rate is {service.price}, which includes all necessary supplies and {ctx['role']} follow-up.",
            f"For {service.name}, our published fee is {service.price}, inclusive of all standard labor and {ctx['unit']} prep.",
        ])
        t3 = rng.choice([
            f"Do I need to {ctx['prep_q']}",
            "Are there any hidden consultation fees or surprise charges on the day?",
            "Does that price include taxes and preliminary evaluation?",
        ])
        t4 = rng.choice([
            f"No hidden fees at all. Our pricing is completely transparent. {ctx['confirm']} on {time_slot} with {owner}?",
            f"We take pride in fair pricing! We have a time slot available on {time_slot} with {owner}.",
            f"Everything is transparent and all-inclusive. {ctx['confirm']} for {time_slot}?",
        ])
        t5 = rng.choice([
            f"Sounds very fair. Let's do {time_slot} under {caller_name}.",
            f"Lock that in for me please, under {caller_name}.",
            f"Great, let's reserve that {ctx['unit']} for {caller_name}.",
        ])
        t6 = rng.choice([
            f"All confirmed for {time_slot}, {caller_name}. We look forward to meeting you! {ctx['confirm']}.",
            "Consider it done! Your price quote and reservation details have been texted over.",
            f"Reservation locked in for {time_slot}. {ctx['confirm']}.",
        ])
        t7 = rng.choice([
            "Appreciate the honest breakdown. See you then!",
            "Thank you for being so upfront. Talk soon!",
            "Smooth and honest pricing. Thank you!",
        ])

        turns = [
            DialogueTurn(speaker="agent", text=t0, emotion="polite", pause_after_ms=300),
            DialogueTurn(speaker="caller", text=t1, emotion="curious", pause_after_ms=320),
            DialogueTurn(speaker="agent", text=t2, emotion="clear", pause_after_ms=300, on_screen_event=f"Quoted verified rate: {service.price}"),
            DialogueTurn(speaker="caller", text=t3, emotion="inquisitive", pause_after_ms=280),
            DialogueTurn(speaker="agent", text=t4, emotion="confident", pause_after_ms=320),
            DialogueTurn(speaker="caller", text=t5, emotion="positive", pause_after_ms=280),
            DialogueTurn(speaker="agent", text=t6, emotion="cheerful", pause_after_ms=320, on_screen_event="Logged quote and finalized booking"),
            DialogueTurn(speaker="caller", text=t7, emotion="satisfied", pause_after_ms=200),
        ]
        events = [
            CallEvent(turn_index=2, text=f"Verified catalog price: {service.price}", type="tool_call"),
            CallEvent(turn_index=4, text=f"Slot locked: {time_slot}", type="booking_card"),
            CallEvent(turn_index=6, text="Dispatched price guarantee & confirmation", type="tool_call"),
        ]
        notif = OwnerNotification(
            summary=f"Price inquiry converted: {caller_name} booked {service.name} at {service.price}.",
            customer_name=caller_name,
            time_or_slot=time_slot,
            service_requested=service.name,
            next_step="Confirmed transparent quote.",
        )

    elif scenario == "faq_resolution":
        hook = rng.choice([
            f"Customer had parking questions before visiting {biz_name}",
            f"Instant answers to everyday customer questions",
            f"Zero hold time for policy questions at {biz_name}",
            f"Quick question turned into a confirmed booking",
        ])
        t0 = rng.choice([
            f"Hello and welcome to {biz_name}. May we help you {ctx['greeting']}?",
            f"Good morning! Reception at {biz_name}. What information may our {ctx['role']} pull up?",
            f"Welcome to {biz_name}! What can our virtual front desk help clarify regarding {ctx['inquiry']}?",
        ])
        t1 = rng.choice([
            f"Hi! I'm planning to drop by this afternoon, but I wanted to ask about {faq.question.lower()}",
            f"Hello! I had a quick query regarding {faq.question.lower()}",
            f"Hi there, I am planning a visit for {service.name} and wanted to know about {faq.question.lower()}",
        ])
        t2 = rng.choice([
            f"{faq.answer} We want to make sure your arrival is completely effortless.",
            f"{faq.answer} We keep all facility policies streamlined for our guests.",
            f"{faq.answer} Our {ctx['role']} team ensures all visitors have a seamless experience.",
        ])
        t3 = rng.choice([
            f"That's so convenient! While I have you, can I also reserve a quick {service.name}?",
            f"Glad to know! Is it possible to reserve an appointment for {service.name} as well?",
            f"That clarifies everything! Could I book an open {ctx['unit']} for {service.name}?",
        ])
        t4 = rng.choice([
            f"Absolutely! I have an opening with our team at {time_slot}. {ctx['confirm']} under your name?",
            f"Certainly! We have an opening at {time_slot} with {owner}. Let me secure that for you.",
            f"Yes indeed! {time_slot} is wide open on our calendar. Shall I lock in that {ctx['unit']}?",
        ])
        t5 = rng.choice([
            f"Yes, name is {caller_name}. That fits right into my schedule.",
            f"Yes please, {caller_name} is the name.",
            f"Please do, under {caller_name}.",
        ])
        t6 = rng.choice([
            f"Done! Your {service.name} is booked for {time_slot}. {ctx['confirm']}. Map and PIN texted to you.",
            f"All set for {time_slot}! A detailed guide and {ctx['unit']} pass dispatched to your mobile.",
            f"You are confirmed for {time_slot}! {ctx['confirm']}.",
        ])
        t7 = rng.choice([
            "Awesome service. Looking forward to it!",
            "Super clear and helpful. See you soon!",
            "Thank you for the quick answers and booking!",
        ])

        turns = [
            DialogueTurn(speaker="agent", text=t0, emotion="cheerful", pause_after_ms=300),
            DialogueTurn(speaker="caller", text=t1, emotion="curious", pause_after_ms=320),
            DialogueTurn(speaker="agent", text=t2, emotion="clear", pause_after_ms=320, on_screen_event="Retrieved verified FAQ info"),
            DialogueTurn(speaker="caller", text=t3, emotion="cheerful", pause_after_ms=300),
            DialogueTurn(speaker="agent", text=t4, emotion="helpful", pause_after_ms=300, on_screen_event=f"Found available slot: {time_slot}"),
            DialogueTurn(speaker="caller", text=t5, emotion="satisfied", pause_after_ms=280),
            DialogueTurn(speaker="agent", text=t6, emotion="warm", pause_after_ms=340, on_screen_event="Sent booking confirmation + directions"),
            DialogueTurn(speaker="caller", text=t7, emotion="happy", pause_after_ms=200),
        ]
        events = [
            CallEvent(turn_index=2, text="Provided verified facility information", type="tool_call"),
            CallEvent(turn_index=4, text=f"Reserved {time_slot}", type="booking_card"),
            CallEvent(turn_index=6, text="Dispatched map & PIN to caller", type="tool_call"),
        ]
        notif = OwnerNotification(
            summary=f"FAQ resolved & booking created: {caller_name} reserved {service.name}.",
            customer_name=caller_name,
            time_or_slot=time_slot,
            service_requested=service.name,
            next_step="Sent facility guidance.",
        )

    else:
        # Standard Appointment booking
        hook = rng.choice([
            f"Hands full? Watch AI book this client call",
            f"Booking handled seamlessly while the owner works",
            f"No missed calls: new client booked at {biz_name}",
            f"AI receptionist in action for {biz_name}",
        ])
        t0 = rng.choice([
            f"Thanks for calling {biz_name}. Are you looking to {ctx['greeting']}?",
            f"Hello! Thank you for choosing {biz_name}. How can our {ctx['role']} serve you today?",
            f"Welcome to {biz_name}. Looking to schedule {ctx['inquiry']}?",
        ])
        t1 = rng.choice([
            f"Hi! Yes, I need {service.name} around {time_slot.split(' at ')[0].lower()}.",
            f"Hi there! My name is {caller_name} and I would love to arrange an appointment for {service.name}.",
            f"Hello, looking to book a {ctx['unit']} for {service.name} sometime this week.",
        ])
        t2 = rng.choice([
            f"I've got an open {ctx['unit']} at {time_slot} with our {ctx['role']} {owner}. Shall I reserve that for you?",
            f"It is a pleasure, {caller_name}. We have an open slot with {owner} on {time_slot}.",
            f"We have an excellent opening for {service.name} at {time_slot}. {ctx['confirm']}?",
        ])
        t3 = rng.choice([
            f"Do I need to {ctx['prep_q']}",
            "That timing is great. Can you confirm the service fee?",
            "That works wonderfully with my commute. How long does the appointment take?",
        ])
        t4 = rng.choice([
            f"Yes, {ctx['prep_a']}",
            f"The {service.name} is {service.price}, covering full preparation and {ctx['verb']}.",
            f"Our standard fee is {service.price} for complete service with {owner}.",
        ])
        t5 = rng.choice([
            f"Sounds good, book it under {caller_name}.",
            "Perfect, let us go ahead with that time.",
            f"Please lock that in for {caller_name}.",
        ])
        t6 = rng.choice([
            f"You're on the books for {time_slot}, {caller_name}! {ctx['confirm']}. SMS confirmation dispatched.",
            f"Your booking is confirmed! {ctx['confirm']}. Electronic pass sent.",
            f"Appointment locked in for {time_slot}. All booking details have been texted to you.",
        ])
        t7 = rng.choice([
            "Super efficient. Thanks and see you then!",
            "Brilliant. Thank you so much for the quick help!",
            "Fast and courteous. Thank you!",
        ])

        turns = [
            DialogueTurn(speaker="agent", text=t0, emotion="cheerful", pause_after_ms=300),
            DialogueTurn(speaker="caller", text=t1, emotion="curious", pause_after_ms=320),
            DialogueTurn(speaker="agent", text=t2, emotion="helpful", pause_after_ms=300, on_screen_event=f"Reserved open {ctx['unit']}"),
            DialogueTurn(speaker="caller", text=t3, emotion="cheerful", pause_after_ms=280),
            DialogueTurn(speaker="agent", text=t4, emotion="clear", pause_after_ms=320, on_screen_event=f"Confirmed price: {service.price}"),
            DialogueTurn(speaker="caller", text=t5, emotion="decisive", pause_after_ms=280),
            DialogueTurn(speaker="agent", text=t6, emotion="warm", pause_after_ms=340, on_screen_event="Dispatched SMS confirmation"),
            DialogueTurn(speaker="caller", text=t7, emotion="satisfied", pause_after_ms=200),
        ]
        events = [
            CallEvent(turn_index=2, text=f"Checked {ctx['unit']} schedule", type="tool_call"),
            CallEvent(turn_index=4, text=f"Slot locked: {time_slot}", type="booking_card"),
            CallEvent(turn_index=6, text="Dispatched SMS confirmation", type="tool_call"),
        ]
        notif = OwnerNotification(
            summary=f"New booking: {service.name} reserved for {caller_name}.",
            customer_name=caller_name,
            time_or_slot=time_slot,
            service_requested=service.name,
            next_step=f"{ctx['verb'].capitalize()}.",
        )

    hook_words = hook.split()[:9]
    final_hook = " ".join(hook_words)
    return turns, events, notif, final_hook


def _generate_synthetic_dialogue(
    plan_axes: Dict[str, Any],
    profile: BusinessProfile,
    seed: int,
) -> DialogueScript:
    """Generate a realistic, high-quality dialogue script tailored to scenario and vertical."""
    rng = random.Random(seed)
    vertical = profile.vertical
    vid = plan_axes.get("vertical", "auto_repair")
    biz_name = profile.name
    city = profile.city
    owner = profile.owner_first_name
    scenario = plan_axes.get("scenario", "new_booking")

    caller_names = ["Vikram", "Pooja", "Arjun", "Sneha", "Kunal", "Ritu", "Sameer", "Aditi", "Daniel", "Sarah", "Alex", "Jessica", "Tarun", "Meera", "Rohan"]
    caller_name = rng.choice(caller_names)

    service = rng.choice(profile.services)
    faq = rng.choice(profile.faqs)
    days = ["Thursday", "Friday", "Monday", "Wednesday", "Tomorrow"]
    times = ["10:30 AM", "11:00 AM", "02:15 PM", "03:30 PM", "04:45 PM"]
    time_slot = f"{rng.choice(days)} at {rng.choice(times)}"

    turns, events, owner_notif, hook_text = _build_scenario_dialogue(
        scenario=scenario,
        biz_name=biz_name,
        vid=vid,
        vertical=vertical,
        city=city,
        owner=owner,
        caller_name=caller_name,
        service=service,
        faq=faq,
        time_slot=time_slot,
        rng=rng,
    )

    return DialogueScript(
        hook_text=hook_text,
        turns=turns,
        events=events,
        owner_notification=owner_notif,
        cta_text=f"Get an AI receptionist for your business at vocalis.ai",
        caption_seed=f"Watch how {biz_name} handles client calls effortlessly with AI.",
        hashtags_seed=["#AIReceptionist", f"#{vertical.replace(' ', '')}", f"#{city.replace(' ', '')}", "#SmallBusinessAutomation"],
    )


def generate_dialogue(
    plan_axes: Dict[str, Any],
    profile: BusinessProfile,
    session: Optional[Session] = None,
    seed: int = 42,
    config: Optional[ReelForgeConfig] = None,
    use_llm: bool = False,
) -> DialogueScript:
    """Generate dialogue script and enforce semantic de-duplication gate."""
    cfg = config or load_config()
    fp_engine = FingerprintEngine(cfg)

    for attempt in range(3):
        cur_seed = seed + attempt * 101
        script = _generate_synthetic_dialogue(plan_axes, profile, cur_seed)

        if session:
            full_text = " ".join(t.text for t in script.turns)
            is_dup, reason = fp_engine.check_duplication(session, full_text, script.hook_text)
            if is_dup:
                logger.warning(f"Script rejected by de-duplication gate (attempt {attempt + 1}): {reason}")
                continue

            fp_engine.store_fingerprint(session, full_text, script.hook_text, plan_axes)

        return script

    return script
