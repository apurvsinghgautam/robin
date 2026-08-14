import asyncio
import os
from unittest.mock import patch

from config import IPINFO_TOKEN, IP2LOCATION_API_KEY, SHODAN_API_KEY, VIRUSTOTAL_API_KEY, CENSYS_API_ID, CENSYS_SECRET
from services import ipinfo, ip2location, shodan, virustotal, censys
from services.ioc_parser import extract_all_iocs_from_job_data
from services.enrichment import enrich_iocs

def print_section(title):
    print(f"\n{'='*50}\n{title}\n{'='*50}")

def check_config():
    print_section("1. CONFIGURATION CHECK")
    print(f"IPINFO_TOKEN: {'configured' if IPINFO_TOKEN else 'missing'}")
    print(f"IP2LOCATION_API_KEY: {'configured' if IP2LOCATION_API_KEY else 'missing'}")
    print(f"SHODAN_API_KEY: {'configured' if SHODAN_API_KEY else 'missing'}")
    print(f"VIRUSTOTAL_API_KEY: {'configured' if VIRUSTOTAL_API_KEY else 'missing'}")
    print(f"CENSYS_API_ID: {'configured' if CENSYS_API_ID else 'missing'}")
    print(f"CENSYS_SECRET: {'configured' if CENSYS_SECRET else 'missing'}")

def run_smoke_tests():
    print_section("2. PROVIDER SMOKE TESTS")
    test_ip = "8.8.8.8"
    test_domain = "example.com"
    
    # IPinfo
    res = ipinfo.enrich_ip(test_ip)
    print(f"IPinfo: {res.get('status')} - type: {res.get('indicator_type')}")
    
    # IP2Location
    res = ip2location.enrich_ip(test_ip)
    print(f"IP2Location: {res.get('status')} - type: {res.get('indicator_type')}")
    
    # Shodan
    res = shodan.enrich_ip(test_ip)
    print(f"Shodan: {res.get('status')} - type: {res.get('indicator_type')}")
    
    # VirusTotal
    res = virustotal.enrich_domain(test_domain)
    print(f"VirusTotal: {res.get('status')} - type: {res.get('indicator_type')}")
    
    # Censys
    res = censys.enrich_domain(test_domain)
    print(f"Censys: {res.get('status')} - type: {res.get('indicator_type')}")

def test_ioc_pipeline():
    print_section("3. IOC ENRICHMENT TEST & 5. STRUCTURED OUTPUT")
    query = "Investigate 1.1.1.1 and evil.com"
    iocs = extract_all_iocs_from_job_data(query, [], [])
    print(f"Extracted IOCs: {iocs}")
    
    results = enrich_iocs(iocs)
    print(f"Enrichment results count: {len(results)}")
    
    # Structure check
    if len(results) > 0:
        sample = results[0]
        keys = list(sample.keys())
        print(f"Structured keys: {keys}")
        
def test_failure_isolation():
    print_section("4. FAILURE ISOLATION")
    
    # Patch shodan to fail
    with patch("services.shodan.requests.get") as mock_get:
        import requests
        mock_get.side_effect = requests.exceptions.Timeout("Simulated Timeout")
        
        iocs = {"ip": ["8.8.4.4"]}
        results = enrich_iocs(iocs)
        
        shodan_res = next((r for r in results if r["provider"] == "shodan"), None)
        other_res = next((r for r in results if r["provider"] != "shodan"), None)
        
        print(f"Shodan result status: {shodan_res['status']} ({shodan_res.get('error_type')})")
        print(f"Other provider status: {other_res['status'] if other_res else 'None'}")
        print(f"Total results: {len(results)}")

if __name__ == "__main__":
    check_config()
    run_smoke_tests()
    test_ioc_pipeline()
    test_failure_isolation()
