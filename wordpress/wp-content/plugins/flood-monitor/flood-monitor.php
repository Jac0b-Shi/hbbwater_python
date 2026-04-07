<?php
/**
 * Plugin Name: Flood Monitor Mail API
 * Description: 为水浸监测系统提供邮件发送 API，支持从后端获取 SMTP 配置
 * Version: 1.1.0
 * Author: System
 */

// 防止直接访问
if (!defined('ABSPATH')) {
    exit;
}

// 后端 API 地址（可通过环境变量或 wp-config.php 定义）
define('FLOOD_MONITOR_BACKEND_URL', getenv('FLOOD_MONITOR_BACKEND_URL') ?: 'http://backend:8000');
define('FLOOD_MONITOR_SHARED_TOKEN', getenv('FLOOD_MONITOR_SHARED_TOKEN') ?: '');

function flood_monitor_validate_internal_token(WP_REST_Request $request) {
    if (empty(FLOOD_MONITOR_SHARED_TOKEN)) {
        return new WP_Error('flood_monitor_missing_token', '内部通信令牌未配置', ['status' => 503]);
    }

    $provided = trim((string) $request->get_header('X-Internal-Token'));
    if (empty($provided) || !hash_equals(FLOOD_MONITOR_SHARED_TOKEN, $provided)) {
        return new WP_Error('flood_monitor_invalid_token', '无效的内部通信令牌', ['status' => 403]);
    }

    return true;
}

/**
 * 注册 REST API 路由
 */
add_action('rest_api_init', function () {
    register_rest_route('flood-monitor/v1', '/send-mail', [
        'methods' => 'POST',
        'callback' => 'flood_monitor_send_mail',
        'permission_callback' => 'flood_monitor_validate_internal_token',
    ]);
    
    register_rest_route('flood-monitor/v1', '/test-mail', [
        'methods' => 'POST',
        'callback' => 'flood_monitor_test_mail',
        'permission_callback' => 'flood_monitor_validate_internal_token',
    ]);
});

/**
 * 从后端获取邮件配置
 */
function flood_monitor_get_mail_config() {
    $cache_key = 'flood_monitor_mail_config';
    $cached = get_transient($cache_key);
    
    // 缓存 5 分钟
    if ($cached !== false) {
        return $cached;
    }
    
    $api_url = FLOOD_MONITOR_BACKEND_URL . '/api/config/notification/mail-config';
    
    $response = wp_remote_get($api_url, [
        'timeout' => 10,
        'sslverify' => false,
        'headers' => [
            'X-Internal-Token' => FLOOD_MONITOR_SHARED_TOKEN,
        ],
    ]);
    
    if (is_wp_error($response)) {
        error_log('Flood Monitor: Failed to get mail config: ' . $response->get_error_message());
        return null;
    }
    
    $body = wp_remote_retrieve_body($response);
    $config = json_decode($body, true);
    
    if (json_last_error() !== JSON_ERROR_NONE) {
        error_log('Flood Monitor: Invalid JSON response from backend');
        return null;
    }
    
    // 缓存配置
    set_transient($cache_key, $config, 300);
    
    return $config;
}

/**
 * 清除邮件配置缓存
 */
function flood_monitor_clear_mail_config_cache() {
    delete_transient('flood_monitor_mail_config');
}

/**
 * 配置 PHPMailer 使用后端提供的 SMTP 设置
 */
add_action('phpmailer_init', function ($phpmailer) {
    $config = flood_monitor_get_mail_config();
    
    // 如果后端未启用邮件或未配置 SMTP，使用默认设置
    if (!$config || !$config['enabled']) {
        return;
    }
    
    // 检查是否有 SMTP 配置
    if (empty($config['smtp_host']) || empty($config['smtp_user'])) {
        return; // 使用 WordPress 默认邮件配置
    }
    
    // 配置 SMTP
    $phpmailer->isSMTP();
    $phpmailer->Host = $config['smtp_host'];
    $phpmailer->Port = intval($config['smtp_port']);
    $phpmailer->SMTPAuth = true;
    $phpmailer->Username = $config['smtp_user'];
    $phpmailer->Password = $config['smtp_pass'];
    
    // SSL/TLS 设置
    if ($config['smtp_ssl']) {
        $phpmailer->SMTPSecure = 'ssl';
    } else {
        $phpmailer->SMTPSecure = 'tls';
    }
    
    // 设置发件人
    if (!empty($config['from_email'])) {
        $phpmailer->From = $config['from_email'];
        $phpmailer->FromName = get_bloginfo('name');
    }
    
    // 启用调试（仅在开发环境）
    // $phpmailer->SMTPDebug = 2;
});

/**
 * 发送邮件 API
 */
function flood_monitor_send_mail(WP_REST_Request $request) {
    $params = $request->get_json_params();
    
    // 验证必填参数
    if (empty($params['to']) || empty($params['subject']) || empty($params['message'])) {
        return new WP_REST_Response([
            'success' => false,
            'message' => '缺少必填参数: to, subject, message'
        ], 400);
    }
    
    $to = sanitize_email($params['to']);
    $subject = sanitize_text_field($params['subject']);
    $message = sanitize_textarea_field($params['message']);
    $headers = isset($params['headers']) ? $params['headers'] : [];
    $attachments = isset($params['attachments']) ? $params['attachments'] : [];
    
    // 验证邮箱格式
    if (!is_email($to)) {
        return new WP_REST_Response([
            'success' => false,
            'message' => '无效的收件人邮箱地址'
        ], 400);
    }
    
    // 清除缓存以获取最新配置
    flood_monitor_clear_mail_config_cache();
    
    // 发送邮件
    $sent = wp_mail($to, $subject, $message, $headers, $attachments);
    
    if ($sent) {
        return new WP_REST_Response([
            'success' => true,
            'message' => '邮件发送成功'
        ], 200);
    } else {
        global $phpmailer;
        $error_msg = '邮件发送失败';
        if (isset($phpmailer) && $phpmailer->ErrorInfo) {
            $error_msg .= ': ' . $phpmailer->ErrorInfo;
        }
        return new WP_REST_Response([
            'success' => false,
            'message' => $error_msg
        ], 500);
    }
}

/**
 * 测试邮件配置 API
 */
function flood_monitor_test_mail(WP_REST_Request $request) {
    $params = $request->get_json_params();
    $to = isset($params['to']) ? sanitize_email($params['to']) : '';
    
    if (empty($to)) {
        $to = get_option('admin_email');
    }
    
    // 获取后端配置
    $config = flood_monitor_get_mail_config();
    $config_info = '';
    
    if ($config && $config['enabled']) {
        if (!empty($config['smtp_host'])) {
            $config_info = "\n\nSMTP 配置:\n";
            $config_info .= "服务器: " . $config['smtp_host'] . "\n";
            $config_info .= "端口: " . $config['smtp_port'] . "\n";
            $config_info .= "用户: " . $config['smtp_user'] . "\n";
            $config_info .= "SSL: " . ($config['smtp_ssl'] ? '是' : '否') . "\n";
        } else {
            $config_info = "\n\n使用 WordPress 默认邮件配置\n";
        }
    } else {
        $config_info = "\n\n邮件通知未在后端启用\n";
    }
    
    $subject = '[水浸监测系统] 邮件测试';
    $message = "这是一封测试邮件。\n\n";
    $message .= "发送时间: " . current_time('mysql') . "\n";
    $message .= "站点: " . get_bloginfo('name') . "\n";
    $message .= "收件人: " . $to . "\n";
    $message .= $config_info;
    $message .= "\n如果收到此邮件，说明邮件配置正常。";
    
    $headers = ['Content-Type: text/plain; charset=UTF-8'];
    
    // 清除缓存以获取最新配置
    flood_monitor_clear_mail_config_cache();
    
    $sent = wp_mail($to, $subject, $message, $headers);
    
    if ($sent) {
        return new WP_REST_Response([
            'success' => true,
            'message' => '测试邮件已发送到: ' . $to
        ], 200);
    } else {
        global $phpmailer;
        $error_msg = '测试邮件发送失败';
        if (isset($phpmailer) && $phpmailer->ErrorInfo) {
            $error_msg .= ': ' . $phpmailer->ErrorInfo;
        }
        return new WP_REST_Response([
            'success' => false,
            'message' => $error_msg
        ], 500);
    }
}

/**
 * 添加 CORS 支持
 */
add_action('init', function () {
    add_filter('rest_pre_serve_request', function ($served, $result, $request, $server) {
        header('Access-Control-Allow-Origin: *');
        header('Access-Control-Allow-Methods: GET, POST, OPTIONS');
        header('Access-Control-Allow-Headers: Authorization, Content-Type');
        
        if ($_SERVER['REQUEST_METHOD'] === 'OPTIONS') {
            exit;
        }
        
        return $served;
    }, 10, 4);
});

/**
 * 添加管理页面（可选）
 */
add_action('admin_menu', function () {
    add_options_page(
        '水浸监测邮件配置',
        '水浸监测邮件',
        'manage_options',
        'flood-monitor-mail',
        'flood_monitor_mail_settings_page'
    );
});

/**
 * 设置页面内容
 */
function flood_monitor_mail_settings_page() {
    // 清除缓存以获取最新配置
    flood_monitor_clear_mail_config_cache();
    $config = flood_monitor_get_mail_config();
    ?>
    <div class="wrap">
        <h1>水浸监测邮件配置</h1>
        
        <div class="card">
            <h2>配置状态</h2>
            <?php if ($config && $config['enabled']): ?>
                <p style="color: green;">✓ 邮件通知已启用</p>
                <?php if (!empty($config['smtp_host'])): ?>
                    <h3>SMTP 配置</h3>
                    <table class="form-table">
                        <tr>
                            <th>SMTP 服务器</th>
                            <td><?php echo esc_html($config['smtp_host']); ?></td>
                        </tr>
                        <tr>
                            <th>端口</th>
                            <td><?php echo esc_html($config['smtp_port']); ?></td>
                        </tr>
                        <tr>
                            <th>用户名</th>
                            <td><?php echo esc_html($config['smtp_user']); ?></td>
                        </tr>
                        <tr>
                            <th>SSL/TLS</th>
                            <td><?php echo $config['smtp_ssl'] ? '是' : '否'; ?></td>
                        </tr>
                    </table>
                <?php else: ?>
                    <p>使用 WordPress 默认邮件配置</p>
                <?php endif; ?>
            <?php else: ?>
                <p style="color: red;">✗ 邮件通知未启用或配置无效</p>
                <p>请在水浸监测系统前端配置邮件通知。</p>
            <?php endif; ?>
        </div>
        
        <div class="card" style="margin-top: 20px;">
            <h2>后端连接</h2>
            <p>后端 API 地址: <code><?php echo esc_html(FLOOD_MONITOR_BACKEND_URL); ?></code></p>
        </div>
    </div>
    <?php
}
