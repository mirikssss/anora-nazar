-- Базы сервисов в одном экземпляре PostgreSQL: у каждого сервиса своя, в чужую никто не ходит.
-- Только на пустом томе; базу, добавленную позже, сервис создаёт сам при migrate (shared.migrations.ensure_database).
CREATE DATABASE node;
CREATE DATABASE bank_sim;
CREATE DATABASE anchor;
CREATE DATABASE network_operator;
