
import pika
import gridfs
from pymongo import MongoClient
from moviepy import VideoFileClip
from bson import ObjectId

import tempfile
import os
import json
from dotenv import load_dotenv

load_dotenv()

def process_video(video_id,email,user_id):
    try:
        video_id = ObjectId(video_id)
        grid_out = video_gridfs.get(video_id)

        original_filename = grid_out.filename
        _, ext = os.path.splitext(original_filename)

        with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as temp_video:
            temp_video.write(grid_out.read())
            temp_video.flush()
            temp_path = temp_video.name

        try:
            mp3_media = VideoFileClip(temp_path)
            mp3_media.audio.write_audiofile(f"{video_id}.mp3")

            with open(f"{video_id}.mp3", "rb") as audio_file:
                file_id = mp3_gridfs.put(audio_file, filename=f"{video_id}.mp3",email=email,user_id=user_id)
                channel.basic_publish(
                    exchange='',
                    routing_key=RABBITMQ_MP3_QUEUE_NAME,
                    body=json.dumps({'video_id': str(video_id),
                                        'file_id': str(file_id),
                                        'filename': f"{video_id}.mp3",
                                        'success':True,
                                        'message': 'Audio extracted successfully',
                                        'email': email,
                                        'user_id': user_id
                                     }),
                    properties=pika.BasicProperties(
                        delivery_mode=2, 
                    )
                )
        finally:
            absolute_path_mp3 = os.path.abspath(f"{video_id}.mp3")
            if os.path.exists(absolute_path_mp3):
                os.remove(absolute_path_mp3)
    except Exception as e:
        channel.basic_publish(
                    exchange='',
                    routing_key=RABBITMQ_MP3_QUEUE_NAME,
                    body=json.dumps({'video_id': str(video_id),
                                        'success': False,
                                        'message': 'Failed to process video',
                                        'email': email,
                                        'user_id': user_id
                                     }),
                    properties=pika.BasicProperties(
                        delivery_mode=2, 
                    )
                )

def callback(ch, method, properties, data):
    try:
        print("Received data from RabbitMQ:")
        data  = json.loads(data)
        video_id = data.get('video_id')
        email = data.get('email')
        user_id = data.get('user_id')
        print(f"Processing video_id: {video_id}, email: {email}, user_id: {user_id}")
        process_video(video_id,email,user_id)
        print(f"Processed video_id: {video_id}, email: {email}, user_id: {user_id}")
        ch.basic_ack(delivery_tag=method.delivery_tag)

    except Exception as e:
        print(f"Error processing message: {e}")
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)


if __name__ == "__main__":
    RABBITMQ_HOST = os.getenv('RABBITMQ_HOST')
    MONGO_HOST = os.getenv('MONGO_HOST')
    MONGO_PORT = int(os.getenv('MONGO_PORT'))
    MONGO_VIDEO_COLLECTION_NAME = os.getenv('MONGO_VIDEO_COLLECTION_NAME')
    MONGO_MP3_COLLECTION_NAME = os.getenv('MONGO_MP3_COLLECTION_NAME')
    RABBITMQ_VIDEO_QUEUE_NAME = os.getenv('RABBITMQ_VIDEO_QUEUE_NAME')
    RABBITMQ_MP3_QUEUE_NAME = os.getenv('RABBITMQ_MP3_QUEUE_NAME')

    print(MONGO_HOST, MONGO_PORT, MONGO_VIDEO_COLLECTION_NAME, MONGO_MP3_COLLECTION_NAME, RABBITMQ_HOST, RABBITMQ_VIDEO_QUEUE_NAME, RABBITMQ_MP3_QUEUE_NAME)
    client = MongoClient(f"mongodb://{MONGO_HOST}:{MONGO_PORT}/")
    video_db = client[MONGO_VIDEO_COLLECTION_NAME]
    video_gridfs = gridfs.GridFS(video_db)

    mp3_db = client[MONGO_MP3_COLLECTION_NAME]
    mp3_gridfs = gridfs.GridFS(mp3_db)

    connection = pika.BlockingConnection(pika.ConnectionParameters(host=RABBITMQ_HOST))
    channel = connection.channel()

    channel.queue_declare(queue=RABBITMQ_MP3_QUEUE_NAME, durable=True)  

    channel.basic_qos(prefetch_count=1)
    channel.basic_consume(queue=RABBITMQ_VIDEO_QUEUE_NAME, on_message_callback=callback)
    print("Started Consuming from RabbitMQ...")
    channel.start_consuming()