-- 清理所有假传感器数据（保留空表结构）
-- 警告：这会删除所有传感器及其读数数据！

USE flood_monitoring;

-- 先删除读数数据（外键依赖）
DELETE FROM sensor_readings;
DELETE FROM sensor_readings_archive;
DELETE FROM sensor_summary_hourly;
DELETE FROM sensor_summary_daily;
DELETE FROM alerts;

-- 删除所有传感器
DELETE FROM sensors;

-- 重置自增ID（可选）
ALTER TABLE sensors AUTO_INCREMENT = 1;
ALTER TABLE sensor_readings AUTO_INCREMENT = 1;
ALTER TABLE alerts AUTO_INCREMENT = 1;

SELECT '所有传感器数据已清理' AS message;
