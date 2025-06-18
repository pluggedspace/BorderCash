import json
import openai
from channels.generic.websocket import AsyncWebsocketConsumer
from django.conf import settings
from app.views import balance_view, transaction_view

from channels.db import database_sync_to_async
from django.contrib.auth.models import AnonymousUser
from rest_framework_simplejwt.authentication import JWTAuthentication
from urllib.parse import parse_qs
from channels.middleware.base import BaseMiddleware
from channels.auth import AuthMiddlewareStack

class JWTAuthMiddleware(BaseMiddleware):
    async def __call__(self, scope, receive, send):
        query_string = parse_qs(scope["query_string"].decode())
        token = query_string.get("token", [None])[0]

        if token:
            user = await self.get_user(token)
            scope["user"] = user
        return await super().__call__(scope, receive, send)

    @database_sync_to_async
    def get_user(self, token):
        try:
            validated_token = JWTAuthentication().get_validated_token(token)
            return JWTAuthentication().get_user(validated_token)
        except:
            return AnonymousUser()

def JWTAuthMiddlewareStack(inner):
    return JWTAuthMiddleware(AuthMiddlewareStack(inner))



class MonicaConsumer(AsyncWebsocketConsumer):
    async def receive(self, text_data):
        cached_response = get_cached_faq_response(message)
        if cached_response:
            return cached_response
        return await self.query_mixtral(message)

        data = json.loads(text_data)
        command = data.get("command")
        
        if command == "balance":
            response = await self.get_balance()
        elif command == "transactions":
            response = await self.get_transactions()
        else:
            response = await self.process_message(data.get("message", ""))

        await self.send(json.dumps({"response": response}))

    async def get_balance(self):
        # Call the imported function from `app.views`
        request = None  # Placeholder, adjust based on authentication
        return balance_view(request).content.decode()

    async def get_transactions(self):
        request = None  # Placeholder
        return transaction_view(request).content.decode()