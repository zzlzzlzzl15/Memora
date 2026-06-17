#!/usr/bin/env python3
"""
修复 documents.py 中的语法错误
sed 命令破坏了函数定义，需要重新构建
"""
import re

# 读取文件
with open('/Users/zzl/Desktop/个人文件夹/Memora/personal_knowledge_base/app/api/documents.py', 'r') as f:
    content = f.read()

# 替换被破坏的函数定义
# 模式：async def function_name(...\n    # 单用户模式...\n    req_logger = Depends(...)):
# 替换为：async def function_name(...\n    req_logger = Depends(...)):\n    current_user = {"user_id": 1, "sub": "admin"}

# 匹配所有被 sed 破坏的函数定义
pattern = r'# 单用户模式：不再需要用户认证\s*\n\s*(req_logger = Depends\([^)]+\)):\s*\n\s*"""\s*\n\s*(current_user)'

replacement = r'\1:\n    """\n    \2 = {"user_id": 1, "sub": "admin"}'

# 使用 re.sub 进行替换
fixed_content = re.sub(pattern, replacement, content)

# 写入文件
with open('/Users/zzl/Desktop/个人文件夹/Memora/personal_knowledge_base/app/api/documents.py', 'w') as f:
    f.write(fixed_content)

print("documents.py 修复完成")
