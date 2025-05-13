CREATE DATABASE  IF NOT EXISTS `esp32_data` /*!40100 DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci */ /*!80016 DEFAULT ENCRYPTION='N' */;
USE `esp32_data`;
-- MySQL dump 10.13  Distrib 8.0.33, for Win64 (x86_64)
--
-- Host: 10.110.3.102    Database: esp32_data
-- ------------------------------------------------------
-- Server version	8.0.39

/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!50503 SET NAMES utf8 */;
/*!40103 SET @OLD_TIME_ZONE=@@TIME_ZONE */;
/*!40103 SET TIME_ZONE='+00:00' */;
/*!40014 SET @OLD_UNIQUE_CHECKS=@@UNIQUE_CHECKS, UNIQUE_CHECKS=0 */;
/*!40014 SET @OLD_FOREIGN_KEY_CHECKS=@@FOREIGN_KEY_CHECKS, FOREIGN_KEY_CHECKS=0 */;
/*!40101 SET @OLD_SQL_MODE=@@SQL_MODE, SQL_MODE='NO_AUTO_VALUE_ON_ZERO' */;
/*!40111 SET @OLD_SQL_NOTES=@@SQL_NOTES, SQL_NOTES=0 */;

--
-- Table structure for table `event_logs`
--

DROP TABLE IF EXISTS `event_logs`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `event_logs` (
  `id` int NOT NULL AUTO_INCREMENT,
  `event_type` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `timestamp` datetime DEFAULT CURRENT_TIMESTAMP,
  `duration` float DEFAULT NULL,
  `machine` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `start_user_id` varchar(45) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `end_user_id` varchar(45) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `start_comment` varchar(500) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `end_comment` varchar(500) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `cancel_reason` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `status` enum('active','canceled','finished') COLLATE utf8mb4_unicode_ci DEFAULT 'finished',
  `reaction_time` float DEFAULT NULL,
  `maintenance_arrival_user_id` varchar(50) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `breakdown` varchar(45) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `user_id` varchar(45) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `reason` varchar(45) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=237 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `event_logs`
--

LOCK TABLES `event_logs` WRITE;
/*!40000 ALTER TABLE `event_logs` DISABLE KEYS */;
INSERT INTO `event_logs` VALUES (223,'maintenance','2025-05-09 15:00:35',123.32,'Machine8','[F[B[F[B[F[F[B1',NULL,'Maintenance',NULL,NULL,'finished',NULL,NULL,'preventive',NULL,NULL),(224,'maintenance','2025-05-09 15:05:53',80.446,'Machine8','[F4548',NULL,'Maintenance',NULL,NULL,'finished',14.3419,'123','preventive',NULL,NULL),(225,'maintenance','2025-05-09 15:06:52',40.3,'Machine8','11111',NULL,'Maintenance',NULL,NULL,'finished',9.5573,'22222','preventive',NULL,NULL),(226,'downtime','2025-05-10 15:08:30',20.4919,'Machine8','123','5454','11','11',NULL,'finished',NULL,NULL,'preventive',NULL,NULL),(227,'downtime','2025-05-09 15:09:36',10.856,'Machine8','1214','45','11','11',NULL,'finished',NULL,NULL,'preventive',NULL,NULL),(228,'downtime','2025-05-09 15:15:56',29.5294,'Machine1','[1245','123','','',NULL,'finished',NULL,NULL,'preventive',NULL,NULL),(229,'break','2025-05-10 15:16:19',10.679,'Machine1','1234','111','111','',NULL,'canceled',NULL,NULL,'corrective',NULL,'False Alarm'),(230,'maintenance','2025-05-09 15:27:21',5.31,'Machine1','1223',NULL,'Maintenance',NULL,NULL,'finished',20.9659,'1234','preventive',NULL,NULL),(231,'maintenance','2025-05-09 15:29:41',123,'Machine1','123',NULL,'Maintenance',NULL,NULL,'finished',21.9999,'1234','corrective',NULL,NULL),(232,'downtime','2025-05-13 15:30:48',43.2706,'Machine1','1212','121','','',NULL,'finished',NULL,NULL,'corrective',NULL,NULL),(233,'downtime','2025-05-09 15:32:13',27.7754,'Machine1','123','123','','',NULL,'finished',NULL,NULL,'corrective',NULL,NULL),(234,'downtime','2025-05-13 15:36:49',29.1992,'Machine1','123','123','456','454',NULL,'finished',NULL,NULL,'corrective',NULL,NULL),(235,'break','2025-05-09 15:37:48',100.2,'Machine1','45687',NULL,'',NULL,NULL,'finished',NULL,NULL,'preventive',NULL,NULL),(236,NULL,'2025-05-13 13:34:07',NULL,NULL,NULL,NULL,NULL,NULL,NULL,'finished',NULL,NULL,'',NULL,NULL);
/*!40000 ALTER TABLE `event_logs` ENABLE KEYS */;
UNLOCK TABLES;
/*!40103 SET TIME_ZONE=@OLD_TIME_ZONE */;

/*!40101 SET SQL_MODE=@OLD_SQL_MODE */;
/*!40014 SET FOREIGN_KEY_CHECKS=@OLD_FOREIGN_KEY_CHECKS */;
/*!40014 SET UNIQUE_CHECKS=@OLD_UNIQUE_CHECKS */;
/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
/*!40111 SET SQL_NOTES=@OLD_SQL_NOTES */;

-- Dump completed on 2025-05-13 16:15:58
