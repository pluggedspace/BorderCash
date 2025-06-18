from decimal import Decimal, InvalidOperation
import logging
from rest_framework import generics, viewsets, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated

from django.conf import settings
from django.db import transaction
from django.contrib.auth.models import User
from django.views import View
from django.http import JsonResponse
from celery import shared_task

from invest.services.utils import analyze_trend
from invest.services.stellar_utils import stellar_service
from invest.tasks import process_trade, transfer_usdc_between_custodies
from invest.models import TokenizedStock, UserInvestment, TransactionLog, InvestmentAccount
from .serializers import TokenizedStockSerializer, UserInvestmentSerializer, TransactionLogSerializer
from app.models import USDAccount


logger = logging.getLogger(__name__)

class InvestmentAccountView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """Retrieve investment account balance."""
        investment_account, _ = InvestmentAccount.objects.get_or_create(user=request.user)
        return Response({"balance": investment_account.balance}, status=status.HTTP_200_OK)

class PortfolioView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """Fetch user's portfolio with current stock values and investment stats."""
        user_investments = UserInvestment.objects.filter(user=request.user)
        portfolio = []
        total_investment_value = 0
        total_purchase_value = 0

        for investment in user_investments:
            stock = investment.stock
            current_value = investment.amount_held * stock.price
            purchase_value = investment.amount_held * investment.purchase_price
            profit_loss = current_value - purchase_value
            percentage_change = ((current_value - purchase_value) / purchase_value) * 100 if purchase_value > 0 else 0

            total_investment_value += current_value
            total_purchase_value += purchase_value

            portfolio.append({
                "stock": stock.name,
                "symbol": stock.symbol,
                "amount_held": float(investment.amount_held),
                "purchase_price": float(investment.purchase_price),
                "current_price": float(stock.price),
                "current_value": float(current_value),
                "profit_loss": float(profit_loss),
                "percentage_change": float(percentage_change)
            })

        overall_profit_loss = total_investment_value - total_purchase_value
        overall_percentage_change = (overall_profit_loss / total_purchase_value * 100) if total_purchase_value > 0 else 0

        investment_account, _ = InvestmentAccount.objects.get_or_create(user=request.user)

        return Response({
            "portfolio": portfolio,
            "investment_balance": float(investment_account.balance),
            "total_investment_value": float(total_investment_value),
            "overall_profit_loss": float(overall_profit_loss),
            "overall_percentage_change": float(overall_percentage_change)
        }, status=status.HTTP_200_OK)



class DepositView(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request):
        """Deposit funds from Swif wallet to investment account."""
        amount = Decimal(request.data.get("amount", 0))

        if amount <= 0:
            return Response({"error": "Invalid deposit amount"}, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            swif_wallet = USDAccount.objects.select_for_update().get(user=request.user)
            investment_account, _ = InvestmentAccount.objects.select_for_update().get_or_create(user=request.user)

            if swif_wallet.balance < amount:
                return Response({"error": "Insufficient balance in Swif wallet"}, status=status.HTTP_400_BAD_REQUEST)

            swif_wallet.balance -= amount
            investment_account.balance += amount
            swif_wallet.save()
            investment_account.save()

        # Trigger Stellar custody transfer (Swif → Investment = to_investment)
        transfer_usdc_between_custodies.delay(str(amount), "to_investment")

        return Response({
            "message": "Deposit successful",
            "investment_balance": investment_account.balance,
            "swif_wallet_balance": swif_wallet.balance
        }, status=status.HTTP_200_OK)

class WithdrawView(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request):
        """Withdraw funds from investment account to Swif wallet with atomic transaction."""
        try:
            try:
                amount = Decimal(str(request.data.get("amount", 0)))
                if amount <= 0:
                    return Response({"status": "error", "message": "Amount must be greater than zero"}, status=status.HTTP_400_BAD_REQUEST)
            except (ValueError, InvalidOperation):
                return Response({"status": "error", "message": "Invalid amount format"}, status=status.HTTP_400_BAD_REQUEST)

            swif_wallet = USDAccount.objects.select_for_update().get(user=request.user)
            investment_account = InvestmentAccount.objects.select_for_update().get(user=request.user)

            if investment_account.balance < amount:
                return Response({
                    "status": "error",
                    "message": "Insufficient balance in investment account",
                    "current_balance": str(investment_account.balance)
                }, status=status.HTTP_400_BAD_REQUEST)

            investment_account.balance -= amount
            swif_wallet.balance += amount
            investment_account.save()
            swif_wallet.save()

            # Trigger Stellar custody transfer (Investment → Swif = to_central)
            transfer_usdc_between_custodies.delay(str(amount), "to_central")

            return Response({
                "status": "success",
                "message": "Withdrawal successful",
                "data": {
                    "investment_balance": str(investment_account.balance),
                    "swif_wallet_balance": str(swif_wallet.balance),
                    "withdrawn_amount": str(amount)
                }
            }, status=status.HTTP_200_OK)

        except USDAccount.DoesNotExist:
            return Response({"status": "error", "message": "SWIF wallet account not found"}, status=status.HTTP_404_NOT_FOUND)
        except InvestmentAccount.DoesNotExist:
            return Response({"status": "error", "message": "Investment account not found"}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({"status": "error", "message": "An unexpected error occurred"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
 
 
            
class InvestmentUpdateView(APIView):
    """
    API endpoint to update an existing investment.
    """
    def put(self, request, investment_id, *args, **kwargs):
        try:
            investment = Investment.objects.get(id=investment_id, user=request.user)
        except Investment.DoesNotExist:
            return Response({"error": "Investment not found"}, status=status.HTTP_404_NOT_FOUND)

        serializer = UserInvestmentSerializer(investment, data=request.data, partial=True)
        if serializer.is_valid():
            # Update investment details
            serializer.save()
            return Response({"status": "success", "message": "Investment updated successfully"}, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class StockListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """Fetch a list of all available stocks."""
        stocks = TokenizedStock.objects.all()
        serializer = TokenizedStockSerializer(stocks, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

class StockDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, stock_id):
        """Fetch details of a specific stock by ID."""
        try:
            stock = TokenizedStock.objects.get(id=stock_id)
            serializer = TokenizedStockSerializer(stock)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except TokenizedStock.DoesNotExist:
            return Response({"error": "Stock not found"}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class TransactionLogView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """Fetch all transaction logs of a user."""
        logs = TransactionLog.objects.filter(user=request.user)
        serializer = TransactionLogSerializer(logs, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

class BuyStockView(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request):
        """Handle stock purchase with atomic transaction support"""
        response_data = {
            'status': 'error',
            'message': '',
            'data': {}
        }
        http_status = status.HTTP_400_BAD_REQUEST
        
        try:
            # Validate asset symbol
            asset_symbol = request.data.get('asset_symbol', '').strip().upper()
            if not asset_symbol:
                response_data['message'] = "Asset symbol is required"
                return Response(response_data, status=http_status)

            # Validate amount
            amount_str = request.data.get('amount')
            if not amount_str:
                response_data['message'] = "Amount is required"
                return Response(response_data, status=http_status)

            try:
                amount = Decimal(str(amount_str))
                if amount <= 0:
                    response_data['message'] = f"Amount must be positive (received: {amount_str})"
                    return Response(response_data, status=http_status)
            except (ValueError, InvalidOperation, TypeError) as e:
                response_data['message'] = f"Invalid amount: {str(e)}"
                return Response(response_data, status=http_status)

            # Validate stop_loss/take_profit
            stop_loss = request.data.get('stop_loss')
            take_profit = request.data.get('take_profit')
            try:
                stop_loss = Decimal(stop_loss) if stop_loss else None
                take_profit = Decimal(take_profit) if take_profit else None
                
                if stop_loss is not None and stop_loss <= 0:
                    raise ValueError("Stop loss must be positive")
                if take_profit is not None and take_profit <= 0:
                    raise ValueError("Take profit must be positive")
            except (ValueError, InvalidOperation) as e:
                response_data['message'] = f"Invalid order parameters: {str(e)}"
                return Response(response_data, status=http_status)

            # Get stock with lock to prevent race conditions
            try:
                stock = TokenizedStock.objects.select_for_update().get(
                    symbol=asset_symbol, 
                    is_active=True
                )
            except TokenizedStock.DoesNotExist:
                response_data['message'] = f"Stock {asset_symbol} not found or inactive"
                http_status = status.HTTP_404_NOT_FOUND
                return Response(response_data, status=http_status)

            # Check account balance with lock
            try:
                account = InvestmentAccount.objects.select_for_update().get(user=request.user)
                total_cost = amount * Decimal(stock.price)
                
                if account.balance < total_cost:
                    response_data['message'] = (
                        f"Insufficient balance. Available: {account.balance}, "
                        f"Required: {total_cost}"
                    )
                    http_status = status.HTTP_403_FORBIDDEN
                    return Response(response_data, status=http_status)

                # Submit trade to Celery
                task = process_trade.apply_async(
                    kwargs={
                        'user_id': request.user.id,
                        'transaction_type': 'BUY',
                        'asset_symbol': asset_symbol,
                        'amount': str(amount),
                        'stop_loss': str(stop_loss) if stop_loss else None,
                        'take_profit': str(take_profit) if take_profit else None,
                    },
                    queue='trades'
                )

                response_data = {
                    'status': 'pending',
                    'message': 'Buy order submitted for processing',
                    'data': {
                        'task_id': task.id,
                        'asset': asset_symbol,
                        'amount': str(amount),
                        'estimated_cost': str(total_cost),
                        'current_price': str(stock.price),
                        'remaining_balance': str(account.balance - total_cost)
                    }
                }
                http_status = status.HTTP_202_ACCEPTED

            except InvestmentAccount.DoesNotExist:
                response_data['message'] = "Investment account not found"
                http_status = status.HTTP_404_NOT_FOUND
                return Response(response_data, status=http_status)

        except Exception as e:
            logger.error(f"BuyStockView error: {str(e)}", exc_info=True)
            response_data['message'] = "An unexpected error occurred"
            http_status = status.HTTP_500_INTERNAL_SERVER_ERROR
            if settings.DEBUG:
                response_data['debug'] = str(e)
        
        return Response(response_data, status=http_status)

class SellStockView(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request):
        """Handle stock sales through custodian model using asset_symbol"""
        response_data = {
            'status': 'error',
            'message': '',
            'data': {}
        }
        http_status = status.HTTP_400_BAD_REQUEST
        
        try:
            # Validate asset symbol
            asset_symbol = request.data.get('asset_symbol', '').strip().upper()
            if not asset_symbol:
                response_data['message'] = "Asset symbol is required"
                return Response(response_data, status=http_status)

            # Validate amount
            amount_str = request.data.get('amount')
            if not amount_str:
                response_data['message'] = "Amount is required"
                return Response(response_data, status=http_status)

            try:
                amount = Decimal(str(amount_str))
                if amount <= 0:
                    response_data['message'] = f"Amount must be positive (received: {amount_str})"
                    return Response(response_data, status=http_status)
            except (ValueError, InvalidOperation, TypeError) as e:
                response_data['message'] = f"Invalid amount: {str(e)}"
                return Response(response_data, status=http_status)

            # Verify stock exists
            try:
                stock = TokenizedStock.objects.select_for_update().get(
                    symbol=asset_symbol, 
                    is_active=True
                )
            except TokenizedStock.DoesNotExist:
                response_data['message'] = f"Stock {asset_symbol} not found or inactive"
                http_status = status.HTTP_404_NOT_FOUND
                return Response(response_data, status=http_status)

            # Verify holdings exist (exact amount checked in task)
            if not UserInvestment.objects.filter(
                user=request.user,
                stock=stock,
                amount_held__gt=0
            ).exists():
                response_data['message'] = f"You don't own {asset_symbol} stock"
                http_status = status.HTTP_403_FORBIDDEN
                return Response(response_data, status=http_status)

            # Submit to Celery
            task = process_trade.apply_async(
                kwargs={
                    "user_id": request.user.id,
                    "transaction_type": "SELL",
                    "asset_symbol": asset_symbol,
                    "amount": str(amount),
                },
                queue='high_priority'
            )
            
            response_data = {
                "status": "pending",
                "message": f"Sell order for {amount} {asset_symbol} submitted",
                "data": {
                    "task_id": task.id,
                    "asset": asset_symbol,
                    "amount": str(amount),
                    "current_price": str(stock.price)
                }
            }
            http_status = status.HTTP_202_ACCEPTED

        except Exception as e:
            logger.error(f"Sell failed: {str(e)}", exc_info=True)
            response_data['message'] = str(e)
            http_status = status.HTTP_500_INTERNAL_SERVER_ERROR
        
        return Response(response_data, status=http_status)

class TaskStatusView(APIView):
    def get(self, request, task_id):
        task = AsyncResult(task_id)
        return Response({
            'ready': task.ready(),
            'successful': task.successful(),
            'result': task.result if task.ready() else None,
            'status': task.status
        })