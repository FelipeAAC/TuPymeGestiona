-- TuPymeGestiona - RESET DE BASE LOCAL
--
-- ATENCION: este archivo elimina toda la base `tupymegestiona`.
-- Usalo solamente para reiniciar una instalación académica/local.
-- Ejecución desde PowerShell:
--   Get-Content .\database\00_reset_database.sql | mysql -u root -p

DROP DATABASE IF EXISTS `tupymegestiona`;

CREATE DATABASE `tupymegestiona`
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;
