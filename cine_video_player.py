#!/usr/bin/env python3
"""
Linux Video Player - 基于 python-mpv 和 GTK3 的现代视频播放器
重构与修复版
"""

import os
# 强制使用 X11 后端，因为基于 XID 的嵌入方式在 Wayland 下会崩溃
os.environ["GDK_BACKEND"] = "x11"

import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, Gdk, GLib

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
        self.current_file = None
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
        self.loop_button = None
        self.speed_combo = None
        self.fullscreen_btn = None
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
        
        # 必须先 show_all 才能获取底层窗口 XID
        self.window.show_all()

    def setup_style(self):
        screen = Gdk.Screen.get_default()
        provider = Gtk.CssProvider()
        # 你的原始 CSS 样式完全保留
        css = """
            * {
                background-color: #1a1a2e;
                color: #eaeaea;
                font-family: 'Segoe UI', 'Roboto', sans-serif;
                font-size: 13px;
            }
            window { background-color: #0f0f1a; }
            #main-box { background-color: #0f0f1a; }
            #video-area { background-color: #000000; }
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
            button:hover { background-color: rgba(93, 92, 222, 0.3); }
            button:active { background-color: rgba(93, 92, 222, 0.5); }
            #play-btn { padding: 6px 14px; }
            #open-btn {
                background-color: rgba(93, 92, 222, 0.2);
                border: 1px solid #5d5cde;
                border-radius: 4px;
                padding: 6px 16px;
            }
            #open-btn:hover { background-color: rgba(93, 92, 222, 0.4); }
            scale { background-color: transparent; }
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
            scale slider:hover { background-color: #5d5cde; }
            #progress-scale trough { min-height: 5px; }
            #volume-scale trough { min-width: 80px; }
            combobox {
                background-color: #2d2d44;
                border: 1px solid #3d3d54;
                border-radius: 4px;
                padding: 4px 8px;
                color: #eaeaea;
            }
            combobox:hover { border-color: #5d5cde; }
            label { color: #b8b8cc; font-size: 12px; }
            #time-label {
                color: #eaeaea;
                font-family: 'Consolas', 'Monaco', monospace;
                font-size: 12px;
                min-width: 100px;
            }
            #header-bar {
                background-color: rgba(15, 15, 26, 0.9);
                border-bottom: 1px solid #16213e;
                padding: 4px 12px;
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
        self.header_bar.set_title("Cine")
        self.header_bar.set_subtitle("Video Player")

        self.open_btn = Gtk.Button.new_with_label("Open")
        self.open_btn.set_name("open-btn")
        self.header_bar.pack_start(self.open_btn)

        self.window.set_titlebar(self.header_bar)

        # Video Area
        self.drawing_area = Gtk.DrawingArea()
        self.drawing_area.set_name("video-area")
        self.drawing_area.set_hexpand(True)
        self.drawing_area.set_vexpand(True)
        self.drawing_area.set_can_focus(True)
        main_box.pack_start(self.drawing_area, True, True, 0)

        # Controls Overlays
        controls_overlay = Gtk.Overlay()
        main_box.pack_start(controls_overlay, False, False, 0)

        self.controls_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self.controls_box.set_name("controls-box")
        self.controls_box.set_margin_top(8)
        self.controls_box.set_margin_bottom(8)
        self.controls_box.set_margin_start(12)
        self.controls_box.set_margin_end(12)
        controls_overlay.add(self.controls_box)

        # Progress Bar
        self.progress_scale = Gtk.Scale(orientation=Gtk.Orientation.HORIZONTAL)
        self.progress_scale.set_name("progress-scale")
        self.progress_scale.set_draw_value(False)
        self.progress_scale.set_range(0, 100)
        self.progress_scale.set_value(0)
        self.controls_box.pack_start(self.progress_scale, False, False, 0)

        # Buttons Row
        buttons_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self.controls_box.pack_start(buttons_row, False, False, 0)

        # Left Controls
        left_controls = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        buttons_row.pack_start(left_controls, False, False, 0)

        self.play_button = Gtk.Button()
        self.play_button.add(Gtk.Image.new_from_icon_name("media-playback-start-symbolic", Gtk.IconSize.BUTTON))
        self.play_button.set_name("play-btn")
        left_controls.pack_start(self.play_button, False, False, 0)

        self.volume_label = Gtk.Button()
        self.volume_label.add(Gtk.Image.new_from_icon_name("audio-volume-high-symbolic", Gtk.IconSize.BUTTON))
        left_controls.pack_start(self.volume_label, False, False, 0)

        self.volume_scale = Gtk.Scale(orientation=Gtk.Orientation.HORIZONTAL)
        self.volume_scale.set_name("volume-scale")
        self.volume_scale.set_draw_value(False)
        self.volume_scale.set_range(0, 100)
        self.volume_scale.set_value(100)
        self.volume_scale.set_size_request(100, -1)
        left_controls.pack_start(self.volume_scale, False, False, 0)

        # Center Time
        center_info = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        center_info.set_halign(Gtk.Align.CENTER)
        buttons_row.pack_start(center_info, True, True, 0)

        self.time_label = Gtk.Label(label="0:00 / 0:00")
        self.time_label.set_name("time-label")
        center_info.pack_start(self.time_label, False, False, 0)

        # Right Controls
        right_controls = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        buttons_row.pack_end(right_controls, False, False, 0)

        speed_store = Gtk.ListStore(str)
        for s in ["0.5x", "1.0x", "1.25x", "1.5x", "2.0x"]:
            speed_store.append([s])
        self.speed_combo = Gtk.ComboBox.new_with_model(speed_store)
        renderer = Gtk.CellRendererText()
        self.speed_combo.pack_start(renderer, True)
        self.speed_combo.add_attribute(renderer, "text", 0)
        self.speed_combo.set_active(1) # Default 1.0x
        right_controls.pack_start(self.speed_combo, False, False, 0)

        self.loop_button = Gtk.Button()
        self.loop_button.add(Gtk.Image.new_from_icon_name("media-playlist-repeat-symbolic", Gtk.IconSize.BUTTON))
        right_controls.pack_start(self.loop_button, False, False, 0)

        self.fullscreen_btn = Gtk.Button()
        self.fullscreen_btn.add(Gtk.Image.new_from_icon_name("view-fullscreen-symbolic", Gtk.IconSize.BUTTON))
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
        self.play_button.connect("clicked", self.toggle_play_pause)
        self.fullscreen_btn.connect("clicked", self.toggle_fullscreen)
        self.loop_button.connect("clicked", self.toggle_loop)

        self.progress_scale.connect("button-press-event", self.on_progress_press)
        self.progress_scale.connect("button-release-event", self.on_progress_release)
        self.progress_scale.connect("value-changed", self.on_progress_changed)

        self.volume_scale.connect("value-changed", self.on_volume_changed)
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

        except Exception as e:
            print(f"MPV 初始化失败: {e}")
            self.show_error_dialog("播放器核心初始化失败，请确保系统已安装 libmpv。")

    def on_draw(self, widget, cr):
        # 【优化】如果视频正在播放，不要用黑色覆盖，让 MPV 渲染
        if self.current_file:
            return True 
            
        width = widget.get_allocated_width()
        height = widget.get_allocated_height()
        cr.set_source_rgb(0.06, 0.06, 0.1)
        cr.rectangle(0, 0, width, height)
        cr.fill()

        cr.set_source_rgba(0.9, 0.9, 0.9, 0.6)
        cr.select_font_face("Sans", Gtk.FontStyle.NORMAL, Gtk.Weight.NORMAL)
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
        else:
            self.window.fullscreen()
            self.controls_box.hide()
            self.header_bar.hide()
            
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
            
            icon_name = "audio-volume-muted-symbolic" if vol == 0 else \
                        "audio-volume-low-symbolic" if vol < 33 else \
                        "audio-volume-medium-symbolic" if vol < 66 else "audio-volume-high-symbolic"
            for child in self.volume_label.get_children():
                self.volume_label.remove(child)
            self.volume_label.add(Gtk.Image.new_from_icon_name(icon_name, Gtk.IconSize.BUTTON))
            self.volume_label.show_all()

    def on_speed_changed(self, combo):
        if self.mpv_player:
            speed_str = combo.get_model()[combo.get_active()][0]
            self.mpv_player.speed = float(speed_str.replace('x', ''))

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