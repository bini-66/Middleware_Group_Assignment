import json


def create_message(
    message_id,
    sender_id,
    message_text
):
    message = {
        "message_id": message_id,
        "sender_id": sender_id,
        "message_text": message_text
    }

    return json.dumps(message)


def decode_message(data):
    return json.loads(data)