# 💸 BorderCash

BorderCash is a professional, open-source fintech infrastructure designed for cross-border payments, digital wallet management, and tokenized asset investments. It leverages a central custody model backed by USDC on the Stellar network to provide secure, fast, and scalable financial services.

## 🚀 Features

- **Centralized Custody**: Secure management of user balances with individual wallet records.
- **Fiat-to-Crypto Bridge**: Seamless deposits and withdrawals via Stellar anchors, converting fiat to USDC.
- **Multi-Currency Support**: Virtual accounts in USD, EUR, and GBP.
- **Investment Engine**: Tokenized stock market trading and asset portfolio management.
- **Integrated KYC**: Built-in identity verification and compliance onboarding.
- **Dispute Resolution**: Automated and human-led support system via the Monica module.
- **Reconciliation**: Internal accounting and audit system (DRAC) for financial integrity.

## 🛠 Tech Stack

### Backend
- **Language**: Python 3.10+
- **Framework**: Django 5.1+ & Django Rest Framework (DRF)
- **Task Queue**: Celery & Redis
- **Database**: PostgreSQL
- **Real-time**: Django Channels (WebSockets)
- **Auth**: SimpleJWT (JWT Bearer Tokens)

### Infrastructure & External Integrations
- **Blockchain**: Stellar Network (USDC)
- **Storage**: Dropbox (via `django-storages`)
- **Payment Gateways**: Changelly (Fiat/Crypto bridge)
- **Identity**: Custom KYC Engine
- **Deployment**: Docker & Docker Compose

## 📦 Installation

### Prerequisites
- Python 3.10+
- PostgreSQL
- Redis
- Docker & Docker Compose (Recommended)

### Quick Start with Docker
1. **Clone the repository**:
   ```bash
   git clone https://github.com/BorderCash/BorderCash.git
   cd BorderCash
   ```

2. **Configure Environment**:
   ```bash
   cp .env.example .env
   # Edit .env with your actual API keys and secrets
   ```

3. **Spin up the system**:
   ```bash
   docker-compose up --build -d
   ```

4. **Run Migrations**:
   ```bash
   docker-compose exec web python manage.py migrate
   ```

5. **Create Admin User**:
   ```bash
   docker-compose exec web python manage.py createsuperuser
   ```

### Manual Installation
1. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```
2. **Apply Migrations**:
   ```bash
   python manage.py migrate
   ```
3. **Run Server**:
   ```bash
   python manage.py runserver
   ```

## 📖 Documentation

For a deep dive into the system architecture, API usage, and administration guides, please refer to the [DOCUMENTATION.md](./DOCUMENTATION.md) file.

## 🤝 Contributing

We welcome contributions! Please read our [CONTRIBUTING.md](./CONTRIBUTING.md) and [SECURITY.md](./SECURITY.md) before getting started.

## 📜 License

This project is licensed under the MIT License - see the [LICENSE](./LICENSE) file for details.



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

git clone https://github.com/BorderCash/BorderCash.git
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

For any questions or support, reach out to support@border.cash



