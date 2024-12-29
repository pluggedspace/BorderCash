import logging
from decimal import Decimal, InvalidOperation

from app.models import Fee

logger = logging.getLogger(__name__)


def calculate_fee(transaction_type, amount):
    try:
        amount = Decimal(amount)  # Ensure `amount` is a valid Decimal
        total_amount, fee_amount = Fee.apply_transaction_fee(transaction_type, amount)
        net_amount = amount - fee_amount
        return total_amount, fee_amount, net_amount
    except InvalidOperation as e:
        logger.error(f"Invalid amount format in calculate_fee: {amount} - Error: {e}")
        raise ValueError("Invalid amount format for fee calculation")  # Raise or handle as needed


def has_sufficient_balance(account, amount):
    return account.balance >= amount


STATE_CODE_MAPPING = {
    "Alabama": "AL", "Alaska": "AK", "Arizona": "AZ", "Arkansas": "AR",
    "California": "CA", "Colorado": "CO", "Connecticut": "CT", "Delaware": "DE",
    "Florida": "FL", "Georgia": "GA", "Hawaii": "HI", "Idaho": "ID",
    "Illinois": "IL", "Indiana": "IN", "Iowa": "IA", "Kansas": "KS",
    "Kentucky": "KY", "Louisiana": "LA", "Maine": "ME", "Maryland": "MD",
    "Massachusetts": "MA", "Michigan": "MI", "Minnesota": "MN", "Mississippi": "MS",
    "Missouri": "MO", "Montana": "MT", "Nebraska": "NE", "Nevada": "NV",
    "New Hampshire": "NH", "New Jersey": "NJ", "New Mexico": "NM", "New York": "NY",
    "North Carolina": "NC", "North Dakota": "ND", "Ohio": "OH", "Oklahoma": "OK",
    "Oregon": "OR", "Pennsylvania": "PA", "Rhode Island": "RI", "South Carolina": "SC",
    "South Dakota": "SD", "Tennessee": "TN", "Texas": "TX", "Utah": "UT",
    "Vermont": "VT", "Virginia": "VA", "Washington": "WA", "West Virginia": "WV",
    "Wisconsin": "WI", "Wyoming": "WY"
}


def get_state_code(state_name):
    return STATE_CODE_MAPPING.get(state_name, "")  # Return empty if not found


class InsufficientFundsError(Exception):
    pass


class UserNotVerifiedError(Exception):
    pass
