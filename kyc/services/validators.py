from django.core.exceptions import ValidationError
import magic


def validate_document_size(file):
    max_size = 10 * 1024 * 1024  # 10MB
    if file.size > max_size:
        raise ValidationError('File size must not exceed 5MB')


def validate_document_type(file):
    valid_mime_types = ['image/jpeg', 'image/png', 'application/pdf']

    # Reset the file pointer to the beginning after reading
    file.seek(0)

    # Create a magic instance
    mime = magic.Magic(mime=True)

    # Get the MIME type
    file_mime_type = mime.from_buffer(file.read())

    # Check if the MIME type is valid
    if file_mime_type not in valid_mime_types:
        raise ValidationError('Unsupported file type')

    # Reset the file pointer to the beginning after reading
    file.seek(0)
