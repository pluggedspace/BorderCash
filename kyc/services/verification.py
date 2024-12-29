import requests
import logging


class Verification:

    @staticmethod
    def verify_address(address, api_key):
        api_key = 'pk.10bfa8852fcb5b465d8247a86c3170a5'
        url = f'https://api.locationiq.com/v1/autocomplete.php?key={api_key}&q={address}&format=json'
        response = requests.get(url)
        if response.status_code == 200 and len(response.json()) > 0:
            return True
        return False

    @staticmethod
    def run_aml_check(user):
        databases = {
            "Global_Sanctions_Database": ("https://ws-public.interpol.int", "GET"),
            "FBI_Wanted": ("https://api.fbi.gov/wanted/v1/list", "GET"),
            "PEP_List": (
            "https://data.opensanctions.org/datasets/20241031/peps/names.txt?v=20241031002704-dys", "File"),
        }

        results = {}
        user_name = user.get_full_name()

        for db_name, (db_url, method) in databases.items():
            try:
                if method == "GET":
                    response = requests.get(db_url, params={'q': user_name})
                    response.raise_for_status()
                    if db_name == "Global_Sanctions_Database":
                        cleared_status = response.json().get('cleared')
                    elif db_name == "FBI_Wanted":
                        cleared_status = not response.json().get("total", 0)
                elif method == "File":
                    response = requests.get(db_url)
                    response.raise_for_status()
                    cleared_status = user_name not in response.text
                results[db_name] = cleared_status if cleared_status is not None else "invalid_response"
            except requests.exceptions.RequestException as err:
                logging.error(f"Error for {db_name}: {err}")
                results[db_name] = "connection_error"
        return results
