# BorderCash System Documentation

BorderCash is a comprehensive fintech platform designed for cross-border payments, investment management, and digital wallet services. It provides a robust infrastructure for handling transactions, KYC verification, and automated financial services.

## 🏗 System Architecture

The system is built on a modular Django architecture with several specialized applications:

### Core Modules
- **`app`**: The central engine handling User Profiles, Transactional logic, and Core Wallet services.
- **`kyc`**: Handles Know Your Customer (KYC) verification and compliance.
- **`iban`**: Manages virtual IBAN generation and account mapping.
- **`invest`**: Manages tokenized stock investments and asset tracking.
- **`monica`**: A support and dispute resolution system for handling customer grievances.
- **`drac`**: Internal reconciliation and accounting system.
- **`backup`**: Automated data backup services.

### Technical Stack
- **Backend**: Django & Django Rest Framework (DRF)
- **Task Queue**: Celery & Redis (for asynchronous processing)
- **Database**: PostgreSQL
- **Real-time**: Django Channels (WebSockets)
- **Storage**: Dropbox (via `django-storages`)
- **Auth**: SimpleJWT (Bearer Token Authentication)

---

## 🛠 Usage Guide

### For Users (API Consumers)

Users interact with the system primarily through the REST API.

#### 1. Authentication
- **Registration**: Create an account via the `/api/register/` endpoint.
- **Verification**: Verify your email using the token sent to your inbox.
- **Login**: Obtain a JWT access and refresh token via `/api/token/`.

#### 2. Core Wallet Operations
- **Deposit**: Fund your account using integrated gateways (e.g., Changelly).
- **Withdrawal**: Request funds to be sent to external wallets or bank accounts.
- **Balance**: Check your current available and locked balances.

#### 3. Investments
- **Browse Assets**: View available tokenized stocks.
- **Invest**: Purchase assets using your wallet balance.
- **Track**: Monitor the real-time value of your investment portfolio.

#### 4. Support & Disputes
- **Raise Dispute**: Use the Monica module to report failed transactions or unauthorized charges.
- **Check Status**: Track the progress of your dispute resolution.

---

### For Administrators (Staff)

Administrators manage the system via the Django Admin Panel (`/admin/`).

#### 1. User Management
- **KYC Approval**: Review submitted documents in the KYC module and approve/reject users.
- **Account Oversight**: Monitor user balances and transaction histories.
- **Role Management**: Assign staff permissions to different team members.

#### 2. Transactional Oversight
- **Audit Logs**: Review all system transactions in the `drac` module.
- **Reconciliation**: Run reconciliation tasks to ensure internal balances match external provider records.

#### 3. Investment Management
- **Asset Updates**: Trigger stock price updates via management commands.
- **Pool Management**: Configure investment pools and public keys.

#### 4. Communications
- **Promotional Emails**: Create and send bulk emails to users via the Promotional Email admin.
- **Email Templates**: Customize the look and feel of system emails.

---

## 🚀 Deployment & Configuration

Detailed deployment steps are available in the `README.md`. Ensure all environment variables listed in `.env.example` are correctly configured.