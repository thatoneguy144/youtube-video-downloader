# Created by thatoneguy
import tkinter as tk, pytubefix, os, urllib.request, io, threading, time, ffmpeg, subprocess, re
from tkinter import messagebox, ttk
from pytubefix import YouTube
from PIL import Image, ImageTk
from pathlib import Path
from proglog import ProgressBarLogger
from ffmpeg_progress_yield import FfmpegProgress

find_vid_count = 0
yt = None

video_download_start = None

class MoviePyTkLogger(ProgressBarLogger):
    def __init__(self, progress_bar, root, status_label):
        super().__init__()
        self.progress_bar = progress_bar
        self.status_label = status_label
        self.root = root

    def bars_callback(self, bar, attr, value, old_value=None):
        total = self.bars[bar]['total']
        percentage = (value / total) * 100

        if bar == "chunk":
            message = f"Processing Audio... {round(percentage, 2)}% ({round(value, 2)}/{round(total, 0)})"
        elif bar == "t":
            message = f"Processing Video... {round(percentage, 2)}% ({round(value, 2)}/{round(total, 0)})"
        else:
            message = f"Combining Audio with Video... {round(percentage, 2)}% ({round(value, 2)}/{round(total, 0)})"
        
        self.root.after(0, self.update_ui, percentage, message)

    def update_ui(self, percentage, message):
        self.status_label.config(text=message)
        self.progress_bar['value'] = percentage
        self.root.update_idletasks()


def download_audio():
    create_progress_items()
    global progress_bar, status_label

    dl_path = str(Path.home() / "Downloads")
    
    url = url_input.get()
    yt = YouTube(url, on_progress_callback=on_progress_audio)
    audio_stream = yt.streams.filter(only_audio=True).order_by('abr').desc().first()
    out_file = audio_stream.download(output_path=dl_path)
    
    base, ext = os.path.splitext(out_file)
    new_file = base + '.mp3'
    try: 
        os.rename(out_file, new_file)
    except FileExistsError:
        messagebox.showerror(title="File already exists", message=f"A file with the path {new_file} already exists!")
        return
    
    messagebox.showinfo(title="Successfully Downloaded Audio", message=f"Audio downloaded to: {new_file}")
    time.sleep(3)
    progress_bar.destroy()
    status_label.destroy()

def get_resolution_input(options: list) -> str:
    dialog = tk.Toplevel(background='black')
    dialog.title("Select a Resolution")

    screen_width = dialog.winfo_screenwidth()
    screen_height = dialog.winfo_screenheight()
    width = 300
    height = 150

    x = int((screen_width // 2) - (width // 2))
    y = int((screen_height // 2.25) - (height // 2))

    dialog.geometry(f"{width}x{height}+{x}+{y}")
    
    selected_value = tk.StringVar(dialog, options[0])
    
    tk.Label(dialog, text="Choose a video resolution:").pack(pady=10)
    
    combo = tk.OptionMenu(dialog, selected_value, *options)
    combo.pack(pady=5, expand=True)
    
    def on_confirm():
        global res
        res = selected_value.get()
        dialog.destroy()

    tk.Button(dialog, text="OK", command=on_confirm).pack(pady=10)
    
    dialog.grab_set()
    dialog.wait_window()
    return res

def download_task():
    try:
        global progress_bar, status_label, video_download_start
        
        url = url_input.get()
        video_download_start = time.time()
        yt = YouTube(url, on_progress_callback=on_progress_video)

        folder_path = Path.home() / "Downloads"

        safe_title = re.sub(r'[<>:"/\\|?*.]', '', yt.title)
        final_output_path = (folder_path / f'{safe_title}.mp4').as_posix()

        video_stream = yt.streams.filter(only_video=True, file_extension='mp4', adaptive=True).order_by('resolution').desc()
        res = get_resolution_input([stream.resolution for index, stream in enumerate(video_stream) if stream.resolution != video_stream[index-1].resolution])
        video_stream = video_stream.filter(res=res).first()
        video_file = video_stream.download(filename=f"t{yt.title}_video_TEMP.mp4")
        

        audio_stream = yt.streams.filter(only_audio=True).order_by('abr').desc().first()
        audio_file = audio_stream.download(filename=f"{yt.title}_audio_TEMP.mp4")

        try: 
            video_input = input(video_file)
            audio_input = input(audio_file)

            folder_path = Path.home() / "Downloads"

            safe_title = re.sub(r'[<>:"/\\|?*.]', '', yt.title)
            final_output_path = str(folder_path / f'{safe_title}_{video_stream.resolution}.mp4')

            stream = ffmpeg.output(
                video_input['v'], 
                audio_input['a'], 
                final_output_path, 
                vcodec='copy', 
                acodec='aac',
                strict='experimental'
            )


            cmd = stream.get_args()
            full_cmd = ["ffmpeg"] + cmd
            start_time = time.time()

            with FfmpegProgress(full_cmd) as ff:
                for progress in ff.run_command_with_progress(popen_kwargs={'creationflags': subprocess.CREATE_NO_WINDOW}):
                    if progress > 0:
                        elapsed = time.time() - start_time
                        total_estimated_time = elapsed / (progress / 100)
                        seconds_left = total_estimated_time - elapsed
                        
                        status_label.config(text=f"Finalizing... {progress:.1f}% | {int(seconds_left)}s left")

                    progress_bar["value"] = progress
                    root.update_idletasks()

            os.remove(audio_file)
            os.remove(video_file)
            messagebox.showinfo(title="Successfully Downloaded Video", message=f"Video downloaded to: {final_output_path}")
        except Exception as e:
            messagebox.showerror(title="Error", message=f"Error: {e}")

        time.sleep(3)
        progress_bar.destroy()
        status_label.destroy()

    except Exception as e:
        messagebox.showerror(title="Error", message=f"Error: {e}")

def on_progress_video(stream, chunk, bytes_remaining):
    media_type = "Video"
    if stream.audio_codec: 
        media_type = "Audio"
    total_size = stream.filesize
    bytes_downloaded = total_size - bytes_remaining
    percentage = (bytes_downloaded / total_size) * 100
    
    global progress_bar, status_label
    progress_bar['value'] = percentage

    elapsed = time.time() - video_download_start
    total_estimated_time = elapsed / (percentage / 100)
    seconds_left = total_estimated_time - elapsed
    seconds = int(seconds_left)
                        
    time_message = f'{seconds}s left'
    if seconds > 3600:
        hours = int(seconds / 3600)
        mintues = 0
        seconds = seconds % 3600
        if seconds > 60:
            minutes = int(seconds / 60)
            seconds = seconds % 60
        time_message = f'{hours}h {minutes}m {seconds}s left'
    elif seconds > 60:
        minutes = int(seconds / 60)
        seconds = seconds % 60
        time_message = f'{minutes}m {seconds}s left'

    message = f"Downloading {media_type}... {round(percentage, 2)}% ({bytes_downloaded}/{total_size}) \n{time_message}"
    status_label.config(text=message)
    root.update_idletasks()

def on_progress_audio(stream, chunk, bytes_remaining):
    total_size = stream.filesize
    bytes_downloaded = total_size - bytes_remaining
    percentage = (bytes_downloaded / total_size) * 100
    
    global progress_bar, status_label
    progress_bar['value'] = percentage

    message = f"Downloading audio... {round(percentage, 2)}% ({bytes_downloaded}/{total_size})"
    status_label.config(text=message)
    root.update_idletasks()

def create_progress_items():
    global progress_bar, status_label
    status_label = tk.Label(content_frame, justify='left', text='Nothing downloading', wraplength=300)
    status_label.pack(anchor='w', pady=5)

    progress_bar = ttk.Progressbar(content_frame, orient="horizontal", length=300, mode="determinate")
    progress_bar.pack(pady=0, anchor='w')

    progress_bar['value'] = 0

def download_video():
    create_progress_items()
    thread = threading.Thread(target=download_task, daemon=True)
    thread.start()


def find_vid():
    global find_vid_count
    url = url_input.get()

    try:
        global yt
        yt = YouTube(url)
    except pytubefix.exceptions.RegexMatchError:
        messagebox.showerror(title="Invalid URL", message="Unable to find the video, or you didn't provide a valid url")
        return

    if find_vid_count > 1:
        build_base_gui()
        title = yt.title
        tk.Label(content_frame, text=title, wraplength=300, justify='left').pack()
        display_thumbnail(yt.thumbnail_url)
        return
    
    title = yt.title
    tk.Label(content_frame, text=title, wraplength=300, justify='left').pack()
    find_vid_count = 2
    display_thumbnail(yt.thumbnail_url)

def display_thumbnail(url):
    with urllib.request.urlopen(url) as u:
        raw_data = u.read()
    
    img = Image.open(io.BytesIO(raw_data))
    img = img.resize((280, 180)) 
    tk_img = ImageTk.PhotoImage(img)
    
    label = tk.Label(content_frame, image=tk_img)
    label.image = tk_img 
    label.pack(pady=5)
    
    global height
    height += img.height
    root.geometry(f"{width}x{height}+{x}+{y}")
    height -= img.height

    build_download_buttons()

def build_base_gui():
    global url_input
    for widget in content_frame.winfo_children():
        widget.destroy()

    tk.Label(content_frame, text="Enter your discord url", justify='left').pack(anchor="w", padx=0)

    url_input = tk.Entry(content_frame, width=43)
    url_input.pack(anchor="w")

    find_vid_button = tk.Button(content_frame, text="Find Video", command=find_vid)
    find_vid_button.pack(pady=5, anchor="w")

def build_download_buttons():
    button_frame = tk.Frame(content_frame)
    button_frame.pack(pady=5, anchor='w')

    audio_download_button = tk.Button(button_frame, text="Download Audio", command=download_audio)
    audio_download_button.pack(side='left')

    video_download_button = tk.Button(button_frame, text="Download Video", command=download_video)
    video_download_button.pack(side='left', padx=5)

root = tk.Tk()
root.title("Youtube Video/Audio Downloader")
url_input = None

screen_width = root.winfo_screenwidth()
screen_height = root.winfo_screenheight()
width = 500
height = 230

x = int((screen_width // 2) - (width // 2))
y = int((screen_height // 2.25) - (height // 2))

root.geometry(f"{width}x{height}+{x}+{y}")
content_frame = tk.Frame(root)
content_frame.pack(expand=True)

build_base_gui()
root.mainloop()
