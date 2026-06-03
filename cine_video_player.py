#!/usr/bin/env python3
"""
Linux Video Player - 基于 python-mpv 和 GTK3 的现代视频播放器
重构与修复版
"""

import os
import json
# 强制使用 X11 后端，因为基于 XID 的嵌入方式在 Wayland 下会崩溃
os.environ["GDK_BACKEND"] = "x11"

import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, Gdk, GLib, Pango

import cairo
import mpv
import sys

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
        self.embedded_subtitles = []
        self.detected_subtitles = []
        self._click_timeout_id = None # 用于解决单双击冲突
        
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

        self.history_file = self.get_history_file()
        self.play_history = self.load_play_history()

    def do_activate(self):
        if not self.window:
            self.create_window()
        self.window.present()

    def create_window(self):
        self.window = Gtk.ApplicationWindow(
            application=self,
            title="Cine - Video Player",
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
        self.header_bar.set_title("Cine Player")
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
        config_dir = os.path.join(GLib.get_user_config_dir(), "cine-player")
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

        if not self.embedded_subtitles and not self.detected_subtitles:
            self.on_open_subtitle_file(None)
            return

        menu = Gtk.Menu()

        self.append_subtitle_menu_items(
            menu,
            "视频内置字幕",
            self.embedded_subtitles,
            self.on_embedded_subtitle_menu_item_activate
        )
        self.append_external_subtitle_file_items(menu)

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

    def on_open_file(self, button):
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
            self.current_file = file_path
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
            
        except Exception as e:
            self.show_error_dialog(f"无法加载视频文件\n\n{str(e)}")

    def toggle_play_pause(self, button):
        if not self.current_file or not self.mpv_player:
            return
            
        self.is_playing = not self.is_playing
        self.mpv_player.pause = not self.is_playing
        self.update_play_button()

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
        else:
            self.window.fullscreen()
            self.controls_box.hide()
            self.header_bar.hide()
            self.playlist_box.hide()
            
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
            speed_str = combo.get_model()[combo.get_active()][0]
            self.mpv_player.speed = float(speed_str.replace('x', ''))

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
            if self.mpv_player: self.mpv_player.seek(-5, 'relative+exact')
            return True
        elif keyname == 'Right':
            if self.mpv_player: self.mpv_player.seek(5, 'relative+exact')
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

    def on_delete_event(self, widget, event):
        if self.mpv_player:
            try: self.mpv_player.terminate()
            except: pass
        self.quit()
        return False

if __name__ == '__main__':
    app = VideoPlayer()
    sys.exit(app.run(sys.argv))
