import os
import sys
import subprocess
import tkinter as tk
from tkinter import filedialog, messagebox, ttk, simpledialog
import logging
import threading
import zipfile
import uuid        # to create a unique file ID
import requests    # for cloud uploads/downloads

#########################
#   Logging Setup
#########################
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


class SmartCompressApp:
    def __init__(self, root):
        self.root = root
        self.root.title("UltraSmartCompressor — Local or Chunked Cloud Compression")
        self.root.geometry("1000x700")

        self.is_compressing = False

        # Create a progress bar + label
        self.progress_label = ttk.Label(self.root, text="No compression in progress")
        self.progress_label.pack(pady=(5, 0))

        self.progress_bar = ttk.Progressbar(self.root, orient=tk.HORIZONTAL, length=400, mode='determinate')
        self.progress_bar.pack(pady=5)

        self.setup_main_interface()

    #########################
    #   Interface Setup
    #########################
    def setup_main_interface(self):
        self.create_toolbar()
        self.create_tabbed_area()

    def create_toolbar(self):
        toolbar_frame = tk.Frame(self.root, bd=2, relief=tk.RAISED)
        toolbar_frame.pack(side=tk.TOP, fill=tk.X)

        add_button = tk.Button(toolbar_frame, text="Add Files", relief=tk.FLAT, command=self.add_files)
        add_button.pack(side=tk.LEFT, padx=2, pady=2)

        extract_button = tk.Button(toolbar_frame, text="Extract", relief=tk.FLAT, command=self.start_extraction)
        extract_button.pack(side=tk.LEFT, padx=2, pady=2)

    def create_tabbed_area(self):
        tab_control = ttk.Notebook(self.root)

        self.compress_tab = ttk.Frame(tab_control)
        tab_control.add(self.compress_tab, text='Compress')
        self.create_compress_tab(self.compress_tab)

        self.decompress_tab = ttk.Frame(tab_control)
        tab_control.add(self.decompress_tab, text='Decompress')
        self.create_decompress_tab(self.decompress_tab)

        tab_control.pack(expand=1, fill="both")

    def create_compress_tab(self, tab):
        ttk.Label(tab, text="Select files to compress:").pack(pady=5)
        self.compress_listbox = tk.Listbox(tab, selectmode=tk.MULTIPLE)
        self.compress_listbox.pack(padx=10, pady=10, fill=tk.BOTH, expand=True)

        ttk.Button(tab, text="Add Files", command=self.add_files).pack(side=tk.LEFT, padx=5)
        ttk.Button(tab, text="Compress", command=self.choose_compression_method).pack(side=tk.RIGHT, padx=5)

    def create_decompress_tab(self, tab):
        ttk.Label(tab, text="Select .zip files to decompress:").pack(pady=5)
        self.decompress_listbox = tk.Listbox(tab, selectmode=tk.MULTIPLE)
        self.decompress_listbox.pack(padx=10, pady=10, fill=tk.BOTH, expand=True)

        ttk.Button(tab, text="Add Files", command=self.add_files).pack(side=tk.LEFT, padx=5)
        ttk.Button(tab, text="Decompress", command=self.start_extraction).pack(side=tk.RIGHT, padx=5)

    #########################
    #   File Selection
    #########################
    def add_files(self):
        files = filedialog.askopenfilenames(title="Select Files")
        for file_path in files:
            ext = os.path.splitext(file_path)[1].lower()
            # If it's .zip, assume user wants to decompress
            if ext == '.zip':
                self.decompress_listbox.insert(tk.END, file_path)
            else:
                self.compress_listbox.insert(tk.END, file_path)

    #########################
    #   Compression Method
    #########################
    def choose_compression_method(self):
        """
        If any file >= 4GB, do chunked cloud-based compression.
        Otherwise, do local .zip compression.
        """
        selected_files = [self.compress_listbox.get(i) for i in self.compress_listbox.curselection()]
        if not selected_files:
            messagebox.showwarning("No Files Selected", "Please select files to compress.")
            return

        if any(os.path.getsize(f) >= 4 * 1024 * 1024 * 1024 for f in selected_files):
            # Suggest chunked cloud compression for large files
            use_cloud = messagebox.askyesno(
                "Cloud Compression",
                "One or more files exceed 4GB. Use chunked cloud-based compression?"
            )
            if use_cloud:
                threading.Thread(target=self.start_cloud_compression, args=(selected_files,), daemon=True).start()
                return

        # Otherwise do local zip
        threading.Thread(target=self.start_local_zip_compression, args=(selected_files,), daemon=True).start()

    #########################
    #   Local Zip Compression
    #########################
    def start_local_zip_compression(self, selected_files):
        if not selected_files:
            return

        self.is_compressing = True
        self.update_progress_label("Starting local ZIP compression...")

        out_zip = filedialog.asksaveasfilename(
            title="Save Compressed Archive As",
            defaultextension=".zip",
            filetypes=[("Zip Files", "*.zip")]
        )
        if not out_zip:
            self.is_compressing = False
            self.update_progress_label("No compression in progress")
            return

        total_size = sum(os.path.getsize(f) for f in selected_files)
        self.progress_bar["maximum"] = total_size
        self.progress_bar["value"] = 0

        try:
            with zipfile.ZipFile(out_zip, 'w', compression=zipfile.ZIP_DEFLATED) as zf:
                accumulated = 0
                for file_path in selected_files:
                    file_size = os.path.getsize(file_path)
                    arcname = os.path.basename(file_path)

                    with open(file_path, 'rb') as fin:
                        data = fin.read()
                        zf.writestr(arcname, data)

                    accumulated += file_size
                    self.root.after(0, self.update_progressbar, accumulated)

            messagebox.showinfo("Compression Complete", f"Files compressed into {out_zip}")
        except Exception as e:
            logging.error(f"Error during local compression: {e}")
            messagebox.showerror("Local Compression Error", str(e))

        self.is_compressing = False
        self.update_progress_label("No compression in progress")
        self.progress_bar["value"] = 0

    #########################
    #   Cloud Chunked Compression
    #########################
    def start_cloud_compression(self, selected_files):
        """
        Splits each file into 50MB chunks and uploads them to a user-provided endpoint,
        then finalizes to get the compressed file. The server must handle chunk assembly.
        """
        self.is_compressing = True

        # Ask user for the cloud server endpoint
        cloud_url = simpledialog.askstring(
            "Cloud Endpoint",
            "Enter your chunked-compression endpoint URL (server must handle chunk assembly):"
        )
        if not cloud_url:
            messagebox.showerror("Endpoint Missing", "No cloud endpoint provided. Aborting.")
            self.is_compressing = False
            return

        # If you need an auth token, prompt here:
        token = simpledialog.askstring("Auth Token", "Enter your Cloud API Key (if needed, else leave blank):")

        chunk_size = 50 * 1024 * 1024  # 50MB
        headers = {}
        if token:
            headers["Authorization"] = f"Bearer {token}"

        for file_path in selected_files:
            file_size = os.path.getsize(file_path)
            file_name = os.path.basename(file_path)

            self.update_progress_label(f"Uploading {file_name} in chunks...")

            file_id = str(uuid.uuid4())
            total_uploaded = 0
            chunk_index = 0

            self.progress_bar["maximum"] = file_size
            self.progress_bar["value"] = 0

            try:
                with open(file_path, 'rb') as fin:
                    while True:
                        chunk = fin.read(chunk_size)
                        if not chunk:
                            break

                        params = {
                            "chunk_idx": chunk_index,
                            "file_id": file_id,
                            "filename": file_name
                        }

                        files = {
                            "chunk": ("chunk.bin", chunk)
                        }

                        resp = requests.post(
                            cloud_url,
                            headers=headers,
                            params=params,
                            files=files
                        )
                        resp.raise_for_status()

                        total_uploaded += len(chunk)
                        chunk_index += 1
                        self.root.after(0, self.update_progressbar, total_uploaded)

                # Now finalize to get the compressed file
                finalize_url = f"{cloud_url}/finalize"
                finalize_params = {"file_id": file_id}
                self.update_progress_label(f"Finalizing compression for {file_name}...")
                finalize_resp = requests.get(
                    finalize_url,
                    headers=headers,
                    params=finalize_params
                )
                finalize_resp.raise_for_status()

                compressed_data = finalize_resp.content
                out_name = file_path + ".cloud_compressed"
                with open(out_name, 'wb') as fout:
                    fout.write(compressed_data)

                messagebox.showinfo(
                    "Cloud Compression Complete",
                    f"File '{file_name}' was compressed via the cloud.\nSaved as: {os.path.basename(out_name)}"
                )

            except Exception as e:
                logging.error(f"Error during chunked cloud compression for {file_name}: {e}")
                messagebox.showerror("Chunked Cloud Error", str(e))
                continue

        self.is_compressing = False
        self.update_progress_label("No compression in progress")
        self.progress_bar["value"] = 0

    #########################
    #   Extraction Logic
    #########################
    def start_extraction(self):
        selected_files = [self.decompress_listbox.get(i) for i in self.decompress_listbox.curselection()]
        if not selected_files:
            messagebox.showwarning("No Files Selected", "Please select .zip files to decompress.")
            return

        out_dir = filedialog.askdirectory(title="Select Folder to Extract Into")
        if not out_dir:
            return

        for zip_path in selected_files:
            try:
                with zipfile.ZipFile(zip_path, 'r') as zf:
                    zf.extractall(out_dir)
                messagebox.showinfo("Extraction Complete", f"Extracted {os.path.basename(zip_path)} into {out_dir}")
            except Exception as e:
                logging.error(f"Error extracting {zip_path}: {e}")
                messagebox.showerror("Extraction Error", str(e))

    #########################
    #   Progress Helpers
    #########################
    def update_progressbar(self, value):
        self.progress_bar["value"] = value
        self.root.update_idletasks()

    def update_progress_label(self, text):
        self.progress_label.config(text=text)
        self.root.update_idletasks()


#########################
#   Main Runner
#########################
if __name__ == "__main__":
    root = tk.Tk()
    app = SmartCompressApp(root)
    root.mainloop()
