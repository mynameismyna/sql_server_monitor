"""
Bağlantı ayarlarını kaydetme ve yükleme modülü
"""
import json
import os
from typing import Optional, Dict

CONFIG_FILE = "connection_config.json"


class ConfigManager:
    """Bağlantı ayarları yönetimi"""
    
    @staticmethod
    def save_connection(server: str, database: str, auth_type: str,
                       username: str = "") -> bool:
        """
        Bağlantı ayarlarını kaydet
        
        Args:
            server: SQL Server adresi
            database: Veritabanı adı
            auth_type: Kimlik doğrulama tipi
            username: Kullanıcı adı (SQL Server Auth için)
        
        Returns:
            Başarılı ise True
        """
        try:
            config = {
                "server": server,
                "database": database,
                "auth_type": auth_type,
                "username": username
            }
            
            ConfigManager._write_config(config)
            
            return True
        except Exception as e:
            print(f"Config kaydetme hatası: {e}")
            return False
    
    @staticmethod
    def load_connection() -> Optional[Dict]:
        """
        Kaydedilmiş bağlantı ayarlarını yükle
        
        Returns:
            Bağlantı ayarları dict'i veya None
        """
        try:
            if not os.path.exists(CONFIG_FILE):
                return None
            
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                config = json.load(f)

            if "password" in config:
                del config["password"]
                ConfigManager._write_config(config)
            
            return config
        except Exception as e:
            print(f"Config yükleme hatası: {e}")
            return None
    
    @staticmethod
    def config_exists() -> bool:
        """Kaydedilmiş config dosyası var mı?"""
        return os.path.exists(CONFIG_FILE)

    @staticmethod
    def _write_config(config: Dict) -> None:
        """Bağlantı ayarlarını atomik olarak, parola içermeden yaz."""
        safe_config = dict(config)
        safe_config.pop("password", None)
        temp_file = f"{CONFIG_FILE}.tmp"

        try:
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(safe_config, f, indent=4, ensure_ascii=False)
            os.replace(temp_file, CONFIG_FILE)
        finally:
            if os.path.exists(temp_file):
                os.remove(temp_file)

