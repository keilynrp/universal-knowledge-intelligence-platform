import time
import asyncio
import os
import sys

# Ensure backend packages can be imported
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.adapters.enrichment.openalex import OpenAlexAdapter
from backend.adapters.enrichment.scholar import ScholarAdapter
from backend.adapters.enrichment.wos import WebOfScienceAdapter

def run_performance_test():
    """
    Runs a performance test isolating the 3 phases of data enrichment APIs.
    We test each API using a well-known scientific query.
    """
    query = "Deep learning"
    
    print("=" * 60)
    print("🚀 DB Disambiguator - API Adapters Performance Benchmark")
    print("=" * 60)
    print(f"Test Query: '{query}'")
    
    # ----------------------------------------------------
    # Phase 1: OpenAlex (Free)
    # ----------------------------------------------------
    print("\n🟢 [PHASE 1] OpenAlex API (Open Data)")
    openalex = OpenAlexAdapter()
    
    t0 = time.time()
    res1 = openalex.search_by_title(query, limit=1)
    t1 = time.time()
    
    if res1:
        print(f"  ✅ Result Found: '{res1[0].title}'")
        print(f"  ✅ Citations: {res1[0].citation_count}")
        print(f"  ⏱️ Time taken: {t1 - t0:.3f} seconds")
    else:
        print(f"  ❌ No results. Time taken: {t1 - t0:.3f} seconds")

    # ----------------------------------------------------
    # Phase 2: Google Scholar (Restricted Scraping)
    # ----------------------------------------------------
    print("\n🟡 [PHASE 2] Google Scholar Wrapper (Scholarly + Free Proxies)")
    print("  * Initializing Proxies (this might take a few seconds)...")
    
    # Let's initialize it and measure
    t_proxy_start = time.time()
    scholar = ScholarAdapter(use_free_proxies=True)
    t_proxy_end = time.time()
    print(f"  * Proxy Setup Time: {t_proxy_end - t_proxy_start:.3f} seconds")
    
    t0 = time.time()
    res2 = scholar.search_by_title(query, limit=1)
    t1 = time.time()
    
    if res2:
        print(f"  ✅ Result Found: '{res2[0].title}'")
        print(f"  ✅ Citations: {res2[0].citation_count}")
        print(f"  ⏱️ Search Time: {t1 - t0:.3f} seconds")
    else:
        print(f"  ❌ No results or IP banned. Time taken: {t1 - t0:.3f} seconds")
        
    # ----------------------------------------------------
    # Phase 3: Web of Science (Premium BYOK)
    # ----------------------------------------------------
    print("\n🔴 [PHASE 3] Web of Science (Clarivate Starter API / BYOK)")
    api_key = os.environ.get("WOS_API_KEY")
    wos = WebOfScienceAdapter(api_key=api_key)
    
    if not wos.is_active:
        print("  ⚠️ Skipped: No WOS_API_KEY environment variable provided.")
    else:
        t0 = time.time()
        res3 = wos.search_by_title(query, limit=1)
        t1 = time.time()
        
        if res3:
            print(f"  ✅ Result Found: '{res3[0].title}'")
            print(f"  ✅ Citations: {res3[0].citation_count}")
            print(f"  ⏱️ Time taken: {t1 - t0:.3f} seconds")
        else:
            print(f"  ❌ No results or bad key. Time taken: {t1 - t0:.3f} seconds")
            
    print("\n" + "=" * 60)
    print("Test Completed.")

if __name__ == "__main__":
    run_performance_test()
