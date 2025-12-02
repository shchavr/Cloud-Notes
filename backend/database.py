import os
import mysql.connector
from mysql.connector import Error

def get_db_connection():
    """Создает подключение к MySQL в Yandex Cloud"""
    try:
        # Эти параметры будем получать из переменных окружения
        connection = mysql.connector.connect(
            host=os.getenv('DB_HOST', 'localhost'),
            port=os.getenv('DB_PORT', '3306'),
            database=os.getenv('DB_NAME', 'notes_db'),
            user=os.getenv('DB_USER', 'root'),
            password=os.getenv('DB_PASSWORD', ''),
            ssl_ca=os.getenv('DB_SSL_CA', None)  # Для Managed MySQL
        )
        return connection
    except Error as e:
        print(f"Error connecting to MySQL: {e}")
        return None

def init_database():
    """Инициализирует таблицы в базе данных"""
    connection = get_db_connection()
    if connection:
        cursor = connection.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS notes (
                id INT AUTO_INCREMENT PRIMARY KEY,
                title VARCHAR(255) NOT NULL,
                content TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                is_deleted BOOLEAN DEFAULT FALSE
            )
        ''')
        connection.commit()
        cursor.close()
        connection.close()