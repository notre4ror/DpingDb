import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import mysql.connector
import json
import os
import re
import subprocess
from datetime import datetime
import threading
import time


def execute_ping(hostname):
    param = '-n' if os.name == 'nt' else '-c'
    count = '1'
    command = ['ping', f'{param}', count, hostname]
    try:
        output = subprocess.check_output(command,
                                        universal_newlines=True,
                                        stderr=subprocess.STDOUT)
        ip_match = re.search(r'\b\d+\.\d+\.\d+\.\d+\b', output.split('from')[-1])
        if not ip_match:
            return None
        
        latency = 0.0
        if os.name == 'nt':
            time_match = re.search(r'time=(\d+)ms', output)
            latency = int(time_match.group(1)) if time_match else -1
        else:
            avg_time = re.search(
                r'rtt min/avg/max/mdev = \S+/([\d.]+)/',
                output.splitlines()[-1]
            )
            latency = float(avg_time.group(1)) if avg_time else -1
        
        return {
            'timestamp': datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
            'ip': ip_match.group(),
            'latency': latency

        }
    except subprocess.CalledProcessError as e:
        return None

class ConfigManager:
    def __init__(self):
        self.config_file = "config.json"
        self.default_config = {
            "hostname": "localhost",
            "database": {
                "host": "127.0.0.1",
                "user": "root",
                "password": "",
                "port": "3306",
                "db_name": "your_database",
                "table_name": "ip_records"
            },
            "output_dir": "./results/",
            "check_interval_minutes": 5
        }

    def load_config(self):
        if not os.path.exists(self.config_file):
            self.save_config()
        
        with open(self.config_file, 'r') as f:
            loaded = json.load(f)
            
        merged = {**self.default_config}
        for key in loaded:
            if isinstance(merged.get(key), dict) and isinstance(loaded[key], dict):
                merged[key].update(loaded[key])
            else:
                merged[key] = loaded[key]
                
        return merged
    
    def save_config(self, data=None):
        config_data = data or self.default_config
        with open(self.config_file, 'w') as f:
            json.dump(config_data, f, indent=4)
            
class DBConnector:
    def __init__(self, config):
        self.config = config
    
    def get_db_connection(self):
        try:
            return mysql.connector.connect(
                host=self.config['database']['host'],
                user=self.config['database']['user'],
                password=self.config['database']['password'],
                port=int(self.config['database']['port']),
                database=self.config['database']['db_name']
            )
        except Exception as e:
            print(f"Database connection failed: {e}")
            return None
    
    def get_stored_ip(self):
        conn = self.get_db_connection()
        if not conn:
            return None
        cursor = conn.cursor()
        query = f"""
            SELECT ip FROM {self.config['database']['table_name']} 
            ORDER BY id DESC LIMIT 1
        """
        try:
            cursor.execute(query)
            result = cursor.fetchone()
            return result[0] if result else None
        except Exception as e:
            print(f"Database query error: {e}")
            return None
        finally:
            cursor.close()
            conn.close()

    def update_ip(self, new_ip):
        conn = self.get_db_connection()
        if not conn:
            print("Could not connect to database during IP update.")
            DPingApp.db_error_occurred = True
            return False
        
        cursor = conn.cursor()
        query = f"""
            INSERT INTO {self.config['database']['table_name']} (ip)
            VALUES (%s) 
            ON DUPLICATE KEY UPDATE ip = %s
        """
        
        try:
            cursor.execute(query, (new_ip, new_ip))
            conn.commit()
            return True
        except Exception as e:
            print(f"Update error: {e}")
            return False
        finally:
            cursor.close()
            conn.close()
class DPingApp:
    def __init__(self, root):
        self.root = root
        self.config_manager = ConfigManager()
        self.config = self.config_manager.load_config()  
        
        self.monitor_active = False
        self.db_connector = DBConnector(self.config)
        
        self.build_gui()
        
    def build_gui(self):
        style = ttk.Style()
        style.theme_use('clam')
        
        notebook = ttk.Notebook(self.root)
        self.tab1 = ttk.Frame(notebook)  # Configuración
        self.tab2 = ttk.Frame(notebook)  # Actividad
        self.tab3 = ttk.Frame(notebook)  # Historial
        
        notebook.add(self.tab1, text="Configuración")
        notebook.add(self.tab2, text="Actividad")
        notebook.add(self.tab3, text="Historial")
        notebook.pack(expand=1, fill='both')
        
        self.create_config_tab()
        self.create_activity_tab()
        self.create_history_tab()

    def create_config_tab(self):
        frame = ttk.LabelFrame(self.tab1, text="Configuración Principal")
        frame.grid(row=0, column=0, padx=20, pady=20)
        
        # Hostname entry
        ttk.Label(frame, text="Hostname:").grid(row=0, sticky='w')
        self.hostname_var = tk.StringVar(value=self.config['hostname'])
        hostname_entry = ttk.Entry(frame, textvariable=self.hostname_var)
        hostname_entry.grid(row=0, column=1, pady=5)

        # Database config entries
        db_frame = ttk.LabelFrame(frame, text="Configuración de Base de Datos")
        db_frame.grid(row=1, columnspan=2, padx=5, pady=5, sticky='w')

        rows_db = [
            ("Host BD:", "database.host", self.config['database']['host']),
            ("Usuario BD:", "database.user", self.config['database']['user']),
            ("Contraseña BD:", "database.password", self.config['database']['password']),
            ("Puerto BD:", "database.port", self.config['database']['port']),
            ("Nombre BD:", "database.db_name", self.config['database']['db_name']),
            ("Tabla:", "database.table_name", self.config['database']['table_name'])
        ]

        for idx, (label, key_path, default) in enumerate(rows_db):
            ttk.Label(db_frame, text=label).grid(row=idx, sticky='w')
            var_key = f"config_{key_path}"
            setattr(self, var_key, tk.StringVar(value=str(default)))
            
            entry_config = ttk.Entry(
                db_frame,
                textvariable=getattr(self, var_key),
                show="*" if "password" in key_path else None
            )
            entry_config.grid(row=idx, column=1)

        # Output directory selector
        ttk.Label(frame, text="Directorio de resultados:").grid(row=2, sticky='w')
        self.output_dir_var = tk.StringVar(value=self.config['output_dir'])
        output_entry = ttk.Entry(
            frame,
            textvariable=self.output_dir_var,
            state='readonly'
        )
        output_entry.grid(row=2, column=1)
        
        select_btn = ttk.Button(
            frame,
            text="Seleccionar Carpeta",
            command=lambda: self.select_directory(output_entry)
        )
        select_btn.grid(row=2, column=2)

        # Check interval
        ttk.Label(frame, text="Intervalo (minutos):").grid(row=3, sticky='w')
        self.interval_var = tk.StringVar(value=self.config['check_interval_minutes'])
        interval_entry = ttk.Entry(
            frame,
            textvariable=self.interval_var,
            width=5
        )
        interval_entry.grid(row=3, column=1)

        # Save button
        save_btn = ttk.Button(
            frame,
            text="Guardar Configuración",
            command=self.save_config_changes
        )
        save_btn.grid(row=4, columnspan=3, pady=(10, 0))

    def select_directory(self, entry):
        selected_dir = filedialog.askdirectory()
        if selected_dir:
            self.output_dir_var.set(selected_dir)

    def save_config_changes(self):
        new_config = {
            "hostname": self.hostname_var.get(),
            "database": {
                "host": getattr(self, f"config_database.host").get(),
                "user": getattr(self, f"config_database.user").get(),
                "password": getattr(self, f"config_database.password").get(),
                "port": int(getattr(self, f"config_database.port").get()),
                "db_name": getattr(self, f"config_database.db_name").get(),
                "table_name": getattr(self, f"config_database.table_name").get()
            },
            "output_dir": self.output_dir_var.get().strip(),
            "check_interval_minutes": int(self.interval_var.get())
        }
        
        try:
            os.makedirs(new_config['output_dir'], exist_ok=True)
            self.config_manager.save_config(new_config)
            messagebox.showinfo("Éxito", "Configuración guardada")
            
            # Status bar actualizada al guardar la configuracion
            self.status_var = tk.StringVar(value="Listo")
            self.status_label = ttk.Label(
                    self.frame_act,
                    textvariable=self.status_var,
                    anchor='w',
                    foreground="green"
                )
            self.status_label.grid(row=0, columnspan=3, sticky='ew')
            
            # Update current config
            self.config = new_config
            self.db_connector = DBConnector(self.config)  # Reconnect with new settings
            
        except Exception as e:
            messagebox.showerror("Error", str(e))
            
    def create_activity_tab(self):
        self.frame_act = ttk.Frame(self.tab2)
        self.frame_act.pack(padx=10, pady=10, expand=True, fill='both')
        
        # Status bar
        self.status_var = tk.StringVar(value="Listo")
        self.status_label = ttk.Label(self.frame_act, textvariable=self.status_var, anchor='w', foreground="green")
        self.status_label.grid(row=0, columnspan=3, sticky='ew')

        # Buttons container
        btn_frame = ttk.Frame(self.frame_act)
        btn_frame.grid(row=1, pady=(20, 5))
        
        self.start_btn = ttk.Button(
            btn_frame,
            text="Iniciar Monitoreo",
            command=self.start_monitoring
        )
        self.start_btn.pack(side='left', padx=(0,10))

        self.stop_btn = ttk.Button(
            btn_frame,
            text="Detener Monitoreo",
            state=tk.DISABLED,
            command=self.stop_monitoring
        )
        self.stop_btn.pack(side='left')

        # Log display
        self.log_text = tk.Text(self.frame_act, wrap=tk.WORD, height=15)
        self.log_text.grid(row=2, columnspan=3, padx=5, pady=(10,0))
        
    def start_monitoring(self):
        try:
            interval_seconds = int(self.config['check_interval_minutes']) * 60
        
            if not self.monitor_active:  
                # Actualización del estado UI antes de iniciar el hilo
                label= "Monitoreo activo en " + self.config["hostname"]
                self.status_var.set(label)
                self.status_label.config(foreground="green")

                self.start_btn.configure(state=tk.DISABLED)
                self.stop_btn.configure(state=tk.NORMAL)

                # ¡Ahora sí establecemos la bandera!
                self.monitor_active = True

                self.monitor_thread = threading.Thread(
                    target=self.run_ping_cycle,
                    args=(interval_seconds,),
                    daemon=True
                )
                self.monitor_thread.start()
        except ValueError:
            messagebox.showerror("Error", "Intervalo inválido. Debe ser un número entero.")

    def update_status(self, text, color="green"):
        self.status_var.set(text)
        self.status_label.config(foreground=color)

    def run_ping_cycle(self, interval):
        while self.monitor_active:
            try:
                result = execute_ping(self.config['hostname'])
                
                if result is not None:
                    current_result = result.copy()
                    
                    # Bloque para operaciones con la base de datos
                    DPingApp.db_error_occurred = False
                    try:
                        db_ip = self.db_connector.get_stored_ip()
                        
                        if current_result["ip"] != db_ip:
                            success = self.db_connector.update_ip(current_result["ip"])
                            
                    except mysql.connector.Error as e:  # Captura errores de conexión/consulta a la BD
                        DPingApp.db_error_occurred = True
                        error_msg = f"Database access failed: {str(e)}"
                        print(error_msg)
                    
                    finally:
                        if DPingApp.db_error_occurred:
                            label = "Monitoreo activo: Modo SOLO ping en " + self.config["hostname"]
                            self.root.after(0, lambda: self.update_status(
                                label, "orange"))
                        else:
                            self.root.after(0, lambda: self.update_status(
                                "Monitoreo activo", "green"))

                    # Mostrar log independientemente del estado de la BD
                    def log_success():
                        self.log_text.insert(
                            tk.END,
                            f"[{result['timestamp']}] IP: {result['ip']} (Latencia: {result['latency']} ms)\n"
                        )
                        self.log_text.see(tk.END)
                    self.root.after(0, log_success)

                    # Guardar en archivo
                    timestamp_filename = result["timestamp"].replace(":", "")
                    filename = os.path.join(
                        self.config["output_dir"],
                        f"{timestamp_filename}_{self.config['hostname']}.json"
                    )
                    with open(filename, "w") as json_file:
                        json.dump(result, json_file)
                
                else:
                    current_time = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
                    
                    def log_failure():
                        self.log_text.insert(
                            tk.END,
                            f"[{current_time}] - Fallo de conexión\n"
                        )
                        self.log_text.see(tk.END)
                    self.root.after(0, log_failure)
            except Exception as e:
                error_msg = f"Error crítico: {str(e)}"
                messagebox.showerror("Error", error_msg)

            time.sleep(interval)


    def stop_monitoring(self):
        self.monitor_active = False
        
        self.status_var.set("Monitoreo detenido")
        self.status_label.config(foreground="red")
        self.start_btn.configure(state=tk.NORMAL)
        self.stop_btn.configure(state=tk.DISABLED)

    def create_history_tab(self):
        frame_hist = ttk.Frame(self.tab3)
        frame_hist.pack(padx=10, pady=10, expand=True, fill='both')
        
        # Filters
        filters_frame = ttk.LabelFrame(frame_hist, text="Filtros")
        filters_frame.grid(row=0, column=0, sticky='nw', padx=5)
        
        self.ip_filter_var = tk.StringVar()
        ttk.Label(filters_frame, text="IP:").grid(row=0, column=0)
        ip_entry = ttk.Entry(filters_frame, textvariable=self.ip_filter_var)
        ip_entry.grid(row=0, column=1)

        load_btn = ttk.Button(
            filters_frame,
            text="Cargar historial",
            command=lambda:self.load_history_files()
        )
        load_btn.grid(row=1, columnspan=2, pady=(5,0))
        
        # Results table
        self.history_treeview = ttk.Treeview(
            frame_hist,
            columns=("timestamp", "ip", "latency"),
            show="headings"
        )
        self.history_treeview.heading("timestamp", text="Fecha/Hora")
        self.history_treeview.heading("ip", text="IP")
        self.history_treeview.heading("latency", text="Latencia (ms)")
        
        self.history_treeview.grid(row=1, column=0, sticky='news', padx=5)
        frame_hist.columnconfigure(0, weight=1)
    
    def show_error(self, message):
        messagebox.showerror("Error crítico", message)

    def load_history_files(self):
        search_dir = self.config["output_dir"]
        # print(self.config["output_dir"])
        file_pattern = "*.json"
        
        # Limpiar visualización actual
        for item in self.history_treeview.get_children():
            self.history_treeview.delete(item)
            
        try:
            files = [
                f for f in os.listdir(search_dir) 
                if f.endswith(".json")
            ]
            for filename in files:
                file_path = os.path.join(search_dir, filename)
                
                with open(file_path, 'r') as json_file:
                    if "config.json" in json_file.name :
                        continue
                    else:
                        try:
                            data = json.load(json_file)
                        except (json.JSONDecodeError, KeyError):
                            messagebox.showerror("Error",f"Archivo {filename} corrupto o mal formado"
                            )
                            continue
                        
                # Validar datos obligatorios
                required_keys = ['timestamp', 'ip', 'latency']
                if not all(key in data for key in required_keys):
                    messagebox.showwarning(
                        "Advertencia",
                        f"Archivo {filename} no cumple con el formato esperado"
                    )
                    continue
                
                # Aplicar filtros
                filter_ip = self.ip_filter_var.get()
                if filter_ip and (filter_ip not in data['ip']):
                    continue
                    
                self.history_treeview.insert(
                    "",
                    "end",
                    values=(
                        data["timestamp"],
                        data["ip"],
                        f"{data['latency']} ms"
                    )
                )
            if not files:
                messagebox.showerror("Directorio sin ficheros", "El directorio esta vacio")
        except FileNotFoundError:
            messagebox.showerror("Error", f"Directorio no encontrado: {search_dir}")
        except Exception as e:
            self.show_error(f"Error al cargar historial: {str(e)}")
        
if __name__ == "__main__":
    root = tk.Tk()
    root.title("DPingDB v2.0")
    
    app = DPingApp(root)
    root.mainloop()
