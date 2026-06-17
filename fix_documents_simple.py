#!/usr/bin/env python3
"""
批量修复 documents.py 中所有被 sed 破坏的函数
使用更简单的方法：直接在每个 "# 单用户模式" 注释后插入 current_user 定义
"""

# 读取文件
with open('/Users/zzl/Desktop/个人文件夹/Memora/personal_knowledge_base/app/api/documents.py', 'r') as f:
    content = f.read()

# 替换模式：找到 "# 单用户模式" 所在行，在下一行插入 current_user
lines = content.split('\n')
fixed_lines = []

i = 0
while i < len(lines):
    line = lines[i]
    
    # 检查是否包含 "# 单用户模式"
    if '# 单用户模式：不再需要用户认证' in line:
        # 保留注释行
        fixed_lines.append(line)
        i += 1
        
        # 在下一行插入 current_user 定义
        fixed_lines.append('    current_user = {"user_id": 1, "sub": "admin"}')
    else:
        fixed_lines.append(line)
        i += 1

# 写回文件
with open('/Users/zzl/Desktop/个人文件夹/Memora/personal_knowledge_base/app/api/documents.py', 'w') as f:
    f.write('\n'.join(fixed_lines))

print("documents.py 修复完成（简单版本）")
