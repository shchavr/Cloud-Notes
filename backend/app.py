from flask import Flask, jsonify, request
from flask_cors import CORS
import logging
from datetime import datetime
import os
import mysql.connector
from mysql.connector import Error
from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv()

# Конфигурация базы данных для Docker
DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'localhost'),  # В Docker будет 'mysql'
    'port': int(os.getenv('DB_PORT', 3306)),
    'database': os.getenv('DB_NAME', 'notes_db'),
    'user': os.getenv('DB_USER', 'root'),
    'password': os.getenv('DB_PASSWORD', ''),
    'ssl_disabled': True  # Важно для Docker MySQL
}

app = Flask(__name__)
CORS(app)

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ========== ФУНКЦИИ ДЛЯ РАБОТЫ С БАЗОЙ ДАННЫХ ==========

def get_db_connection():
    """Создает подключение к MySQL в Docker"""
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        logger.info(f"✅ Database connected to {DB_CONFIG['host']}:{DB_CONFIG['port']}")
        return conn
    except mysql.connector.Error as e:
        logger.error(f"❌ Database connection error: {e}")
        logger.error(f"   Config: host={DB_CONFIG['host']}, port={DB_CONFIG['port']}")
        return None

def init_database():
    """Инициализирует таблицы в базе данных"""
    connection = get_db_connection()
    if connection:
        try:
            cursor = connection.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS notes (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    title VARCHAR(255) NOT NULL,
                    content TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    is_deleted BOOLEAN DEFAULT FALSE
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            ''')
            connection.commit()
            cursor.close()
            connection.close()
            logger.info("✅ Database tables initialized")
        except Exception as e:
            logger.error(f"❌ Database initialization error: {e}")
    else:
        logger.warning("⚠️ Skipping database initialization - connection failed")

# Инициализируем БД при запуске
init_database()

# ========== CRUD ОПЕРАЦИИ ДЛЯ БАЗЫ ДАННЫХ ==========

@app.route('/')
def index():
    """Главная страница API"""
    db_status = "connected" if get_db_connection() else "disconnected"
    
    return jsonify({
        "message": "✅ Cloud Notes API работает с Docker MySQL!",
        "version": "1.0",
        "status": "operational",
        "storage": "MySQL in Docker",
        "database_status": db_status,
        "database_host": DB_CONFIG['host'],
        "database_port": DB_CONFIG['port'],
        "endpoints": {
            "GET /health": "Проверка здоровья",
            "GET /api/notes": "Получить все заметки",
            "POST /api/notes": "Создать заметку",
            "GET /api/notes/<id>": "Получить заметку по ID",
            "PUT /api/notes/<id>": "Обновить заметку",
            "DELETE /api/notes/<id>": "Удалить заметку",
            "POST /api/notes/<id>/restore": "Восстановить заметку"
        }
    })

@app.route('/health', methods=['GET'])
def health():
    """Проверка здоровья приложения"""
    db_status = "connected" if get_db_connection() else "disconnected"
    
    return jsonify({
        "status": "healthy" if db_status == "connected" else "degraded",
        "service": "cloud-notes-api",
        "timestamp": datetime.now().isoformat(),
        "database": db_status,
        "database_host": DB_CONFIG['host'],
        "database_port": DB_CONFIG['port'],
        "database_name": DB_CONFIG['database']
    })

# ---------- CREATE ----------
@app.route('/api/notes', methods=['POST'])
def create_note():
    """Создание новой заметки В БАЗЕ ДАННЫХ"""
    try:
        data = request.json
        
        # Валидация
        if not data:
            return jsonify({"error": "Request body is required"}), 400
            
        title = data.get('title', '').strip()
        content = data.get('content', '').strip()
        
        if not title:
            return jsonify({"error": "Title is required and cannot be empty"}), 400
        
        # Подключаемся к БД
        conn = get_db_connection()
        if not conn:
            return jsonify({"error": "Database connection failed"}), 500
            
        cursor = conn.cursor()
        
        # Вставляем запись в БД
        cursor.execute('''
            INSERT INTO notes (title, content) 
            VALUES (%s, %s)
        ''', (title, content))
        
        note_id = cursor.lastrowid
        conn.commit()
        
        # Получаем созданную запись
        cursor.execute('SELECT * FROM notes WHERE id = %s', (note_id,))
        result = cursor.fetchone()
        
        cursor.close()
        conn.close()
        
        logger.info(f"✅ CREATE: Note #{note_id} created in database: '{title}'")
        
        # Форматируем ответ
        return jsonify({
            "id": result[0],
            "title": result[1],
            "content": result[2] or "",
            "created_at": result[3].isoformat() if result[3] else None,
            "updated_at": result[4].isoformat() if result[4] else None,
            "is_deleted": bool(result[5]),
            "message": "Заметка успешно создана в базе данных"
        }), 201
        
    except Exception as e:
        logger.error(f"❌ CREATE error: {e}")
        return jsonify({"error": "Internal server error"}), 500

# ---------- READ ALL ----------
@app.route('/api/notes', methods=['GET'])
def get_all_notes():
    """Получение всех заметок ИЗ БАЗЫ ДАННЫХ"""
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({"error": "Database connection failed"}), 500
            
        cursor = conn.cursor(dictionary=True)  # Возвращает словари
        
        cursor.execute('''
            SELECT id, title, content, created_at, updated_at 
            FROM notes 
            WHERE is_deleted = FALSE 
            ORDER BY created_at DESC
        ''')
        
        notes = cursor.fetchall()
        
        # Преобразуем datetime в строки
        for note in notes:
            if note['created_at']:
                note['created_at'] = note['created_at'].isoformat()
            if note['updated_at']:
                note['updated_at'] = note['updated_at'].isoformat()
            note['is_deleted'] = False  # Все записи уже отфильтрованы
        
        cursor.close()
        conn.close()
        
        logger.info(f"✅ READ ALL: Retrieved {len(notes)} notes from database")
        
        return jsonify({
            "notes": notes,
            "count": len(notes),
            "message": f"Найдено {len(notes)} заметок в базе данных"
        })
        
    except Exception as e:
        logger.error(f"❌ READ ALL error: {e}")
        return jsonify({"error": "Internal server error"}), 500

# ---------- READ ONE ----------
@app.route('/api/notes/<int:note_id>', methods=['GET'])
def get_note(note_id):
    """Получение одной заметки ИЗ БАЗЫ ДАННЫХ"""
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({"error": "Database connection failed"}), 500
            
        cursor = conn.cursor(dictionary=True)
        
        cursor.execute('''
            SELECT id, title, content, created_at, updated_at, is_deleted 
            FROM notes 
            WHERE id = %s
        ''', (note_id,))
        
        note = cursor.fetchone()
        
        cursor.close()
        conn.close()
        
        if not note:
            return jsonify({"error": f"Заметка с ID {note_id} не найдена"}), 404
        
        if note['is_deleted']:
            return jsonify({"error": f"Заметка с ID {note_id} была удалена"}), 404
        
        # Преобразуем datetime
        if note['created_at']:
            note['created_at'] = note['created_at'].isoformat()
        if note['updated_at']:
            note['updated_at'] = note['updated_at'].isoformat()
        
        # Убираем is_deleted из ответа
        del note['is_deleted']
        
        logger.info(f"✅ READ ONE: Retrieved note #{note_id} from database")
        
        return jsonify(note)
        
    except Exception as e:
        logger.error(f"❌ READ ONE error: {e}")
        return jsonify({"error": "Internal server error"}), 500

# ---------- UPDATE ----------
@app.route('/api/notes/<int:note_id>', methods=['PUT'])
def update_note(note_id):
    """Обновление существующей заметки В БАЗЕ ДАННЫХ"""
    try:
        data = request.json
        
        if not data:
            return jsonify({"error": "Request body is required"}), 400
        
        conn = get_db_connection()
        if not conn:
            return jsonify({"error": "Database connection failed"}), 500
            
        cursor = conn.cursor()
        
        # Проверяем существование и не удалена ли заметка
        cursor.execute('SELECT is_deleted FROM notes WHERE id = %s', (note_id,))
        result = cursor.fetchone()
        
        if not result:
            cursor.close()
            conn.close()
            return jsonify({"error": f"Заметка с ID {note_id} не найдена"}), 404
        
        if result[0]:  # is_deleted = True
            cursor.close()
            conn.close()
            return jsonify({"error": f"Нельзя обновить удаленную заметку"}), 400
        
        # Подготавливаем данные для обновления
        updates = []
        values = []
        
        if 'title' in data:
            title = data['title'].strip()
            if title:
                updates.append("title = %s")
                values.append(title)
            elif title == "":
                cursor.close()
                conn.close()
                return jsonify({"error": "Title cannot be empty"}), 400
                
        if 'content' in data:
            updates.append("content = %s")
            values.append(data['content'].strip())
        
        if not updates:
            cursor.close()
            conn.close()
            return jsonify({"message": "No changes detected"})
        
        # Добавляем ID в конец значений
        values.append(note_id)
        
        # Выполняем обновление
        update_query = f"UPDATE notes SET {', '.join(updates)} WHERE id = %s"
        cursor.execute(update_query, values)
        
        conn.commit()
        cursor.close()
        conn.close()
        
        logger.info(f"✅ UPDATE: Note #{note_id} updated in database")
        
        return jsonify({
            "id": note_id,
            "message": "Заметка успешно обновлена в базе данных"
        })
        
    except Exception as e:
        logger.error(f"❌ UPDATE error: {e}")
        return jsonify({"error": "Internal server error"}), 500

# ---------- DELETE ----------
@app.route('/api/notes/<int:note_id>', methods=['DELETE'])
def delete_note(note_id):
    """Мягкое удаление заметки ИЗ БАЗЫ ДАННЫХ"""
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({"error": "Database connection failed"}), 500
            
        cursor = conn.cursor()
        
        # Используем мягкое удаление (is_deleted = TRUE)
        cursor.execute('''
            UPDATE notes 
            SET is_deleted = TRUE 
            WHERE id = %s AND is_deleted = FALSE
        ''', (note_id,))
        
        rows_affected = cursor.rowcount
        conn.commit()
        
        cursor.close()
        conn.close()
        
        if rows_affected == 0:
            return jsonify({"error": "Заметка не найдена или уже удалена"}), 404
        
        logger.info(f"✅ DELETE: Note #{note_id} soft-deleted from database")
        
        return jsonify({
            "id": note_id,
            "message": "Заметка успешно удалена из базы данных"
        })
        
    except Exception as e:
        logger.error(f"❌ DELETE error: {e}")
        return jsonify({"error": "Internal server error"}), 500

# ---------- RESTORE ----------
@app.route('/api/notes/<int:note_id>/restore', methods=['POST'])
def restore_note(note_id):
    """Восстановление удаленной заметки В БАЗЕ ДАННЫХ"""
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({"error": "Database connection failed"}), 500
            
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE notes 
            SET is_deleted = FALSE 
            WHERE id = %s AND is_deleted = TRUE
        ''', (note_id,))
        
        rows_affected = cursor.rowcount
        conn.commit()
        
        cursor.close()
        conn.close()
        
        if rows_affected == 0:
            return jsonify({"error": "Заметка не найдена или не была удалена"}), 404
        
        logger.info(f"✅ RESTORE: Note #{note_id} restored in database")
        
        return jsonify({
            "id": note_id,
            "message": "Заметка успешно восстановлена в базе данных"
        })
        
    except Exception as e:
        logger.error(f"❌ RESTORE error: {e}")
        return jsonify({"error": "Internal server error"}), 500

# ========== ДОПОЛНИТЕЛЬНЫЕ ЭНДПОИНТЫ ==========

@app.route('/api/stats', methods=['GET'])
def get_stats():
    """Статистика по заметкам ИЗ БАЗЫ ДАННЫХ"""
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({"error": "Database connection failed"}), 500
            
        cursor = conn.cursor()
        
        # Общее количество
        cursor.execute('SELECT COUNT(*) FROM notes')
        total = cursor.fetchone()[0]
        
        # Активные заметки
        cursor.execute('SELECT COUNT(*) FROM notes WHERE is_deleted = FALSE')
        active = cursor.fetchone()[0]
        
        # Удаленные заметки
        deleted = total - active
        
        # ID первой и последней заметки
        cursor.execute('SELECT MIN(id), MAX(id) FROM notes')
        min_max = cursor.fetchone()
        
        cursor.close()
        conn.close()
        
        return jsonify({
            "total_notes": total,
            "active_notes": active,
            "deleted_notes": deleted,
            "storage_type": "MySQL in Docker",
            "database_host": DB_CONFIG['host'],
            "first_note_id": min_max[0],
            "last_note_id": min_max[1]
        })
        
    except Exception as e:
        logger.error(f"❌ STATS error: {e}")
        return jsonify({"error": "Internal server error"}), 500

@app.route('/api/search', methods=['GET'])
def search_notes():
    """Поиск заметок по тексту В БАЗЕ ДАННЫХ"""
    try:
        query = request.args.get('q', '').strip()
        
        if not query:
            return jsonify({"error": "Search query is required"}), 400
        
        conn = get_db_connection()
        if not conn:
            return jsonify({"error": "Database connection failed"}), 500
            
        cursor = conn.cursor(dictionary=True)
        
        search_query = f"%{query}%"
        cursor.execute('''
            SELECT id, title, content, created_at, updated_at 
            FROM notes 
            WHERE is_deleted = FALSE 
            AND (title LIKE %s OR content LIKE %s)
            ORDER BY created_at DESC
        ''', (search_query, search_query))
        
        results = cursor.fetchall()
        
        # Преобразуем datetime в строки
        for note in results:
            if note['created_at']:
                note['created_at'] = note['created_at'].isoformat()
            if note['updated_at']:
                note['updated_at'] = note['updated_at'].isoformat()
        
        cursor.close()
        conn.close()
        
        logger.info(f"🔍 SEARCH: Found {len(results)} notes for query '{query}'")
        
        return jsonify({
            "query": query,
            "results": results,
            "count": len(results)
        })
        
    except Exception as e:
        logger.error(f"❌ SEARCH error: {e}")
        return jsonify({"error": "Internal server error"}), 500

if __name__ == '__main__':
    print("=" * 60)
    print("🚀 Cloud Notes API с Docker MySQL")
    print(f"📍 База данных: {DB_CONFIG['host']}:{DB_CONFIG['port']}")
    print(f"📁 Имя БД: {DB_CONFIG['database']}")
    print("🔗 Адрес: http://localhost:5000")
    print("=" * 60)
    print("\nДоступные эндпоинты:")
    print("  GET  /                    - Информация об API")
    print("  GET  /health              - Проверка здоровья")
    print("  POST /api/notes           - Создать заметку")
    print("  GET  /api/notes           - Все заметки")
    print("  GET  /api/notes/<id>      - Получить заметку")
    print("  PUT  /api/notes/<id>      - Обновить заметку")
    print("  DELETE /api/notes/<id>    - Удалить заметку")
    print("  POST /api/notes/<id>/restore - Восстановить")
    print("  GET  /api/stats           - Статистика")
    print("  GET  /api/search?q=текст  - Поиск")
    print("\n" + "=" * 60)
    
    app.run(host='0.0.0.0', port=5000, debug=True)