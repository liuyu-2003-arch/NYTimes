import json
import os
import shutil


def organize_articles():
    # 读取 articles.json
    try:
        with open('articles.json', 'r', encoding='utf-8') as f:
            articles = json.load(f)
    except FileNotFoundError:
        print("错误: 找不到 articles.json 文件")
        return

    # 创建目标根目录
    base_target_dir = "organized_articles"
    if not os.path.exists(base_target_dir):
        os.makedirs(base_target_dir)

    count = 0
    for article in articles:
        # 获取原始文件路径 (例如 articles/file.html)
        src_path = article['url']

        # 确保原始文件存在
        if not os.path.exists(src_path):
            print(f"跳过 (文件不存在): {src_path}")
            continue

        # 解析日期并转换为 YYYYMMDD 格式
        # 假设日期格式为 YYYY-MM-DD
        date_str = article['date']
        folder_name = date_str.replace('-', '')  # 2025-12-05 -> 20251205

        # 创建日期文件夹
        target_dir = os.path.join(base_target_dir, folder_name)
        if not os.path.exists(target_dir):
            os.makedirs(target_dir)

        # 确定目标文件路径
        filename = os.path.basename(src_path)
        dst_path = os.path.join(target_dir, filename)

        # 复制文件
        shutil.copy2(src_path, dst_path)
        print(f"已复制: {filename} -> {folder_name}/")
        count += 1

    print(f"\n完成！共整理了 {count} 篇文章到 '{base_target_dir}' 文件夹中。")


if __name__ == "__main__":
    organize_articles()