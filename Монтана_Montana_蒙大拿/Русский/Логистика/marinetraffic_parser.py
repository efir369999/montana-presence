#!/usr/bin/env python3
"""
MarineTraffic Data Parser
Парсинг публичных данных + интеграция с API

Ɉ MONTANA PROTOCOL — ML-DSA-65 (FIPS 204)
"""

import os
import re
import json
import requests
from datetime import datetime
from typing import Optional, Dict, List
from bs4 import BeautifulSoup

# API key from environment (when available)
MT_API_KEY = os.environ.get("MARINETRAFFIC_API_KEY")

# Base URLs
MT_BASE = "https://www.marinetraffic.com"
MT_API_BASE = "https://services.marinetraffic.com/api"


class MarineTrafficParser:
    """Parser for MarineTraffic public data + API"""

    def __init__(self, api_key: str = None):
        self.api_key = api_key or MT_API_KEY
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        })

    # =========================================================================
    # PUBLIC DATA (no API key needed)
    # =========================================================================

    def search_vessel_public(self, query: str) -> List[Dict]:
        """
        Search vessel using public search
        Returns basic info: name, MMSI, IMO, type, flag
        """
        url = f"{MT_BASE}/en/ais/index/search/all/keyword:{query}"

        try:
            resp = self.session.get(url, timeout=10)
            if resp.status_code != 200:
                return []

            soup = BeautifulSoup(resp.text, 'html.parser')
            results = []

            # Parse search results
            for item in soup.select('.search-result-item, .vessel-item'):
                vessel = {}

                # Name
                name_el = item.select_one('.vessel-name, .ship-name, a[href*="/vessels/"]')
                if name_el:
                    vessel['name'] = name_el.get_text(strip=True)
                    href = name_el.get('href', '')
                    # Extract MMSI from URL
                    if '/vessels/' in href:
                        parts = href.split('/')
                        for i, p in enumerate(parts):
                            if p == 'vessels' and i + 1 < len(parts):
                                vessel['mmsi'] = parts[-1].split('-')[0]

                # Type
                type_el = item.select_one('.ship-type, .vessel-type')
                if type_el:
                    vessel['type'] = type_el.get_text(strip=True)

                # Flag
                flag_el = item.select_one('.flag, [class*="flag-"]')
                if flag_el:
                    vessel['flag'] = flag_el.get('title', '') or flag_el.get_text(strip=True)

                if vessel.get('name'):
                    results.append(vessel)

            return results

        except Exception as e:
            print(f"Search error: {e}")
            return []

    def get_vessel_page(self, mmsi: str) -> Dict:
        """
        Get vessel details from public page
        """
        url = f"{MT_BASE}/en/ais/details/ships/mmsi:{mmsi}"

        try:
            resp = self.session.get(url, timeout=10)
            if resp.status_code != 200:
                return {}

            soup = BeautifulSoup(resp.text, 'html.parser')
            vessel = {'mmsi': mmsi}

            # Parse vessel details
            # Name
            name_el = soup.select_one('h1.title, .vessel-name')
            if name_el:
                vessel['name'] = name_el.get_text(strip=True)

            # Details table
            for row in soup.select('.vessel-details tr, .details-table tr'):
                cells = row.select('td')
                if len(cells) >= 2:
                    key = cells[0].get_text(strip=True).lower()
                    value = cells[1].get_text(strip=True)

                    if 'imo' in key:
                        vessel['imo'] = value
                    elif 'mmsi' in key:
                        vessel['mmsi'] = value
                    elif 'call sign' in key:
                        vessel['callsign'] = value
                    elif 'flag' in key:
                        vessel['flag'] = value
                    elif 'type' in key:
                        vessel['type'] = value
                    elif 'length' in key:
                        vessel['length'] = self._parse_number(value)
                    elif 'width' in key or 'beam' in key:
                        vessel['width'] = self._parse_number(value)
                    elif 'draught' in key or 'draft' in key:
                        vessel['draught'] = self._parse_number(value)
                    elif 'gross tonnage' in key:
                        vessel['gross_tonnage'] = self._parse_number(value)
                    elif 'deadweight' in key:
                        vessel['deadweight'] = self._parse_number(value)
                    elif 'year built' in key:
                        vessel['year_built'] = self._parse_number(value)

            # Current position
            pos_el = soup.select_one('.position-data, [data-lat], [data-lon]')
            if pos_el:
                vessel['latitude'] = pos_el.get('data-lat')
                vessel['longitude'] = pos_el.get('data-lon')

            # Last position from text
            pos_text = soup.select_one('.last-position, .position-info')
            if pos_text:
                text = pos_text.get_text()
                # Parse coordinates from text
                lat_match = re.search(r'(\d+\.\d+)[°\s]*[NS]', text)
                lon_match = re.search(r'(\d+\.\d+)[°\s]*[EW]', text)
                if lat_match:
                    vessel['latitude'] = float(lat_match.group(1))
                if lon_match:
                    vessel['longitude'] = float(lon_match.group(1))

            return vessel

        except Exception as e:
            print(f"Page parse error: {e}")
            return {}

    def get_port_vessels(self, port_name: str) -> List[Dict]:
        """
        Get vessels currently in port
        """
        url = f"{MT_BASE}/en/ais/index/search/all/keyword:{port_name}"

        try:
            resp = self.session.get(url, timeout=10)
            # Parse and return vessels in that port
            # Similar to search_vessel_public
            return []  # TODO: implement
        except Exception as e:
            print(f"Port search error: {e}")
            return []

    # =========================================================================
    # API METHODS (requires API key)
    # =========================================================================

    def _api_call(self, service: str, params: dict) -> dict:
        """Make API call"""
        if not self.api_key:
            raise ValueError("API key required. Set MARINETRAFFIC_API_KEY")

        url = f"{MT_API_BASE}/{service}/{self.api_key}"
        params['protocol'] = 'jsono'  # JSON output

        try:
            resp = self.session.get(url, params=params, timeout=30)
            return resp.json()
        except Exception as e:
            print(f"API error: {e}")
            return {}

    def api_vessel_info(self, mmsi: str = None, imo: str = None) -> dict:
        """
        PS01 - Vessel Particulars
        Get detailed vessel info via API
        """
        params = {}
        if mmsi:
            params['mmsi'] = mmsi
        elif imo:
            params['imo'] = imo
        else:
            raise ValueError("MMSI or IMO required")

        return self._api_call('vesselparticulars', params)

    def api_vessel_position(self, mmsi: str = None, imo: str = None) -> dict:
        """
        PS07 - Single Vessel Position
        Get current vessel position via API
        """
        params = {'timespan': 60}  # Last 60 minutes
        if mmsi:
            params['mmsi'] = mmsi
        elif imo:
            params['imo'] = imo

        return self._api_call('exportvessel', params)

    def api_port_calls(self, mmsi: str = None, imo: str = None) -> dict:
        """
        VD02 - Port Calls
        Get vessel port call history
        """
        params = {}
        if mmsi:
            params['mmsi'] = mmsi
        elif imo:
            params['imo'] = imo

        return self._api_call('portcalls', params)

    def api_vessels_in_area(self, lat_min: float, lat_max: float,
                            lon_min: float, lon_max: float) -> list:
        """
        PS02 - Vessels in Area
        Get all vessels in geographic area
        """
        params = {
            'MINLAT': lat_min,
            'MAXLAT': lat_max,
            'MINLON': lon_min,
            'MAXLON': lon_max
        }
        return self._api_call('exportvessels', params)

    # =========================================================================
    # HELPERS
    # =========================================================================

    def _parse_number(self, text: str) -> Optional[float]:
        """Extract number from text"""
        if not text:
            return None
        match = re.search(r'[\d,]+\.?\d*', text.replace(',', ''))
        if match:
            try:
                return float(match.group())
            except:
                pass
        return None

    def has_api_key(self) -> bool:
        """Check if API key is configured"""
        return bool(self.api_key)


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

_parser = None


def get_parser() -> MarineTrafficParser:
    """Get singleton parser instance"""
    global _parser
    if _parser is None:
        _parser = MarineTrafficParser()
    return _parser


def search_vessel(query: str) -> List[Dict]:
    """Quick vessel search"""
    return get_parser().search_vessel_public(query)


def get_vessel(mmsi: str) -> Dict:
    """Get vessel details"""
    return get_parser().get_vessel_page(mmsi)


if __name__ == "__main__":
    # Test
    parser = MarineTrafficParser()

    print("API key configured:", parser.has_api_key())

    # Test public search
    print("\nSearching for 'MAERSK'...")
    results = parser.search_vessel_public("MAERSK")
    for v in results[:5]:
        print(f"  - {v}")
