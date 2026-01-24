import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.utils import timezone
from .models import ChatThread, Message, TypingIndicator
from users.models import User

class CommunicationConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.user = self.scope["user"]
        
        if not self.user.is_authenticated:
            await self.close()
            return
        
        self.user_id = str(self.user.id)
        self.user_group = f"user_{self.user_id}"
        
        await self.channel_layer.group_add(self.user_group, self.channel_name)
        await self.accept()
        await self.update_user_status(True)
    
    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.user_group, self.channel_name)
        await self.update_user_status(False)
    
    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
            message_type = data.get('type')
            
            if message_type == 'chat_message':
                await self.handle_chat_message(data)
            elif message_type == 'typing':
                await self.handle_typing(data)
            elif message_type == 'read_receipt':
                await self.handle_read_receipt(data)
            elif message_type == 'call_signal':
                await self.handle_call_signal(data)
            
        except Exception as e:
            await self.send_error(str(e))
    
    async def handle_chat_message(self, data):
        thread_id = data.get('thread_id')
        content = data.get('content')
        
        message = await self.save_message(thread_id, content)
        
        if message:
            thread = await self.get_thread(thread_id)
            other_user = await self.get_other_user(thread)
            
            # Send to sender
            await self.channel_layer.group_send(
                self.user_group,
                {'type': 'chat_message', 'message': await self.message_to_dict(message)}
            )
            
            # Send to receiver
            receiver_group = f"user_{other_user.id}"
            await self.channel_layer.group_send(
                receiver_group,
                {'type': 'chat_message', 'message': await self.message_to_dict(message)}
            )
    
    async def handle_typing(self, data):
        thread_id = data.get('thread_id')
        is_typing = data.get('is_typing', False)
        
        await self.update_typing_indicator(thread_id, is_typing)
        
        thread = await self.get_thread(thread_id)
        other_user = await self.get_other_user(thread)
        
        receiver_group = f"user_{other_user.id}"
        await self.channel_layer.group_send(
            receiver_group,
            {
                'type': 'typing_indicator',
                'thread_id': thread_id,
                'user_id': self.user_id,
                'is_typing': is_typing
            }
        )
    
    async def handle_read_receipt(self, data):
        message_ids = data.get('message_ids', [])
        thread_id = data.get('thread_id')
        
        await self.mark_messages_as_read(message_ids)
        
        thread = await self.get_thread(thread_id)
        other_user = await self.get_other_user(thread)
        
        receiver_group = f"user_{other_user.id}"
        await self.channel_layer.group_send(
            receiver_group,
            {
                'type': 'read_receipt',
                'thread_id': thread_id,
                'message_ids': message_ids,
                'reader_id': self.user_id
            }
        )
    
    async def handle_call_signal(self, data):
        target_user_id = data.get('target_user_id')
        signal_type = data.get('signal_type')
        signal_data = data.get('signal_data')
        
        target_group = f"user_{target_user_id}"
        await self.channel_layer.group_send(
            target_group,
            {
                'type': 'call_signal',
                'from_user_id': self.user_id,
                'signal_type': signal_type,
                'signal_data': signal_data
            }
        )
    
    async def chat_message(self, event):
        await self.send(text_data=json.dumps({
            'type': 'message',
            'data': event['message']
        }))
    
    async def typing_indicator(self, event):
        await self.send(text_data=json.dumps({
            'type': 'typing',
            'thread_id': event['thread_id'],
            'user_id': event['user_id'],
            'is_typing': event['is_typing']
        }))
    
    async def read_receipt(self, event):
        await self.send(text_data=json.dumps({
            'type': 'read_receipt',
            'thread_id': event['thread_id'],
            'message_ids': event['message_ids'],
            'reader_id': event['reader_id']
        }))
    
    async def call_signal(self, event):
        await self.send(text_data=json.dumps({
            'type': 'call_signal',
            'from_user_id': event['from_user_id'],
            'signal_type': event['signal_type'],
            'signal_data': event['signal_data']
        }))
    
    async def send_error(self, error_message):
        await self.send(text_data=json.dumps({
            'type': 'error',
            'error': error_message
        }))
    
    # Database operations
    @database_sync_to_async
    def save_message(self, thread_id, content):
        try:
            thread = ChatThread.objects.get(id=thread_id)
            message = Message.objects.create(
                thread=thread,
                sender=self.user,
                content=content
            )
            return message
        except:
            return None
    
    @database_sync_to_async
    def get_thread(self, thread_id):
        try:
            return ChatThread.objects.get(id=thread_id)
        except:
            return None
    
    @database_sync_to_async
    def get_other_user(self, thread):
        if thread.user1 == self.user:
            return thread.user2
        return thread.user1
    
    @database_sync_to_async
    def update_typing_indicator(self, thread_id, is_typing):
        thread = ChatThread.objects.get(id=thread_id)
        TypingIndicator.objects.update_or_create(
            thread=thread,
            user=self.user,
            defaults={'is_typing': is_typing}
        )
    
    @database_sync_to_async
    def mark_messages_as_read(self, message_ids):
        messages = Message.objects.filter(id__in=message_ids)
        for message in messages:
            if message.sender != self.user:
                message.mark_as_read()
    
    @database_sync_to_async
    def update_user_status(self, is_online):
        User.objects.filter(id=self.user.id).update(
            is_online=is_online,
            last_seen=timezone.now()
        )
    
    @database_sync_to_async
    def message_to_dict(self, message):
        from .serializers import MessageSerializer
        serializer = MessageSerializer(message)
        return serializer.data
