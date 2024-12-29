import requests
from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from .models import IBANAccount, Card, Transaction, AuditLog, Notification
from .serializers import IBANAccountSerializer, CardSerializer, TransactionSerializer, NotificationSerializer


class IBANAccountViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated]

    @staticmethod
    def create(request):
        user = request.user
        response = requests.post('https://api.railsr.com/iban/create', json={'user_id': user.id})
        if response.status_code == 200:
            iban_data = response.json()
            iban = IBANAccount.objects.create(
                user=user,
                iban_number=iban_data['iban'],
                status='Active'
            )
            # Log the action
            AuditLog.objects.create(user=user, action=f"IBAN created: {iban.iban_number}")
            # Send notification
            Notification.objects.create(user=user, message=f"Your IBAN {iban.iban_number} has been created.")
            return Response(IBANAccountSerializer(iban).data, status=status.HTTP_201_CREATED)
        return Response({'error': 'Failed to create IBAN'}, status=response.status_code)

    @staticmethod
    def list(request):
        ibans = IBANAccount.objects.filter(user=request.user)
        serializer = IBANAccountSerializer(ibans, many=True)
        return Response(serializer.data)


class CardViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated]

    @staticmethod
    def create(request):
        user = request.user
        response = requests.post('https://api.railsr.com/card/create', json={'user_id': user.id})
        if response.status_code == 200:
            card_data = response.json()
            card = Card.objects.create(
                user=user,
                card_number=card_data['card_number'],
                card_type=card_data['card_type'],  # Assuming API returns card type like 'Debit'
                status='Active'
            )
            # Log the action
            AuditLog.objects.create(user=user, action=f"Card issued: {card.card_number}")
            # Send notification
            Notification.objects.create(user=user, message=f"Your card {card.card_number} has been issued.")
            return Response(CardSerializer(card).data, status=status.HTTP_201_CREATED)
        return Response({'error': 'Failed to issue card'}, status=response.status_code)

    @staticmethod
    def list(request):
        cards = Card.objects.filter(user=request.user)
        serializer = CardSerializer(cards, many=True)
        return Response(serializer.data)


class TransactionViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated]

    @staticmethod
    def create(request):
        user = request.user
        iban_id = request.data.get('iban_id')
        amount = request.data.get('amount')
        transaction_type = request.data.get('transaction_type')

        try:
            iban = IBANAccount.objects.get(id=iban_id, user=user)

            # Create the transaction
            transaction = Transaction.objects.create(
                iban_account=iban,
                amount=amount,
                transaction_type=transaction_type
            )

            # Log the action
            AuditLog.objects.create(user=user, action=f"{transaction_type} of {amount} on {iban.iban_number}")
            # Send notification
            Notification.objects.create(user=user, message=f"{transaction_type} of {amount} was successful.")
            return Response(TransactionSerializer(transaction).data, status=status.HTTP_201_CREATED)

        except IBANAccount.DoesNotExist:
            return Response({'error': 'IBAN account not found.'}, status=status.HTTP_404_NOT_FOUND)


class NotificationViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated]

    @staticmethod
    def list(request):
        notifications = Notification.objects.filter(user=request.user).order_by('-created_at')
        serializer = NotificationSerializer(notifications, many=True)
        return Response(serializer.data)

    @staticmethod
    def update(request, pk=None):
        try:
            notification = Notification.objects.get(id=pk, user=request.user)
            notification.is_read = True
            notification.save()
            return Response({'status': 'Notification marked as read'}, status=status.HTTP_200_OK)
        except Notification.DoesNotExist:
            return Response({'error': 'Notification not found.'}, status=status.HTTP_404_NOT_FOUND)
