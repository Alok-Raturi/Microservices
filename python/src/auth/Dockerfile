FROM python

WORKDIR /app

RUN apt-get update && apt-get install -y build-essential curl

COPY ./requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

WORKDIR /app
EXPOSE 5000
COPY . .
CMD [ "python", "app.py" ]
