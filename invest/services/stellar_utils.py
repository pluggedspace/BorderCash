import requests
from stellar_sdk import Server, Keypair, TransactionBuilder, Network, Asset
from stellar_sdk.exceptions import NotFoundError, BadResponseError, BadRequestError
from django.conf import settings
from django.db import transaction
from decimal import Decimal, getcontext, DecimalException
import logging

logger = logging.getLogger(__name__)

# Set higher precision for Decimal calculations
getcontext().prec = 10

class StellarService:
    def __init__(self):
        self.network_passphrase = Network.PUBLIC_NETWORK_PASSPHRASE
        self.server = Server(horizon_url="https://horizon.stellar.org")
        self.holder_keypair = Keypair.from_secret(settings.INVESTMENT_ACCOUNT_SECRET)
        self.base_fee = 100  # 100 stroops = 0.00001 XLM
        # Trusted USD issuer (e.g., AnchorUSD)
        self.usd_issuer = "GA5ZSEJYB37JRC5AVCIA5MOP4RHTM335X2KGX3IHOJAPP5RE34K4KZVN"

    def _fetch_xlm_usd_price(self):
        """Internal method to fetch XLM/USD price"""
        try:
            orderbook = self.server.orderbook(
                selling=Asset.native(),  # XLM
                buying=Asset(code="USDC", issuer=self.usd_issuer)
            ).call()
            
            if orderbook.get('asks'):
                return Decimal(orderbook['asks'][0]['price'])
            return None
        except Exception as e:
            logger.error(f"Failed to fetch XLM/USD price: {str(e)}", exc_info=True)
            return None

    def _fetch_asset_price_in_xlm(self, asset_code, issuer):
        """Internal method to fetch asset price in XLM"""
        try:
            orderbook = self.server.orderbook(
                selling=Asset(code=asset_code, issuer=issuer),
                buying=Asset.native()  # XLM
            ).call()
            
            if orderbook.get('bids'):
                return Decimal(orderbook['bids'][0]['price'])
            return None
        except Exception as e:
            logger.error(f"Failed to fetch {asset_code}/XLM price: {str(e)}", exc_info=True)
            return None

    def _fetch_asset_price_in_usd(self, asset_code, issuer):
        """Internal method to fetch asset price in USD"""
        try:
            orderbook = self.server.orderbook(
                selling=Asset(code=asset_code, issuer=issuer),
                buying=Asset(code="USDC", issuer=self.usd_issuer)
            ).call()
        
            if orderbook.get('bids'):
                return Decimal(orderbook['bids'][0]['price'])
            return None
        except Exception as e:
            logger.error(f"Failed to fetch {asset_code}/USD price: {str(e)}", exc_info=True)
            return None

    def fetch_stellar_prices(self, asset_code, issuer):
        """
        Main method to fetch both XLM and USD prices for an asset
        Returns: {
            'price_xlm': Decimal,  # Price in XLM (how much XLM for 1 asset)
            'price_usd': Decimal,  # Price in USD (how much USD for 1 asset)
            'xlm_usd_rate': Decimal  # Conversion rate (how much USD for 1 XLM)
        } or None if failed
        """
        # Get direct USD price of the asset
        asset_usd_price = self._fetch_asset_price_in_usd(asset_code, issuer)
        # Get direct XLM price of the asset
        asset_xlm_price = self._fetch_asset_price_in_xlm(asset_code, issuer)
        # Get XLM/USD conversion rate
        xlm_usd_price = self._fetch_xlm_usd_price()
    
        # Fallback: if we can't get direct USD price, calculate it from XLM price
        if asset_usd_price is None and asset_xlm_price is not None and xlm_usd_price is not None:
            asset_usd_price = asset_xlm_price * xlm_usd_price
    
        # If we have no prices at all, return None
        if asset_xlm_price is None and asset_usd_price is None:
            return None
        
        return {
            'price_xlm': asset_xlm_price,
            'price_usd': asset_usd_price,
            'xlm_usd_rate': xlm_usd_price
        }

    @transaction.atomic
    def update_stock_prices(self):
        from invest.models import TokenizedStock
        """Batch update all tokenized stock prices using fetch_stellar_prices"""
        try:
            stocks = TokenizedStock.objects.filter(is_active=True)
            updates = []
            
            for stock in stocks:
                prices = self.fetch_stellar_prices(stock.symbol, stock.issuer_address)
                if not prices:
                    logger.warning(f"No prices fetched for {stock.symbol}")
                    continue
                    
                # Skip if any required price is None
                if None in (prices.get('price_usd'), prices.get('price_xlm'), stock.price, stock.price_in_xlm):
                    logger.warning(f"Missing price data for {stock.symbol} - current: {stock.price}, new: {prices}")
                    continue
                    
                # Convert to Decimal if not already
                new_price_usd = Decimal(str(prices['price_usd']))
                new_price_xlm = Decimal(str(prices['price_xlm']))
                current_price_usd = Decimal(str(stock.price))
                current_price_xlm = Decimal(str(stock.price_in_xlm))
                
                # Calculate price changes with safe division
                try:
                    usd_change = abs(new_price_usd - current_price_usd) / current_price_usd
                    xlm_change = abs(new_price_xlm - current_price_xlm) / current_price_xlm
                    
                    price_changed = (
                        usd_change > Decimal('0.0001') or 
                        xlm_change > Decimal('0.0001')
                    )
                except (TypeError, DecimalException, ZeroDivisionError) as e:
                    logger.error(f"Price change calculation failed for {stock.symbol}: {str(e)}")
                    continue
                
                if price_changed:
                    stock.price = new_price_usd
                    stock.price_in_xlm = new_price_xlm
                    updates.append(stock)
            
            if updates:
                TokenizedStock.objects.bulk_update(updates, ['price', 'price_in_xlm'])
            return len(updates)
            
        except Exception as e:
            logger.error(f"Price update failed: {str(e)}", exc_info=True)
            raise

    def execute_trade(self, transaction_type, asset_symbol, amount, user_wallet=None, stop_loss=None, take_profit=None):
        from invest.models import TokenizedStock, TransactionLog
        """
        Trade execution using fetch_stellar_prices for consistent price data
        """
        try:
            # Validate inputs
            if transaction_type.lower() not in ['buy', 'sell']:
                raise ValueError("Invalid transaction type")
            
            amount = Decimal(str(amount))
            if amount <= 0:
                raise ValueError("Amount must be positive")

            # Get stock details
            try:
                stock = TokenizedStock.objects.get(symbol=asset_symbol)
            except TokenizedStock.DoesNotExist:
                raise ValueError("Asset not found")

            # Get current prices using the main fetch method
            prices = self.fetch_stellar_prices(stock.symbol, stock.issuer_address)
            if not prices or None in (prices.get('price_usd'), prices.get('price_xlm')):
                raise ValueError("Could not fetch valid current prices")
                
            current_price_usd = Decimal(str(prices['price_usd']))
            current_price_xlm = Decimal(str(prices['price_xlm']))

            # Check trade conditions (using USD price)
            if transaction_type == "sell":
                if stop_loss is not None and current_price_usd <= Decimal(str(stop_loss)):
                    logger.info(f"Stop loss triggered at ${current_price_usd:.4f}")
                elif take_profit is not None and current_price_usd >= Decimal(str(take_profit)):
                    logger.info(f"Take profit triggered at ${current_price_usd:.4f}")
                else:
                    return {
                        "status": "holding",
                        "message": "Price conditions not met",
                        "current_price": float(current_price_usd),
                        "current_price_xlm": float(current_price_xlm)
                    }

            # Prepare assets
            asset = Asset(code=stock.symbol, issuer=stock.issuer_address)
            xlm = Asset.native()

            # Load accounts
            source_account = self.server.load_account(
                user_wallet.public_key if user_wallet else self.holder_keypair.public_key
            )

            # Build transaction
            builder = TransactionBuilder(
                source_account=source_account,
                network_passphrase=self.network_passphrase,
                base_fee=self.base_fee
            )

            if transaction_type == "buy":
                builder.append_payment_op(
                    destination=self.holder_keypair.public_key,
                    asset=asset,
                    amount=str(amount),
                    source=user_wallet.public_key if user_wallet else None
                )
            else:  # sell
                builder.append_payment_op(
                    destination=user_wallet.public_key if user_wallet else self.holder_keypair.public_key,
                    asset=xlm,
                    amount=str(amount * current_price_xlm),  # Use XLM price for DEX trade
                    source=self.holder_keypair.public_key
                )

            transaction = builder.set_timeout(30).build()

            # Sign transaction
            if user_wallet:
                transaction.sign(Keypair.from_secret(user_wallet.private_key))
            transaction.sign(self.holder_keypair)

            # Submit transaction
            response = self.server.submit_transaction(transaction)

            # Log transaction with all price info
            TransactionLog.objects.create(
                asset_symbol=stock.symbol,
                transaction_type=transaction_type,
                amount=amount,
                price=current_price_usd,
                price_xlm=current_price_xlm,
                xlm_usd_rate=prices['xlm_usd_rate'],
                status="completed",
                stellar_tx_hash=response["hash"],
                stop_loss=Decimal(str(stop_loss)) if stop_loss else None,
                take_profit=Decimal(str(take_profit)) if take_profit else None
            )

            return {
                "status": "success",
                "tx_hash": response["hash"],
                "price_usd": float(current_price_usd),
                "price_xlm": float(current_price_xlm),
                "amount": float(amount)
            }

        except NotFoundError as e:
            logger.error(f"Account not found: {str(e)}")
            return {"error": "Stellar account not found"}
        except BadResponseError as e:
            logger.error(f"Stellar bad response: {str(e)}")
            return {"error": "Stellar network error"}
        except BadRequestError as e:
            logger.error(f"Invalid transaction: {str(e)}")
            return {"error": "Invalid transaction parameters"}
        except Exception as e:
            logger.error(f"Trade execution failed: {str(e)}", exc_info=True)
            return {"error": "Trade execution failed"}

# Singleton instance
stellar_service = StellarService()