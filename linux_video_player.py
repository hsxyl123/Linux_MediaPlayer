#!/usr/bin/env python3
"""
Linux Video Player - 基于 python-mpv 和 GTK3 的现代视频播放器
重构与修复版
"""

import os
import json
import hashlib
import shutil
import subprocess
import tempfile
import threading
import time
# 强制使用 X11 后端，因为基于 XID 的嵌入方式在 Wayland 下会崩溃
os.environ["GDK_BACKEND"] = "x11"

import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, Gdk, GLib, Pango

import cairo
import mpv
import requests
import sys
from media_stream import MediaStreamServer, discover_local_ip
from watch_party import WatchPartyClient

WHISPER_API_BASE = os.getenv("WHISPER_API_BASE", "http://192.168.62.1:8000")
WHISPER_MODEL = os.getenv("WHISPER_MODEL", "whisper-large-v3")

class VideoPlayer(Gtk.Application):
    def __init__(self):
        super().__init__(application_id='com.example.videoplayer')
        
        self.mpv_player = None
        self.is_playing = False
        self.is_fullscreen = False
        self.is_seeking = False
        self.is_looping = False
        self.is_playlist_visible = False
        self.current_file = None
        self.last_volume = 100
        self.is_generating_ai_subtitle = False
        self.embedded_subtitles = []
        self.detected_subtitles = []
        self._click_timeout_id = None # 用于解决单双击冲突
        self.watch_party = None
        self.room_code = ""
        self.room_is_host = False
        self.room_user_id = ""
        self.room_sync_guard = False
        self.room_last_media_warning = ""
        self.room_server_url = ""
        self.media_stream_server = None
        self.current_stream_url = ""
        self.remote_stream_url = ""
        self.is_chat_visible = False
        self.danmaku_enabled = True
        self.danmaku_opacity = 80
        self.danmaku_font_size = 32
        self.danmaku_duration = 5
        self.danmaku_items = []
        self.danmaku_tracks = {}  # 轨道索引 -> 占用结束时间（单调时钟）
        self._danmaku_timer_id = None
        self._danmaku_overlay_supported = None
        
        # UI 组件引用
        self.window = None
        self.header_bar = None
        self.drawing_area = None
        self.controls_box = None
        self.progress_scale = None
        self.volume_scale = None
        self.time_label = None
        self.play_button = None
        self.subtitle_button = None
        self.aspect_combo = None
        self.loop_button = None
        self.speed_combo = None
        self.fullscreen_btn = None
        self.volume_label = None
        self.playlist_button = None
        self.playlist_box = None
        self.playlist_view = None
        self.playlist_store = None
        self.ai_subtitle_dialog = None
        self.ai_subtitle_spinner = None
        self.ai_subtitle_status_label = None
        self.room_button = None
        self.chat_toggle_button = None
        self.chat_box = None
        self.chat_view = None
        self.chat_buffer = None
        self.chat_entry = None
        self.chat_send_button = None
        self.chat_status_label = None
        self.chat_users_label = None

        self.history_file = self.get_history_file()
        self.play_history = self.load_play_history()
        GLib.timeout_add_seconds(2, self.broadcast_periodic_playback)

    def do_activate(self):
        if not self.window:
            self.create_window()
        self.window.present()

    def create_window(self):
        self.window = Gtk.ApplicationWindow(
            application=self,
            title="Linux Player",
            default_width=1024,
            default_height=768
        )
        self.window.set_position(Gtk.WindowPosition.CENTER)
        
        self.setup_style()
        self.build_ui()
        self.connect_signals()
        
        # 必须先 show_all 才能获取底层窗口 XID
        self.window.show_all()

    def setup_style(self):
        screen = Gdk.Screen.get_default()
        provider = Gtk.CssProvider()
        css = """
            * {
                color: #202124;
                font-family: 'Segoe UI', 'Roboto', sans-serif;
                font-size: 13px;
            }
            window {
                background-color: #f5f6f8;
            }
            #main-box {
                background-color: #f5f6f8;
            }
            #video-area {
                background-color: #111217;
            }
            #controls-box {
                background-color: #ffffff;
                border-top: 1px solid #dcdfe5;
                padding: 10px 14px 12px 14px;
            }
            button {
                background-image: none;
                background-color: transparent;
                border: none;
                border-radius: 6px;
                padding: 6px;
                min-width: 34px;
                min-height: 34px;
                color: #202124;
            }
            button:hover {
                background-color: #eef0f4;
            }
            button:active {
                background-color: #e1e5ed;
            }
            #play-btn {
                background-color: #ffffff;
                border: none;
                border-radius: 6px;
                box-shadow: none;
                outline-style: none;
                color: #202124;
                min-width: 38px;
                min-height: 38px;
            }
            #play-btn:hover {
                background-color: #f5f7fb;
            }
            #play-btn:active {
                background-color: #e8ebf0;
            }
            #volume-btn {
                box-shadow: none;
                outline-style: none;
            }
            #volume-btn:focus {
                box-shadow: none;
                outline-style: none;
                border-color: transparent;
            }
            #open-btn {
                background-color: #ffffff;
                border: 1px solid #d4d8e0;
                border-radius: 6px;
                padding: 6px 14px;
            }
            #open-btn:hover {
                background-color: #f5f7fb;
                border-color: #b8c0cc;
            }
            #open-btn:active {
                background-color: #e8ebf0;
                border-color: #aeb7c5;
            }
            #playlist-btn {
                background-color: #ffffff;
                border: 1px solid #d4d8e0;
                border-radius: 6px;
                padding: 6px 14px;
            }
            #playlist-btn:hover {
                background-color: #f5f7fb;
                border-color: #b8c0cc;
            }
            #playlist-btn:active {
                background-color: #e8ebf0;
                border-color: #aeb7c5;
            }
            #subtitle-btn {
                background-color: #ffffff;
                border: 1px solid #d4d8e0;
                border-radius: 6px;
                padding: 6px 10px;
            }
            #subtitle-btn:hover {
                background-color: #f5f7fb;
                border-color: #b8c0cc;
            }
            #subtitle-btn:active {
                background-color: #e8ebf0;
                border-color: #aeb7c5;
            }
            #subtitle-btn:disabled {
                color: #aeb5c0;
                border-color: #e1e4ea;
            }
            scale {
                background-color: transparent;
            }
            scale trough {
                min-height: 1px;
                border-radius: 2px;
                background-color: #e6e8ed;
            }
            scale trough highlight {
                min-height: 1px;
                border-radius: 2px;
                background-color: #b8bec8;
            }
            scale slider {
                background-color: #ffffff;
                border: 1px solid #aeb5c0;
                border-radius: 50%;
                min-width: 8px;
                min-height: 8px;
                margin: -1px;
            }
            scale slider:hover {
                background-color: #f5f6f8;
            }
            #progress-scale trough {
                min-height: 1px;
            }
            #progress-scale trough highlight {
                min-height: 1px;
            }
            #progress-scale slider {
                min-width: 8px;
                min-height: 8px;
            }
            #volume-scale trough {
                min-height: 1px;
                min-width: 86px;
            }
            #volume-scale trough highlight {
                min-height: 1px;
            }
            #volume-scale slider {
                min-width: 8px;
                min-height: 8px;
            }
            combobox {
                background-color: #ffffff;
                border: 1px solid #d4d8e0;
                border-radius: 6px;
                padding: 5px 8px;
                color: #202124;
            }
            combobox:hover {
                border-color: #aeb7c5;
            }
            label {
                color: #5f6673;
                font-size: 12px;
            }
            #time-label {
                color: #2f343d;
                font-family: 'Consolas', 'Monaco', monospace;
                font-size: 12px;
                min-width: 110px;
            }
            #header-bar {
                background-color: #ffffff;
                border-bottom: 1px solid #dcdfe5;
                padding: 4px 12px;
            }
            #playlist-box {
                background-color: #ffffff;
                border-left: 1px solid #dcdfe5;
                padding: 10px;
            }
            #playlist-title {
                color: #2f343d;
                font-weight: bold;
                font-size: 12px;
                padding-bottom: 6px;
            }
            treeview {
                background-color: #ffffff;
                color: #202124;
            }
            treeview:selected {
                background-color: #eef0f4;
                color: #202124;
            }
            .suggested-action {
                background-color: #e8f0ff;
                color: #1d4ed8;
            }
            #chat-box {
                background-color: #ffffff;
                border-left: 1px solid #dcdfe5;
                padding: 10px;
            }
            #chat-status {
                font-weight: bold;
                color: #1d4ed8;
            }
        """
        try:
            provider.load_from_data(css.encode())
            Gtk.StyleContext.add_provider_for_screen(screen, provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        except Exception as e:
            print(f"CSS 加载错误: {e}")

    def build_ui(self):
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        main_box.set_name("main-box")
        self.window.add(main_box)

        # Header Bar
        self.header_bar = Gtk.HeaderBar()
        self.header_bar.set_name("header-bar")
        self.header_bar.set_show_close_button(True)
        self.header_bar.set_title("Linux Player")
        self.header_bar.set_subtitle("Ready")

        self.open_btn = Gtk.Button.new_with_label("Open")
        self.open_btn.set_name("open-btn")
        self.open_btn.set_tooltip_text("打开视频文件")
        self.header_bar.pack_start(self.open_btn)

        self.playlist_button = Gtk.Button()
        self.playlist_button.add(Gtk.Image.new_from_icon_name("open-menu-symbolic", Gtk.IconSize.BUTTON))
        self.playlist_button.set_name("playlist-btn")
        self.playlist_button.set_tooltip_text("显示/隐藏播放列表")
        self.header_bar.pack_start(self.playlist_button)

        self.room_button = Gtk.Button.new_with_label("影院房间")
        self.room_button.set_tooltip_text("创建或加入同步观影聊天室")
        self.header_bar.pack_end(self.room_button)

        self.chat_toggle_button = Gtk.Button.new_with_label("隐藏聊天室")
        self.chat_toggle_button.set_tooltip_text("显示或隐藏聊天室")
        self.chat_toggle_button.set_no_show_all(True)
        self.chat_toggle_button.hide()
        self.header_bar.pack_end(self.chat_toggle_button)

        self.window.set_titlebar(self.header_bar)

        content_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        main_box.pack_start(content_box, True, True, 0)

        # Video Area
        self.drawing_area = Gtk.DrawingArea()
        self.drawing_area.set_name("video-area")
        self.drawing_area.set_hexpand(True)
        self.drawing_area.set_vexpand(True)
        self.drawing_area.set_can_focus(True)
        content_box.pack_start(self.drawing_area, True, True, 0)

        self.playlist_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        self.playlist_box.set_name("playlist-box")
        self.playlist_box.set_size_request(240, -1)
        content_box.pack_end(self.playlist_box, False, False, 0)

        playlist_title = Gtk.Label(label="播放列表")
        playlist_title.set_name("playlist-title")
        playlist_title.set_xalign(0)
        self.playlist_box.pack_start(playlist_title, False, False, 0)

        self.playlist_store = Gtk.ListStore(str, str)
        self.playlist_view = Gtk.TreeView(model=self.playlist_store)
        self.playlist_view.set_headers_visible(False)
        self.playlist_view.set_tooltip_column(1)

        playlist_renderer = Gtk.CellRendererText()
        playlist_renderer.set_property("ellipsize", Pango.EllipsizeMode.END)
        playlist_column = Gtk.TreeViewColumn("视频", playlist_renderer, text=0)
        self.playlist_view.append_column(playlist_column)

        playlist_scroll = Gtk.ScrolledWindow()
        playlist_scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        playlist_scroll.add(self.playlist_view)
        self.playlist_box.pack_start(playlist_scroll, True, True, 0)
        self.playlist_box.hide()
        self.refresh_playlist()

        self.chat_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        self.chat_box.set_name("chat-box")
        self.chat_box.set_size_request(300, -1)
        self.chat_box.set_no_show_all(True)
        content_box.pack_end(self.chat_box, False, False, 0)

        self.chat_status_label = Gtk.Label(label="未连接影院房间")
        self.chat_status_label.set_name("chat-status")
        self.chat_status_label.set_xalign(0)
        self.chat_box.pack_start(self.chat_status_label, False, False, 0)

        self.chat_users_label = Gtk.Label(label="在线用户：0")
        self.chat_users_label.set_xalign(0)
        self.chat_box.pack_start(self.chat_users_label, False, False, 0)

        chat_scroll = Gtk.ScrolledWindow()
        chat_scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.chat_view = Gtk.TextView()
        self.chat_view.set_editable(False)
        self.chat_view.set_cursor_visible(False)
        self.chat_view.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        self.chat_buffer = self.chat_view.get_buffer()
        chat_scroll.add(self.chat_view)
        self.chat_box.pack_start(chat_scroll, True, True, 0)

        chat_input_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self.chat_entry = Gtk.Entry()
        self.chat_entry.set_placeholder_text("输入消息...")
        self.chat_send_button = Gtk.Button.new_with_label("发送")
        chat_input_row.pack_start(self.chat_entry, True, True, 0)
        chat_input_row.pack_start(self.chat_send_button, False, False, 0)
        self.chat_box.pack_start(chat_input_row, False, False, 0)

        chat_actions = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        settings_button = Gtk.Button.new_with_label("弹幕设置")
        leave_button = Gtk.Button.new_with_label("离开房间")
        settings_button.connect("clicked", self.show_danmaku_settings)
        leave_button.connect("clicked", self.leave_watch_party)
        chat_actions.pack_start(settings_button, True, True, 0)
        chat_actions.pack_start(leave_button, True, True, 0)
        self.chat_box.pack_start(chat_actions, False, False, 0)
        self.chat_box.hide()

        # Controls Overlays
        controls_overlay = Gtk.Overlay()
        main_box.pack_start(controls_overlay, False, False, 0)

        self.controls_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        self.controls_box.set_name("controls-box")
        controls_overlay.add(self.controls_box)

        # Progress Bar
        self.progress_scale = Gtk.Scale(orientation=Gtk.Orientation.HORIZONTAL)
        self.progress_scale.set_name("progress-scale")
        self.progress_scale.set_draw_value(False)
        self.progress_scale.set_range(0, 100)
        self.progress_scale.set_value(0)
        self.controls_box.pack_start(self.progress_scale, False, False, 0)

        # Buttons Row
        buttons_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.controls_box.pack_start(buttons_row, False, False, 0)

        # Left Controls
        left_controls = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        buttons_row.pack_start(left_controls, False, False, 0)

        self.play_button = Gtk.Button()
        self.play_button.add(Gtk.Image.new_from_icon_name("media-playback-start-symbolic", Gtk.IconSize.BUTTON))
        self.play_button.set_name("play-btn")
        self.play_button.set_tooltip_text("播放/暂停")
        left_controls.pack_start(self.play_button, False, False, 0)

        self.volume_label = Gtk.Button()
        self.volume_label.add(Gtk.Image.new_from_icon_name("audio-volume-high-symbolic", Gtk.IconSize.BUTTON))
        self.volume_label.set_name("volume-btn")
        self.volume_label.set_can_focus(False)
        self.volume_label.set_tooltip_text("音量")
        left_controls.pack_start(self.volume_label, False, False, 0)

        self.volume_scale = Gtk.Scale(orientation=Gtk.Orientation.HORIZONTAL)
        self.volume_scale.set_name("volume-scale")
        self.volume_scale.set_draw_value(False)
        self.volume_scale.set_range(0, 100)
        self.volume_scale.set_value(100)
        self.volume_scale.set_size_request(110, -1)
        left_controls.pack_start(self.volume_scale, False, False, 0)

        # Center Time
        center_info = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        center_info.set_halign(Gtk.Align.CENTER)
        buttons_row.pack_start(center_info, True, True, 0)

        self.time_label = Gtk.Label(label="0:00 / 0:00")
        self.time_label.set_name("time-label")
        center_info.pack_start(self.time_label, False, False, 0)

        # Right Controls
        right_controls = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        buttons_row.pack_end(right_controls, False, False, 0)

        self.subtitle_button = Gtk.Button.new_with_label("CC")
        self.subtitle_button.set_name("subtitle-btn")
        self.subtitle_button.set_tooltip_text("字幕")
        self.subtitle_button.set_sensitive(False)
        right_controls.pack_start(self.subtitle_button, False, False, 0)

        aspect_store = Gtk.ListStore(str, str)
        for label, value in [("自动", "no"), ("16:9", "16:9"), ("4:3", "4:3")]:
            aspect_store.append([label, value])
        self.aspect_combo = Gtk.ComboBox.new_with_model(aspect_store)
        aspect_renderer = Gtk.CellRendererText()
        self.aspect_combo.pack_start(aspect_renderer, True)
        self.aspect_combo.add_attribute(aspect_renderer, "text", 0)
        self.aspect_combo.set_active(0)
        self.aspect_combo.set_tooltip_text("视频比例")
        right_controls.pack_start(self.aspect_combo, False, False, 0)

        speed_store = Gtk.ListStore(str)
        for s in ["0.5x", "1.0x", "1.25x", "1.5x", "2.0x"]:
            speed_store.append([s])
        self.speed_combo = Gtk.ComboBox.new_with_model(speed_store)
        renderer = Gtk.CellRendererText()
        self.speed_combo.pack_start(renderer, True)
        self.speed_combo.add_attribute(renderer, "text", 0)
        self.speed_combo.set_active(1) # Default 1.0x
        self.speed_combo.set_tooltip_text("播放速度")
        right_controls.pack_start(self.speed_combo, False, False, 0)

        self.loop_button = Gtk.Button()
        self.loop_button.add(Gtk.Image.new_from_icon_name("media-playlist-repeat-symbolic", Gtk.IconSize.BUTTON))
        self.loop_button.set_tooltip_text("循环播放")
        right_controls.pack_start(self.loop_button, False, False, 0)

        self.fullscreen_btn = Gtk.Button()
        self.fullscreen_btn.add(Gtk.Image.new_from_icon_name("view-fullscreen-symbolic", Gtk.IconSize.BUTTON))
        self.fullscreen_btn.set_tooltip_text("全屏")
        right_controls.pack_start(self.fullscreen_btn, False, False, 0)

    def connect_signals(self):
        self.window.connect("delete-event", self.on_delete_event)
        self.window.connect("key-press-event", self.on_key_press)

        self.drawing_area.connect("realize", self.on_drawing_area_realize)
        self.drawing_area.connect("draw", self.on_draw)
        self.drawing_area.connect("button-press-event", self.on_video_click)
        # 允许接收鼠标点击事件
        self.drawing_area.add_events(Gdk.EventMask.BUTTON_PRESS_MASK)

        self.open_btn.connect("clicked", self.on_open_file)
        self.playlist_button.connect("clicked", self.toggle_playlist)
        self.room_button.connect("clicked", self.show_watch_party_dialog)
        self.chat_toggle_button.connect("clicked", self.toggle_chat_panel)
        self.chat_send_button.connect("clicked", self.send_chat_message)
        self.chat_entry.connect("activate", self.send_chat_message)
        self.playlist_view.connect("row-activated", self.on_playlist_row_activated)
        self.play_button.connect("clicked", self.toggle_play_pause)
        self.volume_label.connect("clicked", self.toggle_mute)
        self.subtitle_button.connect("clicked", self.on_subtitle_button_clicked)
        self.fullscreen_btn.connect("clicked", self.toggle_fullscreen)
        self.loop_button.connect("clicked", self.toggle_loop)

        self.progress_scale.connect("button-press-event", self.on_progress_press)
        self.progress_scale.connect("button-release-event", self.on_progress_release)
        self.progress_scale.connect("value-changed", self.on_progress_changed)

        self.volume_scale.connect("value-changed", self.on_volume_changed)
        self.aspect_combo.connect("changed", self.on_aspect_changed)
        self.speed_combo.connect("changed", self.on_speed_changed)

    def on_drawing_area_realize(self, widget):
        self.setup_mpv()

    def setup_mpv(self):
        window = self.drawing_area.get_window()
        if not window:
            self.show_error_dialog("初始化失败: 无法获取窗口系统引用。")
            return
            
        try:
            xid = window.get_xid()
            self.mpv_player = mpv.MPV(
                wid=str(xid),
                vo='x11', # 强制 x11 避免 Wayland 下崩溃
                hwdec='auto-safe',
                keep_open='yes', # 播放完毕不自动关闭，保持最后一帧
                osc=False,
                input_default_bindings=False,
                input_vo_keyboard=False,
            )
            print("MPV 初始化成功")
            
            # 【修复1】只使用属性观察器，删除多余的 timer
            @self.mpv_player.property_observer('time-pos')
            def time_observer(_name, value):
                if value is not None and not self.is_seeking:
                    GLib.idle_add(self.update_progress, value)

            @self.mpv_player.property_observer('duration')
            def duration_observer(_name, value):
                if value is not None:
                    GLib.idle_add(self.update_duration, value)

            @self.mpv_player.property_observer('eof-reached')
            def eof_observer(_name, value):
                if value:
                    GLib.idle_add(self.on_eof_reached)

            @self.mpv_player.property_observer('track-list')
            def track_list_observer(_name, value):
                GLib.idle_add(self.update_embedded_subtitles, value)

        except Exception as e:
            print(f"MPV 初始化失败: {e}")
            self.show_error_dialog("播放器核心初始化失败，请确保系统已安装 libmpv。")

    def on_draw(self, widget, cr):
        # 【优化】如果视频正在播放，不要用黑色覆盖，让 MPV 渲染
        if self.current_file:
            return True

        width = widget.get_allocated_width()
        height = widget.get_allocated_height()
        cr.set_source_rgb(0.07, 0.07, 0.09)
        cr.rectangle(0, 0, width, height)
        cr.fill()

        cr.set_source_rgba(1, 1, 1, 0.62)
        cr.select_font_face("Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)
        cr.set_font_size(18)
        text = "点击 Open 打开视频文件"
        text_ext = cr.text_extents(text)
        cr.move_to((width - text_ext.width) / 2, (height + text_ext.height) / 2)
        cr.show_text(text)
        return False

    def on_video_click(self, widget, event):
        if not self.current_file or event.button != 1:
            return

        # 【修复2】解决单双击冲突：延迟判定单击事件
        if event.type == Gdk.EventType.BUTTON_PRESS:
            if self._click_timeout_id:
                GLib.source_remove(self._click_timeout_id)
            # 设置 250ms 延迟，看是否会有后续的 _2BUTTON_PRESS
            self._click_timeout_id = GLib.timeout_add(250, self._execute_single_click)
            
        elif event.type == Gdk.EventType._2BUTTON_PRESS:
            # 确认是双击，取消单击的延迟任务
            if self._click_timeout_id:
                GLib.source_remove(self._click_timeout_id)
                self._click_timeout_id = None
            self.toggle_fullscreen()

    def _execute_single_click(self):
        self._click_timeout_id = None
        self.toggle_play_pause(None)
        return False # 停止 timer

    def get_history_file(self):
        config_dir = os.path.join(GLib.get_user_config_dir(), "linux-player")
        return os.path.join(config_dir, "history.json")

    def load_play_history(self):
        try:
            with open(self.history_file, "r", encoding="utf-8") as f:
                paths = json.load(f)
        except (OSError, json.JSONDecodeError):
            return []

        if not isinstance(paths, list):
            return []

        history = []
        for path in paths:
            if isinstance(path, str) and os.path.exists(path) and path not in history:
                history.append(path)
        return history

    def save_play_history(self):
        try:
            os.makedirs(os.path.dirname(self.history_file), exist_ok=True)
            with open(self.history_file, "w", encoding="utf-8") as f:
                json.dump(self.play_history, f, ensure_ascii=False, indent=2)
        except OSError as e:
            print(f"播放历史保存失败: {e}")

    def add_to_play_history(self, file_path):
        file_path = os.path.abspath(file_path)
        if file_path in self.play_history:
            self.play_history.remove(file_path)

        self.play_history.insert(0, file_path)
        self.play_history = self.play_history[:50]
        self.refresh_playlist()
        self.save_play_history()

    def refresh_playlist(self):
        if not self.playlist_store:
            return

        self.playlist_store.clear()
        for file_path in self.play_history:
            self.playlist_store.append([os.path.basename(file_path), file_path])

    def on_playlist_row_activated(self, treeview, path, column):
        model = treeview.get_model()
        tree_iter = model.get_iter(path)
        file_path = model[tree_iter][1]

        if os.path.exists(file_path):
            self.load_video(file_path)
        else:
            self.show_error_dialog("文件不存在，可能已被移动或删除。")
            self.play_history = [p for p in self.play_history if p != file_path]
            self.refresh_playlist()
            self.save_play_history()

    def toggle_playlist(self, button=None):
        self.is_playlist_visible = not self.is_playlist_visible

        if self.is_playlist_visible and not self.is_fullscreen:
            self.playlist_box.show_all()
            self.playlist_button.get_style_context().add_class("suggested-action")
        else:
            self.playlist_box.hide()
            self.playlist_button.get_style_context().remove_class("suggested-action")

    def find_subtitle_files(self, video_path):
        subtitle_extensions = {".srt", ".ass", ".ssa", ".vtt", ".sub"}
        video_dir = os.path.dirname(video_path)
        video_name = os.path.splitext(os.path.basename(video_path))[0].lower()

        try:
            names = os.listdir(video_dir)
        except OSError:
            return []

        subtitles = []
        for name in names:
            file_path = os.path.join(video_dir, name)
            base, ext = os.path.splitext(name)
            if not os.path.isfile(file_path) or ext.lower() not in subtitle_extensions:
                continue

            subtitle_name = base.lower()
            if subtitle_name == video_name or subtitle_name.startswith(video_name + "."):
                subtitles.append(file_path)

        return sorted(subtitles, key=lambda path: os.path.basename(path).lower())

    def update_subtitle_button(self):
        if not self.current_file:
            self.subtitle_button.set_sensitive(False)
            self.subtitle_button.set_tooltip_text("请先打开视频")
            return

        self.subtitle_button.set_sensitive(True)
        if self.embedded_subtitles:
            self.subtitle_button.set_tooltip_text("选择视频内置字幕，或打开外部字幕")
        elif self.detected_subtitles:
            self.subtitle_button.set_tooltip_text("选择同目录字幕，或打开外部字幕")
        else:
            self.subtitle_button.set_tooltip_text("打开外部字幕文件")

    def update_embedded_subtitles(self, track_list=None):
        if track_list is None and self.mpv_player:
            track_list = getattr(self.mpv_player, "track_list", None)

        embedded_subtitles = []
        for track in track_list or []:
            if not isinstance(track, dict) or track.get("type") != "sub":
                continue
            if track.get("external"):
                continue

            title_parts = []
            if track.get("title"):
                title_parts.append(str(track["title"]))
            if track.get("lang"):
                title_parts.append(str(track["lang"]))

            label = " / ".join(title_parts) if title_parts else f"字幕 {track.get('id')}"
            label = f"{label} (内置)"

            embedded_subtitles.append({
                "id": track.get("id"),
                "label": label,
            })

        self.embedded_subtitles = embedded_subtitles
        self.update_subtitle_button()
        return False

    def refresh_embedded_subtitles_later(self):
        self.update_embedded_subtitles()
        return False

    def append_subtitle_menu_items(self, menu, title, subtitles, callback):
        if not subtitles:
            return

        title_item = Gtk.MenuItem(label=title)
        title_item.set_sensitive(False)
        menu.append(title_item)

        for subtitle in subtitles:
            item = Gtk.MenuItem(label=subtitle["label"])
            item.connect("activate", callback, subtitle)
            menu.append(item)

        menu.append(Gtk.SeparatorMenuItem())

    def append_external_subtitle_file_items(self, menu):
        if not self.detected_subtitles:
            return

        title_item = Gtk.MenuItem(label="同目录字幕")
        title_item.set_sensitive(False)
        menu.append(title_item)

        for subtitle_path in self.detected_subtitles:
            item = Gtk.MenuItem(label=os.path.basename(subtitle_path))
            item.connect("activate", self.on_subtitle_file_menu_item_activate, subtitle_path)
            menu.append(item)

        menu.append(Gtk.SeparatorMenuItem())

    def append_ai_subtitle_menu_items(self, menu):
        cache_path = self.get_ai_subtitle_cache_path(self.current_file)
        has_cache = bool(cache_path and os.path.exists(cache_path))
        if has_cache:
            cache_item = Gtk.MenuItem(label="加载 AI 字幕缓存")
            cache_item.connect("activate", self.load_ai_subtitle_cache)
            menu.append(cache_item)

        generate_text = "重新生成 AI 字幕" if has_cache else "生成 AI 字幕"
        generate_label = "正在生成 AI 字幕..." if self.is_generating_ai_subtitle else generate_text
        generate_item = Gtk.MenuItem(label=generate_label)
        generate_item.set_sensitive(not self.is_generating_ai_subtitle)
        generate_item.connect("activate", self.on_generate_ai_subtitle)
        menu.append(generate_item)
        menu.append(Gtk.SeparatorMenuItem())

    def on_embedded_subtitle_menu_item_activate(self, item, subtitle):
        self.select_subtitle_track(subtitle["id"])

    def select_subtitle_track(self, track_id):
        if not self.mpv_player or track_id is None:
            return

        try:
            self.mpv_player.command("set", "sid", str(track_id))
            self.subtitle_button.set_sensitive(True)
            self.subtitle_button.get_style_context().add_class("suggested-action")
        except Exception as e:
            self.show_error_dialog(f"无法打开内置字幕\n\n{str(e)}")

    def on_subtitle_button_clicked(self, button):
        if not self.current_file:
            return

        menu = Gtk.Menu()

        self.append_subtitle_menu_items(
            menu,
            "视频内置字幕",
            self.embedded_subtitles,
            self.on_embedded_subtitle_menu_item_activate
        )
        self.append_external_subtitle_file_items(menu)
        self.append_ai_subtitle_menu_items(menu)

        external_item = Gtk.MenuItem(label="打开外部字幕...")
        external_item.connect("activate", self.on_open_subtitle_file)
        menu.append(external_item)

        off_item = Gtk.MenuItem(label="关闭字幕")
        off_item.connect("activate", self.on_subtitle_off)
        menu.append(off_item)

        menu.show_all()
        menu.popup_at_widget(button, Gdk.Gravity.SOUTH_WEST, Gdk.Gravity.NORTH_WEST, None)

    def on_subtitle_file_menu_item_activate(self, item, subtitle_path):
        self.load_subtitle(subtitle_path)

    def get_ai_subtitle_cache_path(self, video_path):
        if not video_path:
            return None

        try:
            stat = os.stat(video_path)
        except OSError:
            return None

        key_source = f"{os.path.abspath(video_path)}|{stat.st_size}|{stat.st_mtime_ns}"
        cache_key = hashlib.sha256(key_source.encode("utf-8")).hexdigest()
        cache_dir = os.path.join(GLib.get_user_cache_dir(), "linux-player", "ai-subtitles")
        return os.path.join(cache_dir, f"{cache_key}.srt")

    def has_ai_subtitle_cache(self):
        cache_path = self.get_ai_subtitle_cache_path(self.current_file)
        return bool(cache_path and os.path.exists(cache_path))

    def load_ai_subtitle_cache(self, item=None):
        cache_path = self.get_ai_subtitle_cache_path(self.current_file)
        if cache_path and os.path.exists(cache_path):
            self.load_subtitle(cache_path)
        else:
            self.show_error_dialog("没有找到 AI 字幕缓存。")

    def set_subtitle_busy(self, is_busy, message=None):
        self.is_generating_ai_subtitle = is_busy
        self.subtitle_button.set_sensitive(not is_busy)
        self.subtitle_button.set_tooltip_text(message or ("字幕" if not is_busy else "正在生成 AI 字幕..."))
        return False

    def check_whisper_service(self):
        try:
            response = requests.get(f"{WHISPER_API_BASE.rstrip('/')}/health", timeout=5)
            response.raise_for_status()
        except requests.RequestException as e:
            raise RuntimeError(
                f"无法连接 Whisper 服务: {WHISPER_API_BASE}\n"
                "请检查宿主机服务是否启动，以及虚拟机是否能访问 192.168.62.1:8000。"
            ) from e

    def extract_audio_for_ai_subtitle(self, video_path):
        if not shutil.which("ffmpeg"):
            raise RuntimeError("未找到 ffmpeg，请先安装: sudo apt install ffmpeg")

        temp_file = tempfile.NamedTemporaryFile(prefix="linux-ai-subtitle-", suffix=".mp3", delete=False)
        temp_audio_path = temp_file.name
        temp_file.close()

        command = [
            "ffmpeg",
            "-y",
            "-i", video_path,
            "-vn",
            "-ac", "1",
            "-ar", "16000",
            "-b:a", "64k",
            temp_audio_path,
        ]

        try:
            result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        except OSError as e:
            try:
                os.remove(temp_audio_path)
            except OSError:
                pass
            raise RuntimeError(f"音频提取失败: {e}") from e

        if result.returncode != 0:
            try:
                os.remove(temp_audio_path)
            except OSError:
                pass
            error_text = result.stderr.strip() or "ffmpeg 未返回错误信息"
            raise RuntimeError(f"音频提取失败\n\n{error_text[-1000:]}")

        return temp_audio_path

    def request_ai_subtitle(self, audio_path):
        url = f"{WHISPER_API_BASE.rstrip('/')}/v1/audio/transcriptions"
        headers = {}
        api_key = os.getenv("WHISPER_API_KEY")
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        with open(audio_path, "rb") as audio_file:
            files = {"file": (os.path.basename(audio_path), audio_file, "audio/mpeg")}
            data = {
                "model": WHISPER_MODEL,
                "response_format": "srt",
            }
            try:
                response = requests.post(url, headers=headers, files=files, data=data, timeout=None)
                response.raise_for_status()
            except requests.RequestException as e:
                response_text = getattr(e.response, "text", "") if getattr(e, "response", None) else ""
                detail = f"\n\n{response_text[:1000]}" if response_text else ""
                raise RuntimeError(f"Whisper 转写请求失败: {e}{detail}") from e

        subtitle_text = response.text.strip()
        if not subtitle_text:
            raise RuntimeError("Whisper 服务返回了空字幕。")
        return subtitle_text

    def generate_ai_subtitle_worker(self, video_path, cache_path):
        temp_audio_path = None
        try:
            self.check_whisper_service()
            temp_audio_path = self.extract_audio_for_ai_subtitle(video_path)
            subtitle_text = self.request_ai_subtitle(temp_audio_path)

            os.makedirs(os.path.dirname(cache_path), exist_ok=True)
            with open(cache_path, "w", encoding="utf-8") as f:
                f.write(subtitle_text)
                if not subtitle_text.endswith("\n"):
                    f.write("\n")

            GLib.idle_add(self.on_ai_subtitle_generated, cache_path)
        except Exception as e:
            GLib.idle_add(self.on_ai_subtitle_generation_failed, str(e))
        finally:
            if temp_audio_path:
                try:
                    os.remove(temp_audio_path)
                except OSError:
                    pass

    def on_ai_subtitle_generated(self, cache_path):
        self.set_subtitle_busy(False)
        self.update_subtitle_button()
        self.load_subtitle(cache_path)
        self.update_ai_subtitle_dialog_success()
        return False

    def on_ai_subtitle_generation_failed(self, message):
        self.set_subtitle_busy(False)
        self.update_subtitle_button()
        self.close_ai_subtitle_dialog()
        self.show_error_dialog(f"AI 字幕生成失败\n\n{message}")
        return False

    def on_generate_ai_subtitle(self, item=None):
        if not self.current_file or self.is_generating_ai_subtitle:
            return

        cache_path = self.get_ai_subtitle_cache_path(self.current_file)
        if not cache_path:
            self.show_error_dialog("无法创建 AI 字幕缓存路径。")
            return

        if os.path.exists(cache_path):
            try:
                os.remove(cache_path)
            except OSError:
                pass

        video_path = self.current_file
        self.set_subtitle_busy(True, "正在生成 AI 字幕...")
        self.show_ai_subtitle_progress_dialog()
        worker = threading.Thread(
            target=self.generate_ai_subtitle_worker,
            args=(video_path, cache_path),
            daemon=True,
        )
        worker.start()

    def on_open_subtitle_file(self, item):
        dialog = Gtk.FileChooserDialog(
            title="选择字幕文件",
            parent=self.window,
            action=Gtk.FileChooserAction.OPEN
        )
        dialog.add_buttons("取消", Gtk.ResponseType.CANCEL, "打开", Gtk.ResponseType.ACCEPT)

        filter_subtitle = Gtk.FileFilter()
        filter_subtitle.set_name("字幕文件")
        for pattern in ("*.srt", "*.ass", "*.ssa", "*.vtt", "*.sub"):
            filter_subtitle.add_pattern(pattern)
        dialog.add_filter(filter_subtitle)

        response = dialog.run()
        if response == Gtk.ResponseType.ACCEPT:
            subtitle_path = dialog.get_filename()
            dialog.destroy()
            self.load_subtitle(subtitle_path)
        else:
            dialog.destroy()

    def load_subtitle(self, subtitle_path):
        if not self.mpv_player or not self.current_file:
            return

        try:
            self.mpv_player.command("sub-add", subtitle_path, "select")
            self.subtitle_button.get_style_context().add_class("suggested-action")
        except Exception as e:
            self.show_error_dialog(f"无法加载字幕文件\n\n{str(e)}")

    def on_subtitle_off(self, item):
        if not self.mpv_player:
            return

        try:
            self.mpv_player.command("set", "sid", "no")
            self.subtitle_button.get_style_context().remove_class("suggested-action")
        except Exception as e:
            self.show_error_dialog(f"无法关闭字幕\n\n{str(e)}")

    def show_watch_party_dialog(self, button=None):
        if self.watch_party:
            if self.room_code:
                self.set_chat_panel_visible(True)
            return

        dialog = Gtk.Dialog(title="影院房间", parent=self.window, modal=True)
        dialog.add_buttons(
            "取消", Gtk.ResponseType.CANCEL,
            "加入房间", Gtk.ResponseType.APPLY,
            "创建房间", Gtk.ResponseType.OK,
        )
        dialog.set_default_size(420, 220)
        content = dialog.get_content_area()
        content.set_spacing(10)
        content.set_margin_top(16)
        content.set_margin_bottom(16)
        content.set_margin_left(16)
        content.set_margin_right(16)

        name_entry = Gtk.Entry()
        name_entry.set_placeholder_text("昵称")
        name_entry.set_text(os.getenv("USER", "Viewer"))
        server_entry = Gtk.Entry()
        server_entry.set_placeholder_text("WebSocket 服务地址")
        server_entry.set_text(os.getenv("WATCH_PARTY_SERVER", "ws://127.0.0.1:8765"))
        code_entry = Gtk.Entry()
        code_entry.set_placeholder_text("加入时填写 6 位邀请码")
        code_entry.set_max_length(6)

        for label_text, entry in [
            ("昵称", name_entry),
            ("服务器", server_entry),
            ("邀请码", code_entry),
        ]:
            label = Gtk.Label(label=label_text)
            label.set_xalign(0)
            content.pack_start(label, False, False, 0)
            content.pack_start(entry, False, False, 0)

        dialog.show_all()
        response = dialog.run()
        name = name_entry.get_text().strip()
        server_url = server_entry.get_text().strip()
        code = code_entry.get_text().strip().upper()
        dialog.destroy()

        if response == Gtk.ResponseType.CANCEL:
            return
        if not name or not server_url:
            self.show_error_dialog("昵称和服务器地址不能为空。")
            return
        if response == Gtk.ResponseType.APPLY and len(code) != 6:
            self.show_error_dialog("请输入 6 位邀请码。")
            return
        self.connect_watch_party(
            server_url, name, "join" if response == Gtk.ResponseType.APPLY else "create", code
        )

    def connect_watch_party(self, server_url, name, action, code=""):
        self.leave_watch_party()
        if server_url.startswith("http://"):
            server_url = "ws://" + server_url[len("http://"):]
        elif server_url.startswith("https://"):
            server_url = "wss://" + server_url[len("https://"):]
        self.room_server_url = server_url
        self.chat_buffer.set_text("")
        self.chat_status_label.set_text("正在连接...")
        self.chat_users_label.set_text("在线用户：0")
        self.watch_party = WatchPartyClient(
            server_url,
            name,
            lambda payload: GLib.idle_add(self.handle_watch_party_message, payload),
            lambda reason: GLib.idle_add(self.handle_watch_party_closed, reason),
        )
        self.watch_party.connect(action, code)

    def handle_watch_party_message(self, payload):
        message_type = payload.get("type")
        if message_type == "joined":
            self.room_code = payload.get("room", "")
            self.room_user_id = payload.get("user_id", "")
            self.room_is_host = bool(payload.get("is_host"))
            role = "房主" if self.room_is_host else "成员"
            self.chat_status_label.set_text(f"房间 {self.room_code} · {role}")
            self.room_button.set_label(f"房间 {self.room_code}")
            self.chat_toggle_button.set_no_show_all(False)
            self.chat_toggle_button.show()
            self.set_chat_panel_visible(True)
            self.append_chat_line(f"[系统] 已进入房间，邀请码：{self.room_code}")
            if self.room_is_host:
                self.ensure_host_media_stream()
                self.broadcast_playback_state()
            else:
                self.apply_remote_playback(payload.get("playback", {}))
        elif message_type == "participants":
            users = payload.get("users", [])
            names = [user.get("name", "") + ("（房主）" if user.get("is_host") else "") for user in users]
            self.chat_users_label.set_text(f"在线用户：{len(users)}  " + "、".join(names))
        elif message_type == "chat":
            name = payload.get("name", "Anonymous")
            text = payload.get("text", "")
            self.append_chat_line(f"{name}：{text}")
            if self.danmaku_enabled:
                self.show_danmaku(name, text)
        elif message_type == "system":
            self.append_chat_line(f"[系统] {payload.get('message', '')}")
        elif message_type == "playback" and not self.room_is_host:
            self.apply_remote_playback(payload)
        elif message_type in ("error", "room_closed"):
            self.show_error_dialog(payload.get("message", "房间连接已关闭。"))
            self.leave_watch_party()
        return False

    def handle_watch_party_closed(self, reason):
        if self.watch_party:
            self.append_chat_line(f"[系统] 连接断开：{reason}")
            self.leave_watch_party()
        return False

    def leave_watch_party(self, button=None):
        if self.watch_party:
            self.watch_party.close()
        self.watch_party = None
        self.room_code = ""
        self.room_user_id = ""
        self.room_is_host = False
        self.room_sync_guard = False
        self.room_server_url = ""
        self.remote_stream_url = ""
        if self.media_stream_server:
            self.media_stream_server.close()
            self.media_stream_server = None
        self.set_chat_panel_visible(False)
        if self.chat_box:
            self.chat_box.set_no_show_all(True)
        if self.chat_toggle_button:
            self.chat_toggle_button.hide()
            self.chat_toggle_button.set_no_show_all(True)
        if self.room_button:
            self.room_button.set_label("影院房间")

    def toggle_chat_panel(self, button=None):
        if not self.watch_party or not self.room_code:
            return
        self.set_chat_panel_visible(not self.is_chat_visible)

    def set_chat_panel_visible(self, visible):
        visible = bool(visible and self.watch_party and self.room_code)
        self.is_chat_visible = visible
        if self.chat_box:
            self.chat_box.set_no_show_all(not visible)
            if visible and not self.is_fullscreen:
                self.chat_box.show_all()
            else:
                self.chat_box.hide()
        if self.chat_toggle_button:
            self.chat_toggle_button.set_label(
                "隐藏聊天室" if visible else "显示聊天室"
            )

    def append_chat_line(self, text):
        if not self.chat_buffer:
            return
        end_iter = self.chat_buffer.get_end_iter()
        prefix = "" if end_iter.get_offset() == 0 else "\n"
        self.chat_buffer.insert(end_iter, prefix + str(text))
        mark = self.chat_buffer.create_mark(None, self.chat_buffer.get_end_iter(), False)
        self.chat_view.scroll_mark_onscreen(mark)
        self.chat_buffer.delete_mark(mark)

    def send_chat_message(self, widget=None):
        text = self.chat_entry.get_text().strip()
        if not text:
            return
        if not self.watch_party or not self.watch_party.send({"type": "chat", "text": text}):
            self.show_error_dialog("消息发送失败，请检查房间连接。")
            return
        self.chat_entry.set_text("")

    def show_danmaku(self, name, text):
        """通过 mpv OSD 绘制从右向左滚动的弹幕。"""
        if not self.current_file or not self.mpv_player:
            return
        now = time.monotonic()
        track = self._allocate_track(now)
        self.danmaku_items.append({
            "text": self._escape_osd_ass_text(f"{name}：{text}"),
            "start": now,
            "duration": max(1.0, float(self.danmaku_duration)),
            "track": track,
            "font_size": self.danmaku_font_size,
            "opacity": self.danmaku_opacity,
        })
        self._render_danmaku_osd(now)
        if self._danmaku_timer_id is None:
            self._danmaku_timer_id = GLib.timeout_add(
                16, self._refresh_danmaku_frame
            )

    def _render_danmaku_osd(self, now):
        """生成当前帧的 ASS OSD，并交给 mpv 合成到视频画面。"""
        if not self.mpv_player:
            return
        active_items = []
        ass_fragments = []
        plain_texts = []

        for item in self.danmaku_items:
            progress = (now - item["start"]) / item["duration"]
            if progress < 0 or progress >= 1:
                continue

            font_size = item["font_size"]
            text_width = max(font_size * 4, len(item["text"]) * font_size)
            x_pos = 1920 - progress * (1920 + text_width + 40)
            y_pos = 30 + item["track"] * (font_size + 10)
            alpha = format(
                round((1 - item["opacity"] / 100.0) * 255), "02X"
            )
            fragment = (
                f"{{\\an7\\pos({int(x_pos)},{int(y_pos)})"
                f"\\fs{font_size}\\bord2\\1c&HFFFFFF&\\1a&H{alpha}&"
                f"\\3c&H000000&\\3a&H80&}}{item['text']}"
            )
            ass_fragments.append(fragment)
            plain_texts.append(item["text"])
            active_items.append(item)

        self.danmaku_items = active_items
        # osd-overlay 的 ass-events 格式只接收 ASS Text 字段内容，
        # 不能包含完整的 Dialogue: 事件行。
        data = "\n".join(ass_fragments)
        if self._danmaku_overlay_supported is not False:
            try:
                self.mpv_player.command(
                    "osd-overlay",
                    42,
                    "ass-events" if data else "none",
                    data,
                    1920,
                    1080,
                    100,
                )
                self._danmaku_overlay_supported = True
                return
            except Exception as e:
                if self._danmaku_overlay_supported is None:
                    print(f"DANMAKU osd-overlay unavailable, using fallback: {e}")
                self._danmaku_overlay_supported = False

        # 极旧版 mpv 不支持 osd-overlay 时仅显示纯文本，避免把 ASS
        # 控制标签直接显示给用户。
        fallback = plain_texts[0] if plain_texts else ""
        try:
            self.mpv_player.command("show-text", fallback, 50)
        except Exception as e:
            print(f"DANMAKU OSD render error: {e}")

    def _refresh_danmaku_frame(self):
        if self.mpv_player and self.danmaku_items:
            self._render_danmaku_osd(time.monotonic())
            return True
        self._danmaku_timer_id = None
        return False

    def _allocate_track(self, current_time):
        """分配一个弹幕轨道索引"""
        max_tracks = max(
            1, min(12, (1080 - 40) // (self.danmaku_font_size + 10))
        )
        self.danmaku_tracks = {
            track: release_time
            for track, release_time in self.danmaku_tracks.items()
            if release_time > current_time
        }
        for i in range(max_tracks):
            if i not in self.danmaku_tracks:
                self.danmaku_tracks[i] = current_time + self.danmaku_duration
                return i
        track = min(self.danmaku_tracks, key=self.danmaku_tracks.get)
        self.danmaku_tracks[track] = current_time + self.danmaku_duration
        return track

    def _cleanup_danmaku(self):
        """清理当前显示中的 mpv OSD 弹幕。"""
        self.danmaku_items = []
        self.danmaku_tracks = {}
        if self._danmaku_timer_id is not None:
            GLib.source_remove(self._danmaku_timer_id)
            self._danmaku_timer_id = None
        if self.mpv_player:
            try:
                if self._danmaku_overlay_supported:
                    self.mpv_player.command(
                        "osd-overlay", 42, "none"
                    )
                else:
                    self.mpv_player.command("show-text", "", 0)
            except Exception:
                pass

    @staticmethod
    def _escape_osd_ass_text(text):
        return (
            str(text)
            .replace("\\", r"\\")
            .replace("{", r"\{")
            .replace("}", r"\}")
            .replace("\r", " ")
            .replace("\n", " ")
        )

    def show_danmaku_settings(self, button=None):
        dialog = Gtk.Dialog(title="弹幕设置", parent=self.window, modal=True)
        dialog.set_default_size(460, -1)
        dialog.add_buttons("取消", Gtk.ResponseType.CANCEL, "保存", Gtk.ResponseType.OK)
        content = dialog.get_content_area()
        content.set_spacing(12)
        content.set_margin_top(16)
        content.set_margin_bottom(16)
        content.set_margin_left(16)
        content.set_margin_right(16)

        enabled = Gtk.Switch()
        enabled.set_active(self.danmaku_enabled)
        opacity = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 10, 100, 5)
        opacity.set_size_request(280, -1)
        opacity.set_hexpand(True)
        opacity.set_value(self.danmaku_opacity)
        opacity.set_value_pos(Gtk.PositionType.RIGHT)
        font_size = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 16, 72, 2)
        font_size.set_size_request(280, -1)
        font_size.set_hexpand(True)
        font_size.set_value(self.danmaku_font_size)
        font_size.set_value_pos(Gtk.PositionType.RIGHT)
        duration = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 2, 12, 1)
        duration.set_size_request(280, -1)
        duration.set_hexpand(True)
        duration.set_value(self.danmaku_duration)
        duration.set_value_pos(Gtk.PositionType.RIGHT)

        grid = Gtk.Grid(column_spacing=12, row_spacing=12)
        grid.set_column_homogeneous(False)
        grid.set_hexpand(True)
        for row, (label_text, control) in enumerate([
            ("启用弹幕", enabled),
            ("透明度（%）", opacity),
            ("字号", font_size),
            ("显示时长（秒）", duration),
        ]):
            label = Gtk.Label(label=label_text)
            label.set_xalign(0)
            grid.attach(label, 0, row, 1, 1)
            grid.attach(control, 1, row, 1, 1)
        grid.get_child_at(1, 0).set_halign(Gtk.Align.START)
        content.pack_start(grid, True, True, 0)
        dialog.show_all()
        if dialog.run() == Gtk.ResponseType.OK:
            previous_settings = (
                self.danmaku_opacity,
                self.danmaku_font_size,
                self.danmaku_duration,
            )
            self.danmaku_enabled = enabled.get_active()
            self.danmaku_opacity = int(opacity.get_value())
            self.danmaku_font_size = int(font_size.get_value())
            self.danmaku_duration = int(duration.get_value())
            current_settings = (
                self.danmaku_opacity,
                self.danmaku_font_size,
                self.danmaku_duration,
            )
            if current_settings != previous_settings:
                self._cleanup_danmaku()
        dialog.destroy()

    def current_media_identity(self):
        if not self.current_file or self.remote_stream_url:
            return "", 0
        try:
            return os.path.basename(self.current_file), os.path.getsize(self.current_file)
        except OSError:
            return os.path.basename(self.current_file), 0

    def ensure_host_media_stream(self):
        if not self.room_is_host or not self.current_file or self.remote_stream_url:
            return ""
        if not os.path.isfile(self.current_file):
            return ""
        if not self.media_stream_server:
            advertised_host = discover_local_ip(self.room_server_url)
            self.media_stream_server = MediaStreamServer(advertised_host)
        self.current_stream_url = self.media_stream_server.set_file(self.current_file)
        return self.current_stream_url

    def broadcast_playback_state(self):
        if not self.watch_party or not self.room_is_host or self.room_sync_guard:
            return
        media_name, media_size = self.current_media_identity()
        stream_url = self.ensure_host_media_stream()
        self.watch_party.send({
            "type": "playback",
            "playing": self.is_playing,
            "position": self.get_current_time(),
            "speed": float(getattr(self.mpv_player, "speed", 1.0) or 1.0),
            "media_name": media_name,
            "media_size": media_size,
            "stream_url": stream_url,
        })

    def broadcast_periodic_playback(self):
        self.broadcast_playback_state()
        return True

    def apply_remote_playback(self, state):
        media_name = state.get("media_name", "")
        stream_url = str(state.get("stream_url", "")).strip()
        if not media_name or not stream_url:
            return

        if self.remote_stream_url != stream_url:
            self.load_remote_stream(stream_url, media_name)
            GLib.timeout_add(700, self.finish_remote_playback_sync, dict(state))
            return

        self.finish_remote_playback_sync(state)

    def load_remote_stream(self, stream_url, media_name):
        if not self.mpv_player:
            return
        self.remote_stream_url = stream_url
        self.current_file = stream_url
        self.room_sync_guard = True
        try:
            self.mpv_player.play(stream_url)
            self.is_playing = True
            self.header_bar.set_subtitle(f"{media_name}（房主视频流）")
            self.update_play_button()
            self.drawing_area.queue_draw()
            self.append_chat_line(f"[系统] 已自动加载房主视频：{media_name}")
        finally:
            self.room_sync_guard = False

    def finish_remote_playback_sync(self, state):
        if self.room_is_host or not self.remote_stream_url:
            return False
        self.room_sync_guard = True
        try:
            target = max(0.0, float(state.get("position", 0.0)))
            if state.get("playing"):
                target += max(0.0, time.time() - float(state.get("updated_at", time.time())))
            if abs(self.get_current_time() - target) > 1.2:
                self.mpv_player.seek(target, "absolute+exact")
            self.is_playing = bool(state.get("playing"))
            self.mpv_player.speed = float(state.get("speed", 1.0) or 1.0)
            self.mpv_player.pause = not self.is_playing
            self.update_play_button()
        finally:
            self.room_sync_guard = False
        return False

    def on_open_file(self, button):
        if self.watch_party and not self.room_is_host:
            self.show_info_dialog("房间成员会自动播放房主的视频流，无需打开本地文件。")
            return
        dialog = Gtk.FileChooserDialog(
            title="选择视频文件",
            parent=self.window,
            action=Gtk.FileChooserAction.OPEN
        )
        dialog.add_buttons("取消", Gtk.ResponseType.CANCEL, "打开", Gtk.ResponseType.ACCEPT)
        
        filter_video = Gtk.FileFilter()
        filter_video.set_name("视频文件")
        filter_video.add_mime_type("video/*")
        dialog.add_filter(filter_video)

        response = dialog.run()
        if response == Gtk.ResponseType.ACCEPT:
            file_path = dialog.get_filename()
            dialog.destroy()
            self.load_video(file_path)
        else:
            dialog.destroy()

    def load_video(self, file_path):
        if not self.mpv_player:
            return
        try:
            self.remote_stream_url = ""
            self.current_file = file_path
            self._cleanup_danmaku()
            self.mpv_player.play(file_path)
            self.is_playing = True
            self.update_play_button()
            self.add_to_play_history(file_path)
            self.embedded_subtitles = []
            self.detected_subtitles = self.find_subtitle_files(file_path)
            self.subtitle_button.get_style_context().remove_class("suggested-action")
            self.update_subtitle_button()
            self.apply_current_aspect_ratio()
            GLib.timeout_add(300, self.refresh_embedded_subtitles_later)
            
            self.header_bar.set_subtitle(os.path.basename(file_path))
            self.drawing_area.queue_draw() # 触发重绘清除提示文字
            self.ensure_host_media_stream()
            self.broadcast_playback_state()
            
        except Exception as e:
            self.show_error_dialog(f"无法加载视频文件\n\n{str(e)}")

    def toggle_play_pause(self, button):
        if not self.current_file or not self.mpv_player:
            return
        if self.watch_party and not self.room_is_host:
            return
            
        self.is_playing = not self.is_playing
        self.mpv_player.pause = not self.is_playing
        self.update_play_button()
        self.broadcast_playback_state()

    def update_play_button(self):
        icon_name = "media-playback-pause-symbolic" if self.is_playing else "media-playback-start-symbolic"
        for child in self.play_button.get_children():
            self.play_button.remove(child)
        self.play_button.add(Gtk.Image.new_from_icon_name(icon_name, Gtk.IconSize.BUTTON))
        self.play_button.show_all()

    def toggle_loop(self, button):
        if not self.mpv_player: return
        self.is_looping = not self.is_looping
        self.mpv_player.loop = 'inf' if self.is_looping else 'no'
        
        # 简单更改按钮背景色表示选中状态
        if self.is_looping:
            self.loop_button.get_style_context().add_class("suggested-action")
        else:
            self.loop_button.get_style_context().remove_class("suggested-action")

    def toggle_fullscreen(self, button=None):
        if self.is_fullscreen:
            self.window.unfullscreen()
            self.controls_box.show()
            self.header_bar.show()
            if self.is_playlist_visible:
                self.playlist_box.show_all()
            if self.watch_party and self.room_code and self.is_chat_visible:
                self.chat_box.set_no_show_all(False)
                self.chat_box.show_all()
        else:
            self.window.fullscreen()
            self.controls_box.hide()
            self.header_bar.hide()
            self.playlist_box.hide()
            self.chat_box.hide()
            
        self.is_fullscreen = not self.is_fullscreen
        self.drawing_area.grab_focus() # 全屏后重新获取焦点，保证键盘生效
        
        icon_name = "view-restore-symbolic" if self.is_fullscreen else "view-fullscreen-symbolic"
        for child in self.fullscreen_btn.get_children():
            self.fullscreen_btn.remove(child)
        self.fullscreen_btn.add(Gtk.Image.new_from_icon_name(icon_name, Gtk.IconSize.BUTTON))
        self.fullscreen_btn.show_all()

    # --- 进度条逻辑 ---
    def on_progress_press(self, scale, event):
        self.is_seeking = True

    def on_progress_release(self, scale, event):
        self.is_seeking = False
        if self.watch_party and not self.room_is_host:
            return
        self.seek_to_position(scale.get_value())

    def on_progress_changed(self, scale):
        if self.is_seeking:
            duration = self.get_duration()
            current_time = (scale.get_value() / 100) * duration
            self.update_time_display(current_time, duration)

    def seek_to_position(self, percentage):
        if self.mpv_player and self.current_file:
            target = (percentage / 100) * self.get_duration()
            self.mpv_player.seek(target, 'absolute+exact')
            self.broadcast_playback_state()

    def update_progress(self, time_pos):
        duration = self.get_duration()
        if duration > 0:
            percentage = (time_pos / duration) * 100
            # 只有在非拖动状态才强制更新滑块
            if not self.is_seeking:
                # 阻塞 value-changed 信号防止死循环
                self.progress_scale.handler_block_by_func(self.on_progress_changed)
                self.progress_scale.set_value(percentage)
                self.progress_scale.handler_unblock_by_func(self.on_progress_changed)
            self.update_time_display(time_pos, duration)

    def update_duration(self, duration):
        if duration > 0:
            self.update_time_display(self.get_current_time(), duration)

    def on_eof_reached(self):
        if not self.is_looping:
            self.is_playing = False
            self.update_play_button()
            self.broadcast_playback_state()

    # --- 辅助方法 ---
    def get_duration(self):
        return getattr(self.mpv_player, 'duration', 0) or 0

    def get_current_time(self):
        return getattr(self.mpv_player, 'time_pos', 0) or 0

    def update_time_display(self, current, duration):
        self.time_label.set_text(f"{self.format_time(current)} / {self.format_time(duration)}")

    def format_time(self, seconds):
        if seconds is None or seconds < 0: return "0:00"
        hours, remainder = divmod(int(seconds), 3600)
        minutes, secs = divmod(remainder, 60)
        return f"{hours}:{minutes:02d}:{secs:02d}" if hours > 0 else f"{minutes}:{secs:02d}"

    # --- 其他控制 ---
    def on_volume_changed(self, scale):
        if self.mpv_player:
            vol = int(scale.get_value())
            self.mpv_player.volume = vol
            if vol > 0:
                self.last_volume = vol
            self.update_volume_icon(vol)

    def toggle_mute(self, button):
        current_volume = int(self.volume_scale.get_value())
        if current_volume > 0:
            self.last_volume = current_volume
            self.volume_scale.set_value(0)
        else:
            restore_volume = self.last_volume if self.last_volume > 0 else 100
            self.volume_scale.set_value(restore_volume)

    def update_volume_icon(self, volume):
        icon_name = "audio-volume-muted-symbolic" if volume == 0 else \
                    "audio-volume-low-symbolic" if volume < 33 else \
                    "audio-volume-medium-symbolic" if volume < 66 else "audio-volume-high-symbolic"
        for child in self.volume_label.get_children():
            self.volume_label.remove(child)
        self.volume_label.add(Gtk.Image.new_from_icon_name(icon_name, Gtk.IconSize.BUTTON))
        self.volume_label.show_all()

    def on_speed_changed(self, combo):
        if self.mpv_player:
            if self.watch_party and not self.room_is_host:
                return
            speed_str = combo.get_model()[combo.get_active()][0]
            self.mpv_player.speed = float(speed_str.replace('x', ''))
            self.broadcast_playback_state()

    def apply_current_aspect_ratio(self):
        if not self.mpv_player or not self.aspect_combo:
            return

        active = self.aspect_combo.get_active()
        if active < 0:
            return

        model = self.aspect_combo.get_model()
        aspect_value = model[active][1]
        self.mpv_player.command("set", "video-aspect-override", aspect_value)

    def on_aspect_changed(self, combo):
        if not self.mpv_player:
            return

        try:
            self.apply_current_aspect_ratio()
        except Exception as e:
            self.show_error_dialog(f"无法切换视频比例\n\n{str(e)}")

    def on_key_press(self, widget, event):
        keyval = event.keyval
        keyname = Gdk.keyval_name(keyval)
        
        if keyname == 'space':
            self.toggle_play_pause(None)
            return True
        elif keyname in ('F', 'f'):
            self.toggle_fullscreen()
            return True
        elif keyname == 'Left':
            if self.mpv_player and (not self.watch_party or self.room_is_host):
                self.mpv_player.seek(-5, 'relative+exact')
                self.broadcast_playback_state()
            return True
        elif keyname == 'Right':
            if self.mpv_player and (not self.watch_party or self.room_is_host):
                self.mpv_player.seek(5, 'relative+exact')
                self.broadcast_playback_state()
            return True
        elif keyname == 'Up':
            self.volume_scale.set_value(min(100, self.volume_scale.get_value() + 5))
            return True
        elif keyname == 'Down':
            self.volume_scale.set_value(max(0, self.volume_scale.get_value() - 5))
            return True
        elif keyname == 'Escape' and self.is_fullscreen:
            self.toggle_fullscreen()
            return True
        return False

    def show_error_dialog(self, message):
        dialog = Gtk.MessageDialog(parent=self.window, modal=True,
                                   message_type=Gtk.MessageType.ERROR,
                                   buttons=Gtk.ButtonsType.OK, title="错误")
        dialog.set_markup(message)
        dialog.run()
        dialog.destroy()

    def show_info_dialog(self, message):
        dialog = Gtk.MessageDialog(parent=self.window, modal=True,
                                   message_type=Gtk.MessageType.INFO,
                                   buttons=Gtk.ButtonsType.OK, title="提示")
        dialog.set_markup(message)
        dialog.run()
        dialog.destroy()

    def show_ai_subtitle_progress_dialog(self):
        self.close_ai_subtitle_dialog()

        dialog = Gtk.Dialog(title="AI 字幕", parent=self.window, modal=False)
        dialog.set_resizable(False)
        dialog.set_default_size(320, 120)
        dialog.connect("delete-event", self.on_ai_subtitle_dialog_delete)

        content = dialog.get_content_area()
        content.set_spacing(12)
        content.set_margin_top(18)
        content.set_margin_bottom(18)
        content.set_margin_left(18)
        content.set_margin_right(18)

        spinner = Gtk.Spinner()
        spinner.start()
        content.pack_start(spinner, False, False, 0)

        label = Gtk.Label(label="正在生成 AI 字幕，请稍后")
        label.set_xalign(0.5)
        content.pack_start(label, False, False, 0)

        self.ai_subtitle_dialog = dialog
        self.ai_subtitle_spinner = spinner
        self.ai_subtitle_status_label = label

        dialog.show_all()

    def on_ai_subtitle_dialog_delete(self, dialog, event):
        if self.is_generating_ai_subtitle:
            return True

        self.ai_subtitle_dialog = None
        self.ai_subtitle_spinner = None
        self.ai_subtitle_status_label = None
        return False

    def update_ai_subtitle_dialog_success(self):
        if not self.ai_subtitle_dialog:
            self.show_info_dialog("AI 字幕生成成功，现在请重新点击播放按钮。")
            return

        if self.ai_subtitle_spinner:
            self.ai_subtitle_spinner.stop()
            self.ai_subtitle_spinner.hide()

        if self.ai_subtitle_status_label:
            self.ai_subtitle_status_label.set_text("AI 字幕生成成功，现在请重新点击播放按钮。")

        self.ai_subtitle_dialog.add_button("确定", Gtk.ResponseType.OK)
        self.ai_subtitle_dialog.connect("response", self.on_ai_subtitle_dialog_response)
        self.ai_subtitle_dialog.show_all()

    def on_ai_subtitle_dialog_response(self, dialog, response):
        self.close_ai_subtitle_dialog()

    def close_ai_subtitle_dialog(self):
        if self.ai_subtitle_dialog:
            self.ai_subtitle_dialog.destroy()

        self.ai_subtitle_dialog = None
        self.ai_subtitle_spinner = None
        self.ai_subtitle_status_label = None

    def on_delete_event(self, widget, event):
        self.leave_watch_party()
        self._cleanup_danmaku()
        if self.mpv_player:
            try: self.mpv_player.terminate()
            except: pass
        self.quit()
        return False

if __name__ == '__main__':
    app = VideoPlayer()
    sys.exit(app.run(sys.argv))
