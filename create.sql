CREATE DATABASE vkinder_db
    WITH
    OWNER = postgres
    ENCODING = 'UTF8'
    LC_COLLATE = 'Russian_Russia.1251'
    LC_CTYPE = 'Russian_Russia.1251'
    TABLESPACE = pg_default
    CONNECTION LIMIT = -1;


CREATE TABLE public."findVkinder"
(
    "user" integer NOT NULL,
    find_user integer NOT NULL,
    CONSTRAINT id PRIMARY KEY ("user", find_user)
)

TABLESPACE pg_default;

ALTER TABLE public."findVkinder"
    OWNER to postgres;