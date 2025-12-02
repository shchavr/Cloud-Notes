-- Инициализация базы данных для Cloud Notes
-- Создаем пользователя (уже создан через переменные окружения, но для надежности)

-- Создаем таблицу notes если не существует
CREATE TABLE IF NOT EXISTS notes (
    id INT AUTO_INCREMENT PRIMARY KEY,
    title VARCHAR(255) NOT NULL,
    content TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    is_deleted BOOLEAN DEFAULT FALSE,
    INDEX idx_deleted (is_deleted),
    INDEX idx_created (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Создаем таблицу для аудита (опционально)
CREATE TABLE IF NOT EXISTS audit_log (
    id INT AUTO_INCREMENT PRIMARY KEY,
    note_id INT,
    action VARCHAR(50),
    old_title VARCHAR(255),
    new_title VARCHAR(255),
    changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (note_id) REFERENCES notes(id) ON DELETE SET NULL
);

-- Добавляем тестовые данные
INSERT INTO notes (title, content) VALUES
('Добро пожаловать в Cloud Notes!', 'Это ваша первая заметка в облачном приложении.'),
('План на день', '1. Изучить Docker\n2. Настроить MySQL\n3. Подготовиться к Yandex Cloud'),
('Список покупок', 'Молоко, хлеб, яйца, фрукты');

-- Проверяем создание
SELECT 'Database initialized successfully!' as message;
SELECT COUNT(*) as notes_count FROM notes;