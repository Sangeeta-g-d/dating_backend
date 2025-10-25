import json
from channels.generic.websocket import AsyncWebsocketConsumer

class AskMeConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.question_id = self.scope['url_route']['kwargs']['question_id']
        self.room_group_name = f"askme_{self.question_id}"

        # Join question group
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
        await self.accept()

    async def disconnect(self, close_code):
        # Leave question group
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )

    # Receive broadcast from backend
    async def send_new_answer(self, event):
        await self.send(text_data=json.dumps(event["data"]))


class QuestionConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        # All users join one common group
        await self.channel_layer.group_add("questions_group", self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard("questions_group", self.channel_name)

    async def receive(self, text_data):
        # Not needed if only server pushes data
        pass

    async def send_new_question(self, event):
        question_data = event["question"]
        await self.send(text_data=json.dumps({
            "type": "new_question",
            "data": question_data
        }))