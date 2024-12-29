from django.core.management.base import BaseCommand
from jwcrypto import jwk


class Command(BaseCommand):
    help = 'Generates a new RSA key pair and exports public and private keys'

    def handle(self, *args, **options):
        # Generate a new RSA key pair
        key = jwk.JWK.generate(kty='RSA', size=2048)

        # Export the public and private keys
        public_key = key.export(private_key=False)  # Public key for Railsr
        private_key = key.export(private_key=True)  # Private key for your use

        # Print the keys to the console
        self.stdout.write(self.style.SUCCESS(f'Public Key: {public_key}'))
        self.stdout.write(self.style.SUCCESS(f'Private Key: {private_key}'))

        # Optional: Save the private key to a file for use in your application
        with open('private_key.pem', 'w') as private_key_file:
            private_key_file.write(private_key)
        self.stdout.write(self.style.SUCCESS('Private key saved to private_key.pem'))
