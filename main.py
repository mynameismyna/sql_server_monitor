"""
SQL Sunucu Takip Uygulaması - Ana Dosya
"""
import sys
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QLabel, QLineEdit, QPushButton, 
                             QComboBox, QTextEdit, QTableWidget, QTableWidgetItem,
                             QGroupBox, QMessageBox, QHeaderView, QInputDialog,
                             QSplitter, QFileDialog, QDialog, QDialogButtonBox,
                             QListWidget, QListWidgetItem, QMenuBar, QAction)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt5.QtGui import QFont, QIntValidator
import pandas as pd
from datetime import datetime
from sql_connection import SQLConnection
from predefined_queries import PREDEFINED_QUERIES, get_all_queries, save_user_query, delete_user_query, load_user_queries, rename_user_query, get_user_query_categories
from config_manager import ConfigManager


class QueryThread(QThread):
    """Sorgu çalıştırma için thread sınıfı (UI donmasını önlemek için)"""
    finished = pyqtSignal(bool, object, str)
    
    def __init__(self, sql_conn, query):
        super().__init__()
        self.sql_conn = sql_conn
        self.query = query
    
    def run(self):
        success, result, error = self.sql_conn.execute_query(self.query)
        self.finished.emit(success, result, error)


class SQLServerApp(QMainWindow):
    """Ana uygulama penceresi"""
    
    def __init__(self):
        super().__init__()
        self.sql_conn = SQLConnection()
        self.current_results_columns = None
        self.current_results_rows = None
        self.full_texts = {}
        self.auto_timer = QTimer()
        self.auto_timer.timeout.connect(self.auto_execute_query)
        self.auto_duration_timer = QTimer()
        self.auto_duration_timer.timeout.connect(self.stop_auto_execution)
        self.auto_status_timer = QTimer()
        self.auto_status_timer.timeout.connect(self.update_auto_status)
        self.auto_status_timer.start(1000)  # Her saniye güncelle
        self.auto_start_time = None
        self.auto_duration_seconds = 0
        self.selected_query_name = None  # Seçili sorgu adını takip et
        self.edit_mode = False  # Düzenleme modunda mı?
        self.init_ui()
        self.load_saved_connection()
    
    def init_ui(self):
        """Kullanıcı arayüzünü oluştur"""
        self.setWindowTitle("SQL Sunucu Takip Uygulaması")
        self.setGeometry(100, 100, 1400, 900)
        
        # Menü çubuğu oluştur
        self.create_menu_bar()
        
        # Ana widget
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        
        # Ana layout
        main_layout = QVBoxLayout()
        main_widget.setLayout(main_layout)
        main_layout.setSpacing(5)
        main_layout.setContentsMargins(5, 5, 5, 5)
        
        # Bağlantı paneli
        connection_group = self.create_connection_panel()
        main_layout.addWidget(connection_group)
        
        # Veritabanı seçimi (bağlantıdan sonra görünecek)
        self.database_layout = QHBoxLayout()
        self.database_layout.addWidget(QLabel("Aktif Veritabanı:"))
        self.database_combo = QComboBox()
        self.database_combo.addItem("-- Veritabanı seçin --")
        self.database_combo.currentTextChanged.connect(self.on_database_selected)
        self.database_layout.addWidget(self.database_combo)
        self.database_layout.addStretch()
        
        self.database_widget = QWidget()
        self.database_widget.setLayout(self.database_layout)
        self.database_widget.setVisible(False)
        main_layout.addWidget(self.database_widget)
        
        # Hazır sorgular (bağlantıdan sonra görünecek, şimdilik gizli)
        self.queries_layout = QHBoxLayout()
        
        # Kategori seçimi
        self.queries_layout.addWidget(QLabel("Kategori:"))
        self.category_combo = QComboBox()
        self.category_combo.addItem("-- Kategori seçin --")
        self.category_combo.currentTextChanged.connect(self.on_category_selected)
        self.queries_layout.addWidget(self.category_combo)
        
        # Sorgu seçimi
        self.queries_layout.addWidget(QLabel("Sorgu:"))
        self.predefined_combo = QComboBox()
        self.predefined_combo.addItem("-- Sorgu seçin veya kendi sorgunuzu yazın --")
        self.predefined_combo.currentTextChanged.connect(self.on_predefined_query_selected)
        self.queries_layout.addWidget(self.predefined_combo, 1)
        
        # Butonlar
        self.add_query_btn = QPushButton("Sorguyu Kaydet")
        self.add_query_btn.clicked.connect(self.save_current_query)
        self.add_query_btn.setEnabled(False)
        self.queries_layout.addWidget(self.add_query_btn)
        
        self.manage_queries_btn = QPushButton("Sorguları Yönet")
        self.manage_queries_btn.clicked.connect(self.manage_queries)
        self.manage_queries_btn.setEnabled(False)
        self.queries_layout.addWidget(self.manage_queries_btn)
        
        self.queries_widget = QWidget()
        self.queries_widget.setLayout(self.queries_layout)
        self.queries_widget.setVisible(False)
        main_layout.addWidget(self.queries_widget)
        
        # SQL Editörü (20 satır veya 1/3 alan)
        editor_group = QGroupBox("SQL Sorgu Editörü")
        editor_layout = QVBoxLayout()
        
        # Otomatik çalıştırma paneli
        auto_group = QGroupBox("Otomatik Çalıştırma")
        auto_layout = QHBoxLayout()
        
        auto_layout.addWidget(QLabel("Her"))
        self.interval_input = QLineEdit()
        self.interval_input.setPlaceholderText("5")
        self.interval_input.setMaximumWidth(60)
        self.interval_input.setValidator(QIntValidator(1, 3600))  # 1-3600 saniye arası
        auto_layout.addWidget(self.interval_input)
        
        auto_layout.addWidget(QLabel("saniyede bir"))
        
        auto_layout.addWidget(QLabel("Toplam"))
        self.duration_input = QLineEdit()
        self.duration_input.setPlaceholderText("60")
        self.duration_input.setMaximumWidth(60)
        self.duration_input.setValidator(QIntValidator(1, 86400))  # 1-86400 saniye (24 saat)
        auto_layout.addWidget(self.duration_input)
        
        auto_layout.addWidget(QLabel("saniye boyunca"))
        
        self.auto_start_btn = QPushButton("Başlat")
        self.auto_start_btn.clicked.connect(self.start_auto_execution)
        self.auto_start_btn.setEnabled(False)
        auto_layout.addWidget(self.auto_start_btn)
        
        self.auto_stop_btn = QPushButton("Durdur")
        self.auto_stop_btn.clicked.connect(self.stop_auto_execution)
        self.auto_stop_btn.setEnabled(False)
        auto_layout.addWidget(self.auto_stop_btn)
        
        self.auto_status_label = QLabel("")
        self.auto_status_label.setStyleSheet("color: blue; font-weight: bold;")
        auto_layout.addWidget(self.auto_status_label)
        
        auto_layout.addStretch()
        auto_group.setLayout(auto_layout)
        editor_layout.addWidget(auto_group)
        
        self.query_editor = QTextEdit()
        self.query_editor.setFont(QFont("Consolas", 10))
        self.query_editor.setPlaceholderText("SQL sorgunuzu buraya yazın...")
        # Minimum 20 satır yüksekliği
        font_metrics = self.query_editor.fontMetrics()
        line_height = font_metrics.lineSpacing()
        min_height = line_height * 20
        self.query_editor.setMinimumHeight(min_height)
        editor_layout.addWidget(self.query_editor)
        
        # Butonlar
        btn_layout = QHBoxLayout()
        self.execute_btn = QPushButton("Sorguyu Çalıştır (F5)")
        self.execute_btn.setShortcut("F5")
        self.execute_btn.clicked.connect(self.execute_query)
        self.execute_btn.setEnabled(False)
        btn_layout.addWidget(self.execute_btn)
        
        self.clear_btn = QPushButton("Temizle")
        self.clear_btn.clicked.connect(self.clear_query)
        btn_layout.addWidget(self.clear_btn)
        btn_layout.addStretch()
        editor_layout.addLayout(btn_layout)
        
        editor_group.setLayout(editor_layout)
        
        # Sorgu Sonuçları
        results_group = QGroupBox("Sorgu Sonuçları")
        results_layout = QVBoxLayout()
        
        # Excel export butonu
        results_btn_layout = QHBoxLayout()
        self.export_excel_btn = QPushButton("Excel'e Aktar")
        self.export_excel_btn.clicked.connect(self.export_to_excel)
        self.export_excel_btn.setEnabled(False)
        results_btn_layout.addWidget(self.export_excel_btn)
        results_btn_layout.addStretch()
        results_layout.addLayout(results_btn_layout)
        
        self.results_table = QTableWidget()
        self.results_table.setAlternatingRowColors(True)
        self.results_table.setSelectionBehavior(QTableWidget.SelectRows)
        results_layout.addWidget(self.results_table)
        
        results_group.setLayout(results_layout)
        
        # SQL Editörü ve Sonuçlar arasında ayarlanabilir splitter
        editor_results_splitter = QSplitter(Qt.Vertical)
        editor_results_splitter.addWidget(editor_group)
        editor_results_splitter.addWidget(results_group)
        # Başlangıç oranı: Editör 1/3, Sonuçlar 2/3
        editor_results_splitter.setStretchFactor(0, 1)
        editor_results_splitter.setStretchFactor(1, 2)
        # Minimum boyutlar
        editor_results_splitter.setSizes([300, 600])
        
        main_layout.addWidget(editor_results_splitter, 1)
        
        # Hata mesajları (en altta, 2-3 satır)
        error_group = QGroupBox("Hata Mesajları")
        error_layout = QVBoxLayout()
        
        self.error_text = QTextEdit()
        self.error_text.setFont(QFont("Consolas", 9))
        self.error_text.setStyleSheet("background-color: #ffe6e6;")
        # 2-3 satır yüksekliği
        error_height = line_height * 3
        self.error_text.setMaximumHeight(error_height)
        self.error_text.setMinimumHeight(error_height)
        error_layout.addWidget(self.error_text)
        
        error_group.setLayout(error_layout)
        main_layout.addWidget(error_group)
        
        # Durum çubuğu
        self.statusBar().showMessage("Hazır")
    
    def create_menu_bar(self):
        """Menü çubuğunu oluştur"""
        menubar = self.menuBar()
        
        # Yardım menüsü
        help_menu = menubar.addMenu('Yardım')
        
        # Kullanım Kılavuzu
        help_action = QAction('Kullanım Kılavuzu', self)
        help_action.setShortcut('F1')
        help_action.triggered.connect(self.show_help)
        help_menu.addAction(help_action)
        
        # Sorgu Uyumluluğu
        compatibility_action = QAction('Sorgu Uyumluluğu', self)
        compatibility_action.triggered.connect(self.show_compatibility_info)
        help_menu.addAction(compatibility_action)
        
        help_menu.addSeparator()
        
        # Hakkında
        about_action = QAction('Hakkında', self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)
    
    def create_connection_panel(self):
        """Bağlantı ayarları panelini oluştur"""
        group = QGroupBox("SQL Server Bağlantı Ayarları")
        layout = QHBoxLayout()
        
        # Server
        layout.addWidget(QLabel("Sunucu:"))
        self.server_input = QLineEdit()
        self.server_input.setPlaceholderText("localhost veya IP adresi")
        self.server_input.returnPressed.connect(self.connect_to_server)
        layout.addWidget(self.server_input)
        
        # Auth Type
        layout.addWidget(QLabel("Kimlik Doğrulama:"))
        self.auth_combo = QComboBox()
        self.auth_combo.addItems(["Windows", "SQL Server"])
        self.auth_combo.currentTextChanged.connect(self.on_auth_type_changed)
        layout.addWidget(self.auth_combo)
        
        # Username (SQL Server Auth için)
        layout.addWidget(QLabel("Kullanıcı Adı:"))
        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText("SQL Server kullanıcı adı")
        self.username_input.setEnabled(False)
        self.username_input.returnPressed.connect(self.connect_to_server)
        layout.addWidget(self.username_input)
        
        # Password (SQL Server Auth için)
        layout.addWidget(QLabel("Şifre:"))
        self.password_input = QLineEdit()
        self.password_input.setPlaceholderText("SQL Server şifresi")
        self.password_input.setEchoMode(QLineEdit.Password)
        self.password_input.setEnabled(False)
        self.password_input.returnPressed.connect(self.connect_to_server)
        layout.addWidget(self.password_input)
        
        # Bağlan butonu
        self.connect_btn = QPushButton("Bağlan")
        self.connect_btn.clicked.connect(self.connect_to_server)
        layout.addWidget(self.connect_btn)
        
        # Bağlantı durumu
        self.connection_status = QLabel("Bağlantı Yok")
        self.connection_status.setStyleSheet("color: red; font-weight: bold;")
        layout.addWidget(self.connection_status)
        
        layout.addStretch()
        group.setLayout(layout)
        return group
    
    def on_auth_type_changed(self, text):
        """Kimlik doğrulama tipi değiştiğinde"""
        if text == "SQL Server":
            self.username_input.setEnabled(True)
            self.password_input.setEnabled(True)
        else:
            self.username_input.setEnabled(False)
            self.password_input.setEnabled(False)
    
    def load_saved_connection(self):
        """Kaydedilmiş bağlantı ayarlarını yükle"""
        config = ConfigManager.load_connection()
        if config:
            self.server_input.setText(config.get("server", ""))
            auth_type = config.get("auth_type", "Windows")
            if auth_type in ["Windows", "SQL Server"]:
                index = self.auth_combo.findText(auth_type)
                if index >= 0:
                    self.auth_combo.setCurrentIndex(index)
            self.username_input.setText(config.get("username", ""))
            self.password_input.setText(config.get("password", ""))
    
    def on_database_selected(self, database):
        """Veritabanı seçildiğinde aktif veritabanını değiştir"""
        if not database or database.startswith("--"):
            return
        
        if not self.sql_conn.is_connected():
            return
        
        # Veritabanını değiştir
        success, message = self.sql_conn.change_database(database)
        
        if success:
            self.statusBar().showMessage(f"Aktif veritabanı: {database}")
        else:
            QMessageBox.warning(self, "Uyarı", message)
            self.statusBar().showMessage("Veritabanı değiştirilemedi")
    
    def on_category_selected(self, category):
        """Kategori seçildiğinde sorgu listesini güncelle"""
        self.predefined_combo.clear()
        
        if not category or category.startswith("-- Kategori seçin"):
            self.predefined_combo.addItem("-- Sorgu seçin veya kendi sorgunuzu yazın --")
            return
        
        # Kategori adından sorgu sayısını kaldır
        category_name = category.split(" (")[0]
        
        all_queries = get_all_queries()
        
        if category_name == "Tüm Sorgular":
            # Tüm sorguları göster (kategori başlıkları hariç)
            queries = sorted([q for q in all_queries.keys() if not q.startswith("===")])
            self.predefined_combo.addItem(f"-- {len(queries)} sorgu bulundu --")
            self.predefined_combo.addItems(queries)
        else:
            # Seçili kategorideki sorguları göster (sistem ve kullanıcı sorgularını birlikte)
            category_queries = sorted(self.get_queries_by_category(category_name, all_queries))
            self.predefined_combo.addItem(f"-- {len(category_queries)} sorgu bulundu --")
            self.predefined_combo.addItems(category_queries)
    
    def get_queries_by_category(self, category, all_queries):
        """Kategoriye göre sorguları filtrele"""
        queries = []
        
        # Sistem sorgularını kategoriye göre filtrele
        in_category = False
        for query_name in all_queries.keys():
            if query_name.startswith("==="):
                # Kategori başlığı bulundu
                if category in query_name:
                    in_category = True
                else:
                    in_category = False
            elif in_category and not query_name.startswith("==="):
                # Bu kategorideki bir sorgu
                queries.append(query_name)
        
        # Kullanıcı sorgularını kategoriye göre filtrele
        user_queries = load_user_queries()
        for name, data in user_queries.items():
            if isinstance(data, dict):
                query_category = data.get("category", "Kullanıcı Sorguları")
                if query_category == category:
                    queries.append(name)
        
        return sorted(queries)
    
    def on_predefined_query_selected(self, text):
        """Hazır sorgu seçildiğinde"""
        # Sorgu sayısı göstergelerini atla
        if text and not text.startswith("--"):
            all_queries = get_all_queries()
            if text in all_queries:
                # Sorguyu editöre yükle
                self.query_editor.blockSignals(True)  # Signal'leri geçici olarak durdur
                self.query_editor.setPlainText(all_queries[text])
                self.query_editor.blockSignals(False)
                
                # Seçili sorgu adını kaydet
                self.selected_query_name = text
                self.edit_mode = False
                
                # Editörü read-only yap
                self.query_editor.setReadOnly(True)
                
                # Buton metnini "Sorguyu Düzenle" olarak değiştir
                self.add_query_btn.setText("Sorguyu Düzenle")
        else:
            # Boş seçim yapıldığında normal moda dön
            self.selected_query_name = None
            self.edit_mode = False
            self.query_editor.setReadOnly(False)
            self.add_query_btn.setText("Sorguyu Kaydet")
    
    def select_category_dialog(self, title, message):
        """Kategori seçimi dialog'u"""
        dialog = QDialog(self)
        dialog.setWindowTitle(title)
        dialog.setMinimumWidth(400)
        
        layout = QVBoxLayout()
        
        # Mesaj
        layout.addWidget(QLabel(message))
        
        # Kategori seçimi
        category_group = QGroupBox("Mevcut Kategoriler")
        category_layout = QVBoxLayout()
        
        category_combo = QComboBox()
        
        # Sistem kategorilerini ekle (=== ile başlayanlar)
        all_queries = get_all_queries()
        system_categories = []
        for query_name in all_queries.keys():
            if query_name.startswith("==="):
                category = query_name.replace("===", "").strip()
                system_categories.append(category)
        
        # Kullanıcı kategorilerini ekle
        user_categories = get_user_query_categories()
        
        # Tüm kategorileri birleştir
        all_categories = sorted(set(system_categories + user_categories))
        category_combo.addItems(all_categories)
        
        category_layout.addWidget(category_combo)
        category_group.setLayout(category_layout)
        layout.addWidget(category_group)
        
        # Yeni kategori oluşturma
        new_category_group = QGroupBox("Veya Yeni Kategori Oluştur")
        new_category_layout = QVBoxLayout()
        
        new_category_input = QLineEdit()
        new_category_input.setPlaceholderText("Yeni kategori adı...")
        new_category_layout.addWidget(new_category_input)
        
        new_category_group.setLayout(new_category_layout)
        layout.addWidget(new_category_group)
        
        # Butonlar
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(dialog.accept)
        button_box.rejected.connect(dialog.reject)
        layout.addWidget(button_box)
        
        dialog.setLayout(layout)
        
        if dialog.exec_() == QDialog.Accepted:
            # Yeni kategori girilmişse onu kullan
            new_cat = new_category_input.text().strip()
            if new_cat:
                return new_cat
            # Yoksa seçili kategoriye kaydet
            return category_combo.currentText()
        
        return None
    
    def save_current_query(self):
        """Mevcut sorguyu kullanıcı sorgularına kaydet veya düzenleme modunu aç"""
        query = self.query_editor.toPlainText().strip()
        
        # Eğer bir sorgu seçiliyse ve düzenleme modunda değilse, düzenleme modunu aç
        if self.selected_query_name and not self.edit_mode:
            self.edit_mode = True
            self.query_editor.setReadOnly(False)
            self.add_query_btn.setText("Sorguyu Kaydet")
            return
        
        # Kaydetme işlemi
        if not query:
            QMessageBox.warning(self, "Uyarı", "Kaydetmek için önce bir sorgu yazmalısınız!")
            return
        
        # Eğer düzenleme modundaysa, mevcut sorguyu güncelle
        if self.selected_query_name and self.edit_mode:
            # Kategori seçimi dialog'u
            category = self.select_category_dialog("Sorgu Kategorisi", "Düzenlenen sorgunun kategorisi:")
            if category:
                if save_user_query(self.selected_query_name, query, category):
                    QMessageBox.information(self, "Başarılı", f"'{self.selected_query_name}' sorgusu güncellendi!")
                    # Editörü tekrar read-only yap
                    self.query_editor.setReadOnly(True)
                    self.edit_mode = False
                    self.add_query_btn.setText("Sorguyu Düzenle")
                    # Kategorileri güncelle
                    self.update_categories()
                else:
                    QMessageBox.critical(self, "Hata", "Sorgu güncellenemedi!")
        else:
            # Yeni sorgu kaydet
            name, ok = QInputDialog.getText(self, "Sorgu Kaydet", "Sorgu adı:")
            if ok and name:
                name = name.strip()
                if not name:
                    QMessageBox.warning(self, "Uyarı", "Sorgu adı boş olamaz!")
                    return
                
                # Kategori seçimi
                category = self.select_category_dialog("Sorgu Kategorisi", "Bu sorguyu hangi kategoriye eklemek istersiniz?")
                if category:
                    if save_user_query(name, query, category):
                        QMessageBox.information(self, "Başarılı", f"'{name}' sorgusu '{category}' kategorisine kaydedildi!")
                        # Kategorileri güncelle
                        self.update_categories()
                        # Yeni eklenen kategoriye geç ve sorguyu seç
                        cat_index = self.category_combo.findText(category)
                        if cat_index >= 0:
                            self.category_combo.setCurrentIndex(cat_index)
                        query_index = self.predefined_combo.findText(name)
                        if query_index >= 0:
                            self.predefined_combo.setCurrentIndex(query_index)
                    else:
                        QMessageBox.critical(self, "Hata", "Sorgu kaydedilemedi!")
    
    def update_categories(self):
        """Kategori listesini güncelle"""
        current_category = self.category_combo.currentText()
        # Parantez içindeki sayıyı kaldır
        if current_category and " (" in current_category:
            current_category = current_category.split(" (")[0]
        
        self.category_combo.clear()
        self.category_combo.addItem("-- Kategori seçin --")
        
        all_queries = get_all_queries()
        
        # Toplam sorgu sayısı (kategori başlıkları hariç)
        total_queries = len([q for q in all_queries.keys() if not q.startswith("===")])
        
        # Sabit kategoriler
        self.category_combo.addItem(f"Tüm Sorgular ({total_queries})")
        
        # Kategori sorgu sayılarını hesapla
        category_counts = {}
        
        # Sistem kategorileri için sorgu sayıları
        in_category = None
        for query_name in all_queries.keys():
            if query_name.startswith("==="):
                category = query_name.replace("===", "").strip()
                in_category = category
                if category not in category_counts:
                    category_counts[category] = 0
            elif in_category and not query_name.startswith("==="):
                category_counts[in_category] += 1
        
        # Kullanıcı sorguları için kategori sayıları
        user_queries = load_user_queries()
        for name, data in user_queries.items():
            if isinstance(data, dict):
                cat = data.get("category", "Kullanıcı Sorguları")
                category_counts[cat] = category_counts.get(cat, 0) + 1
        
        # Alfabetik sıralı kategorileri ekle
        for category in sorted(category_counts.keys()):
            count = category_counts[category]
            self.category_combo.addItem(f"{category} ({count})")
        
        # Önceki seçimi geri yükle
        if current_category and not current_category.startswith("--"):
            for i in range(self.category_combo.count()):
                item_text = self.category_combo.itemText(i)
                if item_text.startswith(current_category + " ("):
                    self.category_combo.setCurrentIndex(i)
                    break
    
    def load_databases(self):
        """Sunucudaki veritabanlarını yükle"""
        success, databases, error = self.sql_conn.get_databases()
        
        if success:
            self.database_combo.clear()
            self.database_combo.addItem("-- Veritabanı seçin --")
            self.database_combo.addItems(databases)
            
            # Mevcut bağlı olunan veritabanını seç
            current_db = self.sql_conn.database
            index = self.database_combo.findText(current_db)
            if index >= 0:
                self.database_combo.setCurrentIndex(index)
            
            # Veritabanı panelini göster
            self.database_widget.setVisible(True)
        else:
            QMessageBox.warning(self, "Uyarı", f"Veritabanları alınamadı: {error}")
    
    def update_queries_combo(self):
        """Sorgular combo box'ını güncelle (eski metod - kategorilerle güncellendi)"""
        # Artık update_categories kullanıyoruz
        self.update_categories()
    
    def manage_queries(self):
        """Sorgu yönetim dialog'unu aç"""
        user_queries = load_user_queries()
        
        if not user_queries:
            QMessageBox.information(self, "Bilgi", "Henüz kaydedilmiş sorgu bulunmamaktadır.")
            return
        
        # Dialog oluştur
        dialog = QDialog(self)
        dialog.setWindowTitle("Sorguları Yönet")
        dialog.setMinimumWidth(500)
        dialog.setMinimumHeight(400)
        
        layout = QVBoxLayout()
        
        # Başlık
        title_label = QLabel("Kaydedilmiş Sorgular:")
        title_label.setStyleSheet("font-weight: bold; font-size: 12pt;")
        layout.addWidget(title_label)
        
        # Sorgu listesi
        query_list = QListWidget()
        query_list.addItems(sorted(user_queries.keys()))
        layout.addWidget(query_list)
        
        # Butonlar
        btn_layout = QHBoxLayout()
        
        rename_btn = QPushButton("İsmi Değiştir")
        rename_btn.clicked.connect(lambda: self.rename_query_dialog(dialog, query_list, user_queries))
        btn_layout.addWidget(rename_btn)
        
        delete_btn = QPushButton("Sil")
        delete_btn.clicked.connect(lambda: self.delete_query_dialog(dialog, query_list, user_queries))
        btn_layout.addWidget(delete_btn)
        
        btn_layout.addStretch()
        
        close_btn = QPushButton("Kapat")
        close_btn.clicked.connect(dialog.accept)
        btn_layout.addWidget(close_btn)
        
        layout.addLayout(btn_layout)
        dialog.setLayout(layout)
        dialog.exec_()
    
    def rename_query_dialog(self, parent_dialog, query_list, user_queries):
        """Sorgu ismini değiştir"""
        current_item = query_list.currentItem()
        if not current_item:
            QMessageBox.warning(self, "Uyarı", "Lütfen bir sorgu seçin!")
            return
        
        old_name = current_item.text()
        new_name, ok = QInputDialog.getText(
            self, 
            "Sorgu İsmini Değiştir", 
            f"Yeni isim:",
            text=old_name
        )
        
        if ok and new_name:
            new_name = new_name.strip()
            if not new_name:
                QMessageBox.warning(self, "Uyarı", "İsim boş olamaz!")
                return
            
            if new_name == old_name:
                return  # Aynı isim, değişiklik yok
            
            # Hazır sorgularla çakışma kontrolü
            if new_name in PREDEFINED_QUERIES:
                QMessageBox.warning(self, "Uyarı", f"'{new_name}' ismi hazır sorgularda zaten var!")
                return
            
            # Kullanıcı sorgularında çakışma kontrolü
            if new_name in user_queries:
                QMessageBox.warning(self, "Uyarı", f"'{new_name}' ismi zaten kullanılıyor!")
                return
            
            # İsmi değiştir
            if rename_user_query(old_name, new_name):
                QMessageBox.information(self, "Başarılı", f"Sorgu ismi '{old_name}' → '{new_name}' olarak değiştirildi.")
                
                # Listeyi güncelle
                query_list.clear()
                updated_queries = load_user_queries()
                query_list.addItems(sorted(updated_queries.keys()))
                
                # ComboBox'ı güncelle
                self.update_queries_combo()
                
                # Eğer seçili sorgu değiştirildiyse, yeni ismi seç
                if self.selected_query_name == old_name:
                    self.selected_query_name = new_name
                    index = self.predefined_combo.findText(new_name)
                    if index >= 0:
                        self.predefined_combo.setCurrentIndex(index)
            else:
                QMessageBox.critical(self, "Hata", "Sorgu ismi değiştirilemedi!")
    
    def delete_query_dialog(self, parent_dialog, query_list, user_queries):
        """Sorguyu sil"""
        current_item = query_list.currentItem()
        if not current_item:
            QMessageBox.warning(self, "Uyarı", "Lütfen bir sorgu seçin!")
            return
        
        query_name = current_item.text()
        
        reply = QMessageBox.question(
            self,
            "Sorguyu Sil",
            f"'{query_name}' sorgusunu silmek istediğinize emin misiniz?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            if delete_user_query(query_name):
                QMessageBox.information(self, "Başarılı", f"'{query_name}' sorgusu silindi.")
                
                # Listeyi güncelle
                query_list.clear()
                updated_queries = load_user_queries()
                if updated_queries:
                    query_list.addItems(sorted(updated_queries.keys()))
                else:
                    parent_dialog.accept()  # Liste boşsa dialog'u kapat
                
                # ComboBox'ı güncelle
                self.update_queries_combo()
                
                # Eğer silinen sorgu seçiliyse, seçimi temizle
                if self.selected_query_name == query_name:
                    self.selected_query_name = None
                    self.edit_mode = False
                    self.query_editor.setReadOnly(False)
                    self.add_query_btn.setText("Sorguyu Kaydet")
                    self.query_editor.clear()
            else:
                QMessageBox.critical(self, "Hata", "Sorgu silinemedi!")
    
    def connect_to_server(self):
        """SQL Server'a bağlan"""
        server = self.server_input.text().strip()
        auth_type = self.auth_combo.currentText()
        username = self.username_input.text().strip()
        password = self.password_input.text()
        
        if not server:
            QMessageBox.warning(self, "Uyarı", "Lütfen sunucu adresini girin!")
            return
        
        if auth_type == "SQL Server" and (not username or not password):
            QMessageBox.warning(self, "Uyarı", "SQL Server Authentication için kullanıcı adı ve şifre gereklidir!")
            return
        
        self.connect_btn.setEnabled(False)
        self.statusBar().showMessage("Bağlanılıyor...")
        
        # Varsayılan olarak master veritabanına bağlan
        database = "master"
        
        success, message = self.sql_conn.connect(
            server, database, auth_type, username, password
        )
        
        if success:
            # Bağlantı ayarlarını kaydet (veritabanı olmadan)
            ConfigManager.save_connection(server, "", auth_type, username, password)
            
            self.connection_status.setText("Bağlı ✓")
            self.connection_status.setStyleSheet("color: green; font-weight: bold;")
            self.execute_btn.setEnabled(True)
            self.add_query_btn.setEnabled(True)
            self.manage_queries_btn.setEnabled(True)
            self.auto_start_btn.setEnabled(True)
            self.statusBar().showMessage(f"Bağlantı başarılı: {server} (Veritabanı seçin)")
            
            # Veritabanı listesini yükle
            self.load_databases()
            
            # Hazır sorgular panelini göster ve güncelle
            self.queries_widget.setVisible(True)
            self.update_categories()
        else:
            self.connection_status.setText("Bağlantı Hatası")
            self.connection_status.setStyleSheet("color: red; font-weight: bold;")
            QMessageBox.critical(self, "Bağlantı Hatası", message)
            self.statusBar().showMessage("Bağlantı başarısız")
        
        self.connect_btn.setEnabled(True)
    
    def execute_query(self):
        """SQL sorgusunu çalıştır"""
        query = self.query_editor.toPlainText().strip()
        
        if not query:
            QMessageBox.warning(self, "Uyarı", "Lütfen bir SQL sorgusu girin!")
            return
        
        if not self.sql_conn.is_connected():
            QMessageBox.warning(self, "Uyarı", "Önce SQL Server'a bağlanmalısınız!")
            return
        
        # UI'ı güncelle
        self.execute_btn.setEnabled(False)
        self.export_excel_btn.setEnabled(False)
        self.statusBar().showMessage("Sorgu çalıştırılıyor...")
        self.error_text.clear()
        self.results_table.setRowCount(0)
        self.results_table.setColumnCount(0)
        self.current_results_columns = None
        self.current_results_rows = None
        self.full_texts = {}
        
        # Thread'de sorguyu çalıştır
        self.query_thread = QueryThread(self.sql_conn, query)
        self.query_thread.finished.connect(self.on_query_finished)
        self.query_thread.start()
    
    def on_query_finished(self, success, result, error):
        """Sorgu tamamlandığında"""
        self.execute_btn.setEnabled(True)
        
        if success:
            if isinstance(result, tuple) and len(result) == 2:
                # SELECT sorgusu sonucu
                columns, rows = result
                self.display_results(columns, rows)
                self.statusBar().showMessage(f"Sorgu başarıyla tamamlandı. {len(rows)} satır döndü.")
            else:
                # INSERT, UPDATE, DELETE gibi sorgular
                self.statusBar().showMessage(str(result))
                QMessageBox.information(self, "Başarılı", str(result))
        else:
            # Hata durumu
            self.error_text.setPlainText(error)
            self.statusBar().showMessage("Sorgu hatası!")
        
    def start_auto_execution(self):
        """Otomatik sorgu çalıştırmayı başlat"""
        # Validasyon
        interval_text = self.interval_input.text().strip()
        duration_text = self.duration_input.text().strip()
        
        if not interval_text or not duration_text:
            QMessageBox.warning(self, "Uyarı", "Lütfen interval ve süre değerlerini girin!")
            return
        
        try:
            interval = int(interval_text)
            duration = int(duration_text)
        except ValueError:
            QMessageBox.warning(self, "Uyarı", "Lütfen geçerli sayısal değerler girin!")
            return
        
        if interval <= 0 or duration <= 0:
            QMessageBox.warning(self, "Uyarı", "Interval ve süre değerleri 0'dan büyük olmalıdır!")
            return
        
        if interval > duration:
            QMessageBox.warning(self, "Uyarı", "Interval, toplam süreden küçük olmalıdır!")
            return
        
        query = self.query_editor.toPlainText().strip()
        if not query:
            QMessageBox.warning(self, "Uyarı", "Lütfen bir SQL sorgusu girin!")
            return
        
        if not self.sql_conn.is_connected():
            QMessageBox.warning(self, "Uyarı", "Önce SQL Server'a bağlanmalısınız!")
            return
        
        # Timer'ları başlat
        self.auto_duration_seconds = duration
        self.auto_start_time = datetime.now()
        
        # İlk sorguyu hemen çalıştır
        self.execute_query()
        
        # Interval timer'ı başlat (her X saniyede bir)
        self.auto_timer.start(interval * 1000)  # milisaniye cinsinden
        
        # Duration timer'ı başlat (toplam süre sonunda durdur)
        self.auto_duration_timer.start(duration * 1000)
        
        # UI güncelle
        self.auto_start_btn.setEnabled(False)
        self.auto_stop_btn.setEnabled(True)
        self.interval_input.setEnabled(False)
        self.duration_input.setEnabled(False)
        self.update_auto_status()
    
    def stop_auto_execution(self):
        """Otomatik sorgu çalıştırmayı durdur"""
        self.auto_timer.stop()
        self.auto_duration_timer.stop()
        
        # UI güncelle
        self.auto_start_btn.setEnabled(True)
        self.auto_stop_btn.setEnabled(False)
        self.interval_input.setEnabled(True)
        self.duration_input.setEnabled(True)
        self.auto_status_label.setText("")
        self.auto_start_time = None
    
    def auto_execute_query(self):
        """Otomatik çalıştırma için sorguyu çalıştır"""
        if not self.sql_conn.is_connected():
            self.stop_auto_execution()
            QMessageBox.warning(self, "Uyarı", "Bağlantı kesildi. Otomatik çalıştırma durduruldu.")
            return
        
        query = self.query_editor.toPlainText().strip()
        if not query:
            self.stop_auto_execution()
            QMessageBox.warning(self, "Uyarı", "Sorgu boş. Otomatik çalıştırma durduruldu.")
            return
        
        # Sorguyu çalıştır (normal execute_query fonksiyonunu kullan)
        self.execute_query()
    
    def update_auto_status(self):
        """Otomatik çalıştırma durumunu güncelle"""
        if self.auto_timer.isActive() and self.auto_start_time:
            elapsed = (datetime.now() - self.auto_start_time).total_seconds()
            remaining = max(0, self.auto_duration_seconds - elapsed)
            
            if remaining > 0:
                minutes = int(remaining // 60)
                seconds = int(remaining % 60)
                self.auto_status_label.setText(f"Çalışıyor... Kalan: {minutes:02d}:{seconds:02d}")
            else:
                self.auto_status_label.setText("Tamamlandı")
        else:
            self.auto_status_label.setText("")
    
    def display_results(self, columns, rows):
        """Sonuçları tabloda göster"""
        self.results_table.setColumnCount(len(columns))
        self.results_table.setHorizontalHeaderLabels(columns)
        self.results_table.setRowCount(len(rows))
        
        # Sonuçları sakla (Excel export için)
        self.current_results_columns = columns
        self.current_results_rows = rows
        
        # Tam metinleri saklamak için dictionary
        self.full_texts = {}
        
        MAX_DISPLAY_LENGTH = 50
        
        for row_idx, row in enumerate(rows):
            for col_idx, value in enumerate(row):
                if value is None:
                    display_text = ""
                    full_text = ""
                else:
                    full_text = str(value)
                    # 50 karakterden uzunsa kısalt
                    if len(full_text) > MAX_DISPLAY_LENGTH:
                        display_text = full_text[:MAX_DISPLAY_LENGTH] + "..."
                        # Tam metni sakla (çift tıklama için)
                        self.full_texts[(row_idx, col_idx)] = full_text
                    else:
                        display_text = full_text
                
                item = QTableWidgetItem(display_text)
                # Uzun metinler için tooltip ekle
                if len(full_text) > MAX_DISPLAY_LENGTH:
                    item.setToolTip(f"Çift tıklayarak tam metni görebilirsiniz\n\n{full_text[:500]}...")
                self.results_table.setItem(row_idx, col_idx, item)
        
        # Çift tıklama event'ini bağla (eğer daha önce bağlanmadıysa)
        try:
            self.results_table.itemDoubleClicked.disconnect()
        except:
            pass
        self.results_table.itemDoubleClicked.connect(self.on_cell_double_clicked)
        
        # Sütun genişliklerini ayarla
        self.results_table.resizeColumnsToContents()
        header = self.results_table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Interactive)
        
        # Excel export butonunu aktif et
        self.export_excel_btn.setEnabled(True)
    
    def on_cell_double_clicked(self, item):
        """Hücre çift tıklandığında tam metni göster"""
        row = item.row()
        col = item.column()
        
        # Tam metni kontrol et
        if (row, col) in self.full_texts:
            full_text = self.full_texts[(row, col)]
        else:
            # Eğer kısaltılmamışsa mevcut metni göster
            full_text = item.text()
        
        # Dialog oluştur
        dialog = QDialog(self)
        dialog.setWindowTitle(f"Tam Metin - Satır {row + 1}, Sütun {col + 1}")
        dialog.setMinimumWidth(600)
        dialog.setMinimumHeight(400)
        
        layout = QVBoxLayout()
        
        # Metin alanı
        text_edit = QTextEdit()
        text_edit.setFont(QFont("Consolas", 10))
        text_edit.setPlainText(full_text)
        text_edit.setReadOnly(True)
        text_edit.setLineWrapMode(QTextEdit.NoWrap)
        layout.addWidget(text_edit)
        
        # Butonlar
        button_box = QDialogButtonBox(QDialogButtonBox.Ok)
        button_box.accepted.connect(dialog.accept)
        layout.addWidget(button_box)
        
        dialog.setLayout(layout)
        dialog.exec_()
    
    def clear_query(self):
        """Sorgu editörünü temizle"""
        # Otomatik çalıştırmayı durdur
        if self.auto_timer.isActive():
            self.stop_auto_execution()
        
        # Seçili sorgu durumunu sıfırla
        self.selected_query_name = None
        self.edit_mode = False
        self.query_editor.setReadOnly(False)
        self.add_query_btn.setText("Sorguyu Kaydet")
        
        self.query_editor.clear()
        self.results_table.setRowCount(0)
        self.results_table.setColumnCount(0)
        self.error_text.clear()
        self.export_excel_btn.setEnabled(False)
        self.current_results_columns = None
        self.current_results_rows = None
        self.full_texts = {}
    
    def export_to_excel(self):
        """Sorgu sonuçlarını Excel'e aktar"""
        if not hasattr(self, 'current_results_columns') or not self.current_results_columns:
            QMessageBox.warning(self, "Uyarı", "Aktarılacak sonuç bulunamadı!")
            return
        
        # Dosya kaydetme dialogu
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        default_filename = f"SQL_Sonuclar_{timestamp}.xlsx"
        
        filename, _ = QFileDialog.getSaveFileName(
            self,
            "Excel Dosyası Olarak Kaydet",
            default_filename,
            "Excel Dosyaları (*.xlsx);;Tüm Dosyalar (*)"
        )
        
        if not filename:
            return  # Kullanıcı iptal etti
        
        try:
            # DataFrame oluştur
            df = pd.DataFrame(self.current_results_rows, columns=self.current_results_columns)
            
            # Excel'e yaz
            df.to_excel(filename, index=False, engine='openpyxl')
            
            QMessageBox.information(
                self, 
                "Başarılı", 
                f"Sonuçlar başarıyla Excel dosyasına aktarıldı!\n\nDosya: {filename}\nSatır sayısı: {len(df)}"
            )
            self.statusBar().showMessage(f"Excel dosyası kaydedildi: {filename}")
            
        except Exception as e:
            QMessageBox.critical(
                self, 
                "Hata", 
                f"Excel dosyası kaydedilirken hata oluştu:\n{str(e)}"
            )
            self.statusBar().showMessage("Excel export hatası!")
    
    def closeEvent(self, event):
        """Uygulama kapatılırken"""
        # Otomatik çalıştırmayı durdur
        if self.auto_timer.isActive():
            self.stop_auto_execution()
        
        if self.sql_conn:
            self.sql_conn.disconnect()
        event.accept()
    
    def show_help(self):
        """Kullanım kılavuzunu göster"""
        help_text = self.get_help_content()
        
        dialog = QDialog(self)
        dialog.setWindowTitle("Kullanım Kılavuzu")
        dialog.setMinimumWidth(800)
        dialog.setMinimumHeight(600)
        
        layout = QVBoxLayout()
        
        # Metin alanı
        text_edit = QTextEdit()
        text_edit.setFont(QFont("Segoe UI", 10))
        text_edit.setReadOnly(True)
        text_edit.setHtml(help_text)
        layout.addWidget(text_edit)
        
        # Butonlar
        button_box = QDialogButtonBox(QDialogButtonBox.Ok)
        button_box.accepted.connect(dialog.accept)
        layout.addWidget(button_box)
        
        dialog.setLayout(layout)
        dialog.exec_()
    
    def show_compatibility_info(self):
        """Sorgu uyumluluk bilgilerini göster"""
        compatibility_text = self.get_compatibility_content()
        
        dialog = QDialog(self)
        dialog.setWindowTitle("Sorgu Uyumluluğu")
        dialog.setMinimumWidth(800)
        dialog.setMinimumHeight(600)
        
        layout = QVBoxLayout()
        
        # Metin alanı
        text_edit = QTextEdit()
        text_edit.setFont(QFont("Consolas", 9))
        text_edit.setReadOnly(True)
        text_edit.setPlainText(compatibility_text)
        layout.addWidget(text_edit)
        
        # Butonlar
        button_box = QDialogButtonBox(QDialogButtonBox.Ok)
        button_box.accepted.connect(dialog.accept)
        layout.addWidget(button_box)
        
        dialog.setLayout(layout)
        dialog.exec_()
    
    def show_about(self):
        """Hakkında dialog'unu göster"""
        about_text = """
        <h2>SQL Sunucu Takip Uygulaması</h2>
        <p><b>Versiyon:</b> 1.0</p>
        <p><b>Açıklama:</b> SQL Server üzerinde kapsamlı analizler yapmak, 
        hataları takip etmek ve özel sorgular çalıştırmak için geliştirilmiş 
        masaüstü uygulaması.</p>
        
        <h3>Özellikler:</h3>
        <ul>
            <li>SQL Server bağlantı yönetimi (Windows ve SQL Authentication)</li>
            <li>45+ hazır analiz sorgusu</li>
            <li>Özel sorgu kaydetme ve yönetimi</li>
            <li>Otomatik sorgu çalıştırma (zamanlayıcı ile)</li>
            <li>Excel'e aktarma</li>
            <li>Uzun metin görüntüleme (çift tıklama ile)</li>
            <li>Bağlantı ayarlarını kaydetme</li>
        </ul>
        
        <h3>Teknolojiler:</h3>
        <ul>
            <li>Python 3.8+</li>
            <li>PyQt5</li>
            <li>pyodbc</li>
            <li>pandas</li>
        </ul>
        
        <p><b>Geliştirici:</b> SQL Server Yönetim Araçları</p>
        """
        
        QMessageBox.about(self, "Hakkında", about_text)
    
    def get_help_content(self):
        """Yardım içeriğini oluştur"""
        all_queries = get_all_queries()
        query_count = len([q for q in all_queries.keys() if not q.startswith("===")])
        
        help_html = f"""
        <html>
        <head>
            <style>
                body {{ font-family: Segoe UI; font-size: 11pt; }}
                h1 {{ color: #2c3e50; border-bottom: 2px solid #3498db; padding-bottom: 10px; }}
                h2 {{ color: #34495e; margin-top: 20px; }}
                h3 {{ color: #7f8c8d; margin-top: 15px; }}
                code {{ background-color: #ecf0f1; padding: 2px 6px; border-radius: 3px; font-family: Consolas; }}
                .feature {{ background-color: #e8f5e9; padding: 10px; margin: 10px 0; border-left: 4px solid #4caf50; }}
                .warning {{ background-color: #fff3e0; padding: 10px; margin: 10px 0; border-left: 4px solid #ff9800; }}
                .info {{ background-color: #e3f2fd; padding: 10px; margin: 10px 0; border-left: 4px solid #2196f3; }}
                ul {{ line-height: 1.8; }}
                li {{ margin: 5px 0; }}
            </style>
        </head>
        <body>
            <h1>SQL Sunucu Takip Uygulaması - Kullanım Kılavuzu</h1>
            
            <div class="info">
                <h2>📋 Genel Bakış</h2>
                <p>Bu uygulama SQL Server üzerinde kapsamlı analizler yapmanızı, 
                performans sorunlarını tespit etmenizi ve sistem durumunu izlemenizi sağlar.</p>
                <p><b>Toplam Hazır Sorgu Sayısı:</b> {query_count}+</p>
            </div>
            
            <h2>🚀 Hızlı Başlangıç</h2>
            <ol>
                <li><b>Bağlantı Kurun:</b> SQL Server bilgilerinizi girin ve "Bağlan" butonuna tıklayın</li>
                <li><b>Sorgu Seçin:</b> Dropdown menüden hazır sorgulardan birini seçin veya kendi sorgunuzu yazın</li>
                <li><b>Çalıştırın:</b> F5 tuşuna basın veya "Sorguyu Çalıştır" butonuna tıklayın</li>
                <li><b>Sonuçları İnceleyin:</b> Sonuçlar tabloda görüntülenir, Excel'e aktarabilirsiniz</li>
            </ol>
            
            <h2>🔌 Bağlantı Yönetimi</h2>
            <div class="feature">
                <h3>Bağlantı Ayarları</h3>
                <ul>
                    <li><b>Sunucu:</b> SQL Server adresi (örn: localhost, 192.168.1.100, SERVERNAME\\INSTANCE)</li>
                    <li><b>Veritabanı:</b> Bağlanmak istediğiniz veritabanı (varsayılan: master)</li>
                    <li><b>Kimlik Doğrulama:</b> Windows veya SQL Server Authentication</li>
                    <li><b>Otomatik Kayıt:</b> İlk bağlantıda ayarlar otomatik kaydedilir</li>
                </ul>
            </div>
            
            <h2>📊 Hazır Analiz Sorguları</h2>
            <div class="feature">
                <h3>Kategoriler</h3>
                <ul>
                    <li><b>Performans Analizi:</b> CPU, bellek, I/O kullanımı, yavaş sorgular</li>
                    <li><b>Veritabanı Sağlık Durumu:</b> Dosya büyüme, index fragmentasyonu, statistics</li>
                    <li><b>Güvenlik Analizi:</b> Login'ler, kullanıcılar, izinler</li>
                    <li><b>Yedekleme ve Kurtarma:</b> Backup geçmişi, durum kontrolü</li>
                    <li><b>SQL Agent ve Job'lar:</b> Job durumları, başarısız job'lar</li>
                    <li><b>Always On / Availability Groups:</b> AG durumu, replica bilgileri</li>
                    <li><b>Replication Durumu:</b> Yayıncılar, aboneler</li>
                    <li><b>Connection Pool Analizi:</b> Bağlantı istatistikleri</li>
                    <li><b>Schema ve Obje Analizi:</b> Tablolar, stored procedure'ler, view'ler</li>
                    <li><b>Sistem Kaynakları:</b> CPU, bellek, network istatistikleri</li>
                </ul>
            </div>
            
            <h2>✏️ Özel Sorgu Yönetimi</h2>
            <div class="feature">
                <h3>Sorgu Kaydetme</h3>
                <ol>
                    <li>SQL sorgunuzu editöre yazın</li>
                    <li>"Sorguyu Kaydet" butonuna tıklayın</li>
                    <li>Sorgu adını girin</li>
                    <li>Sorgu kaydedilir ve dropdown menüde görünür</li>
                </ol>
                
                <h3>Sorgu Düzenleme</h3>
                <ol>
                    <li>Kaydedilmiş bir sorgu seçin</li>
                    <li>Editör otomatik olarak read-only olur</li>
                    <li>"Sorguyu Düzenle" butonuna tıklayın</li>
                    <li>Sorguyu düzenleyin ve "Sorguyu Kaydet" ile güncelleyin</li>
                </ol>
                
                <h3>Sorgu Yönetimi</h3>
                <ul>
                    <li><b>Sorguları Yönet:</b> Kaydedilmiş sorguları listele, isim değiştir, sil</li>
                    <li><b>İsim Değiştirme:</b> Sorgu listesinden seçip "İsmi Değiştir"</li>
                    <li><b>Silme:</b> Sorgu listesinden seçip "Sil"</li>
                </ul>
            </div>
            
            <h2>⏱️ Otomatik Sorgu Çalıştırma</h2>
            <div class="feature">
                <h3>Özellikler</h3>
                <ul>
                    <li><b>Interval:</b> Her kaç saniyede bir çalıştırılacak (1-3600 saniye)</li>
                    <li><b>Duration:</b> Toplam kaç saniye boyunca çalışacak (1-86400 saniye = 24 saat)</li>
                    <li><b>İlk Çalıştırma:</b> Başlatıldığında sorgu hemen çalıştırılır</li>
                    <li><b>Durum Göstergesi:</b> Kalan süre gerçek zamanlı gösterilir</li>
                    <li><b>Otomatik Durdurma:</b> Belirtilen süre sonunda otomatik durur</li>
                </ul>
                
                <h3>Kullanım</h3>
                <ol>
                    <li>Sorgunuzu yazın veya seçin</li>
                    <li>Interval ve Duration değerlerini girin</li>
                    <li>"Başlat" butonuna tıklayın</li>
                    <li>İstediğiniz zaman "Durdur" ile durdurabilirsiniz</li>
                </ol>
            </div>
            
            <h2>📤 Excel'e Aktarma</h2>
            <div class="feature">
                <ul>
                    <li>Sorgu çalıştırıldıktan sonra "Excel'e Aktar" butonu aktif olur</li>
                    <li>Butona tıklayın ve dosya konumunu seçin</li>
                    <li>Varsayılan dosya adı: <code>SQL_Sonuclar_YYYYMMDD_HHMMSS.xlsx</code></li>
                    <li>Tüm sonuçlar (uzun metinler dahil) Excel'e aktarılır</li>
                </ul>
            </div>
            
            <h2>📝 Sonuç Görüntüleme</h2>
            <div class="feature">
                <h3>Uzun Metinler</h3>
                <ul>
                    <li>50 karakterden uzun metinler otomatik kısaltılır</li>
                    <li>Format: <code>İlk 50 karakter...</code></li>
                    <li>Tam metni görmek için hücreye <b>çift tıklayın</b></li>
                    <li>Dialog penceresinde tam metin görüntülenir ve kopyalanabilir</li>
                </ul>
                
                <h3>Tablo Özellikleri</h3>
                <ul>
                    <li>Satır ve sütun seçimi</li>
                    <li>Alternatif satır renkleri</li>
                    <li>Otomatik sütun genişliği ayarlama</li>
                    <li>Manuel sütun genişliği ayarlama (sürükle-bırak)</li>
                </ul>
            </div>
            
            <h2>⌨️ Klavye Kısayolları</h2>
            <div class="info">
                <ul>
                    <li><b>F1:</b> Kullanım Kılavuzu</li>
                    <li><b>F5:</b> Sorguyu Çalıştır</li>
                    <li><b>Enter:</b> Bağlantı alanlarında bağlan</li>
                </ul>
            </div>
            
            <h2>⚠️ Önemli Notlar</h2>
            <div class="warning">
                <h3>İzinler</h3>
                <p>Çoğu sorgu için <code>VIEW SERVER STATE</code> veya <code>sysadmin</code> rolü gereklidir.</p>
                
                <h3>Uyumluluk</h3>
                <p>Bazı sorgular belirli SQL Server versiyonları veya özellikler gerektirebilir. 
                Detaylı bilgi için "Yardım > Sorgu Uyumluluğu" menüsüne bakın.</p>
                
                <h3>System Database'ler</h3>
                <p>Backup ve Job sorguları <code>msdb</code> veritabanına erişim gerektirir.</p>
            </div>
            
            <h2>🔧 Sorun Giderme</h2>
            <div class="info">
                <h3>Bağlantı Sorunları</h3>
                <ul>
                    <li>SQL Server'ın çalıştığından emin olun</li>
                    <li>Firewall ayarlarını kontrol edin</li>
                    <li>ODBC Driver 17 veya üzeri yüklü olmalı</li>
                    <li>Port numarasını kontrol edin (varsayılan: 1433)</li>
                </ul>
                
                <h3>Sorgu Hataları</h3>
                <ul>
                    <li>Hata mesajlarını "Hata Mesajları" bölümünde kontrol edin</li>
                    <li>İzin eksikliği olabilir - VIEW SERVER STATE kontrol edin</li>
                    <li>SQL Server versiyonunu kontrol edin: <code>SELECT @@VERSION</code></li>
                    <li>Özellik yüklü mü kontrol edin (Always On, Replication vb.)</li>
                </ul>
            </div>
            
            <h2>📞 Destek</h2>
            <p>Daha fazla bilgi için uygulama içindeki "Sorgu Uyumluluğu" bölümüne bakın 
            veya README.md dosyasını inceleyin.</p>
        </body>
        </html>
        """
        return help_html
    
    def get_compatibility_content(self):
        """Uyumluluk bilgilerini oluştur"""
        try:
            with open('QUERY_COMPATIBILITY.md', 'r', encoding='utf-8') as f:
                return f.read()
        except FileNotFoundError:
            return """
Sorgu Uyumluluk Rehberi

Genel Uyumluluk:
- Çoğu sorgu SQL Server 2008 ve üzeri versiyonlarda çalışır
- Bazı sorgular belirli gereksinimlere sahiptir

Gerekli İzinler:
- VIEW SERVER STATE veya sysadmin rolü
- msdb veritabanı sorguları için msdb erişimi
- distribution veritabanı sorguları için Replication yapılandırması

Özellik Bazlı Sorgular:
- Always On: SQL Server 2012+ Enterprise Edition
- Replication: Replication özelliği yüklü olmalı
- SQL Agent: SQL Agent servisi çalışıyor olmalı

Detaylı bilgi için QUERY_COMPATIBILITY.md dosyasına bakın.
            """


def main():
    """Ana fonksiyon"""
    app = QApplication(sys.argv)
    app.setStyle('Fusion')  # Modern görünüm için
    
    window = SQLServerApp()
    window.show()
    
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
