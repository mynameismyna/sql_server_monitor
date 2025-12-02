"""
SQL Server bağlantı yönetimi modülü
"""
import pyodbc
from typing import Optional, Dict, Any, Tuple
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class SQLConnection:
    """SQL Server bağlantı yönetimi sınıfı"""
    
    def __init__(self):
        self.connection: Optional[pyodbc.Connection] = None
        self.server: str = ""
        self.database: str = ""
        self.auth_type: str = "Windows"  # Windows veya SQL Server
        self.username: str = ""
        self.password: str = ""
    
    def connect(self, server: str, database: str, auth_type: str = "Windows", 
                username: str = "", password: str = "") -> Tuple[bool, str]:
        """
        SQL Server'a bağlan
        
        Args:
            server: SQL Server adresi
            database: Veritabanı adı
            auth_type: Kimlik doğrulama tipi ("Windows" veya "SQL Server")
            username: SQL Server kullanıcı adı (SQL Server Authentication için)
            password: SQL Server şifresi (SQL Server Authentication için)
        
        Returns:
            (başarılı mı, mesaj) tuple'ı
        """
        try:
            # Mevcut bağlantıyı kapat
            if self.connection:
                self.connection.close()
            
            self.server = server
            self.database = database
            self.auth_type = auth_type
            self.username = username
            self.password = password
            
            # Connection string oluştur
            if auth_type == "Windows":
                conn_str = (
                    f"DRIVER={{ODBC Driver 17 for SQL Server}};"
                    f"SERVER={server};"
                    f"DATABASE={database};"
                    f"Trusted_Connection=yes;"
                )
            else:  # SQL Server Authentication
                conn_str = (
                    f"DRIVER={{ODBC Driver 17 for SQL Server}};"
                    f"SERVER={server};"
                    f"DATABASE={database};"
                    f"UID={username};"
                    f"PWD={password};"
                )
            
            # Bağlantıyı aç
            self.connection = pyodbc.connect(conn_str, timeout=10)
            logger.info(f"SQL Server'a başarıyla bağlanıldı: {server}/{database}")
            return True, "Bağlantı başarılı!"
            
        except pyodbc.Error as e:
            error_msg = f"Bağlantı hatası: {str(e)}"
            logger.error(error_msg)
            return False, error_msg
        except Exception as e:
            error_msg = f"Beklenmeyen hata: {str(e)}"
            logger.error(error_msg)
            return False, error_msg
    
    def execute_query(self, query: str) -> Tuple[bool, Any, Optional[str]]:
        """
        SQL sorgusu çalıştır
        
        Args:
            query: Çalıştırılacak SQL sorgusu
        
        Returns:
            (başarılı mı, sonuçlar, hata mesajı) tuple'ı
            Sonuçlar: List of tuples veya None
        """
        if not self.connection:
            return False, None, "Önce SQL Server'a bağlanmalısınız!"
        
        try:
            cursor = self.connection.cursor()
            cursor.execute(query)
            
            # SELECT sorgusu ise sonuçları al
            if query.strip().upper().startswith('SELECT'):
                results = cursor.fetchall()
                columns = [column[0] for column in cursor.description]
                return True, (columns, results), None
            else:
                # INSERT, UPDATE, DELETE gibi sorgular için commit
                self.connection.commit()
                affected_rows = cursor.rowcount
                return True, f"{affected_rows} satır etkilendi.", None
                
        except pyodbc.Error as e:
            error_msg = f"SQL Hatası: {str(e)}"
            logger.error(error_msg)
            return False, None, error_msg
        except Exception as e:
            error_msg = f"Beklenmeyen hata: {str(e)}"
            logger.error(error_msg)
            return False, None, error_msg
    
    def disconnect(self):
        """Bağlantıyı kapat"""
        if self.connection:
            self.connection.close()
            self.connection = None
            logger.info("SQL Server bağlantısı kapatıldı")
    
    def is_connected(self) -> bool:
        """Bağlantı durumunu kontrol et"""
        if not self.connection:
            return False
        try:
            cursor = self.connection.cursor()
            cursor.execute("SELECT 1")
            return True
        except:
            return False
    
    def get_databases(self) -> Tuple[bool, list, Optional[str]]:
        """
        Sunucudaki veritabanı listesini al
        
        Returns:
            (başarılı mı, veritabanı listesi, hata mesajı) tuple'ı
        """
        if not self.connection:
            return False, [], "Önce SQL Server'a bağlanmalısınız!"
        
        try:
            cursor = self.connection.cursor()
            cursor.execute("SELECT name FROM sys.databases ORDER BY name")
            databases = [row[0] for row in cursor.fetchall()]
            return True, databases, None
        except pyodbc.Error as e:
            error_msg = f"Veritabanları alınırken hata: {str(e)}"
            logger.error(error_msg)
            return False, [], error_msg
        except Exception as e:
            error_msg = f"Beklenmeyen hata: {str(e)}"
            logger.error(error_msg)
            return False, [], error_msg
    
    def change_database(self, database: str) -> Tuple[bool, str]:
        """
        Aktif veritabanını değiştir
        
        Args:
            database: Yeni veritabanı adı
        
        Returns:
            (başarılı mı, mesaj) tuple'ı
        """
        if not self.connection:
            return False, "Önce SQL Server'a bağlanmalısınız!"
        
        try:
            cursor = self.connection.cursor()
            cursor.execute(f"USE [{database}]")
            self.database = database
            logger.info(f"Veritabanı değiştirildi: {database}")
            return True, f"Veritabanı değiştirildi: {database}"
        except pyodbc.Error as e:
            error_msg = f"Veritabanı değiştirme hatası: {str(e)}"
            logger.error(error_msg)
            return False, error_msg
        except Exception as e:
            error_msg = f"Beklenmeyen hata: {str(e)}"
            logger.error(error_msg)
            return False, error_msg

