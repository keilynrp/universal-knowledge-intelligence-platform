import time
import asyncio
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import Optional

import logging
import os

from backend import models
from backend.adapters.enrichment.openalex import OpenAlexAdapter
from backend.adapters.enrichment.scholar import ScholarAdapter
from backend.adapters.enrichment.wos import WebOfScienceAdapter

logger = logging.getLogger(__name__)

# Initialize our Phase 1, 2, and 3 adapters
adapter_wos = WebOfScienceAdapter(api_key=os.environ.get("WOS_API_KEY")) # Phase 3 (Premium)
adapter_openalex = OpenAlexAdapter() # Phase 1 (Free & Fast)
adapter_scholar = ScholarAdapter(use_free_proxies=True) # Phase 2 (Restricted Scraping)

def enrich_single_record(db: Session, product: models.RawProduct) -> models.RawProduct:
    """
    Synchronously enriches a single record by title or DOI.
    Uses a cascade fallback strategy prioritizing Premium Data: 
    Web of Science (BYOK) -> OpenAlex (Free API) -> Google Scholar (Scraping).
    """
    if not product.product_name and not product.model:
        return product
        
    query = product.product_name or product.model
    if not query:
        return product
        
    enriched_data = None
    source = "Unknown"
    
    try:
        # Phase 3: Premium BYOK Priority
        if adapter_wos.is_active:
            results_wos = adapter_wos.search_by_title(query, limit=1)
            if results_wos and len(results_wos) > 0:
                enriched_data = results_wos[0]
                source = "Web of Science"
                
        # Phase 1: Free Open API
        if not enriched_data:
            results = adapter_openalex.search_by_title(query, limit=1)
            if results and len(results) > 0:
                enriched_data = results[0]
                source = "OpenAlex"
            else:
                # Phase 2: Scraping Fallback
                logger.info(f"OpenAlex failed to find data for '{query}'. Falling back to Google Scholar...")
                results_scholar = adapter_scholar.search_by_title(query, limit=1)
                if results_scholar and len(results_scholar) > 0:
                    enriched_data = results_scholar[0]
                    source = "Google Scholar"
            
        if enriched_data:
            # Populate our Generalized NDO fields
            product.enrichment_doi = enriched_data.doi
            product.enrichment_citation_count = enriched_data.citation_count
            product.enrichment_concepts = ", ".join(enriched_data.concepts) if enriched_data.concepts else None
            product.enrichment_source = source
            product.enrichment_status = "completed"
        else:
            product.enrichment_status = "failed"
            product.enrichment_source = "None"
            
    except Exception as e:
        logger.error(f"Error enriching record ID {product.id}: {e}")
        product.enrichment_status = "failed"
        
    db.commit()
    return product

async def background_enrichment_worker(db_generator):
    """
    Background worker that runs slowly to avoid rate limit bans.
    Pulls records where enrichment_status == 'pending'.
    """
    # Wait a bit before starting so server can boot
    await asyncio.sleep(5)
    
    while True:
        try:
            db = next(db_generator)
            # Find one pending record
            product = db.query(models.RawProduct).filter(
                models.RawProduct.enrichment_status == "pending"
            ).first()
            
            if product:
                enrich_single_record(db, product)
                db.close()
                # Polite rate limiting (e.g. 1 process per 2 seconds)
                await asyncio.sleep(2)
            else:
                db.close()
                # If no pending records, sleep for a while
                await asyncio.sleep(10)
        except Exception as e:
            # Sleep on error before retrying
            await asyncio.sleep(10)

def trigger_enrichment_bulk(db: Session, skip: int = 0, limit: int = 100):
    """
    Marks a batch of products as 'pending' so the background worker picks them up.
    """
    products = db.query(models.RawProduct).filter(
        models.RawProduct.enrichment_status.in_(["none", "failed"])
    ).offset(skip).limit(limit).all()
    
    count = 0
    for p in products:
        p.enrichment_status = "pending"
        count += 1
        
    db.commit()
    return count
