#!/usr/bin/env python3
"""
Linux Video Player - 基于 python-mpv 和 GTK3 的现代视频播放器
支持: 播放控制、倍速播放、视频比例调整、全屏模式、键盘快捷键
"""

import os
# 强制使用 X11 后端，因为 python-mpv 嵌入 GTK3 强依赖于 X11 的 XID，Wayland下会导致直接崩溃
os.environ["GDK_BACKEND"] = "x11"

import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, Gdk, GLib, GObject, Gio
import cairo

import mpv
import sys
import threading

class VideoPlayer(Gtk.Application):
    def __init__(self):
        super().__init__(application_id='com.example.videoplayer',
                         flags=Gio.ApplicationFlags.FLAGS_NONE)
        
        self.mpv_player = None
        self.is_playing = False
        self.is_fullscreen = False
        self.is_seeking = False
        self.current_file = None
        self.update_timer = None
        
        self.window = None
        self.header_bar = None # 记录 header_bar 以便全屏时隐藏
        self.drawing_area = None
        self.controls_box = None
        self.progress_scale = None
        self.volume_scale = None
        self.time_label = None
        self.play_button = None
        self.stop_button = None
        self.speed_combo = None
        self.aspect_combo = None
        self.fullscreen_btn = None
        self.open_btn = None
        self.volume_label = None

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
        self.apply_css()
        
        # 必须先 show_all 才能在后续触发 realize 信号并获取正常的系统底层窗口 ID
        self.window.show_all()

    def setup_style(self):
        screen = Gdk.Screen.get_default()
        provider = Gtk.CssProvider()
        # 这里的 CSS 完全保留你原始的样式
        css = """
            * {
                background-color: #1a1a2e;
                color: #eaeaea;
                font-family: 'Segoe UI', 'Roboto', sans-serif;
                font-size: 13px;
            }
            
            window {
                background-color: #0f0f1a;
            }
            
            #main-box {
                background-color: #0f0f1a;
            }
            
            #video-area {
                background-color: #000000;
            }
            
            #controls-box {
                background-color: rgba(26, 26, 46, 0.95);
                border-top: 1px solid #16213e;
                padding: 8px;
            }
            
            button {
                background-image: none;
                background-color: transparent;
                border: none;
                border-radius: 4px;
                padding: 6px 10px;
                min-width: 32px;
                min-height: 32px;
                color: #eaeaea;
                transition: all 200ms ease;
            }
            
            button:hover {
                background-color: rgba(93, 92, 222, 0.3);
            }
            
            button:active {
                background-color: rgba(93, 92, 222, 0.5);
            }
            
            #play-btn {
                padding: 6px 14px;
            }
            
            #open-btn {
                background-color: rgba(93, 92, 222, 0.2);
                border: 1px solid #5d5cde;
                border-radius: 4px;
                padding: 6px 16px;
            }
            
            #open-btn:hover {
                background-color: rgba(93, 92, 222, 0.4);
            }
            
            scale {
                background-color: transparent;
            }
            
            scale trough {
                min-height: 5px;
                border-radius: 3px;
                background-color: #2d2d44;
            }
            
            scale trough highlight {
                min-height: 5px;
                border-radius: 3px;
                background-color: linear-gradient(to right, #5d5cde, #7b68ee);
            }
            
            scale slider {
                background-color: #ffffff;
                border: 2px solid #5d5cde;
                border-radius: 50%;
                margin: -6px;
            }
            
            scale slider:hover {
                background-color: #5d5cde;
            }
            
            #progress-scale trough {
                min-height: 5px;
            }
            
            #volume-scale trough {
                min-width: 80px;
            }
            
            combobox {
                background-color: #2d2d44;
                border: 1px solid #3d3d54;
                border-radius: 4px;
                padding: 4px 8px;
                color: #eaeaea;
            }
            
            combobox:hover {
                border-color: #5d5cde;
            }
            
            label {
                color: #b8b8cc;
                font-size: 12px;
            }
            
            #time-label {
                color: #eaeaea;
                font-family: 'Consolas', 'Monaco', monospace;
                font-size: 12px;
                min-width: 100px;
            }
            
            #title-label {
                color: #eaeaea;
                font-size: 13px;
                font-weight: 500;
            }
            
            #header-bar {
                background-color: rgba(15, 15, 26, 0.9);
                border-bottom: 1px solid #16213e;
                padding: 4px 12px;
            }
            
            separator {
                background-color: #2d2d44;
            }
            
            .fullscreen-overlay {
                opacity: 0;
                transition: opacity 300ms ease;
            }
            
            .fullscreen-overlay.visible {
                opacity: 1;
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

        self.header_bar = Gtk.HeaderBar()
        self.header_bar.set_name("header-bar")
        self.header_bar.set_show_close_button(True)
        self.header_bar.set_title("Cine")
        self.header_bar.set_subtitle("Video Player")

        self.open_btn = Gtk.Button.new_with_label("Open")
        self.open_btn.set_name("open-btn")
        self.header_bar.pack_start(self.open_btn)

        menu_btn = Gtk.Button()
        menu_icon = Gtk.Image.new_from_icon_name("view-list-symbolic", Gtk.IconSize.BUTTON)
        menu_btn.add(menu_icon)
        self.header_bar.pack_end(menu_btn)

        self.window.set_titlebar(self.header_bar)

        video_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        video_box.set_homogeneous(True)
        video_box.expand = True
        main_box.pack_start(video_box, True, True, 0)

        self.drawing_area = Gtk.DrawingArea()
        self.drawing_area.set_name("video-area")
        self.drawing_area.set_hexpand(True)
        self.drawing_area.set_vexpand(True)
        self.drawing_area.set_can_focus(True) # 让画布能够捕获键盘焦点
        video_box.pack_start(self.drawing_area, True, True, 0)

        controls_overlay = Gtk.Overlay()
        main_box.pack_start(controls_overlay, False, False, 0)

        self.controls_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self.controls_box.set_name("controls-box")
        self.controls_box.set_margin_top(8)
        self.controls_box.set_margin_bottom(8)
        self.controls_box.set_margin_start(12)
        self.controls_box.set_margin_end(12)
        controls_overlay.add(self.controls_box)

        progress_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.controls_box.pack_start(progress_box, False, False, 0)

        self.progress_scale = Gtk.Scale(orientation=Gtk.Orientation.HORIZONTAL)
        self.progress_scale.set_name("progress-scale")
        self.progress_scale.set_draw_value(False)
        self.progress_scale.set_hexpand(True)
        self.progress_scale.set_range(0, 100)
        self.progress_scale.set_value(0)
        progress_box.pack_start(self.progress_scale, True, True, 0)

        buttons_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self.controls_box.pack_start(buttons_row, False, False, 0)

        left_controls = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        buttons_row.pack_start(left_controls, False, False, 0)

        self.play_button = Gtk.Button()
        play_icon = Gtk.Image.new_from_icon_name("media-playback-start-symbolic", Gtk.IconSize.BUTTON)
        self.play_button.add(play_icon)
        self.play_button.set_name("play-btn")
        left_controls.pack_start(self.play_button, False, False, 0)

        stop_btn = Gtk.Button()
        stop_icon = Gtk.Image.new_from_icon_name("media-playback-stop-symbolic", Gtk.IconSize.BUTTON)
        stop_btn.add(stop_icon)
        left_controls.pack_start(stop_btn, False, False, 0)

        prev_btn = Gtk.Button()
        prev_icon = Gtk.Image.new_from_icon_name("media-skip-backward-symbolic", Gtk.IconSize.BUTTON)
        prev_btn.add(prev_icon)
        left_controls.pack_start(prev_btn, False, False, 0)

        next_btn = Gtk.Button()
        next_icon = Gtk.Image.new_from_icon_name("media-skip-forward-symbolic", Gtk.IconSize.BUTTON)
        next_btn.add(next_icon)
        left_controls.pack_start(next_btn, False, False, 0)

        volume_btn = Gtk.Button()
        volume_icon = Gtk.Image.new_from_icon_name("audio-volume-high-symbolic", Gtk.IconSize.BUTTON)
        volume_btn.add(volume_icon)
        left_controls.pack_start(volume_btn, False, False, 0)

        self.volume_scale = Gtk.Scale(orientation=Gtk.Orientation.HORIZONTAL)
        self.volume_scale.set_name("volume-scale")
        self.volume_scale.set_draw_value(False)
        self.volume_scale.set_range(0, 100)
        self.volume_scale.set_value(100)
        self.volume_scale.set_size_request(100, -1)
        left_controls.pack_start(self.volume_scale, False, False, 0)

        center_info = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        center_info.set_halign(Gtk.Align.CENTER)
        center_info.set_hexpand(True)
        buttons_row.pack_start(center_info, True, True, 0)

        self.time_label = Gtk.Label(label="0:00 / 0:00")
        self.time_label.set_name("time-label")
        self.time_label.set_xalign(0.5)
        center_info.pack_start(self.time_label, False, False, 0)

        right_controls = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        buttons_row.pack_end(right_controls, False, False, 0)

        speed_store = Gtk.ListStore(str)
        speeds = ["0.5x", "0.75x", "1.0x", "1.25x", "1.5x", "2.0x"]
        for s in speeds:
            speed_store.append([s])

        self.speed_combo = Gtk.ComboBox.new_with_model(speed_store)
        renderer_text = Gtk.CellRendererText()
        self.speed_combo.pack_start(renderer_text, True)
        self.speed_combo.add_attribute(renderer_text, "text", 0)
        self.speed_combo.set_active(2)
        right_controls.pack_start(self.speed_combo, False, False, 0)

        aspect_btn = Gtk.Button()
        aspect_icon = Gtk.Image.new_from_icon_name("view-fullscreen-symbolic", Gtk.IconSize.BUTTON)
        aspect_btn.add(aspect_icon)
        right_controls.pack_start(aspect_btn, False, False, 0)

        loop_btn = Gtk.Button()
        loop_icon = Gtk.Image.new_from_icon_name("media-playlist-repeat-symbolic", Gtk.IconSize.BUTTON)
        loop_btn.add(loop_icon)
        right_controls.pack_start(loop_btn, False, False, 0)

        settings_btn = Gtk.Button()
        settings_icon = Gtk.Image.new_from_icon_name("emblem-system-symbolic", Gtk.IconSize.BUTTON)
        settings_btn.add(settings_icon)
        right_controls.pack_start(settings_btn, False, False, 0)

        self.fullscreen_btn = Gtk.Button()
        fullscreen_icon = Gtk.Image.new_from_icon_name("view-fullscreen-symbolic", Gtk.IconSize.BUTTON)
        self.fullscreen_btn.add(fullscreen_icon)
        right_controls.pack_start(self.fullscreen_btn, False, False, 0)

        self.stop_button = stop_btn
        self.volume_label = volume_btn

    def connect_signals(self):
        self.window.connect("delete-event", self.on_delete_event)
        self.window.connect("key-press-event", self.on_key_press)
        
        # 将 setup_mpv 的触发时机改到窗口 realize 之后，避免提早调用导致 XID 异常报错崩溃
        self.drawing_area.connect("realize", self.on_drawing_area_realize)
        self.drawing_area.connect("draw", self.on_draw)
        self.drawing_area.connect("button-press-event", self.on_video_click)
        self.drawing_area.add_events(Gdk.EventMask.BUTTON_PRESS_MASK)

        self.open_btn.connect("clicked", self.on_open_file)
        self.play_button.connect("clicked", self.toggle_play_pause)
        self.stop_button.connect("clicked", self.on_stop)
        self.fullscreen_btn.connect("clicked", self.toggle_fullscreen)

        self.progress_scale.connect("button-press-event", self.on_progress_press)
        self.progress_scale.connect("button-release-event", self.on_progress_release)
        self.progress_scale.connect("value-changed", self.on_progress_changed)

        self.volume_scale.connect("value-changed", self.on_volume_changed)
        self.speed_combo.connect("changed", self.on_speed_changed)

    def on_drawing_area_realize(self, widget):
        self.setup_mpv()

    def setup_mpv(self):
        try:
            window = self.drawing_area.get_window()
            if not window:
                return
            xid = window.get_xid()
            
            self.mpv_player = mpv.MPV(
                wid=str(xid),
                vo='x11', # 强制使用 x11 输出避免报错
                ytdl=False,
                osc=False,
                input_default_bindings=False,
                input_vo_keyboard=False,
                keep_open='no',
                cursor_autohide=1000,
                force_window='immediate',
                hwdec='auto-safe'
            )
            print("MPV 初始化成功")
            
            # 属性观察器在 mpv 初始化完成后挂载
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

        except Exception as e:
            print(f"MPV 初始化失败: {e}")
            self.mpv_player = mpv.MPV(
                ytdl=False,
                osc=False,
                input_default_bindings=False,
                input_vo_keyboard=False,
                keep_open='no',
                cursor_autohide=1000
            )

    def on_draw(self, widget, cr):
        if not self.current_file or not self.is_playing:
            width = widget.get_allocated_width()
            height = widget.get_allocated_height()
            
            cr.set_source_rgb(0.06, 0.06, 0.1)
            cr.rectangle(0, 0, width, height)
            cr.fill()

            if not self.current_file:
                cr.set_source_rgba(0.9, 0.9, 0.9, 0.6)
                cr.select_font_face("Sans", Gtk.FontStyle.NORMAL, Gtk.Weight.NORMAL)
                cr.set_font_size(18)
                
                text = "打开视频文件开始播放"
                text_ext = cr.text_extents(text)
                x = (width - text_ext.width) / 2
                y = (height + text_ext.height) / 2
                cr.move_to(x, y)
                cr.show_text(text)

        return False

    def on_video_click(self, widget, event):
        if event.button == 1 and self.current_file:
            # 增加双击全屏特性，防止全屏后控制栏隐藏导致无法退出
            if event.type == Gdk.EventType._2BUTTON_PRESS:
                self.toggle_fullscreen()
            elif event.type == Gdk.EventType.BUTTON_PRESS:
                self.toggle_play_pause(None)

    def on_open_file(self, button):
        dialog = Gtk.FileChooserDialog(
            title="选择视频文件",
            parent=self.window,
            action=Gtk.FileChooserAction.OPEN
        )
        dialog.add_buttons(
            "取消", Gtk.ResponseType.CANCEL,
            "打开", Gtk.ResponseType.ACCEPT
        )
        
        filter_video = Gtk.FileFilter()
        filter_video.set_name("视频文件")
        filter_video.add_mime_type("video/*")
        for ext in ["*.mp4", "*.mkv", "*.avi", "*.webm", "*.mov", "*.flv", "*.wmv"]:
            filter_video.add_pattern(ext)
        dialog.add_filter(filter_video)
        
        filter_all = Gtk.FileFilter()
        filter_all.set_name("所有文件")
        filter_all.add_pattern("*")
        dialog.add_filter(filter_all)

        response = dialog.run()
        if response == Gtk.ResponseType.ACCEPT:
            file_path = dialog.get_filename()
            dialog.destroy()
            self.load_video(file_path)
        else:
            dialog.destroy()

    def load_video(self, file_path):
        try:
            self.current_file = file_path
            
            if self.mpv_player:
                self.mpv_player.play(file_path)
                self.is_playing = True
                self.update_play_button()
                self.start_progress_update()
                
                filename = os.path.basename(file_path)
                self.header_bar.set_subtitle(filename)
                
                self.drawing_area.queue_draw()
                
                print(f"正在播放: {file_path}")
                
        except Exception as e:
            print(f"加载视频失败: {e}")
            self.show_error_dialog(f"无法加载视频文件\n\n{str(e)}")

    def toggle_play_pause(self, button):
        if not self.current_file:
            return
            
        if self.mpv_player:
            if self.is_playing:
                self.mpv_player.pause = True
                self.is_playing = False
            else:
                self.mpv_player.pause = False
                self.is_playing = True
            
            self.update_play_button()

    def update_play_button(self):
        child = self.play_button.get_child()
        if child:
            self.play_button.remove(child)
        
        if self.is_playing:
            icon = Gtk.Image.new_from_icon_name("media-playback-pause-symbolic", Gtk.IconSize.BUTTON)
        else:
            icon = Gtk.Image.new_from_icon_name("media-playback-start-symbolic", Gtk.IconSize.BUTTON)
        
        self.play_button.add(icon)
        self.play_button.show_all()

    def on_stop(self, button):
        if self.mpv_player and self.current_file:
            self.mpv_player.pause = True
            self.mpv_player.seek(0, 'absolute+exact')
            self.is_playing = False
            self.update_play_button()
            self.progress_scale.set_value(0)
            self.update_time_display(0, self.get_duration())

    def toggle_fullscreen(self, button=None):
        if self.is_fullscreen:
            self.window.unfullscreen()
            self.is_fullscreen = False
            self.controls_box.show()
            self.header_bar.show()
        else:
            self.window.fullscreen()
            self.is_fullscreen = True
            # 进入全屏时完美隐藏控制栏，保持纯净视频画面
            self.controls_box.hide()
            self.header_bar.hide()
            # 【核心修复】：重新捕获键盘焦点，防止按键交互失效
            self.drawing_area.grab_focus()
        
        self.update_fullscreen_button()

    def update_fullscreen_button(self):
        child = self.fullscreen_btn.get_child()
        if child:
            self.fullscreen_btn.remove(child)
        
        if self.is_fullscreen:
            icon = Gtk.Image.new_from_icon_name("view-restore-symbolic", Gtk.IconSize.BUTTON)
        else:
            icon = Gtk.Image.new_from_icon_name("view-fullscreen-symbolic", Gtk.IconSize.BUTTON)
        
        self.fullscreen_btn.add(icon)
        self.fullscreen_btn.show_all()

    def on_progress_press(self, scale, event):
        self.is_seeking = True

    def on_progress_release(self, scale, event):
        self.is_seeking = False
        value = scale.get_value()
        self.seek_to_position(value)

    def on_progress_changed(self, scale):
        if self.is_seeking:
            value = scale.get_value()
            duration = self.get_duration()
            if duration > 0:
                current_time = (value / 100) * duration
                self.update_time_display(current_time, duration)

    def seek_to_position(self, percentage):
        if self.mpv_player and self.current_file:
            duration = self.get_duration()
            if duration > 0:
                target_time = (percentage / 100) * duration
                try:
                    self.mpv_player.seek(target_time, 'absolute+exact')
                    print(f"跳转到: {target_time:.1f}秒 ({percentage:.1f}%)")
                except Exception as e:
                    print(f"跳转失败: {e}")

    def on_volume_changed(self, scale):
        volume = int(scale.get_value())
        if self.mpv_player:
            try:
                self.mpv_player.volume = volume
                self.update_volume_icon(volume)
            except Exception as e:
                print(f"设置音量失败: {e}")

    def update_volume_icon(self, volume):
        child = self.volume_label.get_child()
        if child:
            self.volume_label.remove(child)
        
        if volume == 0:
            icon_name = "audio-volume-muted-symbolic"
        elif volume < 33:
            icon_name = "audio-volume-low-symbolic"
        elif volume < 66:
            icon_name = "audio-volume-medium-symbolic"
        else:
            icon_name = "audio-volume-high-symbolic"
        
        icon = Gtk.Image.new_from_icon_name(icon_name, Gtk.IconSize.BUTTON)
        self.volume_label.add(icon)
        self.volume_label.show_all()

    def on_speed_changed(self, combo):
        model = combo.get_model()
        active = combo.get_active()
        if active >= 0:
            speed_str = model[active][0]
            speed = float(speed_str.replace('x', ''))
            if self.mpv_player:
                try:
                    self.mpv_player.speed = speed
                    print(f"播放速度: {speed}x")
                except Exception as e:
                    print(f"设置速度失败: {e}")

    def get_duration(self):
        try:
            if self.mpv_player:
                return self.mpv_player.duration or 0
        except:
            pass
        return 0

    def get_current_time(self):
        try:
            if self.mpv_player:
                return self.mpv_player.time_pos or 0
        except:
            pass
        return 0

    def update_progress(self, time_pos):
        if not self.is_seeking and time_pos is not None:
            duration = self.get_duration()
            if duration > 0:
                percentage = (time_pos / duration) * 100
                self.progress_scale.set_value(percentage)
                self.update_time_display(time_pos, duration)

    def update_duration(self, duration):
        if duration > 0:
            self.progress_scale.set_range(0, 100)
            current_time = self.get_current_time()
            self.update_time_display(current_time, duration)

    def update_time_display(self, current, duration):
        current_str = self.format_time(current)
        duration_str = self.format_time(duration)
        self.time_label.set_text(f"{current_str} / {duration_str}")

    def format_time(self, seconds):
        if seconds is None or seconds < 0:
            return "0:00"
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        if hours > 0:
            return f"{hours}:{minutes:02d}:{secs:02d}"
        return f"{minutes}:{secs:02d}"

    def start_progress_update(self):
        if self.update_timer:
            GLib.source_remove(self.update_timer)
        self.update_timer = GLib.timeout_add(1000, self.update_progress_tick)

    def update_progress_tick(self):
        if self.is_playing and self.mpv_player:
            try:
                time_pos = self.mpv_player.time_pos
                if time_pos is not None:
                    duration = self.get_duration()
                    if duration > 0:
                        percentage = (time_pos / duration) * 100
                        self.progress_scale.set_value(percentage)
                        self.update_time_display(time_pos, duration)
            except:
                pass
        return self.is_playing

    def on_eof_reached(self):
        self.is_playing = False
        self.update_play_button()
        if self.update_timer:
            GLib.source_remove(self.update_timer)
            self.update_timer = None

    def on_key_press(self, widget, event):
        keyval = event.keyval
        keyname = Gdk.keyval_name(keyval)
        
        if keyname == 'space':
            self.toggle_play_pause(None)
            return True
        elif keyname == 'F' or keyname == 'f':
            if not (event.state & Gdk.ModifierType.CONTROL_MASK):
                self.toggle_fullscreen()
                return True
        elif keyname == 'Left':
            self.seek_relative(-5)
            return True
        elif keyname == 'Right':
            self.seek_relative(5)
            return True
        elif keyname == 'Up':
            self.adjust_volume(10)
            return True
        elif keyname == 'Down':
            self.adjust_volume(-10)
            return True
        elif keyname == 'Escape' and self.is_fullscreen:
            self.toggle_fullscreen()
            return True
        
        return False

    def seek_relative(self, seconds):
        if self.mpv_player and self.current_file:
            try:
                current = self.get_current_time()
                new_time = max(0, current + seconds)
                self.mpv_player.seek(new_time, 'absolute+exact')
                print(f"{'快进' if seconds > 0 else '快退'} {abs(seconds)}秒")
            except Exception as e:
                print(f"快进/快退失败: {e}")

    def adjust_volume(self, delta):
        current_vol = int(self.volume_scale.get_value())
        new_vol = max(0, min(100, current_vol + delta))
        self.volume_scale.set_value(new_vol)
        print(f"音量: {new_vol}%")

    def show_error_dialog(self, message):
        dialog = Gtk.MessageDialog(
            parent=self.window,
            modal=True,
            message_type=Gtk.MessageType.ERROR,
            buttons=Gtk.ButtonsType.OK,
            title="错误"
        )
        dialog.set_markup(message)
        dialog.run()
        dialog.destroy()

    def apply_css(self):
        pass

    def on_delete_event(self, widget, event):
        self.cleanup()
        return False

    def cleanup(self):
        if self.update_timer:
            GLib.source_remove(self.update_timer)
            self.update_timer = None
        
        if self.mpv_player:
            try:
                self.mpv_player.terminate()
            except:
                pass
            self.mpv_player = None
        
        self.quit()

def main():
    app = VideoPlayer()
    exit_status = app.run(sys.argv)
    sys.exit(exit_status)

if __name__ == '__main__':
    main()