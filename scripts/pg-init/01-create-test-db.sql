-- Runs once on first postgres volume creation. The application database
-- (lenny) is created by POSTGRES_DB; this adds the isolated test database.
CREATE DATABASE lenny_test OWNER lenny;
