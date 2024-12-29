Wallet System

This is a comprehensive wallet platform built using Django and Flutter, designed to provide users with a seamless experience for managing virtual accounts, investing in assets, and transferring funds. The wallet operates with central custody backed by USDC on the Stellar network and offers access to deposits, transfers, investments, and KYC services.

Features

1. Central Custody and User Wallets

Centralized custody of user balances, with individual wallet records per user.

Deposits and withdrawals via Stellar anchors, converting fiat into USDC and storing it on the Stellar network.

Transfers between users by using unique wallet IDs.



2. Multi-Currency Support

Virtual accounts in USD, EUR, and GBP for users.

Integration with IBAN & Wire Accounts for deposits and incoming transfers.



3. Investment Options

Access to stock market trading, real estate, and bond investments, leveraging the Stellar network.



4. Custom KYC Service

A separate KYC service built into the system to verify users of the wallet application.

Users can register and go through onboarding, with identity verification managed in the same project.



5. API Integration and Frontend

Flutter-based frontend with four main pages:

Wallet: Displays balances, transaction history, and deposit/withdrawal options.

Investment: Shows investment opportunities and portfolio management.

Card: Manages virtual cards linked to the wallet for purchases and transactions.

Settings: Provides user preferences, profile information, and KYC status.


API integration for all functionalities, including transactions, investments, and KYC verification.




Architecture

The wallet system consists of two Django apps:

1. Wallet App: Handles user registration, wallet management, transactions, and interactions with the Stellar network.


2. KYC App: Provides KYC verification services for users of the Wallet App. It ensures compliance and user verification before enabling full functionality.



Flow Overview

User Registration & KYC

1. Users sign up via the app, and their information is sent to the KYC service.


2. Once verified, the user can start transacting, investing, and using virtual accounts.



Deposits & Withdrawals

1. Deposit: Users deposit funds via bank accounts (NUBAN, IBAN), which are converted into USDC and stored in the central custody account.


2. Withdrawal: Users initiate withdrawals, which are converted back from USDC and transferred to their respective fiat bank accounts using Stellar anchors.



Transfers

Users can transfer funds between each other using unique wallet IDs.


Investments

Users can view and manage investments in stocks, real estate, and bonds directly from the app.


Prerequisites

Django 3.x+

Stellar SDK for Python and Flutter

Flutter SDK for building the mobile frontend

PostgreSQL as the database

APIs for IBAN, NUBAN, KYC, and Stellar Anchors


Installation

1. Clone the repository:

git clone https://github.com/rootcreator/bank.git
cd Bank


2. Install dependencies:

pip install -r requirements.txt


3. Set up the database:

python manage.py migrate


4. Set up environment variables for API keys (Stellar, IBAN, NUBAN, etc.).


5. Run the development server:

python manage.py runserver


6. Start the Flutter frontend:

cd flutter-app
flutter run



Usage

Register as a new user and complete the KYC process.

Deposit funds using a NUBAN or IBAN account.

Manage your wallet, transfer funds, and explore investment opportunities.

Withdraw funds to your bank account.


Contributing

1. Fork the repository.


2. Create a new branch (git checkout -b feature-branch).


3. Make your changes and commit them (git commit -m 'Add new feature').


4. Push the branch (git push origin feature-branch).


5. Open a pull request.



Contact

For any questions or support, reach out to support@pluggedspace.org



