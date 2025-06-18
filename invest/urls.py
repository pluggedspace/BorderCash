from django.urls import path
from .views import (
    InvestmentAccountView,
    PortfolioView,
    DepositView,
    WithdrawView,
    InvestmentUpdateView,
    StockListView,
    StockDetailView,
    TransactionLogView,
    BuyStockView,
    SellStockView,
    TaskStatusView,
)

urlpatterns = [
    # Accounts and Balances
    path("investment-account/", InvestmentAccountView.as_view(), name="investment-account"),
    path("portfolio/", PortfolioView.as_view(), name="portfolio"),

    # Deposit and Withdrawals
    path("deposit/", DepositView.as_view(), name="deposit"),
    path("withdraw/", WithdrawView.as_view(), name="withdraw"),

    # Investments and Orders
    path("update/", InvestmentUpdateView.as_view(), name="update-investment"),
    path("buy/", BuyStockView.as_view(), name="buy-stock"),
    path("sell/", SellStockView.as_view(), name="sell-stock"),

    # Stocks
    path("stocks/", StockListView.as_view(), name="stock-list"),
    path("stocks/<int:stock_id>/", StockDetailView.as_view(), name="stock-detail"),

    # Logs and Tasks
    path("transaction-logs/", TransactionLogView.as_view(), name="transaction-logs"),
    path("task-status/<str:task_id>/", TaskStatusView.as_view(), name="task-status"),
]
