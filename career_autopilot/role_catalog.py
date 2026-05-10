from __future__ import annotations

import csv
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ROLE_CSV_PATH = PROJECT_ROOT / "data" / "seeds" / "target_roles.csv"


ROLE_GROUPS: dict[str, list[str]] = {
    "Software, IT, and Technology": [
        "Software Engineer",
        "Web Developer",
        "Front-End Developer",
        "Back-End Developer",
        "Full-Stack Developer",
        "Mobile App Developer",
        "Python Developer",
        "Java Developer",
        ".NET Developer",
        "QA Engineer",
        "Software Tester",
        "DevOps Engineer",
        "Cloud Engineer",
        "Cybersecurity Analyst",
        "Network Engineer",
        "System Administrator",
        "Database Administrator",
        "Data Analyst",
        "Data Engineer",
        "Machine Learning Engineer",
        "AI Engineer",
        "Product Manager",
        "UI/UX Designer",
        "Technical Support Specialist",
        "IT Project Manager",
    ],
    "Healthcare and Medical": [
        "Registered Nurse",
        "Physician",
        "Physician Assistant",
        "Nurse Practitioner",
        "Medical Assistant",
        "Pharmacy Technician",
        "Pharmacist",
        "Physical Therapist",
        "Occupational Therapist",
        "Radiologic Technologist",
        "Medical Laboratory Technician",
        "Medical Coder",
        "Medical Biller",
        "Healthcare Administrator",
        "Dental Assistant",
        "Dental Hygienist",
        "Home Health Aide",
        "EMT / Paramedic",
        "Patient Care Technician",
        "Clinical Research Coordinator",
    ],
    "Business, Finance, and Administration": [
        "Business Analyst",
        "Financial Analyst",
        "Accountant",
        "Auditor",
        "Bookkeeper",
        "Payroll Specialist",
        "Tax Associate",
        "HR Generalist",
        "Recruiter",
        "Administrative Assistant",
        "Executive Assistant",
        "Office Manager",
        "Operations Manager",
        "Project Manager",
        "Program Manager",
        "Management Consultant",
        "Compliance Analyst",
        "Risk Analyst",
        "Procurement Specialist",
        "Supply Chain Analyst",
    ],
    "Sales, Retail, and Customer Service": [
        "Sales Representative",
        "Account Executive",
        "Business Development Representative",
        "Retail Sales Associate",
        "Store Manager",
        "Cashier",
        "Customer Service Representative",
        "Call Center Representative",
        "Customer Success Manager",
        "Sales Manager",
        "Marketing Coordinator",
        "Digital Marketing Specialist",
        "Social Media Manager",
        "SEO Specialist",
        "Content Writer",
        "Brand Manager",
        "E-commerce Specialist",
        "Merchandiser",
    ],
    "Education and Training": [
        "Teacher",
        "Assistant Teacher",
        "Professor",
        "Adjunct Faculty",
        "Tutor",
        "Instructional Designer",
        "School Counselor",
        "Academic Advisor",
        "Librarian",
        "Training Specialist",
        "Corporate Trainer",
        "Curriculum Developer",
        "Education Coordinator",
        "Special Education Teacher",
        "Teaching Assistant",
    ],
    "Engineering and Manufacturing": [
        "Mechanical Engineer",
        "Electrical Engineer",
        "Civil Engineer",
        "Industrial Engineer",
        "Manufacturing Engineer",
        "Quality Engineer",
        "Process Engineer",
        "Production Supervisor",
        "CNC Operator",
        "Machine Operator",
        "Maintenance Technician",
        "Plant Manager",
        "Welder",
        "Assembly Technician",
        "CAD Designer",
        "Automation Engineer",
        "Robotics Engineer",
    ],
    "Construction, Skilled Trades, and Maintenance": [
        "Construction Laborer",
        "Carpenter",
        "Electrician",
        "Plumber",
        "HVAC Technician",
        "Painter",
        "Mason",
        "Heavy Equipment Operator",
        "Construction Manager",
        "Site Supervisor",
        "Building Inspector",
        "Maintenance Worker",
        "Facilities Technician",
        "General Contractor",
        "Roofer",
    ],
    "Transportation, Logistics, and Warehouse": [
        "Truck Driver",
        "Delivery Driver",
        "Warehouse Associate",
        "Forklift Operator",
        "Logistics Coordinator",
        "Dispatcher",
        "Supply Chain Coordinator",
        "Inventory Specialist",
        "Shipping and Receiving Clerk",
        "Package Handler",
        "Material Handler",
        "Fleet Manager",
        "Operations Coordinator",
        "Transportation Manager",
    ],
    "Hospitality, Food, and Travel": [
        "Hotel Front Desk Agent",
        "Front Desk Manager",
        "Housekeeper",
        "Restaurant Server",
        "Cook",
        "Chef",
        "Bartender",
        "Barista",
        "Food Service Worker",
        "Restaurant Manager",
        "Event Coordinator",
        "Travel Agent",
        "Flight Attendant",
        "Hotel Manager",
        "Catering Manager",
    ],
    "Legal, Government, and Public Safety": [
        "Lawyer / Attorney",
        "Paralegal",
        "Legal Assistant",
        "Compliance Officer",
        "Police Officer",
        "Firefighter",
        "Security Officer",
        "Correctional Officer",
        "Court Clerk",
        "Public Administrator",
        "Policy Analyst",
        "Government Program Analyst",
        "Immigration Specialist",
        "Contract Specialist",
    ],
    "Science, Research, and Environment": [
        "Research Assistant",
        "Research Scientist",
        "Laboratory Technician",
        "Biologist",
        "Chemist",
        "Environmental Scientist",
        "Data Scientist",
        "Statistician",
        "Clinical Research Associate",
        "Quality Control Analyst",
        "Food Scientist",
        "Geologist",
    ],
    "Media, Design, and Creative": [
        "Graphic Designer",
        "Video Editor",
        "Photographer",
        "Content Creator",
        "Copywriter",
        "Journalist",
        "Editor",
        "Animator",
        "Motion Graphics Designer",
        "Art Director",
        "Creative Director",
        "UX Designer",
        "UI Designer",
        "Social Media Content Specialist",
    ],
    "Real Estate and Property": [
        "Real Estate Agent",
        "Property Manager",
        "Leasing Consultant",
        "Mortgage Loan Officer",
        "Appraiser",
        "Real Estate Analyst",
        "Maintenance Supervisor",
        "Community Manager",
        "Escrow Officer",
        "Title Specialist",
    ],
    "Agriculture, Food Production, and Natural Resources": [
        "Farm Worker",
        "Agricultural Technician",
        "Farm Manager",
        "Food Production Worker",
        "Quality Assurance Technician",
        "Animal Care Technician",
        "Forestry Worker",
        "Equipment Operator",
        "Agronomist",
        "Food Safety Specialist",
    ],
    "Personal Care, Fitness, and Social Services": [
        "Social Worker",
        "Case Manager",
        "Counselor",
        "Therapist",
        "Childcare Worker",
        "Caregiver",
        "Personal Trainer",
        "Fitness Instructor",
        "Hairstylist",
        "Barber",
        "Cosmetologist",
        "Community Outreach Coordinator",
        "Nonprofit Program Coordinator",
    ],
}


ROLE_METADATA: dict[str, dict[str, list[str]]] = {
    "Software Engineer": {
        "aliases": ["Software Developer"],
        "keywords": ["backend", "frontend", "api", "programming", "application development"],
    },
    "Web Developer": {
        "keywords": ["html", "css", "javascript", "web apps", "frontend"],
    },
    "Front-End Developer": {
        "aliases": ["Frontend Developer"],
        "keywords": ["react", "next.js", "javascript", "typescript", "ui"],
    },
    "Back-End Developer": {
        "aliases": ["Backend Developer"],
        "keywords": ["api", "python", "java", "node.js", "sql", "microservices"],
    },
    "Full-Stack Developer": {
        "aliases": ["Full Stack Developer"],
        "keywords": ["frontend", "backend", "react", "node.js", "typescript", "sql"],
    },
    "Mobile App Developer": {
        "keywords": ["ios", "android", "swift", "kotlin", "react native", "flutter"],
    },
    "Python Developer": {
        "keywords": ["python", "fastapi", "django", "flask", "automation", "backend"],
    },
    "Java Developer": {
        "keywords": ["java", "spring", "microservices", "backend"],
    },
    ".NET Developer": {
        "aliases": ["DotNet Developer"],
        "keywords": [".net", "c#", "asp.net", "azure"],
    },
    "QA Engineer": {
        "aliases": ["Software Tester", "QA Analyst"],
        "keywords": ["test automation", "selenium", "playwright", "quality assurance"],
    },
    "DevOps Engineer": {
        "keywords": ["docker", "kubernetes", "terraform", "ci/cd", "aws", "gcp", "azure"],
    },
    "Cloud Engineer": {
        "keywords": ["aws", "gcp", "azure", "cloud infrastructure", "terraform"],
    },
    "Cybersecurity Analyst": {
        "keywords": ["security", "siem", "soc", "incident response", "threat", "vulnerability"],
    },
    "System Administrator": {
        "aliases": ["Sysadmin"],
        "keywords": ["windows", "linux", "servers", "infrastructure"],
    },
    "Database Administrator": {
        "aliases": ["DBA"],
        "keywords": ["sql", "postgresql", "mysql", "oracle", "database"],
    },
    "Data Analyst": {
        "keywords": ["sql", "tableau", "power bi", "dashboard", "analytics", "reporting"],
    },
    "Data Engineer": {
        "keywords": ["etl", "elt", "sql", "python", "airflow", "dbt", "bigquery", "snowflake"],
    },
    "Machine Learning Engineer": {
        "aliases": ["ML Engineer"],
        "keywords": ["machine learning", "pytorch", "tensorflow", "model serving", "mlops"],
    },
    "AI Engineer": {
        "keywords": ["llm", "rag", "langchain", "agents", "prompt engineering", "python"],
    },
    "UI/UX Designer": {
        "aliases": ["UI Designer", "UX Designer"],
        "keywords": ["figma", "design systems", "wireframes", "prototyping", "user research"],
    },
    "Technical Support Specialist": {
        "aliases": ["IT Support Specialist", "Help Desk Specialist"],
        "keywords": ["troubleshooting", "support", "ticketing", "customer support"],
    },
    "IT Project Manager": {
        "aliases": ["Technical Project Manager"],
        "keywords": ["agile", "scrum", "delivery", "stakeholder management"],
    },
    "Registered Nurse": {
        "aliases": ["RN"],
        "keywords": ["patient care", "clinical", "hospital", "icu", "triage", "charting"],
    },
    "Physician Assistant": {
        "aliases": ["PA"],
        "keywords": ["clinical", "patient care", "assessment", "diagnosis"],
    },
    "Nurse Practitioner": {
        "aliases": ["NP"],
        "keywords": ["patient care", "clinical", "primary care", "telehealth"],
    },
    "Medical Assistant": {
        "keywords": ["patient intake", "clinical support", "ehr", "emr"],
    },
    "Radiologic Technologist": {
        "aliases": ["Radiology Tech"],
        "keywords": ["x-ray", "imaging", "radiology"],
    },
    "Medical Laboratory Technician": {
        "aliases": ["Lab Tech"],
        "keywords": ["laboratory", "specimens", "testing", "clinical lab"],
    },
    "Healthcare Administrator": {
        "keywords": ["healthcare operations", "compliance", "clinic", "hospital administration"],
    },
    "EMT / Paramedic": {
        "aliases": ["EMT", "Paramedic"],
        "keywords": ["emergency care", "ambulance", "first response"],
    },
    "Clinical Research Coordinator": {
        "keywords": ["clinical trials", "research", "study coordination", "irb"],
    },
    "Business Analyst": {
        "keywords": ["requirements", "stakeholders", "process improvement", "analytics"],
    },
    "Financial Analyst": {
        "keywords": ["financial modeling", "forecasting", "excel", "budgeting"],
    },
    "Recruiter": {
        "keywords": ["talent acquisition", "sourcing", "screening", "hiring"],
    },
    "Customer Success Manager": {
        "keywords": ["account management", "retention", "customer onboarding"],
    },
    "Digital Marketing Specialist": {
        "keywords": ["paid search", "campaigns", "google ads", "analytics"],
    },
    "SEO Specialist": {
        "keywords": ["search engine optimization", "keyword research", "content seo"],
    },
    "Teacher": {
        "keywords": ["classroom", "lesson plans", "instruction", "education"],
    },
    "Instructional Designer": {
        "keywords": ["e-learning", "curriculum", "learning design", "training"],
    },
    "Mechanical Engineer": {
        "keywords": ["cad", "solidworks", "manufacturing", "mechanical systems"],
    },
    "Electrical Engineer": {
        "keywords": ["circuits", "pcb", "electronics", "electrical systems"],
    },
    "Automation Engineer": {
        "keywords": ["plc", "scada", "robotics", "test automation", "controls"],
    },
    "Truck Driver": {
        "aliases": ["CDL Driver"],
        "keywords": ["delivery", "transportation", "logistics", "cdl"],
    },
    "Lawyer / Attorney": {
        "aliases": ["Lawyer", "Attorney"],
        "keywords": ["legal", "litigation", "contracts", "compliance"],
    },
    "Paralegal": {
        "keywords": ["legal research", "case management", "documents"],
    },
    "Research Scientist": {
        "keywords": ["research", "experiments", "publications", "analysis"],
    },
    "Data Scientist": {
        "keywords": ["machine learning", "statistics", "python", "modeling", "analytics"],
    },
    "Graphic Designer": {
        "keywords": ["adobe", "branding", "visual design", "layout"],
    },
    "UX Designer": {
        "keywords": ["user research", "wireframes", "prototypes", "figma"],
    },
    "UI Designer": {
        "keywords": ["visual design", "figma", "design systems", "ui"],
    },
    "Real Estate Agent": {
        "keywords": ["listings", "buyers", "sellers", "real estate"],
    },
    "Social Worker": {
        "keywords": ["case management", "community", "support services"],
    },
    "Therapist": {
        "keywords": ["mental health", "counseling", "treatment"],
    },
}


def _split_field(value: str) -> list[str]:
    return [part.strip() for part in (value or "").split("|") if part.strip()]


def _load_seed_role_records() -> list[dict[str, Any]]:
    if not ROLE_CSV_PATH.exists():
        return []

    records: list[dict[str, Any]] = []
    with ROLE_CSV_PATH.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            label = str(row.get("label", "")).strip()
            if not label:
                continue
            records.append(
                {
                    "category": str(row.get("category", "")).strip() or "Custom",
                    "label": label,
                    "aliases": _split_field(str(row.get("aliases", ""))),
                    "keywords": _split_field(str(row.get("keywords", ""))),
                }
            )
    return records


def get_role_records(extra_roles: list[str] | None = None) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    seen: set[str] = set()

    seed_records = _load_seed_role_records()
    source_records: list[dict[str, Any]] = []
    if seed_records:
        source_records = seed_records
    else:
        for category, roles in ROLE_GROUPS.items():
            for label in roles:
                meta = ROLE_METADATA.get(label, {})
                source_records.append(
                    {
                        "category": category,
                        "label": label,
                        "aliases": list(meta.get("aliases", [])),
                        "keywords": list(meta.get("keywords", [])),
                    }
                )

    for record in source_records:
        label = str(record.get("label", "")).strip()
        if not label or label in seen:
            continue
        records.append(record)
        seen.add(label)

    for role in extra_roles or []:
        label = role.strip()
        if not label or label in seen:
            continue
        records.append(
            {
                "category": "Custom",
                "label": label,
                "aliases": [],
                "keywords": [],
            }
        )
        seen.add(label)

    return records


def get_role_record(role_label: str, extra_roles: list[str] | None = None) -> dict[str, Any] | None:
    target = role_label.strip().lower()
    if not target:
        return None
    for record in get_role_records(extra_roles=extra_roles):
        label = str(record.get("label", "")).strip().lower()
        aliases = [str(x).strip().lower() for x in record.get("aliases", []) or []]
        if target == label or target in aliases:
            return record
    return None
