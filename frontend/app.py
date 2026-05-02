"""Streamlit frontend for the Python/MQTT HBBWater project."""

import base64
import html as html_lib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import plotly.express as px
import requests
import streamlit as st
from streamlit.components.v1 import html as component_html

API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000/api").rstrip("/")
API_PUBLIC_BASE_URL = os.getenv("API_PUBLIC_BASE_URL", API_BASE_URL).rstrip("/")
ASSET_DIR = Path(__file__).resolve().parent / "assets"
MAP_IMAGE_PATH = ASSET_DIR / "campus-water-map.webp"

st.set_page_config(page_title="校园水浸监测系统", layout="wide")


def api_url(path: str) -> str:
    return f"{API_BASE_URL}/{path.lstrip('/')}"


def request_json(method: str, path: str, **kwargs) -> Any:
    token = st.session_state.get("token")
    headers = kwargs.pop("headers", {})
    if token:
        headers["Authorization"] = f"Bearer {token}"
    response = requests.request(method, api_url(path), headers=headers, timeout=8, **kwargs)
    if response.status_code >= 400:
        try:
            detail = response.json().get("detail", response.text)
        except Exception:
            detail = response.text
        raise RuntimeError(detail)
    if not response.content:
        return None
    return response.json()


def load_json(path: str, fallback):
    try:
        return request_json("GET", path)
    except Exception as exc:
        st.warning(f"接口读取失败: {exc}")
        return fallback


@st.cache_data(show_spinner=False)
def load_map_base64() -> str:
    return base64.b64encode(MAP_IMAGE_PATH.read_bytes()).decode("ascii")


def sensor_type_label(sensor_type: str) -> str:
    return "超声波" if sensor_type == "ultrasonic" else "浸水"


def status_label(status: str) -> str:
    return {
        "normal": "正常",
        "warning": "预警",
        "danger": "危险",
        "alarm": "告警",
        "offline": "离线",
        "inactive": "停用",
    }.get(status, status)


def status_badge(row: dict) -> str:
    if not row.get("is_active", True):
        return "inactive"
    if not row.get("online"):
        return "offline"
    return row.get("last_status") or "normal"


def status_css(status: str) -> str:
    if status in {"danger", "alarm"}:
        return "danger"
    if status == "warning":
        return "warning"
    if status in {"offline", "inactive"}:
        return "offline"
    return "normal"


def reading_text(sensor: dict) -> str:
    sensor_type = sensor.get("type")
    status = sensor.get("display_status") or status_badge(sensor)
    if status in {"offline", "inactive"}:
        return "暂无上报"
    value = sensor.get("last_value")
    unit = sensor.get("last_unit") or ("state" if sensor_type == "immersion" else "cm")
    if value is None:
        return "暂无数据"
    if sensor_type == "immersion":
        return "检测到浸水" if float(value) >= 1 else "未检测到浸水"
    return f"{float(value):.1f} {unit}"


def mqtt_topic(sensor_type: str, device_id: str) -> str:
    return f"hbbwater/{sensor_type}/{device_id}/data"


def sample_payload(sensor_type: str, device_id: str, value: float | bool = 12.5) -> dict:
    if sensor_type == "immersion":
        return {
            "device_id": device_id,
            "type": "immersion",
            "water_detected": bool(value),
            "battery": 91,
            "rssi": -58,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    return {
        "device_id": device_id,
        "type": "ultrasonic",
        "value": value,
        "unit": "cm",
        "battery": 85,
        "rssi": -65,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def json_block(data: dict) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2)


def apply_global_style() -> None:
    st.markdown(
        """
        <style>
        .block-container {
            max-width: 1440px;
            padding-top: 1.4rem;
        }
        div[data-testid="stMetric"] {
            background: #ffffff;
            border: 1px solid #e5edf6;
            border-radius: 8px;
            padding: 16px 18px;
            box-shadow: 0 12px 30px rgba(15, 23, 42, 0.06);
        }
        div[data-testid="stMetricLabel"] {
            color: #64748b;
        }
        .section-caption {
            color: #64748b;
            margin-top: -0.6rem;
            margin-bottom: 1rem;
            font-size: 0.92rem;
        }
        .mqtt-box {
            border: 1px solid #dbe5f0;
            background: #f8fbff;
            border-radius: 8px;
            padding: 14px 16px;
        }
        .mqtt-topic {
            font-family: Consolas, monospace;
            background: #0f172a;
            color: #e2e8f0;
            border-radius: 6px;
            padding: 8px 10px;
            overflow-wrap: anywhere;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def login_panel() -> None:
    with st.sidebar:
        st.header("账户")
        if st.session_state.get("token"):
            user = load_json("account/me", {})
            st.caption(f"已登录: {user.get('display_name') or user.get('username')}")
            if st.button("退出登录", use_container_width=True):
                st.session_state.pop("token", None)
                st.rerun()
            return

        username = st.text_input("用户名", value="admin")
        password = st.text_input("密码", value="admin123456", type="password")
        if st.button("登录", type="primary", use_container_width=True):
            try:
                data = request_json("POST", "auth/login", json={"username": username, "password": password})
                st.session_state["token"] = data["access_token"]
                st.rerun()
            except Exception as exc:
                st.error(f"登录失败: {exc}")


def render_simulator() -> None:
    st.sidebar.header("Python 数据模拟")
    device_id = st.sidebar.text_input("设备 ID", value="US001")
    sensor_type = st.sidebar.selectbox("传感器类型", ["ultrasonic", "immersion"], format_func=sensor_type_label)
    if sensor_type == "ultrasonic":
        value = st.sidebar.number_input("水位值", value=12.5, step=0.5)
        unit = st.sidebar.selectbox("单位", ["cm", "mm"])
        payload_value: float | bool = value
    else:
        payload_value = st.sidebar.checkbox("检测到浸水", value=True)
        unit = "state"
    battery = st.sidebar.slider("电量", 0, 100, 85)
    st.sidebar.caption(f"MQTT Topic: `{mqtt_topic(sensor_type, device_id)}`")
    if st.sidebar.button("通过 HTTP 模拟上报", use_container_width=True):
        try:
            request_json(
                "POST",
                "ingest/http",
                json={
                    "device_id": device_id,
                    "type": sensor_type,
                    "value": payload_value,
                    "unit": unit,
                    "battery": battery,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                },
            )
            st.sidebar.success("已上报")
            st.rerun()
        except Exception as exc:
            st.sidebar.error(f"上报失败: {exc}")
    st.sidebar.caption(f"API: {API_PUBLIC_BASE_URL}")


def render_dashboard() -> None:
    st.title("校园水浸监测系统")
    st.markdown('<div class="section-caption">Python + MQTT 的校园水浸监测、告警与可视化平台</div>', unsafe_allow_html=True)
    stats = load_json("dashboard/stats", {})
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("传感器总数", stats.get("sensors_total", 0))
    col2.metric("在线传感器", stats.get("sensors_online", 0))
    col3.metric("活跃告警", stats.get("active_alerts", 0))
    col4.metric("今日读数", stats.get("readings_today", 0))

    sensors = load_json("dashboard/sensor-status", [])
    alerts = load_json("alerts?limit=20", [])
    readings = load_json("readings/recent?limit=80", [])

    st.subheader("传感器状态")
    if sensors:
        df = pd.DataFrame(sensors)
        df["状态"] = df.apply(lambda row: status_label(status_badge(row.to_dict())), axis=1)
        df["MQTT Topic"] = df.apply(lambda row: mqtt_topic(row["type"], row["device_id"]), axis=1)
        st.dataframe(
            df[
                [
                    "device_id",
                    "name",
                    "type",
                    "location",
                    "last_value",
                    "last_unit",
                    "last_battery",
                    "last_seen_at",
                    "状态",
                    "MQTT Topic",
                ]
            ],
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info("暂无传感器。可以从左侧模拟上报，系统会按 MQTT 绑定规则自动注册设备。")

    col_a, col_b = st.columns([1.15, 0.85])
    with col_a:
        st.subheader("近期读数")
        if readings:
            df = pd.DataFrame(readings)
            sensors_df = pd.DataFrame(sensors)
            if not sensors_df.empty:
                df = df.merge(sensors_df[["id", "device_id"]], left_on="sensor_id", right_on="id", how="left")
            fig = px.line(
                df.sort_values("created_at"),
                x="created_at",
                y="value",
                color="device_id",
                markers=True,
                labels={"created_at": "时间", "value": "读数"},
            )
            fig.update_layout(height=380, margin=dict(l=20, r=20, t=30, b=20))
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.caption("暂无读数")

    with col_b:
        st.subheader("近期告警")
        if alerts:
            st.dataframe(pd.DataFrame(alerts), use_container_width=True, hide_index=True)
        else:
            st.caption("暂无告警")


def render_map_html(sensors: list[dict]) -> None:
    markers = []
    for index, sensor in enumerate(sensors):
        x = sensor.get("map_x")
        y = sensor.get("map_y")
        if x is None:
            x = 16 + (index % 4) * 20
        if y is None:
            y = 18 + (index // 4) * 16
        status = sensor.get("display_status") or status_badge(sensor)
        css = status_css(status)
        align_right = " align-right" if float(x) > 70 else ""
        align_bottom = " align-bottom" if float(y) > 70 else ""
        label = html_lib.escape(sensor.get("device_id", ""))
        title = html_lib.escape(f"{sensor.get('location') or '未配置位置'} | {status_label(status)} | {reading_text(sensor)}")
        reading = html_lib.escape(reading_text(sensor))
        sensor_type = html_lib.escape(sensor_type_label(sensor.get("type", "")))
        markers.append(
            f"""
            <div class="sensor-marker status-{css}{align_right}{align_bottom}" style="left:{float(x):.3f}%;top:{float(y):.3f}%;" title="{title}">
              <span class="sensor-dot"><span class="sensor-dot-core"></span></span>
              <span class="sensor-label">
                <span class="sensor-id">{label}</span>
                <span class="sensor-reading">{reading}</span>
                <span class="sensor-hint">{sensor_type} / {html_lib.escape(status_label(status))}</span>
              </span>
            </div>
            """
        )

    map_src = f"data:image/webp;base64,{load_map_base64()}"
    component_html(
        f"""
        <style>
        body {{
          margin: 0;
          font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
          color: #0f172a;
        }}
        .map-stage-shell {{
          border: 1px solid #dbe5f0;
          border-radius: 8px;
          background:
            radial-gradient(circle at 16% 12%, rgba(56, 189, 248, 0.18), transparent 22%),
            linear-gradient(180deg, #e8f1fb 0%, #f6f9fc 100%);
          padding: 14px;
          overflow: auto;
        }}
        .map-stage {{
          position: relative;
          min-width: 860px;
          width: 100%;
        }}
        .map-image {{
          display: block;
          width: 100%;
          border-radius: 8px;
          box-shadow: 0 18px 38px rgba(15, 23, 42, 0.16);
          user-select: none;
        }}
        .sensor-marker {{
          position: absolute;
          transform: translate(-50%, -50%);
          z-index: 5;
        }}
        .sensor-dot {{
          position: relative;
          display: inline-block;
          width: 22px;
          height: 22px;
          border-radius: 999px;
          background: rgba(255, 255, 255, 0.92);
          box-shadow: 0 0 0 6px rgba(59, 130, 246, 0.18), 0 8px 24px rgba(15, 23, 42, 0.24);
          color: #16a34a;
          vertical-align: middle;
        }}
        .sensor-dot::before,
        .sensor-dot::after {{
          content: "";
          position: absolute;
          inset: 50%;
          border-radius: 999px;
          transform: translate(-50%, -50%);
          border: 2px solid currentColor;
          opacity: 0.24;
        }}
        .sensor-dot::before {{
          width: 30px;
          height: 30px;
        }}
        .sensor-dot::after {{
          width: 42px;
          height: 42px;
        }}
        .sensor-dot-core {{
          display: block;
          width: 12px;
          height: 12px;
          margin: 5px;
          border-radius: 999px;
          background: currentColor;
        }}
        .sensor-label {{
          position: absolute;
          left: 22px;
          top: 50%;
          transform: translateY(-50%);
          min-width: 118px;
          max-width: 174px;
          padding: 9px 12px;
          border-radius: 8px;
          background: rgba(255, 255, 255, 0.96);
          box-shadow: 0 16px 28px rgba(15, 23, 42, 0.18);
          border: 1px solid rgba(226, 232, 240, 0.9);
        }}
        .align-right .sensor-label {{
          left: auto;
          right: 22px;
        }}
        .align-bottom .sensor-label {{
          top: auto;
          bottom: 12px;
          transform: none;
        }}
        .sensor-id {{
          display: block;
          font-size: 12px;
          font-weight: 800;
          letter-spacing: 0.02em;
        }}
        .sensor-reading {{
          display: block;
          margin-top: 4px;
          color: #2563eb;
          font-size: 13px;
          font-weight: 700;
        }}
        .sensor-hint {{
          display: inline-flex;
          margin-top: 6px;
          padding: 2px 8px;
          border-radius: 999px;
          background: #eff6ff;
          color: #475569;
          font-size: 11px;
        }}
        .status-normal .sensor-dot {{ color: #16a34a; }}
        .status-warning .sensor-dot {{ color: #f59e0b; }}
        .status-danger .sensor-dot {{ color: #ef4444; }}
        .status-offline .sensor-dot {{ color: #64748b; }}
        .status-offline .sensor-label {{
          background: rgba(248, 250, 252, 0.96);
          color: #475569;
        }}
        .legend {{
          display: flex;
          gap: 14px;
          flex-wrap: wrap;
          margin-top: 12px;
          color: #475569;
          font-size: 12px;
        }}
        .legend-item {{
          display: inline-flex;
          align-items: center;
          gap: 6px;
        }}
        .legend-dot {{
          width: 10px;
          height: 10px;
          border-radius: 999px;
          display: inline-block;
        }}
        .dot-normal {{ background: #16a34a; }}
        .dot-warning {{ background: #f59e0b; }}
        .dot-danger {{ background: #ef4444; }}
        .dot-offline {{ background: #64748b; }}
        </style>
        <div class="map-stage-shell">
          <div class="map-stage">
            <img class="map-image" src="{map_src}" alt="校园水位地图" />
            {"".join(markers)}
          </div>
          <div class="legend">
            <span class="legend-item"><i class="legend-dot dot-normal"></i>正常</span>
            <span class="legend-item"><i class="legend-dot dot-warning"></i>预警</span>
            <span class="legend-item"><i class="legend-dot dot-danger"></i>危险/告警</span>
            <span class="legend-item"><i class="legend-dot dot-offline"></i>离线/停用</span>
          </div>
        </div>
        """,
        height=720,
        scrolling=True,
    )


def render_map() -> None:
    st.title("水位监测地图")
    st.markdown(
        '<div class="section-caption">点位坐标按百分比保存，MQTT 设备上报后会在地图和状态表中同步更新。</div>',
        unsafe_allow_html=True,
    )
    sensors = load_json("dashboard/sensor-status", [])
    if not sensors:
        st.info("暂无地图数据。先到“传感器管理”添加设备，或从左侧模拟 MQTT/HTTP 上报。")
        return

    for sensor in sensors:
        sensor["display_status"] = status_badge(sensor)

    active_sensors = [sensor for sensor in sensors if sensor.get("is_active", True)]
    online_count = sum(1 for sensor in active_sensors if sensor.get("online"))
    abnormal_count = sum(1 for sensor in active_sensors if sensor.get("display_status") in {"warning", "danger", "alarm"})
    ultrasonic_values = [
        float(sensor["last_value"])
        for sensor in active_sensors
        if sensor.get("type") == "ultrasonic" and sensor.get("online") and sensor.get("last_value") is not None
    ]

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("监测点总数", len(active_sensors))
    col2.metric("在线点位", online_count)
    col3.metric("预警/告警", abnormal_count)
    col4.metric("平均水位", f"{sum(ultrasonic_values) / len(ultrasonic_values):.1f} cm" if ultrasonic_values else "--")

    filter_col, select_col = st.columns([0.45, 0.55])
    with filter_col:
        status_filter = st.radio("状态筛选", ["全部", "正常", "异常", "离线"], horizontal=True)
    with select_col:
        selected_device = st.selectbox(
            "点位配置",
            [sensor["device_id"] for sensor in sensors],
            format_func=lambda device: f"{device} - {next((s.get('name') or s.get('location') for s in sensors if s['device_id'] == device), '')}",
        )

    filtered = sensors
    if status_filter == "正常":
        filtered = [sensor for sensor in sensors if sensor.get("display_status") == "normal"]
    elif status_filter == "异常":
        filtered = [sensor for sensor in sensors if sensor.get("display_status") in {"warning", "danger", "alarm"}]
    elif status_filter == "离线":
        filtered = [sensor for sensor in sensors if sensor.get("display_status") in {"offline", "inactive"}]

    render_map_html(filtered)

    selected = next((sensor for sensor in sensors if sensor["device_id"] == selected_device), None)
    if selected:
        left, right = st.columns([0.48, 0.52])
        with left:
            st.subheader("点位详情")
            st.write(
                {
                    "设备ID": selected["device_id"],
                    "类型": sensor_type_label(selected["type"]),
                    "位置": selected.get("location"),
                    "状态": status_label(selected.get("display_status", "offline")),
                    "最近读数": reading_text(selected),
                    "电量": selected.get("last_battery"),
                    "最近上报": selected.get("last_seen_at"),
                }
            )
        with right:
            st.subheader("地图坐标与 MQTT 绑定")
            with st.form("map-position-form"):
                x = st.slider("地图 X 坐标 (%)", 0.0, 100.0, float(selected.get("map_x") or 50.0), 0.5)
                y = st.slider("地图 Y 坐标 (%)", 0.0, 100.0, float(selected.get("map_y") or 50.0), 0.5)
                map_locked = st.checkbox("锁定点位", value=bool(selected.get("map_locked")))
                baseline = st.number_input(
                    "超声波基准值(cm，可选)",
                    min_value=0.0,
                    value=float(selected.get("water_level_baseline") or 0.0),
                    step=0.5,
                    disabled=selected.get("type") != "ultrasonic",
                )
                if st.form_submit_button("保存点位配置", type="primary"):
                    payload = {"map_x": x, "map_y": y, "map_locked": map_locked}
                    if selected.get("type") == "ultrasonic" and baseline > 0:
                        payload["water_level_baseline"] = baseline
                    try:
                        request_json("PUT", f"sensors/{selected['id']}", json=payload)
                        st.success("点位配置已保存")
                        st.rerun()
                    except Exception as exc:
                        st.error(f"保存失败: {exc}")

            st.markdown('<div class="mqtt-box">', unsafe_allow_html=True)
            st.caption("MQTT 绑定规则：设备 ID 与 Topic 中的 device_id 一致即可绑定。")
            st.markdown(
                f'<div class="mqtt-topic">{html_lib.escape(mqtt_topic(selected["type"], selected["device_id"]))}</div>',
                unsafe_allow_html=True,
            )
            st.code(json_block(sample_payload(selected["type"], selected["device_id"])), language="json")
            st.markdown("</div>", unsafe_allow_html=True)


def render_sensor_admin() -> None:
    st.title("传感器管理")
    st.markdown(
        '<div class="section-caption">新增传感器时，设备 ID 就是 MQTT 绑定键；删除传感器会同时删除关联读数和告警。</div>',
        unsafe_allow_html=True,
    )
    sensors = load_json("sensors", [])
    query = st.text_input("搜索传感器、位置或 MQTT Topic", placeholder="US001 / 地下室 / hbbwater")

    rows = []
    for sensor in sensors:
        topic = mqtt_topic(sensor["type"], sensor["device_id"])
        if query and query.lower() not in " ".join(
            [sensor.get("device_id", ""), sensor.get("name", ""), sensor.get("location", ""), topic]
        ).lower():
            continue
        rows.append(
            {
                "ID": sensor["id"],
                "设备ID": sensor["device_id"],
                "名称": sensor.get("name"),
                "类型": sensor_type_label(sensor["type"]),
                "位置": sensor.get("location"),
                "预警阈值": sensor.get("threshold_warn"),
                "危险阈值": sensor.get("threshold_danger"),
                "地图X": sensor.get("map_x"),
                "地图Y": sensor.get("map_y"),
                "MQTT Topic": topic,
                "启用": sensor.get("is_active"),
            }
        )

    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    add_col, edit_col = st.columns([0.48, 0.52])
    with add_col:
        with st.expander("添加传感器并绑定 MQTT", expanded=True):
            with st.form("sensor-create"):
                device_id = st.text_input("设备 ID", placeholder="US002")
                name = st.text_input("名称", placeholder="一号楼地下室超声波水位")
                sensor_type = st.selectbox("类型", ["ultrasonic", "immersion"], format_func=sensor_type_label)
                location = st.text_input("安装位置")
                pos1, pos2 = st.columns(2)
                map_x = pos1.number_input("地图 X(%)", min_value=0.0, max_value=100.0, value=50.0)
                map_y = pos2.number_input("地图 Y(%)", min_value=0.0, max_value=100.0, value=50.0)
                direction = st.selectbox("阈值方向", ["greater_or_equal", "less_or_equal"])
                warn = st.number_input("预警阈值", value=10.0)
                danger = st.number_input("危险阈值", value=20.0)
                st.caption("创建后设备发布到下方 Topic 即完成 MQTT 绑定。")
                preview_device_id = device_id or "US002"
                st.code(mqtt_topic(sensor_type, preview_device_id), language="text")
                st.code(json_block(sample_payload(sensor_type, preview_device_id)), language="json")
                if st.form_submit_button("创建传感器", type="primary"):
                    try:
                        request_json(
                            "POST",
                            "sensors",
                            json={
                                "device_id": device_id,
                                "name": name,
                                "type": sensor_type,
                                "location": location,
                                "map_x": map_x,
                                "map_y": map_y,
                                "threshold_warn": warn,
                                "threshold_danger": danger,
                                "threshold_dir": direction,
                            },
                        )
                        st.success("传感器已创建，MQTT Topic 已绑定")
                        st.rerun()
                    except Exception as exc:
                        st.error(f"创建失败: {exc}")

    with edit_col:
        with st.expander("编辑 / 删除 / 查看绑定", expanded=True):
            if not sensors:
                st.info("暂无传感器")
            else:
                selected_id = st.selectbox(
                    "选择传感器",
                    [sensor["id"] for sensor in sensors],
                    format_func=lambda value: next(
                        f"{sensor['device_id']} - {sensor.get('name') or sensor.get('location')}"
                        for sensor in sensors
                        if sensor["id"] == value
                    ),
                )
                sensor = next(item for item in sensors if item["id"] == selected_id)
                st.markdown('<div class="mqtt-box">', unsafe_allow_html=True)
                st.caption("当前 MQTT 绑定")
                st.markdown(
                    f'<div class="mqtt-topic">{html_lib.escape(mqtt_topic(sensor["type"], sensor["device_id"]))}</div>',
                    unsafe_allow_html=True,
                )
                st.code(json_block(sample_payload(sensor["type"], sensor["device_id"])), language="json")
                st.markdown("</div>", unsafe_allow_html=True)

                with st.form("sensor-update"):
                    name = st.text_input("名称", value=sensor.get("name") or "")
                    sensor_type = st.selectbox(
                        "类型",
                        ["ultrasonic", "immersion"],
                        index=0 if sensor["type"] == "ultrasonic" else 1,
                        format_func=sensor_type_label,
                    )
                    location = st.text_input("安装位置", value=sensor.get("location") or "")
                    map_x = st.number_input("地图 X(%)", min_value=0.0, max_value=100.0, value=float(sensor.get("map_x") or 50.0), key="edit-map-x")
                    map_y = st.number_input("地图 Y(%)", min_value=0.0, max_value=100.0, value=float(sensor.get("map_y") or 50.0), key="edit-map-y")
                    warn = st.number_input("预警阈值", value=float(sensor.get("threshold_warn") or 10.0), key="edit-warn")
                    danger = st.number_input("危险阈值", value=float(sensor.get("threshold_danger") or 20.0), key="edit-danger")
                    is_active = st.checkbox("启用", value=bool(sensor.get("is_active")))
                    save, delete = st.columns(2)
                    save_clicked = save.form_submit_button("保存修改", type="primary", use_container_width=True)
                    delete_clicked = delete.form_submit_button("删除传感器", use_container_width=True)

                if save_clicked:
                    try:
                        request_json(
                            "PUT",
                            f"sensors/{selected_id}",
                            json={
                                "name": name,
                                "type": sensor_type,
                                "location": location,
                                "map_x": map_x,
                                "map_y": map_y,
                                "threshold_warn": warn,
                                "threshold_danger": danger,
                                "is_active": is_active,
                            },
                        )
                        st.success("传感器已更新")
                        st.rerun()
                    except Exception as exc:
                        st.error(f"保存失败: {exc}")

                if delete_clicked:
                    st.session_state["pending_delete_sensor_id"] = selected_id

                if st.session_state.get("pending_delete_sensor_id") == selected_id:
                    st.warning(f"确认删除 {sensor['device_id']}？此操作会删除读数和告警。")
                    confirm_left, confirm_right = st.columns(2)
                    if confirm_left.button("确认删除", type="primary", use_container_width=True):
                        try:
                            request_json("DELETE", f"sensors/{selected_id}")
                            st.session_state.pop("pending_delete_sensor_id", None)
                            st.success("传感器已删除")
                            st.rerun()
                        except Exception as exc:
                            st.error(f"删除失败: {exc}")
                    if confirm_right.button("取消", use_container_width=True):
                        st.session_state.pop("pending_delete_sensor_id", None)
                        st.rerun()


def render_alerts() -> None:
    st.title("告警管理")
    status_filter = st.selectbox("状态筛选", ["全部", "active", "resolved"])
    path = "alerts?limit=200" if status_filter == "全部" else f"alerts?status={status_filter}&limit=200"
    alerts = load_json(path, [])
    if alerts:
        st.dataframe(pd.DataFrame(alerts), use_container_width=True, hide_index=True)
        active_ids = [item["id"] for item in alerts if item.get("status") == "active"]
        if active_ids:
            alert_id = st.selectbox("手动解除告警", active_ids)
            if st.button("解除选中告警", type="primary"):
                try:
                    request_json("PUT", f"alerts/{alert_id}/resolve")
                    st.success("告警已解除")
                    st.rerun()
                except Exception as exc:
                    st.error(f"解除失败: {exc}")
    else:
        st.info("暂无告警")


apply_global_style()
login_panel()
render_simulator()

page = st.sidebar.radio("导航", ["仪表盘", "水位地图", "传感器管理", "告警管理"], label_visibility="collapsed")
if page == "仪表盘":
    render_dashboard()
elif page == "水位地图":
    render_map()
elif page == "传感器管理":
    render_sensor_admin()
else:
    render_alerts()
