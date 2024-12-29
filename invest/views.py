import logging
from decimal import Decimal

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import TradingAccount, PortfolioAllocation, TransactionHistory, TradeHistory
from .services.alpaca_client import AlpacaClient
from .services.utils import fetch_batch_stock_prices, fetch_current_stock_price

# Configure logging
logger = logging.getLogger(__name__)


class TradingViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated]

    @action(detail=False, methods=['post'])
    def place_order(self, request):
        """Place an order with Alpaca API."""
        symbol = request.data.get("symbol")
        qty = request.data.get("quantity")
        side = request.data.get("side")

        # Input validation
        if not symbol or not qty or not side:
            logger.error(f"Missing parameters: symbol={symbol}, qty={qty}, side={side}")
            return Response({"error": "Missing required parameters: symbol, quantity, and side are required."},
                            status=status.HTTP_400_BAD_REQUEST)

        try:
            qty = Decimal(qty)
        except ValueError:
            logger.error(f"Invalid quantity: {qty}. Quantity must be a valid number.")
            return Response({"error": "Invalid quantity. Must be a valid decimal number."},
                            status=status.HTTP_400_BAD_REQUEST)

        if qty <= 0:
            logger.error(f"Invalid quantity: {qty}. Quantity must be greater than zero.")
            return Response({"error": "Quantity must be greater than zero."}, status=status.HTTP_400_BAD_REQUEST)

        if side not in ['buy', 'sell']:
            logger.error(f"Invalid side: {side}. Side must be 'buy' or 'sell'.")
            return Response({"error": "Invalid side, must be 'buy' or 'sell'."}, status=status.HTTP_400_BAD_REQUEST)

        # Fetch stock price before placing the order
        current_price = fetch_current_stock_price(symbol)
        if current_price is None:
            logger.error(f"Failed to fetch price for symbol: {symbol}")
            return Response({"error": "Failed to fetch stock price."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        # Place the order with Alpaca (including sub_tag)
        order_response = self.place_alpaca_order(request.user, symbol, qty, side)

        if "error" in order_response:
            logger.error(f"Error placing order: {order_response['error']}")
            return Response(order_response, status=status.HTTP_400_BAD_REQUEST)

        # Record the transaction in the database using a database transaction
        from django.db import transaction
        try:
            with transaction.atomic():  # This is where transaction is being used
                # Record the transaction
                transaction = TransactionHistory.objects.create(
                    user=request.user,
                    symbol=symbol,
                    transaction_type=TransactionHistory.TransactionType.BUY if side == "buy" else TransactionHistory.TransactionType.SELL,
                    quantity=qty,
                    price=current_price,  # Use the fetched price
                    status=TransactionHistory.TransactionStatus.PENDING,
                )

                # Update portfolio allocation if it's a buy or sell
                if side == "buy":
                    portfolio, created = PortfolioAllocation.objects.select_for_update().get_or_create(
                        user=request.user, symbol=symbol
                    )
                    portfolio.quantity += qty
                    portfolio.avg_price = ((portfolio.avg_price * portfolio.quantity) + (qty * current_price)) / (
                            portfolio.quantity + qty
                    )
                    portfolio.save()

                logger.info(f"Transaction recorded for {request.user} with symbol {symbol} and quantity {qty}")

            return Response(order_response, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error(f"Transaction failed: {str(e)}")
            return Response({"error": "Transaction failed, please try again later."},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @staticmethod
    def place_alpaca_order(user, symbol, qty, side):
        """Helper method to place order on Alpaca API."""
        try:
            trading_account = TradingAccount.objects.get(user=user)
            alpaca_tag = trading_account.alpaca_tag  # Use the same value for sub_tag as alpaca_tag

            alpaca_client = AlpacaClient()  # Initialize Alpaca client

            # Adjust the Alpaca order to handle both individual and omnibus model accounts
            order_response = alpaca_client.place_order(symbol, qty, side, alpaca_tag,
                                                       alpaca_tag)  # sub_tag is the same as alpaca_tag

            # Check if the order response is valid
            if order_response.get("error"):
                logger.error(f"Alpaca order failed: {order_response['error']}")
                return {"error": f"Alpaca order failed: {order_response['error']}"}

            return order_response
        except TradingAccount.DoesNotExist:
            logger.error(f"Trading account not found for user: {user.id}")
            return {"error": "Trading account not found."}
        except Exception as e:
            logger.error(f"Error placing Alpaca order: {e}")
            return {"error": str(e)}

    @action(detail=False, methods=['get'])
    def user_portfolio(self, request):
        """Get the user's portfolio data."""
        allocations = PortfolioAllocation.objects.filter(user=request.user)
        portfolio_data = []

        for allocation in allocations:
            current_price = fetch_batch_stock_prices(allocation.symbol)
            if current_price is None:
                continue  # Skip if price fetch fails

            current_value = current_price * allocation.quantity
            profit_or_loss = (current_price - allocation.avg_price) * allocation.quantity

            portfolio_data.append({
                "symbol": allocation.symbol,
                "quantity": allocation.quantity,
                "avg_price": allocation.avg_price,
                "current_value": current_value,
                "profit_or_loss": profit_or_loss,
            })

        return Response(portfolio_data, status=status.HTTP_200_OK)

    @action(detail=False, methods=['get'])
    def user_trade_history(self, request):
        """Get the user's trade history."""
        trades = TradeHistory.objects.filter(user=request.user)
        trade_data = []

        for trade in trades:
            current_value = trade.current_value()
            profit_or_loss = trade.profit_or_loss()

            trade_data.append({
                "symbol": trade.stock_symbol,
                "quantity": trade.quantity,
                "purchase_price": trade.purchase_price,
                "current_value": current_value,
                "profit_or_loss": profit_or_loss,
                "purchase_timestamp": trade.purchase_timestamp,
            })

        return Response(trade_data, status=status.HTTP_200_OK)
