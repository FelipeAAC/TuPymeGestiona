-- TuPymeGestiona - creación de una base MySQL vacía
--
-- Ejecución desde PowerShell:
--   Get-Content .\database\01_create_database.sql | mysql -u root -p
--
-- Si se necesita otro nombre, cambiar DB_NAME en backend/.env y editar el
-- identificador de abajo antes de ejecutar este archivo.

CREATE DATABASE IF NOT EXISTS `tupymegestiona`
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;
