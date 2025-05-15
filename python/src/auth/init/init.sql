use microservices;

CREATE TABLE IF NOT EXISTS USERS(
	id VARCHAR(500) PRIMARY KEY,
    email VARCHAR(400),
    password VARCHAR(500)
);