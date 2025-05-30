from flask import Flask,request,Response
from dotenv import load_dotenv
from pymongo import MongoClient
from jwt import decode
from bson import ObjectId

import os
import time
import gridfs
import pika

load_dotenv()

MONGODB_COLLECTION = os.getenv("MONGODB_COLLECTION")
JWT_SECRET = os.getenv("JWT_SECRET_KEY")
MONGODB_HOST = os.getenv("MONGODB_HOST")
MONGODB_PORT = int(os.getenv("MONGODB_PORT"))
RABBITMQ_HOST = os.getenv("RABBITMQ_HOST")
RABBITMQ_VIDEO_QUEUE = os.getenv("RABBITMQ_VIDEO_HOST")

app = Flask(__name__)
client = MongoClient(f"mongodb://{MONGODB_HOST}:{MONGODB_PORT}/{MONGODB_COLLECTION}")
gridfs = gridfs.GridFS(client[MONGODB_COLLECTION])
connection = pika.BlockingConnection(pika.ConnectionParameters(RABBITMQ_HOST))
channel = connection.channel()
channel.queue_declare(queue='video', durable=True)

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
            video_id = gridfs.put(video, filename=video.filename, content_type=video.content_type,user_id=request.user_data.get("user_id"))
            try:
                channel.basic_publish(exchange='',
                                      routing_key=RABBITMQ_VIDEO_QUEUE,
                                      body=str(video_id),
                                      properties=pika.BasicProperties(
                                          delivery_mode=2
                                      ))
            except Exception as e:
                  gridfs.delete(video_id) 
                  return f"Error publishing to RabbitMQ: {e}", 500
        except Exception as _:
            return "Error uploading video", 500
        return "Video uploaded successfully", 200

@app.route('/api/v1/media/download/<video_id>', methods=['GET'])
def download_video(video_id):
    try:
        video_id = video_id.strip()
        file = gridfs.find_one({"_id": ObjectId(video_id)})
        return Response(
            file.read(),
            mimetype=file._file.get("contentType"), 
            headers={
                "Content-Disposition": f"inline; id={video_id}",
                "Accept-Ranges": "bytes"
            }
        )
    except Exception as e:
        return "Video not found", 404
    


if __name__ == "__main__":
        print(MONGODB_HOST)
        print(MONGODB_PORT)
        print(MONGODB_COLLECTION)
        app.run(host='0.0.0.0', port=5001, debug=True)