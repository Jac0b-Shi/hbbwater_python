-- 校园水浸监测系统数据库初始化脚本
-- MySQL 8.0+

-- 创建数据库
CREATE DATABASE IF NOT EXISTS flood_monitoring 
    CHARACTER SET utf8mb4 
    COLLATE utf8mb4_unicode_ci;

USE flood_monitoring;

-- 创建数据库用户（本地访问）
CREATE USER IF NOT EXISTS 'flood_user'@'localhost' IDENTIFIED BY 'flood_monitoring_2025';
GRANT ALL PRIVILEGES ON flood_monitoring.* TO 'flood_user'@'localhost';

-- 创建数据库用户（Docker 网络访问，允许任何主机）
CREATE USER IF NOT EXISTS 'flood_user'@'%' IDENTIFIED BY 'flood_monitoring_2025';
GRANT ALL PRIVILEGES ON flood_monitoring.* TO 'flood_user'@'%';

FLUSH PRIVILEGES;

-- 传感器配置表
CREATE TABLE IF NOT EXISTS sensors (
    id INT AUTO_INCREMENT PRIMARY KEY,
    sensor_id VARCHAR(50) NOT NULL UNIQUE COMMENT '传感器唯一标识',
    sensor_type ENUM('ultrasonic', 'immersion') NOT NULL COMMENT '传感器类型',
    location VARCHAR(100) NOT NULL COMMENT '安装位置',
    description TEXT COMMENT '描述信息',
    warning_level DECIMAL(10,2) DEFAULT NULL COMMENT '预警水位值(cm)',
    danger_level DECIMAL(10,2) DEFAULT NULL COMMENT '危险水位值(cm)',
    normal_interval INT DEFAULT 1800 COMMENT '正常模式上报间隔(秒),默认30分钟',
    alert_interval INT DEFAULT 300 COMMENT '预警模式上报间隔(秒),默认5分钟',
    is_active BOOLEAN DEFAULT TRUE COMMENT '是否启用',
    report_method ENUM('http_api', 'webhook', 'mqtt', 'coap', 'udp_binary') DEFAULT 'http_api' COMMENT '数据上报方式',
    webhook_token VARCHAR(64) DEFAULT NULL COMMENT 'Webhook唯一标识',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_type (sensor_type),
    INDEX idx_active (is_active),
    UNIQUE KEY uk_webhook_token (webhook_token)
) ENGINE=InnoDB COMMENT='传感器配置表';

-- 传感器原始数据表（热数据，≤14天）
-- 使用普通表+索引方案，分区表在MySQL中有较多限制（不支持外键、主键必须包含分区列等）
CREATE TABLE IF NOT EXISTS sensor_readings (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    sensor_id VARCHAR(50) NOT NULL,
    sensor_type ENUM('ultrasonic', 'immersion') NOT NULL,
    -- 超声波传感器字段
    water_level DECIMAL(10,2) DEFAULT NULL COMMENT '水位(cm)',
    -- 浸水传感器字段
    water_detected BOOLEAN DEFAULT NULL COMMENT '是否检测到水',
    duration INT DEFAULT NULL COMMENT '浸水持续时间(秒)',
    severity ENUM('low', 'medium', 'high') DEFAULT NULL COMMENT '严重程度',
    -- 通用字段
    status ENUM('normal', 'warning', 'danger', 'alarm', 'offline') NOT NULL DEFAULT 'normal',
    battery_level DECIMAL(5,2) DEFAULT NULL COMMENT '电池电量(%)',
    signal_strength INT DEFAULT NULL COMMENT '信号强度(dBm)',
    raw_data JSON COMMENT '原始JSON数据',
    recorded_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    -- 复合索引优化查询性能
    INDEX idx_sensor_time (sensor_id, recorded_at),
    INDEX idx_time (recorded_at),
    INDEX idx_status (status),
    INDEX idx_sensor_type (sensor_type),
    INDEX idx_recorded_sensor (recorded_at, sensor_id)
) ENGINE=InnoDB COMMENT='传感器原始数据表（热数据）';

-- 传感器数据归档表（>14天历史数据）
CREATE TABLE IF NOT EXISTS sensor_readings_archive (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    sensor_id VARCHAR(50) NOT NULL,
    sensor_type ENUM('ultrasonic', 'immersion') NOT NULL,
    water_level DECIMAL(10,2) DEFAULT NULL,
    water_detected BOOLEAN DEFAULT NULL,
    duration INT DEFAULT NULL,
    severity ENUM('low', 'medium', 'high') DEFAULT NULL,
    status ENUM('normal', 'warning', 'danger', 'alarm', 'offline') NOT NULL,
    battery_level DECIMAL(5,2) DEFAULT NULL,
    signal_strength INT DEFAULT NULL,
    raw_data JSON,
    recorded_at TIMESTAMP NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_sensor_time (sensor_id, recorded_at),
    INDEX idx_time (recorded_at),
    INDEX idx_sensor_type (sensor_type)
) ENGINE=InnoDB COMMENT='传感器数据归档表';

-- 小时汇总数据表
CREATE TABLE IF NOT EXISTS sensor_summary_hourly (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    sensor_id VARCHAR(50) NOT NULL,
    summary_date DATE NOT NULL,
    summary_hour TINYINT NOT NULL CHECK (summary_hour >= 0 AND summary_hour <= 23),
    -- 统计数据
    reading_count INT DEFAULT 0 COMMENT '读数次数',
    avg_water_level DECIMAL(10,2) DEFAULT NULL,
    max_water_level DECIMAL(10,2) DEFAULT NULL,
    min_water_level DECIMAL(10,2) DEFAULT NULL,
    water_detected_count INT DEFAULT 0 COMMENT '检测到水次数',
    alarm_count INT DEFAULT 0 COMMENT '告警次数',
    warning_count INT DEFAULT 0 COMMENT '预警次数',
    avg_battery_level DECIMAL(5,2) DEFAULT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uk_sensor_hour (sensor_id, summary_date, summary_hour),
    INDEX idx_date (summary_date)
    -- FOREIGN KEY (sensor_id) REFERENCES sensors(sensor_id) ON DELETE CASCADE
) ENGINE=InnoDB COMMENT='小时汇总数据表';

-- 日汇总数据表
CREATE TABLE IF NOT EXISTS sensor_summary_daily (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    sensor_id VARCHAR(50) NOT NULL,
    summary_date DATE NOT NULL,
    -- 统计数据
    reading_count INT DEFAULT 0,
    avg_water_level DECIMAL(10,2) DEFAULT NULL,
    max_water_level DECIMAL(10,2) DEFAULT NULL,
    min_water_level DECIMAL(10,2) DEFAULT NULL,
    water_detected_duration INT DEFAULT 0 COMMENT '浸水持续时间(分钟)',
    alarm_count INT DEFAULT 0,
    warning_count INT DEFAULT 0,
    avg_battery_level DECIMAL(5,2) DEFAULT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uk_sensor_date (sensor_id, summary_date),
    INDEX idx_date (summary_date)
    -- FOREIGN KEY (sensor_id) REFERENCES sensors(sensor_id) ON DELETE CASCADE
) ENGINE=InnoDB COMMENT='日汇总数据表';

-- 告警记录表
CREATE TABLE IF NOT EXISTS alerts (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    sensor_id VARCHAR(50) NOT NULL,
    alert_type ENUM('high_water', 'water_detected', 'sensor_offline', 'low_battery') NOT NULL,
    severity ENUM('low', 'medium', 'high', 'critical') NOT NULL DEFAULT 'medium',
    message TEXT NOT NULL,
    details JSON COMMENT '详细信息',
    is_resolved BOOLEAN DEFAULT FALSE,
    resolved_at TIMESTAMP NULL,
    resolved_by VARCHAR(50) DEFAULT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_sensor (sensor_id),
    INDEX idx_type (alert_type),
    INDEX idx_severity (severity),
    INDEX idx_created (created_at),
    INDEX idx_resolved (is_resolved)
    -- FOREIGN KEY (sensor_id) REFERENCES sensors(sensor_id) ON DELETE CASCADE
) ENGINE=InnoDB COMMENT='告警记录表';

-- 系统配置表
CREATE TABLE IF NOT EXISTS system_config (
    id INT AUTO_INCREMENT PRIMARY KEY,
    config_key VARCHAR(100) NOT NULL UNIQUE,
    config_value TEXT,
    description VARCHAR(255),
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB COMMENT='系统配置表';

-- 插入默认配置
INSERT INTO system_config (config_key, config_value, description) VALUES
('data_retention_days', '14', '热数据保留天数'),
('archive_enabled', '1', '是否启用自动归档'),
('summary_enabled', '1', '是否启用数据统计'),
('alert_cooldown_minutes', '30', '相同告警冷却时间(分钟)'),
('offline_timeout_minutes', '60', '传感器离线判定时间(分钟)');

-- 传感器数据由用户通过前端界面添加，不再预置示例数据
