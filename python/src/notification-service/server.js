const express = require("express");
const jwt = require("jsonwebtoken");
const amqp = require("amqplib");

const { createServer } = require("http");
const { Server } = require("socket.io");
const { createClient } = require("redis");
const { createAdapter } = require("@socket.io/redis-adapter");


const app = express();
const httpServer = createServer(app);
const io = new Server(httpServer);


const JWT_SECRET = process.env.JWT_SECRET_KEY
const RABBITMQ_URL = `amqp://${process.env.RABBITMQ_HOST}`; 
const QUEUE_NAME = process.env.MP3_QUEUE_NAME
const REDIS_URL = `redis://${REDIS_HOST}:${process.env.REDIS_PORT}`;


io.use((socket, next) => {
  const token = socket.handshake.auth.token;
    console.log(token)
  if (!token) {
    return next(new Error("Authentication error: token missing"));
  }

  try {
    const payload = jwt.verify(token, JWT_SECRET);
    socket.user = payload;
    next();
  } catch (err) {
    return next(new Error("Authentication error: invalid token"));
  }
});

async function startRabbitMQ() {
  try {
    const connection = await amqp.connect(RABBITMQ_URL);
    const channel = await connection.createChannel();

    await channel.assertQueue(QUEUE_NAME, { durable: true });

    console.log("Waiting for messages in RabbitMQ...");

    channel.consume(
      QUEUE_NAME,
      (msg) => {
        if (msg !== null) {
          const messageStr = msg.content.toString();
          let message;

          try {
            message = JSON.parse(messageStr);
            console.log(message)
          } catch (err) {
            console.error("Invalid message format:", messageStr);
            channel.ack(msg);
            return;
          }

          const userId = message.user_id;
          if (userId) {
            io.to(`user:${userId}`).emit("message", message);
            console.log(`Sent message to user ${userId}`);
          } else {
            console.log(`User ${userId} not connected`);
          }

          channel.ack(msg); 
        }
      },
      { noAck: false }
    );
  } catch (err) {
    console.error("RabbitMQ connection error:", err);
  }
}


io.on("connection", (socket) => {
    const userId = socket.user.user_id;
  console.log(`User ${userId} connected`);

    socket.join(`user:${userId}`);

    socket.on("disconnect", () => {
    console.log(`User ${userId} disconnected`);
  });
});


async function startServer() {

    const pubClient = createClient({ url: REDIS_URL });
const subClient = pubClient.duplicate();

await pubClient.connect();
await subClient.connect();

io.adapter(createAdapter(pubClient, subClient));
  httpServer.listen(3000, async () => {
    console.log("Socket.IO server listening on port 3000");
    try {
      await startRabbitMQ();
    } catch (err) {
      console.error("Failed to start RabbitMQ:", err);
    }
  });
}

startServer();