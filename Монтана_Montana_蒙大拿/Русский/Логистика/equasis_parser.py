#!/usr/bin/env python3
"""
Equasis Parser — Free Maritime Database
Ship owners, operators, managers, inspections

Ɉ MONTANA PROTOCOL — ML-DSA-65 (FIPS 204)
"""

import os
import re
import json
import requests
from typing import Optional, Dict, List
from bs4 import BeautifulSoup

# Credentials from environment
EQUASIS_USER = os.environ.get("EQUASIS_USER")
EQUASIS_PASS = os.environ.get("EQUASIS_PASS")

EQUASIS_BASE = "https://www.equasis.org/EquasisWeb"


class EquasisParser:
    """Parser for Equasis maritime database"""

    def __init__(self, username: str = None, password: str = None):
        self.username = username or EQUASIS_USER
        self.password = password or EQUASIS_PASS
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        })
        self.logged_in = False

    def login(self) -> bool:
        """Login to Equasis"""
        if not self.username or not self.password:
            print("Equasis credentials not configured")
            return False

        try:
            # Get login page first (for cookies/tokens)
            self.session.get(f"{EQUASIS_BASE}/authen/HomePage")

            # Login
            login_data = {
                'j_username': self.username,
                'j_password': self.password,
                'submit': 'Login'
            }

            resp = self.session.post(
                f"{EQUASIS_BASE}/authen/submitLogin",
                data=login_data,
                allow_redirects=True
            )

            # Check if login successful
            if 'HomePage' in resp.url or 'restricted' in resp.url.lower():
                self.logged_in = True
                print("Equasis login successful")
                return True
            else:
                print("Equasis login failed")
                return False

        except Exception as e:
            print(f"Login error: {e}")
            return False

    def search_vessel(self, query: str) -> List[Dict]:
        """
        Search vessel by name, IMO, or MMSI
        Returns list of matching vessels
        """
        if not self.logged_in:
            if not self.login():
                return []

        try:
            # Search page
            search_data = {
                'P_NAME': query,
                'P_IMO': '',
                'P_CALLSIGN': '',
                'P_MMSI': '',
                'P_FLAG': '',
                'submit': 'Search'
            }

            # If query looks like IMO number
            if query.isdigit() and len(query) == 7:
                search_data = {
                    'P_NAME': '',
                    'P_IMO': query,
                    'P_CALLSIGN': '',
                    'P_MMSI': '',
                    'P_FLAG': '',
                    'submit': 'Search'
                }
            # If query looks like MMSI
            elif query.isdigit() and len(query) == 9:
                search_data = {
                    'P_NAME': '',
                    'P_IMO': '',
                    'P_CALLSIGN': '',
                    'P_MMSI': query,
                    'P_FLAG': '',
                    'submit': 'Search'
                }

            resp = self.session.post(
                f"{EQUASIS_BASE}/restricted/search/SearchShip",
                data=search_data
            )

            soup = BeautifulSoup(resp.text, 'html.parser')
            results = []

            # Parse search results table
            table = soup.find('table', {'class': 'shiplist'}) or soup.find('table')
            if table:
                rows = table.find_all('tr')[1:]  # Skip header
                for row in rows[:20]:  # Limit to 20 results
                    cells = row.find_all('td')
                    if len(cells) >= 4:
                        vessel = {
                            'name': cells[0].get_text(strip=True),
                            'imo': cells[1].get_text(strip=True),
                            'type': cells[2].get_text(strip=True) if len(cells) > 2 else '',
                            'flag': cells[3].get_text(strip=True) if len(cells) > 3 else '',
                        }
                        # Get link to details
                        link = cells[0].find('a')
                        if link:
                            vessel['details_url'] = link.get('href', '')
                        results.append(vessel)

            return results

        except Exception as e:
            print(f"Search error: {e}")
            return []

    def get_vessel_details(self, imo: str) -> Dict:
        """
        Get detailed vessel information including owners/operators
        """
        if not self.logged_in:
            if not self.login():
                return {}

        try:
            # Access vessel page by IMO
            resp = self.session.get(
                f"{EQUASIS_BASE}/restricted/ShipInfo",
                params={'P_IMO': imo}
            )

            soup = BeautifulSoup(resp.text, 'html.parser')
            vessel = {'imo': imo}

            # Parse vessel details
            # Ship name
            name_el = soup.find('span', {'class': 'shipname'}) or soup.find('h2')
            if name_el:
                vessel['name'] = name_el.get_text(strip=True)

            # Parse info table
            for row in soup.find_all('tr'):
                cells = row.find_all('td')
                if len(cells) >= 2:
                    label = cells[0].get_text(strip=True).lower()
                    value = cells[1].get_text(strip=True)

                    if 'imo' in label:
                        vessel['imo'] = value
                    elif 'mmsi' in label:
                        vessel['mmsi'] = value
                    elif 'call sign' in label:
                        vessel['callsign'] = value
                    elif 'flag' in label:
                        vessel['flag'] = value
                    elif 'type' in label:
                        vessel['type'] = value
                    elif 'gross tonnage' in label:
                        vessel['gross_tonnage'] = value
                    elif 'deadweight' in label:
                        vessel['deadweight'] = value
                    elif 'year of build' in label:
                        vessel['year_built'] = value

            # Get company information (owners, operators, managers)
            vessel['companies'] = self._parse_companies(soup)

            return vessel

        except Exception as e:
            print(f"Details error: {e}")
            return {}

    def _parse_companies(self, soup: BeautifulSoup) -> List[Dict]:
        """Parse company information from vessel page"""
        companies = []

        # Look for company section
        company_section = soup.find('div', {'id': 'company'}) or soup.find('table', {'class': 'company'})

        if company_section:
            for row in company_section.find_all('tr'):
                cells = row.find_all('td')
                if len(cells) >= 2:
                    company = {}
                    role = cells[0].get_text(strip=True).lower()

                    if 'registered owner' in role:
                        company['role'] = 'owner'
                    elif 'ship manager' in role or 'ism manager' in role:
                        company['role'] = 'manager'
                    elif 'operator' in role:
                        company['role'] = 'operator'
                    elif 'technical manager' in role:
                        company['role'] = 'technical_manager'
                    else:
                        company['role'] = role

                    company['name'] = cells[1].get_text(strip=True)

                    # Get additional info if available
                    if len(cells) > 2:
                        company['country'] = cells[2].get_text(strip=True)

                    if company.get('name'):
                        companies.append(company)

        # Alternative parsing for different page structure
        if not companies:
            for text_block in soup.find_all(['p', 'div', 'span']):
                text = text_block.get_text()
                if 'Registered owner' in text:
                    match = re.search(r'Registered owner[:\s]+([^\n]+)', text)
                    if match:
                        companies.append({
                            'role': 'owner',
                            'name': match.group(1).strip()
                        })
                if 'Ship manager' in text:
                    match = re.search(r'Ship manager[:\s]+([^\n]+)', text)
                    if match:
                        companies.append({
                            'role': 'manager',
                            'name': match.group(1).strip()
                        })

        return companies

    def get_company_contacts(self, company_name: str) -> Dict:
        """
        Search for company details
        Note: Equasis has limited company contact info
        """
        if not self.logged_in:
            if not self.login():
                return {}

        try:
            resp = self.session.get(
                f"{EQUASIS_BASE}/restricted/CompanyInfo",
                params={'P_COMPANY': company_name}
            )

            soup = BeautifulSoup(resp.text, 'html.parser')
            company = {'name': company_name}

            # Parse company info
            for row in soup.find_all('tr'):
                cells = row.find_all('td')
                if len(cells) >= 2:
                    label = cells[0].get_text(strip=True).lower()
                    value = cells[1].get_text(strip=True)

                    if 'address' in label:
                        company['address'] = value
                    elif 'country' in label:
                        company['country'] = value
                    elif 'telephone' in label or 'phone' in label:
                        company['phone'] = value
                    elif 'fax' in label:
                        company['fax'] = value
                    elif 'email' in label:
                        company['email'] = value

            # Get fleet size
            fleet_section = soup.find('table', {'class': 'fleet'})
            if fleet_section:
                company['fleet_size'] = len(fleet_section.find_all('tr')) - 1

            return company

        except Exception as e:
            print(f"Company search error: {e}")
            return {}


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

_parser = None


def get_parser() -> EquasisParser:
    """Get singleton parser instance"""
    global _parser
    if _parser is None:
        _parser = EquasisParser()
    return _parser


def search_vessel(query: str) -> List[Dict]:
    """Quick vessel search"""
    return get_parser().search_vessel(query)


def get_vessel(imo: str) -> Dict:
    """Get vessel with owner/operator info"""
    return get_parser().get_vessel_details(imo)


def get_contacts(company_name: str) -> Dict:
    """Get company contacts"""
    return get_parser().get_company_contacts(company_name)


if __name__ == "__main__":
    parser = EquasisParser()

    if parser.login():
        print("\nSearching for 'EVER GIVEN'...")
        results = parser.search_vessel("EVER GIVEN")
        for v in results[:3]:
            print(f"  - {v}")

        if results:
            print(f"\nGetting details for IMO {results[0].get('imo')}...")
            details = parser.get_vessel_details(results[0].get('imo'))
            print(json.dumps(details, indent=2, ensure_ascii=False))
