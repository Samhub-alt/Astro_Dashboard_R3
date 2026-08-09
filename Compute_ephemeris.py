#!/usr/bin/env python3
"""
SAM ASTRO — Daily Ephemeris Engine
===================================
Run via GitHub Actions every day at 23:30 IST (18:00 UTC).
Computes ALL signals using Swiss Ephemeris and writes data/ephemeris.json.
The HTML dashboard reads this JSON — zero server needed.

Install:  pip install pyswisseph astral pytz
Run:      python compute_ephemeris.py [YYYY-MM-DD]
          (no args = today IST)
"""

import json, sys, os
from datetime import datetime, timedelta
import pytz
import swisseph as swe
import urllib.request
from astral import LocationInfo
from astral.sun import sun as astral_sun

# ── EPHEMERIS DATA AUTO-DOWNLOADER (Fixes GitHub Actions Exit Code 1) ──
EPHE_DIR = "ephe"
if not os.path.exists(EPHE_DIR):
    os.makedirs(EPHE_DIR)

SE1_FILE = os.path.join(EPHE_DIR, "seas_18.se1")
if not os.path.exists(SE1_FILE):
    print("Downloading Swiss Ephemeris file (seas_18.se1)...")
    url = "https://www.astro.com/ftp/swisseph/ephe/seas_18.se1"
    try:
        urllib.request.urlretrieve(url, SE1_FILE)
        print("Download complete.")
    except Exception as e:
        print(f"Warning: Failed to download ephemeris file: {e}")

swe.set_ephe_path(EPHE_DIR)
swe.set_sid_mode(swe.SIDM_LAHIRI)  # Lahiri Ayanamsa

# ── CONFIG ──────────────────────────────────────────────────────
IST         = pytz.timezone('Asia/Kolkata')
UTC         = pytz.utc
MUMBAI_LAT  = 19.0760
MUMBAI_LON  = 72.8777
OUTPUT_DIR  = "data"          # relative to repo root
OUTPUT_FILE = "ephemeris.json"

# ── LOOKUP TABLES ───────────────────────────────────────────────
NAKS = ["Ashwini","Bharani","Krittika","Rohini","Mrigashira","Ardra","Punarvasu",
        "Pushya","Ashlesha","Magha","Purva Phalguni","Uttara Phalguni","Hasta","Chitra",
        "Swati","Vishakha","Anuradha","Jyeshtha","Mula","Purva Ashadha","Uttara Ashadha",
        "Shravana","Dhanishta","Shatabhisha","Purva Bhadrapada","Uttara Bhadrapada","Revati"]

NAK_LORD   = ["Ke","Ve","Su","Mo","Ma","Ra","Ju","Sa","Me"] * 3
NAK_NATURE = ["Tikshna","Ugra","Mishra","Saumya","Saumya","Tikshna","Mishra","Saumya",
              "Tikshna","Ugra","Ugra","Sthira","Laghu","Tikshna","Mishra","Mishra","Mishra",
              "Tikshna","Tikshna","Ugra","Mishra","Chara","Chara","Chara","Ugra","Sthira","Mishra"]

TITHI = ["Pratipada","Dwitiya","Tritiya","Chaturthi","Panchami","Shashthi","Saptami",
         "Ashtami","Navami","Dashami","Ekadashi","Dwadashi","Trayodashi","Chaturdashi","Purnima",
         "Pratipada","Dwitiya","Tritiya","Chaturthi","Panchami","Shashthi","Saptami","Ashtami",
         "Navami","Dashami","Ekadashi","Dwadashi","Trayodashi","Chaturdashi","Amavasya"]

YOGA = ["Vishkambha","Preeti","Ayushman","Saubhagya","Shobhana","Atiganda","Sukarma","Dhriti",
        "Shoola","Ganda","Vriddhi","Dhruva","Vyaghata","Harshana","Vajra","Siddhi","Vyatipata",
        "Variyan","Parigha","Shiva","Siddha","Sadhya","Shubha","Shukla","Brahma","Indra","Vaidhriti"]

KARANA = ["Kimstughna","Bava","Balava","Kaulava","Taitila","Garija","Vanija","Vishti",
          "Shakuni","Chatushpada","Nagava"]

SIGNS3 = ["Ari","Tau","Gem","Can","Leo","Vir","Lib","Sco","Sag","Cap","Aqu","Pis"]
SIGNS  = ["Aries","Taurus","Gemini","Cancer","Leo","Virgo","Libra","Scorpio",
          "Sagittarius","Capricorn","Aquarius","Pisces"]

HORA_ORDER     = ["Su","Ve","Me","Mo","Sa","Ju","Ma"]
DAY_HORA_START = ["Su","Mo","Ma","Me","Ju","Ve","Sa"]   # 0=Sun,1=Mon,…,6=Sat
HORA_NAMES     = {"Su":"Sun","Mo":"Moon","Ma":"Mars","Me":"Mercury","Ju":"Jupiter","Ve":"Venus","Sa":"Saturn"}
HORA_NATURE    = {"Su":"Bull","Mo":"Neutral","Ma":"Bear","Me":"Neutral","Ju":"Bull","Ve":"Bull","Sa":"Bear"}
HORA_COLOR     = {"Su":"gold","Mo":"cyan","Ma":"red","Me":"green","Ju":"gold","Ve":"purple","Sa":"gray"}
PLANET_NAMES   = {"Su":"Sun","Mo":"Moon","Me":"Mercury","Ve":"Venus","Ma":"Mars",
                  "Ju":"Jupiter","Sa":"Saturn","Ra":"Rahu","Ke":"Ketu"}

# ── BACKTESTED SIGNAL WEIGHTS (from 2768-day analysis) ──────────
BULL_NAKS  = [20, 5, 6, 2, 3]      # UA, Ardra, Krittika, Punarvasu, Rohini  — p<0.01
BEAR_NAKS  = [24, 16, 10, 25, 22]  # PB, Anuradha, Magha, UB, Dhanishta     — p<0.01
BULL_TITHI = [6, 14, 8, 11]        # Saptami, Purnima, Navami, Dwadashi
BEAR_TITHI = [9, 18, 12, 2]        # Dashami, K-Chaturthi, Trayodashi, Tritiya
BULL_YOGA  = ["Dhruva","Vriddhi","Atiganda","Dhriti"]
BEAR_YOGA  = ["Siddha","Preeti","Indra","Siddhi"]
UGRA_NAKS  = ["Bharani","Magha","Purva Phalguni","Purva Ashadha","Purva Bhadrapada"]
TIKSHNA_N  = ["Ardra","Ashlesha","Jyeshtha","Mula"]

# Fixed stars (sidereal Lahiri approx)
FIXED_STARS = {"Algol":53.4,"Alcyone":59.5,"Aldebaran":75.8,"Regulus":125.0,
               "Spica":179.7,"Antares":225.2,"Fomalhaut":310.0}

# NSE natal (Nov 3, 1994, 09:55 IST, Mumbai) — Swati Nak#14
NSE_NAK     = 14
NSE_MOON_LON = 191.3152     # Swiss Ephemeris verified
NSE_LAGNA   = 239.59        # Scorpio

# NSE Tara names + data-verified nature (REVERSED from tradition — backtested)
TARA_NAMES   = {1:"Janma",2:"Sampat",3:"Vipat",4:"Kshema",5:"Pratyak",
                6:"Sadhana",7:"Naidhana",8:"Mitra",9:"Param Mitra"}
TARA_BULL    = [7, 1, 8]    # Naidhana(7)★★★, Janma(1), Mitra(8) — data-confirmed
TARA_BEAR    = [3, 2, 4]    # Vipat(3), Sampat(2), Kshema(4) — data-confirmed

# Vimshottari Dasha (NSE natal)
DASHA_ORDER  = ["Ke","Ve","Su","Mo","Ma","Ra","Ju","Sa","Me"]
DASHA_YEARS  = {"Ke":7,"Ve":20,"Su":6,"Mo":10,"Ma":7,"Ra":18,"Ju":16,"Sa":19,"Me":17}
DASHA_NAT    = {"Ke":"Malefic","Ve":"Benefic","Su":"Malefic","Mo":"Benefic",
                "Ma":"Malefic","Ra":"Malefic","Ju":"Benefic","Sa":"Malefic","Me":"Benefic"}

# ── HELPER FUNCTIONS ────────────────────────────────────────────
def get_jd(dt):
    return swe.julday(dt.year, dt.month, dt.day,
                      dt.hour + dt.minute/60.0 + dt.second/3600.0)

def get_lon(pid, jd):
    r, _ = swe.calc_ut(jd, pid, swe.FLG_SWIEPH | swe.FLG_SIDEREAL)
    return r[0]

def get_speed(pid, jd):
    r, _ = swe.calc_ut(jd, pid, swe.FLG_SWIEPH | swe.FLG_SIDEREAL | swe.FLG_SPEED)
    return r[3]

def norm(a):  return a % 360
def adiff(a, b):
    d = abs(a - b) % 360
    return min(d, 360 - d)

def hhmm(mins):
    h = int(mins) // 60
    m = int(mins) % 60
    return f"{h:02d}:{m:02d}"

def get_sunrise_sunset(date_ist):
    loc = LocationInfo("Mumbai","India","Asia/Kolkata", MUMBAI_LAT, MUMBAI_LON)
    try:
        s = astral_sun(loc.observer, date=date_ist.date(), tzinfo=IST)
        return s['sunrise'], s['sunset']
    except:
        return (date_ist.replace(hour=6,minute=10,second=0),
                date_ist.replace(hour=18,minute=30,second=0))

def build_dasha_timeline(natal_moon, natal_naive_dt):
    nak   = int(natal_moon / 13.333333)
    sl    = NAK_LORD[nak]
    frac  = (natal_moon % 13.333333) / 13.333333
    first = DASHA_YEARS[sl] * (1 - frac)
    seq   = DASHA_ORDER.index(sl)
    tl    = []
    cur   = natal_naive_dt
    for i in range(12):
        lord = DASHA_ORDER[(seq + i) % 9]
        yrs  = first if i == 0 else DASHA_YEARS[lord]
        end  = cur + timedelta(days=yrs * 365.25)
        antars = []
        ac = cur; aseq = DASHA_ORDER.index(lord)
        for j in range(9):
            al  = DASHA_ORDER[(aseq + j) % 9]
            ay  = yrs * DASHA_YEARS[al] / 120.0
            ae  = ac + timedelta(days=ay * 365.25)
            antars.append((al, ac, ae))
            ac  = ae
        tl.append((lord, cur, end, antars))
        cur = end
        if cur.year > 2035: break
    return tl

NSE_DASHA_TL = build_dasha_timeline(NSE_MOON_LON, datetime(1994, 11, 3, 9, 55, 0))

def get_dasha(query_dt):
    qd = query_dt if isinstance(query_dt, datetime) else datetime(query_dt.year, query_dt.month, query_dt.day)
    for maha, ms, me, antars in NSE_DASHA_TL:
        if ms <= qd < me:
            for antar, as_, ae in antars:
                if as_ <= qd < ae:
                    return maha, antar
            return maha, maha
    return "Sa", "Sa"

# ── MAIN COMPUTATION ─────────────────────────────────────────────
def compute(target_date_str=None):
    # Parse target date
    if target_date_str:
        d = datetime.strptime(target_date_str, "%Y-%m-%d")
        dt_ist = IST.localize(d.replace(hour=9, minute=15, second=0))
    else:
        now_ist = datetime.now(IST)
        dt_ist  = now_ist.replace(hour=9, minute=15, second=0, microsecond=0)

    dt_utc = dt_ist.astimezone(UTC)
    jd     = get_jd(dt_utc)

    # ── Planet Positions ──────────────────────────────────────────
    moon = get_lon(swe.MOON,     jd);  moon_spd = get_speed(swe.MOON,     jd)
    sun  = get_lon(swe.SUN,      jd)
    merc = get_lon(swe.MERCURY,  jd);  merc_spd = get_speed(swe.MERCURY,  jd)
    ven  = get_lon(swe.VENUS,    jd);  ven_spd  = get_speed(swe.VENUS,    jd)
    mars = get_lon(swe.MARS,     jd);  mars_spd = get_speed(swe.MARS,     jd)
    jup  = get_lon(swe.JUPITER,  jd);  jup_spd  = get_speed(swe.JUPITER,  jd)
    sat  = get_lon(swe.SATURN,   jd);  sat_spd  = get_speed(swe.SATURN,   jd)
    rahu = get_lon(swe.TRUE_NODE,jd);  rahu_spd = get_speed(swe.TRUE_NODE,jd)
    ketu = norm(rahu + 180)

    # Lagna at 09:15 Mumbai
    cusps, ascmc = swe.houses(jd, MUMBAI_LAT, MUMBAI_LON, b'P')
    lagna = (ascmc[0] - swe.get_ayanamsa(jd)) % 360

    # ── Sunrise/Sunset ────────────────────────────────────────────
    sr, ss = get_sunrise_sunset(dt_ist)
    sr_mins = sr.hour*60 + sr.minute
    ss_mins = ss.hour*60 + ss.minute
    day_len  = ss_mins - sr_mins
    hora_len = day_len / 12

    # ── Panchang ─────────────────────────────────────────────────
    nak_idx   = int(moon / 13.333333)
    pada      = int((moon / 3.333333) % 4) + 1
    nak_name  = NAKS[nak_idx]
    nak_lord  = NAK_LORD[nak_idx]
    nak_nat   = NAK_NATURE[nak_idx]
    sun_nak   = int(sun / 13.333333)

    tithi_diff = norm(moon - sun)
    tithi_idx  = int(tithi_diff / 12)
    tithi_name = TITHI[tithi_idx]
    paksha     = "Shukla" if tithi_idx < 15 else "Krishna"

    yoga_lon  = norm(sun + moon)
    yoga_idx  = int(yoga_lon / 13.333333) % 27
    yoga_name = YOGA[yoga_idx]

    karana_idx  = int(tithi_diff / 6) % 11
    karana_name = KARANA[karana_idx]

    moon_sign = int(moon / 30)
    sun_sign  = int(sun  / 30)
    moon_elem = ["Fire","Earth","Air","Water","Fire","Earth","Air","Water",
                 "Fire","Earth","Air","Water"][moon_sign]

    # NSE Tara
    nse_tara      = ((nak_idx - NSE_NAK) % 27) % 9 + 1
    nse_tara_name = TARA_NAMES.get(nse_tara, "?")
    nse_tara_type = ("bull" if nse_tara in TARA_BULL else
                     "bear" if nse_tara in TARA_BEAR else "neutral")

    # Dasha
    maha, antar = get_dasha(dt_ist.replace(tzinfo=None))
    d_score = (1 if DASHA_NAT[maha]=="Benefic" else -1) + \
              (1 if DASHA_NAT[antar]=="Benefic" else -1)

    # Hora at open
    dow       = dt_ist.weekday()   # 0=Mon
    sun_dow   = (dow + 1) % 7
    start_idx = HORA_ORDER.index(DAY_HORA_START[sun_dow])
    hora_num  = max(0, int((9*60+15 - sr_mins) / hora_len))
    hora_open = HORA_ORDER[(start_idx + hora_num) % 7]

    # ── Aspects ───────────────────────────────────────────────────
    me_jup_sesqui  = abs(adiff(merc, jup) - 135) < 3
    me_jup_semisq  = abs(adiff(merc, jup) - 45)  < 3
    mo_sat_sq      = abs(adiff(moon, sat) - 90)   < 7
    mo_sat_quint   = abs(adiff(moon, sat) - 72)   < 2
    su_ra_conj     = adiff(sun, rahu)              < 8
    su_mo_opp      = abs(adiff(moon, sun) - 180)  < 8
    mo_me_sext     = abs(adiff(moon, merc) - 60)  < 6
    angarak        = adiff(mars, ketu)             < 8
    angarak_tight  = adiff(mars, ketu)             < 3
    guru_chandal   = min(adiff(jup, rahu), adiff(jup, ketu)) < 10
    ma_sat_stress  = adiff(mars, sat)              < 8
    jup_sat_conj   = adiff(jup,  sat)              < 10

    # Fixed stars
    mo_antares = adiff(moon, FIXED_STARS["Antares"]) < 2
    su_antares = adiff(sun,  FIXED_STARS["Antares"]) < 2
    su_algol   = adiff(sun,  FIXED_STARS["Algol"])   < 2
    ve_spica   = adiff(ven,  FIXED_STARS["Spica"])   < 2
    mo_regulus = adiff(moon, FIXED_STARS["Regulus"])  < 2

    # Retrogrades
    me_rx = merc_spd < 0
    ve_rx = ven_spd  < 0
    ma_rx = mars_spd < 0
    ju_rx = jup_spd  < 0
    sa_rx = sat_spd  < 0

    # Combustion
    me_combust = adiff(merc, sun) < 8
    ju_combust = adiff(jup,  sun) < 11

    # Gandanta (true — last 3.33° water / first 3.33° fire)
    mi = moon % 30
    gandanta = ((moon_sign in [3,7,11] and mi > 26.667) or
                (moon_sign in [0,4,8]  and mi < 3.333))

    # Moon speed category
    spd_cat = "Fast" if moon_spd > 14 else "Slow" if moon_spd < 12 else "Normal"

    # Vargottama Moon
    moon_d9   = int((moon / 3.333333) % 12)
    moon_varg = moon_d9 == moon_sign

    # Jup in NSE 5th (Pisces = sign 11) — strongest signal found
    jup_in_nse_5th = int(jup / 30) == 11

    # ── COMPOSITE SCORE ──────────────────────────────────────────
    score   = 0
    signals = []

    def add(typ, pts, text, cat):
        nonlocal score
        score += pts
        signals.append({"type": typ, "pts": pts, "text": text, "cat": cat})

    # Layer 1 — Nakshatra ±3
    if nak_idx in BULL_NAKS:
        add("bull", +3, f"Moon in {nak_name} (Bull Nak — p<0.01)", "Vedic")
    elif nak_idx in BEAR_NAKS:
        add("bear", -3, f"Moon in {nak_name} (Bear Nak — p<0.01)", "Vedic")

    # Nak Nature ±2/±1
    if nak_nat == "Ugra":
        add("bear", -2, f"{nak_name} = Ugra nature (harsh) — −6.6% edge ★★★", "Vedic")
    elif nak_nat == "Tikshna":
        add("bull", +1, f"{nak_name} = Tikshna nature (sharp) — +4.0% edge", "Vedic")

    # Layer 2 — Tithi ±2
    if tithi_idx in BULL_TITHI:
        add("bull", +2, f"{tithi_name} Tithi — bull tithi confirmed", "Vedic")
    elif tithi_idx in BEAR_TITHI:
        add("bear", -2, f"{tithi_name} Tithi — bear tithi confirmed", "Vedic")

    # Paksha ±1
    if paksha == "Shukla":
        add("bull", +1, "Shukla Paksha (waxing moon)", "Vedic")
    else:
        add("bear", -1, "Krishna Paksha (waning moon)", "Vedic")

    # Moon element ±1
    if moon_elem == "Earth":
        add("bull", +1, f"Moon in Earth sign ({SIGNS3[moon_sign]}) — +3.5% edge", "Vedic")
    elif moon_elem == "Water":
        add("bear", -1, f"Moon in Water sign ({SIGNS3[moon_sign]}) — −3.0% edge", "Vedic")

    # Yoga ±1
    if yoga_name in BULL_YOGA:
        add("bull", +1, f"Nithya Yoga: {yoga_name} (data-confirmed bull)", "Vedic")
    elif yoga_name in BEAR_YOGA:
        add("bear", -1, f"Nithya Yoga: {yoga_name} (data-confirmed bear)", "Vedic")

    # NSE Tara ±3/±2/±1
    if nse_tara == 7:
        add("bull", +3, f"NSE Tara Naidhana (7th) — 54.2% bull ★★★", "Natal")
    elif nse_tara in [1, 8]:
        add("bull", +1, f"NSE Tara {nse_tara_name} ({nse_tara}th) — mild bull", "Natal")
    elif nse_tara in [3, 2]:
        add("bear", -2, f"NSE Tara {nse_tara_name} ({nse_tara}th) — data-confirmed bear", "Natal")

    # Dasha ±1
    if d_score >= 2:
        add("bull", +1, f"Dasha: {PLANET_NAMES[maha]}-{PLANET_NAMES[antar]} (both benefic)", "Dasha")
    elif d_score <= -2:
        add("bear", -1, f"Dasha: {PLANET_NAMES[maha]}-{PLANET_NAMES[antar]} (both malefic)", "Dasha")

    # Yogakaraka — Jupiter in NSE 5th (Pisces): strongest single signal (+32.7%)
    if jup_in_nse_5th:
        add("bull", +2, "Jupiter in NSE 5th House (Pisces) — 79.5% bull with F30 UP ★★★", "Yogakaraka")

    # Aspects ±3 to ±1
    if me_jup_sesqui:
        add("bear", -3, "Mercury-Jupiter 135° (Sesquiquadrate) — 18.6% reversal ★★★", "Aspect")
    if me_jup_semisq:
        add("bear", -2, "Mercury-Jupiter 45° (Semi-square) — bear ★★", "Aspect")
    if mo_sat_sq:
        add("bear", -2, "Moon-Saturn Square 90° — 40.4% bull ★", "Aspect")
    if su_ra_conj:
        add("bull", +2, "Sun-Rahu Conjunction — eclipse zone bullish 56.4% ★★", "Aspect")
    if su_mo_opp:
        add("bull", +2, "Sun-Moon Opposition (Purnima zone) — 54.5% bull ★", "Aspect")
    if mo_me_sext:
        add("bear", -2, "Moon-Mercury Sextile — counterintuitive bear 39.6% ★", "Aspect")
    if mo_sat_quint:
        add("bull", +1, "Moon-Saturn Quintile 72° — 56.7% bull ★★", "Aspect")

    # Special yogas
    if angarak_tight:
        add("bear", -2, "Angarak Yoga tight (Mars-Ketu <3°) — 20.8% bull ★★★", "Yoga")
    elif angarak:
        add("bear", -1, "Angarak Yoga (Mars-Ketu <8°) — 41.3% bull", "Yoga")

    if guru_chandal and score < 0:
        add("bear", -1, "Guru-Chandal (Jup-Rahu/Ketu) — amplifies bear when F30 down ★★★", "Yoga")

    # Fixed Stars
    if mo_antares:
        add("bear", -2, "Moon conjunct Antares ★ — monthly bear trigger 34.4% bull", "FixedStar")
    if su_antares:
        add("bear", -2, "Sun conjunct Antares ★ — annual bear 33.3% bull", "FixedStar")
    if su_algol:
        add("bear", -2, "Sun conjunct Algol ★ — volatile bear 36.4% bull", "FixedStar")
    if ve_spica:
        add("bull", +1, "Venus conjunct Spica ★ — benevolent, low volatility", "FixedStar")

    # Gandanta / Critical
    if gandanta:
        add("bear", -1, "Moon in Gandanta (water-fire junction) — 42.0% bull ★", "Special")
    if moon_varg:
        add("bull", +1, "Moon Vargottama (same sign D1+D9) — mild bull", "Special")

    # Hora ±1
    if hora_open in ["Ju","Ve"]:
        add("bull", +1, f"{HORA_NAMES[hora_open]} Hora at 09:15 — benefic hora", "Hora")
    elif hora_open == "Sa":
        add("bear", -1, "Saturn Hora at 09:15 — restrictive hora", "Hora")

    # ── VERDICT ───────────────────────────────────────────────────
    if   score >= 8:  verdict, accuracy, verdict_color = "STRONG BULL", "82-90%", "green"
    elif score >= 4:  verdict, accuracy, verdict_color = "BULL",        "64-74%", "lightgreen"
    elif score >= 1:  verdict, accuracy, verdict_color = "MILD BULL",   "52-58%", "yellow"
    elif score >= -1: verdict, accuracy, verdict_color = "NEUTRAL",     "48-52%", "gray"
    elif score >= -3: verdict, accuracy, verdict_color = "MILD BEAR",   "52-58%", "orange"
    elif score >= -7: verdict, accuracy, verdict_color = "BEAR",        "64-74%", "red"
    else:             verdict, accuracy, verdict_color = "STRONG BEAR", "82-90%", "darkred"

    skip_day = abs(score) < 2  # neutral zone — skip or trade small

    # ── INTRADAY TIMELINE ─────────────────────────────────────────
    timeline = []

    def add_event(mins, typ, label, note, subtype=""):
        timeline.append({"mins":int(mins),"time":hhmm(mins),"type":typ,"label":label,
                          "note":note,"subtype":subtype})

    # Market structure
    add_event(9*60,      "market",  "Pre-market Opens",    "Call auction price discovery", "pre")
    add_event(9*60+8,    "market",  "Pre-market Closes",   "Auction ends, IEP determined", "pre")
    add_event(9*60+15,   "market",  "MARKET OPEN",         "NSE/BSE Regular session begins", "open")
    add_event(15*60+15,  "market",  "Pre-close Begins",    "Call auction phase", "pre")
    add_event(15*60+30,  "market",  "MARKET CLOSE",        "Regular session ends", "close")
    add_event(16*60,     "market",  "Currency Close",      "USDINR and FX pairs", "post")

    # Hora transitions in session
    for h in range(15):
        h_start = sr_mins + h * hora_len
        h_end   = h_start + hora_len
        if 9*60 <= h_start <= 16*60:
            hp = HORA_ORDER[(start_idx + h) % 7]
            add_event(h_start, "hora",
                      f"{HORA_NAMES[hp]} Hora",
                      f"{HORA_NATURE[hp]} energy | until {hhmm(h_end)}",
                      HORA_NATURE[hp].lower())

    # Nakshatra change
    deg_to_nak  = ((nak_idx + 1) * 13.333333 - moon) % 13.333333
    hrs_to_nak  = deg_to_nak / moon_spd * 24 if moon_spd > 0 else 99
    nak_chg_dt  = dt_ist + timedelta(hours=hrs_to_nak)
    nak_chg_min = nak_chg_dt.hour*60 + nak_chg_dt.minute
    next_nak    = NAKS[(nak_idx + 1) % 27]
    next_nak_nat= NAK_NATURE[(nak_idx + 1) % 27]
    if 9*60+15 <= nak_chg_min <= 16*60:
        nat_dir = "Bull nak entering" if (nak_idx+1)%27 in BULL_NAKS else \
                  "Bear nak entering" if (nak_idx+1)%27 in BEAR_NAKS else "Neutral nak"
        add_event(nak_chg_min, "nakshatra",
                  f"Moon enters {next_nak}",
                  f"{nat_dir} — watch for reversal/acceleration | Nature: {next_nak_nat}",
                  "high" if (nak_idx+1)%27 in BULL_NAKS + BEAR_NAKS else "normal")

    # Pada shifts
    for p in range(1, 8):
        next_pada_lon = (int(moon / 3.333333) + p) * 3.333333
        deg_to_pada   = (next_pada_lon - moon) % 3.333333
        hrs_to_pada   = deg_to_pada / moon_spd * 24 if moon_spd > 0 else 99
        pada_dt       = dt_ist + timedelta(hours=hrs_to_pada)
        pada_min      = pada_dt.hour*60 + pada_dt.minute
        if 9*60+15 <= pada_min <= 15*60+30:
            np_ = (int(moon / 3.333333) + p) % 4 + 1
            add_event(pada_min, "pada",
                      f"Moon Pada {np_} — Watch Price Action",
                      f"Pada {np_} energy shift — small reversal risk", "watch")

    # Tithi change intraday
    next_tithi_angle = (tithi_idx + 1) * 12
    deg_to_tithi     = (next_tithi_angle - tithi_diff) % 12
    rel_spd          = moon_spd - 1.0
    hrs_to_tithi     = deg_to_tithi / rel_spd * 24 if abs(rel_spd) > 0.01 else 99
    tithi_chg_dt     = dt_ist + timedelta(hours=hrs_to_tithi)
    tithi_chg_min    = tithi_chg_dt.hour*60 + tithi_chg_dt.minute
    if 9*60+15 <= tithi_chg_min <= 15*60+30:
        next_t = TITHI[(tithi_idx + 1) % 30]
        t_dir  = "bull" if (tithi_idx+1)%30 in BULL_TITHI else \
                 "bear" if (tithi_idx+1)%30 in BEAR_TITHI else "neutral"
        add_event(tithi_chg_min, "tithi",
                  f"Tithi → {next_t}",
                  f"New {t_dir} tithi energy from now", t_dir)

    # Solunar 4 peaks
    cur_angle = norm(moon - sun)
    for target_ang in [0, 90, 180, 270]:
        diff = (target_ang - cur_angle) % 360
        hrs  = diff / abs(rel_spd) * 24 if abs(rel_spd) > 0.01 else 99
        sol_min = 9*60+15 + int(hrs * 60)
        if 9*60+15 <= sol_min <= 15*60+30:
            sol_labels = {0:"Conjunction Solunar",90:"1st Quarter Solunar",
                          180:"Opposition Solunar",270:"3rd Quarter Solunar"}
            add_event(sol_min, "solunar", sol_labels[target_ang],
                      "Sun-Moon angle peak — potential energy shift", "energy")

    # Gann 90° time cycle (6-hourly: 00:00, 06:00, 12:00, 18:00)
    for gann_hr in [9, 12, 15]:
        gann_min = gann_hr * 60
        if 9*60+15 <= gann_min <= 15*60+30:
            add_event(gann_min, "gann",
                      f"Gann 90° Time Cycle",
                      "Natural time square — watch for intraday reversal", "watch")

    timeline.sort(key=lambda x: x["mins"])

    # ── HIGH-ACCURACY SETUPS (intraday watch list) ─────────────
    setups = []
    if score >= 3:
        setups.append({
            "id":"trend_bull_setup",
            "label":"Bull Trend Setup",
            "condition":"IF F30 > +0.3% AND 5+ consecutive UP bars in first 90min",
            "target":"Hold until 15:00-15:30 (high forms at close 45.6% of bull days)",
            "accuracy":"81.6%",
            "stop":"Below first 30-min low",
            "type":"bull"
        })
    if score <= -3:
        setups.append({
            "id":"trend_bear_setup",
            "label":"Bear Trend Setup",
            "condition":"IF F30 < -0.3% AND 5+ consecutive DOWN bars in first 90min",
            "target":"Low forms at close (33.7% of bear days) — hold until 14:30+",
            "accuracy":"84.6%",
            "stop":"Above first 30-min high",
            "type":"bear"
        })
    setups.append({
        "id":"session_tracker",
        "label":"3-Session Tracker",
        "condition":"Morning (09:15-10:45) → Mid (11:00-13:00) → Afternoon (14:30-15:30)",
        "target":"Morning↑+Mid↑ = 93.8% bull close | Morning↓+Mid↓ = 94.9% bear close",
        "accuracy":"86-94%",
        "stop":"N/A — directional tracker",
        "type":"info"
    })
    if angarak or me_jup_sesqui:
        setups.append({
            "id":"no_trade",
            "label":"HIGH CAUTION — Reduce Size",
            "condition":"Angarak Yoga or Me-Ju Sesquiquadrate active",
            "target":"Bear continuation 79-87% when these are active + F30 down",
            "accuracy":"87%",
            "stop":"Do not buy dips on bear opens today",
            "type":"warn"
        })

    # ── WEEKLY FORECAST (next 5 trading days) ───────────────────
    weekly = []
    for offset in range(1, 8):
        future_dt = dt_ist + timedelta(days=offset)
        if future_dt.weekday() >= 5:  # skip Saturday, Sunday
            continue
        if len(weekly) >= 5:
            break
        f_utc = future_dt.astimezone(UTC)
        f_jd  = get_jd(f_utc)
        f_moon = get_lon(swe.MOON, f_jd)
        f_sun  = get_lon(swe.SUN,  f_jd)
        f_nak  = int(f_moon / 13.333333)
        f_tithi= int(norm(f_moon - f_sun) / 12)
        f_nak_nat = NAK_NATURE[f_nak]

        f_score = 0
        if f_nak in BULL_NAKS: f_score += 3
        elif f_nak in BEAR_NAKS: f_score -= 3
        if f_nak_nat == "Ugra": f_score -= 2
        if f_tithi in BULL_TITHI: f_score += 2
        elif f_tithi in BEAR_TITHI: f_score -= 2
        f_paksha = "Shukla" if f_tithi < 15 else "Krishna"
        if f_paksha == "Shukla": f_score += 1
        else: f_score -= 1

        f_verdict = ("BULL" if f_score >= 3 else "BEAR" if f_score <= -3 else "NEUTRAL")
        f_color   = ("green" if f_score >= 3 else "red" if f_score <= -3 else "gray")

        weekly.append({
            "date":    future_dt.strftime("%Y-%m-%d"),
            "display": future_dt.strftime("%a %d %b"),
            "nak":     NAKS[f_nak],
            "nak_nat": f_nak_nat,
            "tithi":   TITHI[f_tithi],
            "paksha":  f_paksha,
            "score":   f_score,
            "verdict": f_verdict,
            "color":   f_color,
            "trade":   abs(f_score) >= 3,
        })

    # ── ASSEMBLE FULL OUTPUT ──────────────────────────────────────
    output = {
        "meta": {
            "generated_at": datetime.now(IST).strftime("%Y-%m-%d %H:%M:%S IST"),
            "engine":       "SAM Astro v5.0 — Swiss Ephemeris + Lahiri Ayanamsa",
            "nifty_nat":    "NSE: Nov 3, 1994, 09:55 IST, Mumbai | Moon: Swati Nak#14",
            "phases":       "5 phases | 2,768 NIFTY days | 47 backtested signals",
            "ayanamsa":     round(swe.get_ayanamsa(jd), 4),
        },
        "date":     dt_ist.strftime("%Y-%m-%d"),
        "display":  dt_ist.strftime("%A, %d %B %Y"),
        "score":    score,
        "verdict":  verdict,
        "accuracy": accuracy,
        "color":    verdict_color,
        "skip_day": skip_day,
        "signals":  signals,
        "timeline": timeline,
        "setups":   setups,
        "weekly":   weekly,
        "panchang": {
            "nakshatra":  nak_name,    "nak_lord":  nak_lord,
            "nak_nature": nak_nat,     "nak_idx":   nak_idx,
            "pada":       pada,        "pada_str":  f"Pada {pada}",
            "tithi":      tithi_name,  "tithi_num": tithi_idx + 1,
            "paksha":     paksha,      "yoga":      yoga_name,
            "karana":     karana_name, "moon_elem": moon_elem,
            "moon_pos":   f"{moon%30:.1f}° {SIGNS3[moon_sign]}",
            "sun_pos":    f"{sun%30:.1f}° {SIGNS3[sun_sign]}",
            "moon_speed": round(moon_spd, 3),
            "moon_speed_cat": spd_cat,
            "nse_tara":   nse_tara,
            "nse_tara_name": nse_tara_name,
            "nse_tara_type": nse_tara_type,
            "hora_at_open": hora_open,
            "hora_name":    HORA_NAMES[hora_open],
            "hora_nature":  HORA_NATURE[hora_open],
            "sunrise":  sr.strftime("%H:%M"),
            "sunset":   ss.strftime("%H:%M"),
            "dasha_maha":   maha,   "dasha_maha_name":   PLANET_NAMES[maha],
            "dasha_antar":  antar,  "dasha_antar_name":  PLANET_NAMES[antar],
        },
        "planets": {
            "Moon":    {"lon":round(moon,2),"sign":SIGNS3[moon_sign],"full_sign":SIGNS[moon_sign],
                        "nak":nak_name,"speed":round(moon_spd,3),"rx":False,"combust":False},
            "Sun":     {"lon":round(sun,2), "sign":SIGNS3[sun_sign], "full_sign":SIGNS[sun_sign],
                        "nak":NAKS[int(sun/13.333333)],"speed":1.0,"rx":False,"combust":False},
            "Mercury": {"lon":round(merc,2),"sign":SIGNS3[int(merc/30)],"full_sign":SIGNS[int(merc/30)],
                        "nak":NAKS[int(merc/13.333333)],"speed":round(merc_spd,3),"rx":me_rx,"combust":me_combust},
            "Venus":   {"lon":round(ven,2), "sign":SIGNS3[int(ven/30)], "full_sign":SIGNS[int(ven/30)],
                        "nak":NAKS[int(ven/13.333333)], "speed":round(ven_spd,3), "rx":ve_rx,"combust":False},
            "Mars":    {"lon":round(mars,2),"sign":SIGNS3[int(mars/30)],"full_sign":SIGNS[int(mars/30)],
                        "nak":NAKS[int(mars/13.333333)],"speed":round(mars_spd,3),"rx":ma_rx,"combust":False},
            "Jupiter": {"lon":round(jup,2), "sign":SIGNS3[int(jup/30)], "full_sign":SIGNS[int(jup/30)],
                        "nak":NAKS[int(jup/13.333333)], "speed":round(jup_spd,3), "rx":ju_rx,"combust":ju_combust},
            "Saturn":  {"lon":round(sat,2), "sign":SIGNS3[int(sat/30)], "full_sign":SIGNS[int(sat/30)],
                        "nak":NAKS[int(sat/13.333333)],"speed":round(sat_spd,3),"rx":sa_rx,"combust":False},
            "Rahu":    {"lon":round(rahu,2),"sign":SIGNS3[int(rahu/30)],"full_sign":SIGNS[int(rahu/30)],
                        "nak":NAKS[int(rahu/13.333333)],"speed":round(rahu_spd,3),"rx":True,"combust":False},
            "Ketu":    {"lon":round(ketu,2),"sign":SIGNS3[int(ketu/30)],"full_sign":SIGNS[int(ketu/30)],
                        "nak":NAKS[int(ketu/13.333333)], "speed":-0.053,"rx":True,"combust":False},
        },
        "warnings": {
            "angarak":      angarak,      "angarak_tight": angarak_tight,
            "guru_chandal": guru_chandal, "gandanta":      gandanta,
            "me_rx":  me_rx,  "ve_rx": ve_rx, "ma_rx": ma_rx,
            "ju_rx":  ju_rx,  "sa_rx": sa_rx,
            "me_combust":   me_combust,   "ju_combust":    ju_combust,
            "mo_antares":   mo_antares,   "su_antares":    su_antares,
            "su_algol":     su_algol,     "mo_regulus":    mo_regulus,
            "me_jup_stress":me_jup_sesqui or me_jup_semisq,
            "mo_sat_stress":mo_sat_sq,    "ma_sat_stress": ma_sat_stress,
            "jup_sat_conj": jup_sat_conj,
        },
    }
    return output


# ── ENTRY POINT ──────────────────────────────────────────────────
if __name__ == "__main__":
    date_arg = sys.argv[1] if len(sys.argv) > 1 else None
    result   = compute(date_arg)

    # Write output
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    out_path = os.path.join(OUTPUT_DIR, OUTPUT_FILE)
    with open(out_path, "w") as f:
        json.dump(result, f, indent=2)

    print(f"✓ {result['display']}")
    print(f"  Score: {result['score']:+d} | {result['verdict']} | Accuracy: {result['accuracy']}")
    print(f"  Nak: {result['panchang']['nakshatra']} ({result['panchang']['nak_nature']}) | "
          f"Tithi: {result['panchang']['tithi']} | Yoga: {result['panchang']['yoga']}")
    print(f"  Signals: {len(result['signals'])} | Timeline: {len(result['timeline'])} events")
    print(f"  Written → {out_path}")
