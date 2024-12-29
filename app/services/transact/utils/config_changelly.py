# Define constants for Stellar server and keypair
import logging

from stellar_sdk import Server, Asset, TransactionBuilder, Network

STELLAR_SERVER = Server("https://horizon-testnet.stellar.org")
STELLAR_PUBLIC_KEY = "GCA3RMKZWC7ZHFRBXAPKCWSP3FOWNRRX2NR5K4QZDOKSZVJSA3FSIZKQ"
STELLAR_SECRET_KEY = "SC34UKYKGMAUFWRZNB7ELZDKHJILDMR4SYSKD3B2MEM5YDMGF7US2M3L"
USDC_ASSET = Asset("USDC", "GA5ZSEJYB37JRC5AVCIA5MOP4RHTM335X2KGX3IHOJAPP5RE34K4KZVN")
TRANSACTION_TIMEOUT = 30  # Adjust timeout as needed
asset_issuer = "GA5ZSEJYB37JRC5AVCIA5MOP4RHTM335X2KGX3IHOJAPP5RE34K4KZVN"
asset_code = "USDC"


# Establish trustline function
def establish_trustline_for_usdc(account, keypair, asset):
        try:
            transaction_builder = TransactionBuilder(
                source_account=account,
                network_passphrase=Network.TESTNET_NETWORK_PASSPHRASE,
                base_fee=STELLAR_SERVER.fetch_base_fee()
            )
            transaction = transaction_builder.append_change_trust_op(
                asset=asset
            ).set_timeout(TRANSACTION_TIMEOUT).build()

            transaction.sign(keypair)
            response = STELLAR_SERVER.submit_transaction(transaction)
            return response
        except Exception as e:
            logging.error(f"Error establishing trustline for USDC: {e}")
            return None
