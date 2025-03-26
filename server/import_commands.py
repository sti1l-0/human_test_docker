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

        # 尝试不同的编码方式读取文件
        encodings = ['utf-8', 'latin1', 'cp1252', 'iso-8859-1']
        file_content = None
        
        for encoding in encodings:
            try:
                with open(csv_file_path, 'r', encoding=encoding) as csvfile:
                    file_content = csvfile.read()
                print(f"Successfully read file with {encoding} encoding")
                break
            except UnicodeDecodeError:
                continue
        
        if file_content is None:
            raise Exception("Could not read file with any supported encoding")

        # 使用成功读取的内容创建CSV reader
        csvreader = csv.reader(file_content.splitlines())
        # 跳过标题行（如果有的话）
        next(csvreader, None)
        
        # 插入命令
        for row in csvreader:
            if len(row) >= 2:
                command = row[1].strip()
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
    # csv_file = "../../llm_data_deal/user_commands.csv"
    csv_file = "../../llm_data_deal/train.csv"
    if import_commands_from_csv(csv_file):
        print("Import completed successfully")
    else:
        print("Import failed") 