import os
import logging
import asyncio
import aiohttp
from fuzzywuzzy import fuzz


class Verification:
    @staticmethod
    async def verify_address(address, api_key=None):
        """Verify if an address exists using LocationIQ."""
        api_key = os.getenv("LOCATIONIQ_API_KEY")
        if not api_key:
            logging.error("API key for LocationIQ is missing.")
            return False

        url = f"https://api.locationiq.com/v1/autocomplete.php?key={api_key}&q={address}&format=json"
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status == 200:
                    results = await response.json()
                    if results and address.lower() in results[0].get("display_name", "").lower():
                        return True
        return False

    @staticmethod
    async def run_aml_check(user):
        """Perform AML (Anti-Money Laundering) checks using multiple sources."""
        databases = {
            "OpenSanctions": "https://api.opensanctions.org/match",
            "FBI_Wanted": "https://api.fbi.gov/wanted/v1/list",
        }

        user_name = user.get_full_name()
        results = {}

        async def fetch(url, params=None):
            """Fetch data from an API asynchronously."""
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(url, params=params) as response:
                        if response.status == 200:
                            return await response.json()
            except Exception as e:
                logging.error(f"Error fetching from {url}: {e}")
            return None

        tasks = {
            "OpenSanctions": fetch(databases["OpenSanctions"], params={"q": user_name}),
            "FBI_Wanted": fetch(databases["FBI_Wanted"]),
        }
        responses = await asyncio.gather(*tasks.values())

        # OpenSanctions API Response Processing
        open_sanctions_result = responses[0]
        if open_sanctions_result and open_sanctions_result.get("matches"):
            results["OpenSanctions"] = any(
                fuzz.partial_ratio(user_name.lower(), match["name"].lower()) > 80
                for match in open_sanctions_result["matches"]
            )

        # FBI Wanted API Response Processing
        fbi_wanted_result = responses[1]
        if fbi_wanted_result:
            results["FBI_Wanted"] = any(
                fuzz.partial_ratio(user_name.lower(), person["title"].lower()) > 80
                for person in fbi_wanted_result.get("items", [])
            )

        return results
