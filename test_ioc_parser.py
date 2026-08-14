from services.ioc_parser import extract_iocs, extract_all_iocs_from_job_data

def test_extract_iocs():
    text = "Here is an IP 1.2.3.4 and a domain evil.com. Also a URL https://phishing.net/login and a hash 5e884898da28047151d0e56f8dc6292773603d0d6aabbdd62a11ef721d1542d8."
    iocs = extract_iocs(text)
    
    assert "1.2.3.4" in iocs["ip"]
    assert "evil.com" in iocs["domain"]
    assert "https://phishing.net/login" in iocs["url"]
    assert "phishing.net" in iocs["domain"]
    assert "5e884898da28047151d0e56f8dc6292773603d0d6aabbdd62a11ef721d1542d8" in iocs["hash"]

def test_extract_invalid_ipv4():
    text = "This is not an IP 999.999.999.999 and neither is 1.2.3"
    iocs = extract_iocs(text)
    assert len(iocs["ip"]) == 0

def test_extract_all_iocs_from_job_data():
    query = "Investigate 8.8.8.8"
    search_results = [
        {"title": "Search result for badguy.com", "link": "http://some-onion-link.onion"}
    ]
    scraped_data = [
        {"url": "http://some-onion-link.onion", "content": "Contact us at http://contact.badguy.com"}
    ]
    
    master_iocs = extract_all_iocs_from_job_data(query, search_results, scraped_data)
    
    assert "8.8.8.8" in master_iocs["ip"]
    assert "badguy.com" in master_iocs["domain"]
    assert "contact.badguy.com" in master_iocs["domain"]
    assert "http://contact.badguy.com" in master_iocs["url"]
