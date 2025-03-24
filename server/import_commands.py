import csv
import sqlite3
import os

def import_commands_from_csv(csv_file_path):
    # 确保CSV文件存在
    if not os.path.exists(csv_file_path):
        print(f"Error: CSV file '{csv_file_path}' does not exist")
        return False

    try:
        # 连接到数据库
        conn = sqlite3.connect('commands.db')
        cursor = conn.cursor()

        # 读取CSV文件
        with open(csv_file_path, 'r', encoding='utf-8') as csvfile:
            csvreader = csv.reader(csvfile)
            # 跳过标题行（如果有的话）
            next(csvreader, None)
            
            # 插入命令
            for row in csvreader:
                if len(row) >= 3:  # 确保行至少有3列
                    command = row[2].strip()  # 获取第三列并去除空白字符
                    if command:  # 确保命令不为空
                        cursor.execute(
                            "INSERT INTO commands (command, requested) VALUES (?, 0)",
                            (command,)
                        )
                        print(f"Imported command: {command}")

        # 提交更改
        conn.commit()
        conn.close()
        print("Successfully imported all commands from CSV file")
        return True

    except Exception as e:
        print(f"Error importing commands: {str(e)}")
        if 'conn' in locals():
            conn.close()
        return False

if __name__ == "__main__":
    # 获取当前目录下的commands.csv文件
    csv_file = "commands.csv"
    if import_commands_from_csv(csv_file):
        print("Import completed successfully")
    else:
        print("Import failed") 