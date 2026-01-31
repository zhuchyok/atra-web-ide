#!/usr/bin/env python3
import sqlite3
import json

USER_ID = 556251171
NEW_DEPOSIT = 1000.0

conn = sqlite3.connect('trading.db')
cursor = conn.cursor()

print(f"\n=== ОБНОВЛЕНИЕ ДЕПОЗИТА для user {USER_ID} ===\n")

# Получаем данные из users_data (JSON)
cursor.execute("SELECT data FROM users_data WHERE user_id = ?", (str(USER_ID),))
row = cursor.fetchone()

if row and row[0]:
    user_data = json.loads(row[0])
    print(f"БЫЛО: deposit={user_data.get('deposit')}, balance={user_data.get('balance')}")
    
    # Обновляем deposit и balance
    user_data['deposit'] = NEW_DEPOSIT
    user_data['balance'] = NEW_DEPOSIT
    
    # Сохраняем обратно
    cursor.execute("""
        UPDATE users_data 
        SET data = ?, updated_at = CURRENT_TIMESTAMP
        WHERE user_id = ?
    """, (json.dumps(user_data), str(USER_ID)))
    
    conn.commit()
    
    # Проверяем результат
    cursor.execute("SELECT data FROM users_data WHERE user_id = ?", (str(USER_ID),))
    row = cursor.fetchone()
    if row:
        updated_data = json.loads(row[0])
        print(f"СТАЛО: deposit={updated_data.get('deposit')}, balance={updated_data.get('balance')}")
        print(f"\n✅ Депозит обновлён на {NEW_DEPOSIT}")
else:
    print(f"❌ Пользователь {USER_ID} не найден в таблице users_data")

# Также обновляем user_data.json если есть
try:
    with open('user_data.json', 'r') as f:
        file_data = json.load(f)
    
    if str(USER_ID) in file_data:
        file_data[str(USER_ID)]['deposit'] = NEW_DEPOSIT
        file_data[str(USER_ID)]['balance'] = NEW_DEPOSIT
        
        with open('user_data.json', 'w') as f:
            json.dump(file_data, f, indent=2)
        
        print("✅ user_data.json тоже обновлён")
except Exception as e:
    print(f"⚠️ user_data.json: {e}")

conn.close()
print("\n===========================================\n")

