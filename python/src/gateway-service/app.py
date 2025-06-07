from flask import Flask,request,send_file
from dotenv import load_dotenv
from pymongo import MongoClient
from jwt import decode
from bson import ObjectId

import os
import time
import gridfs
import pika
import json

load_dotenv()

MONGODB_VIDEOS_COLLECTION = os.getenv("MONGODB_VIDEOS_COLLECTION")
MONGODB_AUDIOS_COLLECTION = os.getenv("MONGODB_AUDIOS_COLLECTION")
JWT_SECRET = os.getenv("JWT_SECRET_KEY")
MONGODB_HOST = os.getenv("MONGODB_HOST")
MONGODB_PORT = int(os.getenv("MONGODB_PORT"))
RABBITMQ_HOST = os.getenv("RABBITMQ_HOST")
RABBITMQ_VIDEO_QUEUE = os.getenv("RABBITMQ_VIDEO_HOST")

print(MONGODB_VIDEOS_COLLECTION, MONGODB_AUDIOS_COLLECTION, JWT_SECRET, MONGODB_HOST, MONGODB_PORT, RABBITMQ_HOST, RABBITMQ_VIDEO_QUEUE)

app = Flask(__name__)
client = MongoClient(f"mongodb://{MONGODB_HOST}:{MONGODB_PORT}/")
gridfs_video = gridfs.GridFS(client[MONGODB_VIDEOS_COLLECTION])
gridfs_audio = gridfs.GridFS(client[MONGODB_AUDIOS_COLLECTION])
connection = pika.BlockingConnection(pika.ConnectionParameters(RABBITMQ_HOST))
channel = connection.channel()
channel.queue_declare(queue=RABBITMQ_VIDEO_QUEUE, durable=True)

@app.before_request
def auth_middleware():
        token = request.headers.get('Authorization')
        if token:
                try:
                    decoded_token = decode(token,JWT_SECRET,algorithms=["HS256"])
                    if decoded_token.get("exp") < int(round(time.time())):
                        return "Token expired", 401
                    request.user_data  = {
                        "email" : decoded_token.get("email"),
                        "user_id" : decoded_token.get("user_id")
                    }
                except Exception as _:
                    return "JWT ERROR", 401
        else:
                return "Unauthorized", 401

@app.route('/api/v1/media/upload',methods=['POST'])
def upload_video():
        video = request.files.get('video')
        if len(request.files) != 1:
            return "Invalid number of video files is there", 400
        if not video:
                return "No video file provided", 400
        try:
            video_id = gridfs_video.put(video, filename=video.filename, content_type=video.content_type,user_id=request.user_data.get("user_id"))
            try:
                channel.basic_publish(exchange='',
                                      routing_key=RABBITMQ_VIDEO_QUEUE,
                                      body=json.dumps({
                                            'video_id': str(video_id),
                                            'user_id': request.user_data.get("user_id"),
                                            'email': request.user_data.get("email"),
                                      }),
                                      properties=pika.BasicProperties(
                                          delivery_mode=2
                                      ))
            except Exception as e:
                  gridfs_video.delete(video_id) 
                  return f"Error publishing to RabbitMQ: {e}", 500
        except Exception as _:
            return "Error uploading video", 500
        return "Video uploaded successfully", 200

@app.route('/api/v1/media/download/<mp3_id>', methods=['GET'])
def download_video(mp3_id):
    try:
        mp3_id = mp3_id.strip()
        file = gridfs_audio.find_one({"_id": ObjectId(mp3_id)})
        return send_file(file, download_name=file.filename)
    except Exception as _:
        return "Video not found", 404
    


if __name__ == "__main__":
        app.run(host='0.0.0.0', port=5001, debug=True)