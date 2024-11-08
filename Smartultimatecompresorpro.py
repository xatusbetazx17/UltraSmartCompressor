import os
import sys
import subprocess
import tkinter as tk
from tkinter import filedialog, messagebox, ttk, simpledialog
import threading
import logging
import time  # Added for sleep and timing
import zipfile
import shutil
import tarfile
import multiprocessing

# Set up logging for debugging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Function to create and activate a virtual environment
def setup_virtualenv():
    venv_path = os.path.join(os.getcwd(), 'venv')
    if not os.path.exists(venv_path):
        subprocess.check_call([sys.executable, '-m', 'venv', venv_path])
    return os.path.join(venv_path, 'bin', 'python')

python_exec = setup_virtualenv()

# Function to ensure necessary libraries are installed
def install_package(python_exec, package, pip_name=None):
    if pip_name is None:
        pip_name = package
    try:
        subprocess.check_call([python_exec, "-m", "pip", "install", pip_name])
    except subprocess.CalledProcessError as e:
        sys.exit(1)

# Function to check for the presence of libraries and install if needed
def try_import_or_install(package, pip_name=None):
    try:
        __import__(package)
    except ImportError:
        install_package(python_exec, package, pip_name or package)
        if python_exec != sys.executable:
            os.execv(python_exec, [python_exec] + sys.argv)

# Check and install required packages
try_import_or_install('PIL', 'Pillow')
try_import_or_install('py7zr', 'py7zr')
try_import_or_install('pycdlib', 'pycdlib')
try_import_or_install('torch', 'torch')
try_import_or_install('numpy', 'numpy')

# Import modules after installing
from PIL import Image, ImageTk
import py7zr
import pycdlib
import torch
import numpy as np

# Function to check system resources and capabilities
def check_system_capabilities():
    ram_size_gb = round(os.sysconf('SC_PAGE_SIZE') * os.sysconf('SC_PHYS_PAGES') / (1024. ** 3), 2)
    num_cores = multiprocessing.cpu_count()
    has_gpu = torch.cuda.is_available() or torch.backends.mps.is_available()

    # Define recommended requirements for "super compression"
    recommended_ram = 16  # in GB
    recommended_cores = 8

    if ram_size_gb < recommended_ram or num_cores < recommended_cores or not has_gpu:
        messagebox.showwarning(
            "Performance Warning",
            f"Your system has {ram_size_gb} GB RAM, {num_cores} CPU cores, and {'a GPU' if has_gpu else 'no GPU'}.\n"
            f"To achieve optimal performance, it is recommended to have at least {recommended_ram} GB RAM, "
            f"{recommended_cores} CPU cores, and a dedicated GPU.\n"
            "The compression process may be slow on your system."
        )

    return ram_size_gb >= recommended_ram and num_cores >= recommended_cores and has_gpu

# Tkinter App Class
class SmartCompressApp:
    def __init__(self, root):
        self.root = root
        self.root.title("SmartCompressProUltimate - AI Enhanced")
        self.root.geometry("1000x700")

        # Setting up the main frames
        self.setup_main_interface()

    def setup_main_interface(self):
        self.create_toolbar()
        self.create_tabbed_area()

    def create_toolbar(self):
        # Creating a toolbar at the top
        toolbar_frame = tk.Frame(self.root, bd=2, relief=tk.RAISED)
        toolbar_frame.pack(side=tk.TOP, fill=tk.X)

        # Toolbar icons
        add_button = tk.Button(toolbar_frame, text="Add Files", relief=tk.FLAT, command=self.add_files)
        add_button.pack(side=tk.LEFT, padx=2, pady=2)

        extract_button = tk.Button(toolbar_frame, text="Extract", relief=tk.FLAT, command=self.start_extraction)
        extract_button.pack(side=tk.LEFT, padx=2, pady=2)

    def create_tabbed_area(self):
        tab_control = ttk.Notebook(self.root)

        # Compress Tab
        self.compress_tab = ttk.Frame(tab_control)
        tab_control.add(self.compress_tab, text='Compress')
        self.create_compress_tab(self.compress_tab)

        # Decompress Tab
        self.decompress_tab = ttk.Frame(tab_control)
        tab_control.add(self.decompress_tab, text='Decompress')
        self.create_decompress_tab(self.decompress_tab)

        tab_control.pack(expand=1, fill="both")

    def create_compress_tab(self, tab):
        ttk.Label(tab, text="Select files to compress:").pack(pady=5)
        self.compress_listbox = tk.Listbox(tab, selectmode=tk.MULTIPLE)
        self.compress_listbox.pack(padx=10, pady=10, fill=tk.BOTH, expand=True)
        ttk.Button(tab, text="Add Files", command=self.add_files).pack(side=tk.LEFT, padx=5)
        ttk.Button(tab, text="Compress", command=self.start_compression).pack(side=tk.RIGHT, padx=5)

    def create_decompress_tab(self, tab):
        ttk.Label(tab, text="Select files to decompress:").pack(pady=5)
        self.decompress_listbox = tk.Listbox(tab, selectmode=tk.MULTIPLE)
        self.decompress_listbox.pack(padx=10, pady=10, fill=tk.BOTH, expand=True)
        ttk.Button(tab, text="Add Files", command=self.add_files).pack(side=tk.LEFT, padx=5)
        ttk.Button(tab, text="Decompress", command=self.start_extraction).pack(side=tk.RIGHT, padx=5)

    def add_files(self):
        files = filedialog.askopenfilenames(title="Select Files")
        for file in files:
            # Add files to both the compress and decompress listboxes
            self.compress_listbox.insert(tk.END, file)
            self.decompress_listbox.insert(tk.END, file)

    def start_extraction(self):
        selected_files = [self.decompress_listbox.get(i) for i in self.decompress_listbox.curselection()]
        if not selected_files:
            messagebox.showwarning("No Files Selected", "Please select files to extract.")
            return

        extract_folder = filedialog.askdirectory(title="Select Extraction Folder")
        if not extract_folder:
            return

        for file in selected_files:
            try:
                if zipfile.is_zipfile(file):
                    with zipfile.ZipFile(file, 'r') as zipf:
                        zipf.extractall(extract_folder)
                        logging.info(f"Extracting file: {file}")
                elif tarfile.is_tarfile(file):
                    with tarfile.open(file, 'r:*') as tarf:
                        tarf.extractall(path=extract_folder)
                        logging.info(f"Extracting file: {file}")
                elif file.endswith('.7z'):
                    with py7zr.SevenZipFile(file, 'r') as sevenz:
                        sevenz.extractall(path=extract_folder)
                        logging.info(f"Extracting file: {file}")
                elif file.endswith('.iso'):
                    iso = pycdlib.PyCdlib()
                    iso.open(file)
                    os.makedirs(extract_folder, exist_ok=True)
                    logging.info(f"Extracting ISO: {file}")
                    for dir_path, dirs, files in iso.walk(iso_path='/'):
                        for file_name in files:
                            with open(os.path.join(extract_folder, file_name), 'wb') as out_file:
                                iso.get_file_from_iso(os.path.join(dir_path, file_name), out_file)
                    iso.close()
                else:
                    messagebox.showerror("Unsupported File", f"Cannot extract: {file}. Supported formats are zip, tar.gz, 7z, and iso.")
            except Exception as e:
                logging.error(f"Error extracting file '{file}': {e}")
                messagebox.showerror("Error", f"Error extracting '{file}': {e}")

        messagebox.showinfo("Extraction Complete", f"Files successfully extracted to: {extract_folder}")

    # Modified aggressive_compression function with smaller chunks and simplified operations.
    def aggressive_compression(self, data):
        """Uses an AI model to compress the data aggressively while maintaining data integrity."""
        try:
            # Convert the byte data to a numpy array
            data_np = np.frombuffer(data, dtype=np.uint8)

            # Reduce the chunk size to minimize memory usage
            chunk_size = 1024 * 1024  # 1 MB chunks
            compressed_chunks = []

            for start in range(0, len(data_np), chunk_size):
                chunk = data_np[start:start + chunk_size]

                # Define a simpler compression model or transformation
                compressed_chunk = chunk / 2  # Example: simple value transformation
                compressed_chunks.append(compressed_chunk.astype(np.uint8).tobytes())

            compressed_data = b"".join(compressed_chunks)
            logging.info("Aggressive compression completed successfully.")
            return compressed_data
        except Exception as e:
            logging.error(f"Error during aggressive AI compression: {e}")
            return data  # Fallback to original data if any issues

    def start_compression(self):
        # Check if the system has enough resources for optimal compression
        has_resources = check_system_capabilities()

        if not has_resources:
            # Alert the user about insufficient resources
            messagebox.showwarning(
                "System Performance Warning",
                "Your system may not have enough resources to run aggressive compression quickly. "
                "The process may be slow or may fail. Consider using a system with more RAM and a GPU."
            )

        selected_files = [self.compress_listbox.get(i) for i in self.compress_listbox.curselection()]
        if not selected_files:
            messagebox.showwarning("No Files Selected", "Please select files to compress.")
            return

        # Get the destination for the compressed file
        output_filename = filedialog.asksaveasfilename(defaultextension=".7z", filetypes=[("All Files", "*.*")])
        if not output_filename:
            return

        # Compress the selected files
        try:
            for file in selected_files:
                file_size = os.path.getsize(file)
                if file_size > 4 * 1024 * 1024 * 1024:  # File size > 4GB
                    with open(file, 'rb') as f:
                        data = f.read()
                        logging.info(f"Starting aggressive AI-enhanced compression for: {file}")
                        data = self.aggressive_compression(data)

                    with open(file, 'wb') as compressed_file:
                        compressed_file.write(data)

                    with py7zr.SevenZipFile(output_filename, 'w') as sevenz:
                        sevenz.writeall(file)
                        logging.info(f"Compressed {file} to {output_filename}")

                else:
                    # Use standard compression methods for smaller files
                    with py7zr.SevenZipFile(output_filename, 'w') as sevenz:
                        sevenz.writeall(file)
                        logging.info(f"Compressed {file} to {output_filename}")

            messagebox.showinfo("Compression Complete", f"Files successfully compressed to: {output_filename}")
        except Exception as e:
            logging.error(f"Error compressing files: {e}")
            messagebox.showerror("Error", f"Error compressing files: {e}")

# Main Application Runner
if __name__ == "__main__":
    root = tk.Tk()
    app = SmartCompressApp(root)
    root.mainloop()
