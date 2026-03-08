"""
Offline script to generate the UKIP demo dataset.

Produces data/demo/demo_entities.xlsx with 1,000 synthetic entities across
4 categories: Technology, Healthcare, Science, Engineering.

Run once before committing the dataset:
    python scripts/generate_demo_dataset.py

Requires (dev-only, NOT added to requirements.txt):
    pip install faker numpy openpyxl
"""
from __future__ import annotations

import math
import random
import sys
from pathlib import Path

# ── Verify optional deps ──────────────────────────────────────────────────────
try:
    import numpy as np
    from faker import Faker
    import openpyxl
except ImportError as e:
    print(f"Missing dev dependency: {e}")
    print("Install with: pip install faker numpy openpyxl")
    sys.exit(1)

# ── Config ────────────────────────────────────────────────────────────────────
OUTPUT_PATH = Path(__file__).parent.parent / "data" / "demo" / "demo_entities.xlsx"
TOTAL = 1_000
SEED  = 42

random.seed(SEED)
np.random.seed(SEED)
fake = Faker()
Faker.seed(SEED)

# ── Domain categories ─────────────────────────────────────────────────────────
CATEGORIES = [
    {
        "name": "Technology",
        "brands": ["TechCorp", "Nexasoft", "DataStream", "CloudPeak", "ByteLogic", "InnoSys"],
        "classifications": ["Software", "Hardware", "IoT Device", "AI Module", "Network Equipment"],
        "concepts": [
            "machine learning, neural networks, deep learning",
            "cloud computing, microservices, kubernetes",
            "cybersecurity, encryption, zero-trust",
            "natural language processing, transformers, BERT",
            "computer vision, object detection, YOLO",
            "blockchain, distributed ledger, smart contracts",
            "edge computing, real-time processing, low latency",
            "data engineering, ETL pipelines, data lakes",
        ],
        "sources": ["openalex", "wos", "scholar"],
    },
    {
        "name": "Healthcare",
        "brands": ["MedTech", "BioNova", "PharmaCure", "HealthPulse", "ClinGen", "VitaLab"],
        "classifications": ["Medical Device", "Pharmaceutical", "Diagnostic Kit", "Surgical Instrument", "Wearable"],
        "concepts": [
            "clinical trials, randomized controlled, placebo",
            "genomics, CRISPR, gene editing, epigenetics",
            "immunotherapy, oncology, tumor microenvironment",
            "telemedicine, remote monitoring, digital health",
            "drug delivery, nanoparticles, bioavailability",
            "precision medicine, biomarkers, proteomics",
            "epidemiology, cohort study, risk factors",
            "neuroscience, fMRI, cognitive function",
        ],
        "sources": ["openalex", "wos"],
    },
    {
        "name": "Science",
        "brands": ["AstroLab", "QuantumRes", "GeoSci", "EcoMetrics", "NanoProbe", "ChemSynth"],
        "classifications": ["Research Instrument", "Analytical Tool", "Sensor", "Reagent", "Simulation Software"],
        "concepts": [
            "quantum mechanics, entanglement, superposition",
            "materials science, nanotechnology, graphene",
            "climate change, carbon capture, greenhouse gases",
            "particle physics, hadron collider, Higgs boson",
            "astrophysics, dark matter, gravitational waves",
            "biochemistry, protein folding, enzyme kinetics",
            "environmental science, biodiversity, ecosystem services",
            "computational chemistry, molecular dynamics, DFT",
        ],
        "sources": ["openalex", "scholar"],
    },
    {
        "name": "Engineering",
        "brands": ["BuildTech", "StructoCore", "EnergyFlow", "MechPrecision", "AutoDrive", "RoboFlex"],
        "classifications": ["Industrial Equipment", "Automation System", "Energy Component", "Sensor Module", "Control Unit"],
        "concepts": [
            "finite element analysis, structural mechanics, CAD",
            "renewable energy, solar panels, wind turbines",
            "autonomous vehicles, LIDAR, sensor fusion",
            "additive manufacturing, 3D printing, sintering",
            "PID control, feedback loops, servo systems",
            "thermodynamics, heat transfer, fluid mechanics",
            "robotics, inverse kinematics, path planning",
            "signal processing, FFT, Kalman filter",
        ],
        "sources": ["openalex", "wos", "scholar"],
    },
]

# ── Generation ────────────────────────────────────────────────────────────────
PER_CATEGORY = TOTAL // len(CATEGORIES)  # 250 each

YEARS = list(range(2020, 2025))

def log_normal_citations() -> int:
    """Log-normal distribution: most entities have few citations, a few have many."""
    raw = int(np.random.lognormal(mean=3.0, sigma=1.5))
    return max(0, min(raw, 5000))

rows: list[dict] = []
idx = 0

for cat in CATEGORIES:
    for _ in range(PER_CATEGORY):
        idx += 1
        enriched = random.random() < 0.72  # ~72% enrichment rate
        brand = random.choice(cat["brands"])
        year  = random.choice(YEARS)
        month = random.randint(1, 12)
        day   = random.randint(1, 28)

        rows.append({
            "entity_name":             f"{brand} {cat['classifications'][idx % len(cat['classifications'])]} {idx:04d}",
            "brand_capitalized":       brand,
            "brand_lower":             brand.lower(),
            "classification":          cat["classifications"][idx % len(cat["classifications"])],
            "entity_type":             cat["name"],
            "sku":                     f"DEMO-{cat['name'][:3].upper()}-{idx:05d}",
            "creation_date":           f"{year}-{month:02d}-{day:02d}",
            "status":                  "active",
            "validation_status":       "valid",
            "enrichment_status":       "completed" if enriched else "none",
            "enrichment_citation_count": log_normal_citations() if enriched else 0,
            "enrichment_concepts":     random.choice(cat["concepts"]) if enriched else None,
            "enrichment_source":       random.choice(cat["sources"]) if enriched else None,
        })

# Shuffle so categories are mixed
random.shuffle(rows)

# ── Write Excel ───────────────────────────────────────────────────────────────
import pandas as pd  # noqa: PLC0415

OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
df = pd.DataFrame(rows)
df.to_excel(OUTPUT_PATH, index=False, engine="openpyxl")
print(f"OK Generated {len(rows)} demo entities -> {OUTPUT_PATH}")
