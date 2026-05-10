from __future__ import annotations

from typing import Any

from .role_catalog import get_sector_options


COUNTRY_REGIONS: dict[str, list[str]] = {
    "United States": [
        "Alabama", "Alaska", "Arizona", "Arkansas", "California", "Colorado", "Connecticut",
        "Delaware", "Florida", "Georgia", "Hawaii", "Idaho", "Illinois", "Indiana", "Iowa",
        "Kansas", "Kentucky", "Louisiana", "Maine", "Maryland", "Massachusetts", "Michigan",
        "Minnesota", "Mississippi", "Missouri", "Montana", "Nebraska", "Nevada",
        "New Hampshire", "New Jersey", "New Mexico", "New York", "North Carolina",
        "North Dakota", "Ohio", "Oklahoma", "Oregon", "Pennsylvania", "Rhode Island",
        "South Carolina", "South Dakota", "Tennessee", "Texas", "Utah", "Vermont",
        "Virginia", "Washington", "West Virginia", "Wisconsin", "Wyoming", "District of Columbia",
    ],
    "Canada": [
        "Alberta", "British Columbia", "Manitoba", "New Brunswick", "Newfoundland and Labrador",
        "Northwest Territories", "Nova Scotia", "Nunavut", "Ontario", "Prince Edward Island",
        "Quebec", "Saskatchewan", "Yukon",
    ],
    "Australia": [
        "Australian Capital Territory", "New South Wales", "Northern Territory", "Queensland",
        "South Australia", "Tasmania", "Victoria", "Western Australia",
    ],
    "New Zealand": [
        "Auckland", "Bay of Plenty", "Canterbury", "Gisborne", "Hawke's Bay", "Manawatu-Whanganui",
        "Marlborough", "Nelson", "Northland", "Otago", "Southland", "Taranaki",
        "Tasman", "Waikato", "Wellington", "West Coast",
    ],
    "United Kingdom": ["England", "Scotland", "Wales", "Northern Ireland"],
    "Ireland": ["Connacht", "Leinster", "Munster", "Ulster"],
    "Germany": ["Bavaria", "Berlin", "Brandenburg", "Hamburg", "Hesse", "Lower Saxony", "North Rhine-Westphalia", "Saxony", "Baden-Wurttemberg"],
    "France": ["Auvergne-Rhone-Alpes", "Brittany", "Grand Est", "Hauts-de-France", "Ile-de-France", "Normandy", "Nouvelle-Aquitaine", "Occitanie", "Pays de la Loire", "Provence-Alpes-Cote d'Azur"],
    "Netherlands": ["Drenthe", "Flevoland", "Friesland", "Gelderland", "Groningen", "Limburg", "North Brabant", "North Holland", "Overijssel", "South Holland", "Utrecht", "Zeeland"],
    "Belgium": ["Brussels-Capital", "Flanders", "Wallonia"],
    "Luxembourg": ["Diekirch", "Grevenmacher", "Luxembourg"],
    "Switzerland": ["Aargau", "Basel", "Bern", "Geneva", "Lucerne", "St. Gallen", "Ticino", "Vaud", "Zurich"],
    "Austria": ["Burgenland", "Carinthia", "Lower Austria", "Salzburg", "Styria", "Tyrol", "Upper Austria", "Vienna", "Vorarlberg"],
    "Sweden": ["Blekinge", "Gotland", "Halland", "Jonkoping", "Norrbotten", "Skane", "Stockholm", "Uppsala", "Vasterbotten", "Vastra Gotaland"],
    "Norway": ["Agder", "Innlandet", "More og Romsdal", "Nordland", "Oslo", "Rogaland", "Troms og Finnmark", "Trondelag", "Vestfold og Telemark", "Vestland", "Viken"],
    "Denmark": ["Capital Region", "Central Denmark", "North Denmark", "Region Zealand", "Southern Denmark"],
    "Finland": ["Central Finland", "Kanta-Hame", "Lapland", "North Ostrobothnia", "Pirkanmaa", "Southwest Finland", "Uusimaa"],
    "Spain": ["Andalusia", "Aragon", "Basque Country", "Canary Islands", "Catalonia", "Galicia", "Madrid", "Valencian Community"],
    "Portugal": ["Alentejo", "Algarve", "Centro", "Lisbon", "Madeira", "North"],
    "Italy": ["Campania", "Emilia-Romagna", "Lazio", "Lombardy", "Piedmont", "Sardinia", "Sicily", "Tuscany", "Veneto"],
    "Poland": ["Dolnoslaskie", "Lodzkie", "Lubelskie", "Malopolskie", "Mazowieckie", "Pomorskie", "Slaskie", "Wielkopolskie"],
    "Czechia": ["Central Bohemian", "Moravian-Silesian", "Pilsen", "Prague", "South Moravian", "Usti nad Labem"],
    "Hungary": ["Budapest", "Bacs-Kiskun", "Baranya", "Borsod-Abauj-Zemplen", "Fejer", "Pest"],
    "Romania": ["Bucharest", "Cluj", "Constanta", "Iasi", "Sibiu", "Timis"],
    "Greece": ["Attica", "Central Macedonia", "Crete", "Peloponnese", "South Aegean", "Thessaly"],
    "Turkey": ["Ankara", "Antalya", "Bursa", "Istanbul", "Izmir", "Kocaeli"],
    "United Arab Emirates": ["Abu Dhabi", "Ajman", "Dubai", "Fujairah", "Ras Al Khaimah", "Sharjah"],
    "Saudi Arabia": ["Eastern Province", "Makkah", "Madinah", "Riyadh"],
    "Qatar": ["Doha", "Al Rayyan", "Al Wakrah", "Umm Salal"],
    "Singapore": ["Central Region", "East Region", "North East Region", "North Region", "West Region"],
    "Malaysia": ["Johor", "Kedah", "Kuala Lumpur", "Penang", "Sabah", "Sarawak", "Selangor"],
    "Indonesia": ["Bali", "Banten", "East Java", "Jakarta", "Riau Islands", "West Java", "Yogyakarta"],
    "Philippines": ["Calabarzon", "Central Luzon", "Central Visayas", "Davao", "Metro Manila", "Western Visayas"],
    "India": ["Andhra Pradesh", "Delhi", "Gujarat", "Karnataka", "Kerala", "Maharashtra", "Tamil Nadu", "Telangana", "Uttar Pradesh", "West Bengal"],
    "Pakistan": ["Balochistan", "Islamabad Capital Territory", "Khyber Pakhtunkhwa", "Punjab", "Sindh"],
    "Japan": ["Aichi", "Fukuoka", "Hokkaido", "Hyogo", "Kanagawa", "Kyoto", "Osaka", "Tokyo"],
    "South Korea": ["Busan", "Daegu", "Daejeon", "Gyeonggi", "Incheon", "Seoul"],
    "Taiwan": ["Kaohsiung", "New Taipei", "Taichung", "Tainan", "Taipei"],
    "Hong Kong": ["Hong Kong Island", "Kowloon", "New Territories"],
    "China": ["Beijing", "Chongqing", "Guangdong", "Jiangsu", "Shanghai", "Sichuan", "Zhejiang"],
    "Thailand": ["Bangkok", "Chiang Mai", "Chonburi", "Khon Kaen", "Phuket"],
    "Vietnam": ["Da Nang", "Hai Phong", "Ha Noi", "Ho Chi Minh City"],
    "Mexico": ["Baja California", "Chihuahua", "Jalisco", "Mexico City", "Nuevo Leon", "Queretaro"],
    "Brazil": ["Bahia", "Distrito Federal", "Minas Gerais", "Parana", "Rio de Janeiro", "Rio Grande do Sul", "Sao Paulo"],
    "Argentina": ["Buenos Aires", "Cordoba", "Mendoza", "Santa Fe"],
    "Chile": ["Antofagasta", "Bio-Bio", "Metropolitan Region", "Valparaiso"],
    "Colombia": ["Antioquia", "Bogota", "Cundinamarca", "Valle del Cauca"],
    "South Africa": ["Eastern Cape", "Gauteng", "KwaZulu-Natal", "Western Cape"],
    "Nigeria": ["Abuja FCT", "Kano", "Lagos", "Rivers"],
    "Egypt": ["Alexandria", "Cairo", "Giza", "Red Sea"],
}


COMPANY_RANKING_OPTIONS: list[dict[str, str]] = [
    {"value": "any", "label": "Any company"},
    {"value": "fortune_1_50", "label": "Fortune 1-50"},
    {"value": "fortune_1_100", "label": "Fortune 1-100"},
    {"value": "fortune_1_500", "label": "Fortune 1-500"},
    {"value": "non_fortune", "label": "Non-Fortune / Other Companies"},
]

WORK_AUTHORIZATION_OPTIONS = [
    "Prefer not to answer",
    "U.S. Citizen",
    "Permanent Resident / Green Card",
    "Naturalized Citizen",
    "Refugee / Asylee",
    "Employment Authorization Document (EAD)",
    "F-1 CPT",
    "F-1 OPT",
    "F-1 STEM OPT",
    "H-1B",
    "H-4 EAD",
    "L-1",
    "L-2 EAD",
    "O-1",
    "TN Visa",
    "E-3 Visa",
    "J-1 Visa",
    "J-2 EAD",
    "Dependent Visa Holder",
    "Need Sponsorship",
    "Authorized to work in Canada",
    "Authorized to work in United Kingdom",
    "Authorized to work in Australia",
    "Authorized to work in New Zealand",
]

VETERAN_STATUS_OPTIONS = [
    "Prefer not to answer",
    "Not a veteran",
    "Veteran",
    "Protected veteran",
    "Recently separated veteran",
    "Active duty wartime or campaign badge veteran",
    "Armed forces service medal veteran",
    "Disabled veteran",
]

RACE_ETHNICITY_OPTIONS = [
    "Prefer not to answer",
    "American Indian or Alaska Native",
    "Asian",
    "Black or African American",
    "Hispanic or Latino",
    "Middle Eastern or North African",
    "Native Hawaiian or Other Pacific Islander",
    "Two or More Races",
    "White",
    "Other",
]

GENDER_IDENTITY_OPTIONS = [
    "Prefer not to answer",
    "Male",
    "Female",
    "Non-binary",
    "Transgender",
    "Agender",
    "Genderqueer",
    "Another identity",
]

DISABILITY_STATUS_OPTIONS = [
    "Prefer not to answer",
    "No, I do not have a disability",
    "Yes, I have a disability",
    "I have a record of a disability",
    "I do not wish to answer",
]

WORK_PREFERENCE_OPTIONS = [
    "Remote",
    "Hybrid",
    "On-site",
    "Flexible",
    "Contract",
    "Full-time",
    "Part-time",
]


FORTUNE_1_50 = {
    "walmart",
    "amazon",
    "apple",
    "unitedhealth group",
    "berkshire hathaway",
    "cvs health",
    "alphabet",
    "exxon mobil",
    "mckesson",
    "cencora",
    "costco wholesale",
    "cigna group",
    "cardinal health",
    "chevron",
    "ford motor",
    "jpmorgan chase",
    "general motors",
    "elevance health",
    "centene",
    "meta platforms",
    "home depot",
    "walgreens boots alliance",
    "bank of america",
    "verizon communications",
    "at&t",
    "comcast",
    "marathon petroleum",
    "fannie mae",
    "kroger",
    "phillips 66",
    "valero energy",
    "microsoft",
    "target",
    "procter & gamble",
    "citigroup",
    "lowe's",
    "ups",
    "boeing",
    "bank of new york mellon",
    "goldman sachs group",
    "johnson & johnson",
    "morgan stanley",
    "fedex",
    "sysco",
    "american express",
    "lockheed martin",
    "energy transfer",
    "hp",
    "wells fargo",
    "state farm insurance",
}

FORTUNE_1_100_EXTRA = {
    "pepsico",
    "intel",
    "nike",
    "best buy",
    "oracle",
    "world fuel services",
    "paccar",
    "qualcomm",
    "dell technologies",
    "caterpillar",
    "delta air lines",
    "adobe",
    "american airlines group",
    "tesla",
    "humana",
    "capital one financial",
    "hca healthcare",
    "metlife",
    "merck",
    "prudential financial",
    "charter communications",
    "international business machines",
    "allstate",
    "northrop grumman",
    "abbvie",
    "jabil",
    "deere",
    "penske automotive group",
    "conocophillips",
    "stryker",
    "union pacific",
    "us bancorp",
    "publix super markets",
    "bristol-myers squibb",
    "thermo fisher scientific",
    "broadcom",
    "booking holdings",
    "exelon",
    "gilead sciences",
    "3m",
    "dominion energy",
    "aig",
    "truist financial",
    "coca-cola",
    "micron technology",
    "starbucks",
    "airbnb",
    "lyft",
    "snowflake",
}

FORTUNE_1_500_EXTRA = {
    "flex",
    "salesforce",
    "service now",
    "zoom video communications",
    "intuit",
    "workday",
    "autodesk",
    "amdocs",
    "nvidia",
    "mongodb",
    "datadog",
    "cloudflare",
    "dropbox",
    "palantir technologies",
    "robinhood markets",
}


def _normalize_company(value: str) -> str:
    normalized = (value or "").lower().strip()
    replacements = {
        ", inc.": "",
        ", inc": "",
        " inc.": "",
        " inc": "",
        ", llc": "",
        " llc": "",
        ", corp.": "",
        ", corp": "",
        " corporation": "",
        " co.": "",
        " company": "",
        " holdings": "",
        " technologies": "",
        " group": "",
    }
    for old, new in replacements.items():
        normalized = normalized.replace(old, new)
    return " ".join(normalized.split())


FORTUNE_1_50 = {_normalize_company(name) for name in FORTUNE_1_50}
FORTUNE_1_100_EXTRA = {_normalize_company(name) for name in FORTUNE_1_100_EXTRA}
FORTUNE_1_500_EXTRA = {_normalize_company(name) for name in FORTUNE_1_500_EXTRA}


def company_ranking_bucket(company_name: str) -> str:
    normalized = _normalize_company(company_name)
    if not normalized:
        return "non_fortune"
    if normalized in FORTUNE_1_50:
        return "fortune_1_50"
    if normalized in FORTUNE_1_100_EXTRA:
        return "fortune_1_100"
    if normalized in FORTUNE_1_500_EXTRA:
        return "fortune_1_500"
    return "non_fortune"


def company_matches_ranking(company_name: str, selected_filter: str) -> bool:
    selected = (selected_filter or "any").strip()
    if selected == "any":
        return True
    bucket = company_ranking_bucket(company_name)
    order = {
        "fortune_1_50": 1,
        "fortune_1_100": 2,
        "fortune_1_500": 3,
        "non_fortune": 4,
    }
    if selected == "non_fortune":
        return bucket == "non_fortune"
    if bucket == "non_fortune":
        return False
    return order.get(bucket, 99) <= order.get(selected, 99)


def get_profile_option_payload() -> dict[str, Any]:
    return {
        "job_sectors": get_sector_options(),
        "countries": [
            {"label": country, "regions": regions}
            for country, regions in COUNTRY_REGIONS.items()
        ],
        "company_ranking_filters": COMPANY_RANKING_OPTIONS,
        "work_authorization_statuses": WORK_AUTHORIZATION_OPTIONS,
        "veteran_statuses": VETERAN_STATUS_OPTIONS,
        "race_ethnicity_options": RACE_ETHNICITY_OPTIONS,
        "gender_identity_options": GENDER_IDENTITY_OPTIONS,
        "disability_status_options": DISABILITY_STATUS_OPTIONS,
        "work_preference_options": WORK_PREFERENCE_OPTIONS,
    }

